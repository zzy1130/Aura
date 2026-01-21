# Literature Verifier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a `/literature-verifier` command that verifies citations exist, have correct metadata, and are used in proper context.

**Architecture:** Backend service parses .bib files, looks up papers via Semantic Scholar, validates metadata and context using LLM, streams results via SSE. Frontend displays results in a dedicated panel with approve/fix actions.

**Tech Stack:** Python (FastAPI, Pydantic), TypeScript (React), SSE streaming, Semantic Scholar API, Haiku LLM for context validation.

---

## Task 1: Backend - VerificationResult Data Models

**Files:**
- Create: `backend/services/reference_verifier.py`

**Step 1: Create the data models**

```python
"""
Reference Verification Service

Verifies that bibliography entries are real papers with correct metadata
and are cited in appropriate context.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from services.latex_parser import BibEntry
from services.semantic_scholar import Paper


@dataclass
class CitationContext:
    """A citation usage in the document."""
    cite_key: str
    line_number: int
    surrounding_text: str  # ~200 chars around \cite{}
    claim: str  # Extracted claim being made (text before citation)


@dataclass
class VerificationResult:
    """Result of verifying a single citation."""
    cite_key: str
    status: Literal["verified", "warning", "error", "pending"]

    # Existence check
    exists: bool = False
    matched_paper: Optional[dict] = None  # Paper.to_dict() from Semantic Scholar

    # Metadata check
    metadata_issues: list[str] = field(default_factory=list)

    # Context check
    context_score: float = 0.0  # 0-1 confidence
    context_explanation: str = ""
    checked_via: Literal["abstract", "pdf", "skipped", "failed"] = "skipped"

    # Original data
    bib_entry: Optional[dict] = None  # BibEntry as dict
    usages: list[CitationContext] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "cite_key": self.cite_key,
            "status": self.status,
            "exists": self.exists,
            "matched_paper": self.matched_paper,
            "metadata_issues": self.metadata_issues,
            "context_score": self.context_score,
            "context_explanation": self.context_explanation,
            "checked_via": self.checked_via,
            "bib_entry": self.bib_entry,
            "usages": [
                {
                    "cite_key": u.cite_key,
                    "line_number": u.line_number,
                    "surrounding_text": u.surrounding_text,
                    "claim": u.claim,
                }
                for u in self.usages
            ],
        }
```

**Step 2: Verify the module imports correctly**

Run: `cd /Users/zhongzhiyi/Aura/backend && python3 -c "from services.reference_verifier import VerificationResult, CitationContext; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/services/reference_verifier.py
git commit -m "feat(verifier): Add VerificationResult data models"
```

---

## Task 2: Backend - Citation Context Extraction

**Files:**
- Modify: `backend/services/reference_verifier.py`

**Step 1: Add context extraction function**

Add after the dataclasses:

```python
import re
from pathlib import Path
from services.latex_parser import find_citations, parse_bib_file_path, BibEntry


# Citation patterns (same as latex_parser but we need the positions)
CITATION_COMMANDS = [
    "cite", "citep", "citet", "citeauthor", "citeyear",
    "autocite", "textcite", "parencite", "footcite",
    "fullcite", "nocite",
]
CITATION_REGEX = re.compile(
    r"\\(" + "|".join(CITATION_COMMANDS) + r")\{([^}]+)\}"
)


def extract_citation_contexts(
    tex_content: str,
    cite_key: str,
    context_chars: int = 200,
) -> list[CitationContext]:
    """
    Find all usages of a citation and extract surrounding context.

    Args:
        tex_content: Full LaTeX document content
        cite_key: The citation key to find
        context_chars: Characters to extract around each citation

    Returns:
        List of CitationContext for each usage
    """
    lines = tex_content.split("\n")
    contexts: list[CitationContext] = []

    for line_num, line in enumerate(lines, start=1):
        for match in CITATION_REGEX.finditer(line):
            keys_str = match.group(2)
            keys = [k.strip() for k in keys_str.split(",")]

            if cite_key not in keys:
                continue

            # Get position in line
            cite_start = match.start()

            # Extract claim (text before the citation on this line and previous lines)
            claim_text = line[:cite_start].strip()

            # If claim is short, include previous line
            if len(claim_text) < 50 and line_num > 1:
                prev_line = lines[line_num - 2].strip()
                claim_text = prev_line + " " + claim_text

            # Clean up the claim
            claim_text = claim_text.strip()
            if claim_text.endswith(","):
                claim_text = claim_text[:-1]

            # Get surrounding context (before and after)
            line_start = max(0, cite_start - context_chars // 2)
            line_end = min(len(line), match.end() + context_chars // 2)
            surrounding = line[line_start:line_end]

            contexts.append(CitationContext(
                cite_key=cite_key,
                line_number=line_num,
                surrounding_text=surrounding,
                claim=claim_text[-200:] if len(claim_text) > 200 else claim_text,
            ))

    return contexts
```

**Step 2: Test the extraction**

Run:
```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
from services.reference_verifier import extract_citation_contexts

tex = r"""
\section{Introduction}
Transformers have revolutionized NLP \cite{vaswani2017}.
The attention mechanism enables capturing long-range dependencies \citep{vaswani2017,brown2020}.
"""

contexts = extract_citation_contexts(tex, "vaswani2017")
print(f"Found {len(contexts)} usages")
for ctx in contexts:
    print(f"  Line {ctx.line_number}: {ctx.claim[:50]}...")
EOF
```
Expected: Found 2 usages with claims extracted

**Step 3: Commit**

```bash
git add backend/services/reference_verifier.py
git commit -m "feat(verifier): Add citation context extraction"
```

---

## Task 3: Backend - Paper Lookup Service

**Files:**
- Modify: `backend/services/reference_verifier.py`

**Step 1: Add paper lookup function**

Add after `extract_citation_contexts`:

```python
import asyncio
import httpx
from services.semantic_scholar import SemanticScholarClient, Paper


async def lookup_paper(
    bib_entry: BibEntry,
    http_client: httpx.AsyncClient,
) -> tuple[bool, Optional[Paper], list[str]]:
    """
    Look up a paper in Semantic Scholar.

    Tries in order:
    1. DOI lookup
    2. arXiv ID lookup
    3. Title search

    Returns:
        (exists, matched_paper, metadata_issues)
    """
    s2_client = SemanticScholarClient(http_client)
    fields = bib_entry.fields
    metadata_issues: list[str] = []

    # Try DOI first
    doi = fields.get("doi", "")
    if doi:
        paper = await s2_client.get_paper(f"DOI:{doi}")
        if paper:
            issues = _compare_metadata(bib_entry, paper)
            return True, paper, issues

    # Try arXiv ID
    arxiv_id = fields.get("eprint", "") or fields.get("arxiv", "")
    if arxiv_id:
        # Clean up arXiv ID (remove version suffix like v1, v2)
        arxiv_clean = re.sub(r"v\d+$", "", arxiv_id)
        paper = await s2_client.get_paper(f"arXiv:{arxiv_clean}")
        if paper:
            issues = _compare_metadata(bib_entry, paper)
            return True, paper, issues

    # Fall back to title search
    title = fields.get("title", "")
    if title:
        # Clean title (remove braces, extra whitespace)
        clean_title = re.sub(r"[{}]", "", title).strip()
        papers = await s2_client.search(clean_title, limit=5)

        # Find best match by title similarity
        for paper in papers:
            if _titles_match(clean_title, paper.title):
                issues = _compare_metadata(bib_entry, paper)
                return True, paper, issues

    return False, None, ["Paper not found in Semantic Scholar"]


def _titles_match(bib_title: str, paper_title: str, threshold: float = 0.8) -> bool:
    """Check if titles match using simple word overlap."""
    bib_words = set(bib_title.lower().split())
    paper_words = set(paper_title.lower().split())

    # Remove common words
    stopwords = {"a", "an", "the", "of", "in", "on", "for", "to", "and", "with"}
    bib_words -= stopwords
    paper_words -= stopwords

    if not bib_words or not paper_words:
        return False

    overlap = len(bib_words & paper_words)
    return overlap / max(len(bib_words), len(paper_words)) >= threshold


def _compare_metadata(bib_entry: BibEntry, paper: Paper) -> list[str]:
    """Compare bib entry metadata with found paper."""
    issues: list[str] = []
    fields = bib_entry.fields

    # Check year
    bib_year = fields.get("year", "")
    if bib_year and paper.year:
        try:
            if int(bib_year) != paper.year:
                issues.append(f"Year mismatch: bib says {bib_year}, found {paper.year}")
        except ValueError:
            pass

    # Check title similarity
    bib_title = re.sub(r"[{}]", "", fields.get("title", "")).strip().lower()
    paper_title = paper.title.lower()
    if bib_title and paper_title:
        if not _titles_match(bib_title, paper_title, threshold=0.7):
            issues.append(f"Title mismatch: '{bib_title[:50]}...' vs '{paper_title[:50]}...'")

    return issues
```

**Step 2: Test the lookup**

Run:
```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
import httpx
from services.reference_verifier import lookup_paper
from services.latex_parser import BibEntry

async def test():
    async with httpx.AsyncClient() as client:
        # Test with a known paper
        entry = BibEntry(
            key="vaswani2017",
            entry_type="article",
            fields={"title": "Attention Is All You Need", "year": "2017"},
            raw="",
        )
        exists, paper, issues = await lookup_paper(entry, client)
        print(f"Exists: {exists}")
        if paper:
            print(f"Found: {paper.title}")
        print(f"Issues: {issues}")

asyncio.run(test())
EOF
```
Expected: Exists: True, Found: Attention Is All You Need

**Step 3: Commit**

```bash
git add backend/services/reference_verifier.py
git commit -m "feat(verifier): Add paper lookup via Semantic Scholar"
```

---

## Task 4: Backend - Context Validation with LLM

**Files:**
- Modify: `backend/services/reference_verifier.py`

**Step 1: Add context validation function**

Add after `_compare_metadata`:

```python
from anthropic import AsyncAnthropic


CONTEXT_VALIDATION_PROMPT = """Given this claim from a paper:
"{claim}"

And this abstract from the cited paper "{title}":
"{abstract}"

Does the abstract support this claim? Respond with exactly one of:
- SUPPORTED: The abstract clearly supports this claim
- PLAUSIBLE: The abstract is related but doesn't directly confirm
- UNSUPPORTED: The abstract contradicts or doesn't relate to this claim
- UNCERTAIN: Cannot determine from abstract alone

Then add a one-sentence explanation on the next line."""


async def validate_context(
    claim: str,
    paper_title: str,
    paper_abstract: str,
    anthropic_client: AsyncAnthropic,
) -> tuple[float, str, str]:
    """
    Validate if a claim is supported by a paper's abstract.

    Returns:
        (score, explanation, verdict)
        - score: 0.0-1.0 confidence
        - explanation: Why it matches/doesn't
        - verdict: SUPPORTED/PLAUSIBLE/UNSUPPORTED/UNCERTAIN
    """
    if not claim or not paper_abstract:
        return 0.5, "No claim or abstract to validate", "UNCERTAIN"

    prompt = CONTEXT_VALIDATION_PROMPT.format(
        claim=claim[:500],
        title=paper_title,
        abstract=paper_abstract[:1000],
    )

    try:
        response = await anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text.strip()
        lines = result.split("\n", 1)
        verdict = lines[0].strip().upper()
        explanation = lines[1].strip() if len(lines) > 1 else ""

        # Map verdict to score
        score_map = {
            "SUPPORTED": 0.9,
            "PLAUSIBLE": 0.6,
            "UNSUPPORTED": 0.2,
            "UNCERTAIN": 0.5,
        }

        # Extract verdict from response (might have extra text)
        for v in score_map:
            if v in verdict:
                return score_map[v], explanation, v

        return 0.5, explanation or result, "UNCERTAIN"

    except Exception as e:
        return 0.5, f"Validation failed: {str(e)}", "UNCERTAIN"
```

**Step 2: Test context validation (requires API key)**

Run:
```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
import httpx
from anthropic import AsyncAnthropic
from services.reference_verifier import validate_context

async def test():
    http_client = httpx.AsyncClient()
    anthropic = AsyncAnthropic(
        auth_token="vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336",
        base_url="https://colorist-gateway-staging.arco.ai",
        http_client=http_client,
    )

    score, explanation, verdict = await validate_context(
        claim="Transformers have revolutionized natural language processing",
        paper_title="Attention Is All You Need",
        paper_abstract="We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
        anthropic_client=anthropic,
    )
    print(f"Verdict: {verdict}, Score: {score}")
    print(f"Explanation: {explanation}")
    await http_client.aclose()

asyncio.run(test())
EOF
```
Expected: Verdict: SUPPORTED or PLAUSIBLE

**Step 3: Commit**

```bash
git add backend/services/reference_verifier.py
git commit -m "feat(verifier): Add context validation with Haiku"
```

---

## Task 5: Backend - Main Verifier Class

**Files:**
- Modify: `backend/services/reference_verifier.py`

**Step 1: Add the ReferenceVerifier class**

Add at the end of the file:

```python
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)


class ReferenceVerifier:
    """
    Orchestrates reference verification for a LaTeX project.

    Verification steps:
    1. Parse .bib file to get all entries
    2. Parse .tex file(s) to find citation usages
    3. For each citation:
       a. Look up paper in Semantic Scholar
       b. Compare metadata
       c. Validate context claims
    """

    def __init__(
        self,
        project_path: str,
        http_client: httpx.AsyncClient,
        anthropic_client: AsyncAnthropic,
    ):
        self.project_path = Path(project_path)
        self.http_client = http_client
        self.anthropic_client = anthropic_client

    def _find_bib_file(self) -> Optional[Path]:
        """Find the .bib file in the project."""
        bib_files = list(self.project_path.glob("*.bib"))
        if bib_files:
            return bib_files[0]
        return None

    def _find_tex_files(self) -> list[Path]:
        """Find all .tex files in the project."""
        return list(self.project_path.glob("**/*.tex"))

    async def verify_all(self) -> AsyncGenerator[VerificationResult, None]:
        """
        Verify all citations in the project.

        Yields VerificationResult for each citation as verification completes.
        """
        # Find bib file
        bib_path = self._find_bib_file()
        if not bib_path:
            logger.warning("No .bib file found")
            return

        # Parse bib entries
        bib_entries = parse_bib_file_path(bib_path)
        if not bib_entries:
            logger.warning("No entries in .bib file")
            return

        # Read all tex content
        tex_content = ""
        for tex_path in self._find_tex_files():
            try:
                tex_content += tex_path.read_text(encoding="utf-8", errors="replace")
                tex_content += "\n"
            except Exception as e:
                logger.error(f"Failed to read {tex_path}: {e}")

        # Verify each entry
        for entry in bib_entries:
            result = await self._verify_entry(entry, tex_content)
            yield result

    async def _verify_entry(
        self,
        entry: BibEntry,
        tex_content: str,
    ) -> VerificationResult:
        """Verify a single bibliography entry."""
        cite_key = entry.key

        # Extract usage contexts
        usages = extract_citation_contexts(tex_content, cite_key)

        # Look up paper
        exists, paper, metadata_issues = await lookup_paper(entry, self.http_client)

        if not exists:
            return VerificationResult(
                cite_key=cite_key,
                status="error",
                exists=False,
                metadata_issues=metadata_issues,
                bib_entry={"key": entry.key, "fields": entry.fields},
                usages=usages,
            )

        # Validate context if we have usages and abstract
        context_score = 0.0
        context_explanation = ""
        checked_via = "skipped"

        if usages and paper and paper.abstract:
            # Use first usage for context validation
            first_claim = usages[0].claim
            if first_claim:
                context_score, context_explanation, verdict = await validate_context(
                    claim=first_claim,
                    paper_title=paper.title,
                    paper_abstract=paper.abstract,
                    anthropic_client=self.anthropic_client,
                )
                checked_via = "abstract"

        # Determine status
        if metadata_issues:
            status = "warning"
        elif context_score < 0.4:
            status = "warning"
        else:
            status = "verified"

        return VerificationResult(
            cite_key=cite_key,
            status=status,
            exists=True,
            matched_paper=paper.to_dict() if paper else None,
            metadata_issues=metadata_issues,
            context_score=context_score,
            context_explanation=context_explanation,
            checked_via=checked_via,
            bib_entry={"key": entry.key, "fields": entry.fields},
            usages=usages,
        )
```

**Step 2: Verify the class imports correctly**

Run: `cd /Users/zhongzhiyi/Aura/backend && python3 -c "from services.reference_verifier import ReferenceVerifier; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/services/reference_verifier.py
git commit -m "feat(verifier): Add ReferenceVerifier orchestrator class"
```

---

## Task 6: Backend - Memory Namespace for Approvals

**Files:**
- Modify: `backend/services/memory.py`

**Step 1: Add literature_verifier namespace to MemoryData**

Find the `MemoryData` dataclass and add the new field:

```python
@dataclass
class MemoryData:
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    papers: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    conventions: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    # Literature verifier state (isolated from agent memory)
    literature_verifier: dict = field(default_factory=lambda: {
        "approved_citations": [],
        "last_run": None,
    })

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
```

**Step 2: Update the load method to handle the new field**

Find the `load` method and add:

```python
def load(self) -> MemoryData:
    """Load memory from disk."""
    if not self.memory_file.exists():
        return MemoryData()

    try:
        data = json.loads(self.memory_file.read_text())
        return MemoryData(
            version=data.get("version", 1),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            papers=data.get("papers", []),
            citations=data.get("citations", []),
            conventions=data.get("conventions", []),
            todos=data.get("todos", []),
            notes=data.get("notes", []),
            literature_verifier=data.get("literature_verifier", {
                "approved_citations": [],
                "last_run": None,
            }),
        )
    except (json.JSONDecodeError, KeyError):
        return MemoryData()
```

**Step 3: Add helper methods for literature verifier**

Add to MemoryService class:

```python
def get_approved_citations(self) -> list[str]:
    """Get list of manually approved citation keys."""
    memory = self.load()
    return memory.literature_verifier.get("approved_citations", [])

def approve_citation(self, cite_key: str) -> None:
    """Mark a citation as manually approved."""
    memory = self.load()
    approved = memory.literature_verifier.get("approved_citations", [])
    if cite_key not in approved:
        approved.append(cite_key)
        memory.literature_verifier["approved_citations"] = approved
        memory.literature_verifier["last_run"] = datetime.now().isoformat()
        self.save(memory)

def unapprove_citation(self, cite_key: str) -> None:
    """Remove manual approval from a citation."""
    memory = self.load()
    approved = memory.literature_verifier.get("approved_citations", [])
    if cite_key in approved:
        approved.remove(cite_key)
        memory.literature_verifier["approved_citations"] = approved
        self.save(memory)
```

**Step 4: Verify changes work**

Run: `cd /Users/zhongzhiyi/Aura/backend && python3 -c "from services.memory import MemoryService; print('OK')"`
Expected: OK

**Step 5: Commit**

```bash
git add backend/services/memory.py
git commit -m "feat(verifier): Add literature_verifier namespace to memory"
```

---

## Task 7: Backend - API Endpoints

**Files:**
- Modify: `backend/main.py`

**Step 1: Add request models**

Find the Request/Response Models section and add:

```python
class VerifyReferencesRequest(BaseModel):
    project_path: str
    bib_file: Optional[str] = None


class ApproveReferenceRequest(BaseModel):
    project_path: str
    cite_key: str
```

**Step 2: Add the SSE streaming endpoint**

Add after the memory endpoints (around line 600+):

```python
# ============ Literature Verifier Endpoints ============

@app.post("/api/verify-references")
async def verify_references(request: VerifyReferencesRequest):
    """
    Verify all references in a project.
    Streams results as SSE events.
    """
    import httpx
    from anthropic import AsyncAnthropic
    from services.reference_verifier import ReferenceVerifier
    from services.memory import MemoryService

    async def generate():
        # Initialize clients
        http_client = httpx.AsyncClient()
        anthropic = AsyncAnthropic(
            auth_token="vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336",
            base_url="https://colorist-gateway-staging.arco.ai",
            http_client=http_client,
        )

        try:
            verifier = ReferenceVerifier(
                project_path=request.project_path,
                http_client=http_client,
                anthropic_client=anthropic,
            )

            # Get approved citations
            memory = MemoryService(request.project_path)
            approved = set(memory.get_approved_citations())

            # Send started event
            yield {
                "event": "started",
                "data": json.dumps({"project_path": request.project_path}),
            }

            stats = {"verified": 0, "warnings": 0, "errors": 0}

            async for result in verifier.verify_all():
                # Skip if already approved
                if result.cite_key in approved:
                    result.status = "verified"
                    result.context_explanation = "Manually approved"

                # Update stats
                if result.status == "verified":
                    stats["verified"] += 1
                elif result.status == "warning":
                    stats["warnings"] += 1
                else:
                    stats["errors"] += 1

                yield {
                    "event": "result",
                    "data": json.dumps(result.to_dict()),
                }

            yield {
                "event": "complete",
                "data": json.dumps(stats),
            }

        finally:
            await http_client.aclose()

    return EventSourceResponse(generate())


@app.get("/api/verify-references/state")
async def get_verifier_state(project_path: str):
    """Get saved verifier state (approved citations)."""
    from services.memory import MemoryService

    memory = MemoryService(project_path)
    return {
        "approved_citations": memory.get_approved_citations(),
    }


@app.post("/api/verify-references/approve")
async def approve_reference(request: ApproveReferenceRequest):
    """Approve a reference manually."""
    from services.memory import MemoryService

    memory = MemoryService(request.project_path)
    memory.approve_citation(request.cite_key)
    return {"success": True, "cite_key": request.cite_key}


@app.post("/api/verify-references/unapprove")
async def unapprove_reference(request: ApproveReferenceRequest):
    """Remove approval from a reference."""
    from services.memory import MemoryService

    memory = MemoryService(request.project_path)
    memory.unapprove_citation(request.cite_key)
    return {"success": True, "cite_key": request.cite_key}
```

**Step 3: Test the endpoint exists**

Run: `cd /Users/zhongzhiyi/Aura/backend && python3 -c "from main import app; print([r.path for r in app.routes if 'verify' in r.path])"`
Expected: List containing '/api/verify-references'

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(verifier): Add verify-references API endpoints"
```

---

## Task 8: Frontend - API Client Methods

**Files:**
- Modify: `app/lib/api.ts`

**Step 1: Add TypeScript types**

Add after the Chat Session Types section:

```typescript
// =============================================================================
// Literature Verifier Types
// =============================================================================

export interface CitationUsage {
  cite_key: string;
  line_number: number;
  surrounding_text: string;
  claim: string;
}

export interface VerificationResult {
  cite_key: string;
  status: 'verified' | 'warning' | 'error' | 'pending';
  exists: boolean;
  matched_paper: {
    paper_id: string;
    title: string;
    authors: string[];
    year?: number;
    abstract: string;
    citation_count: number;
    url: string;
  } | null;
  metadata_issues: string[];
  context_score: number;
  context_explanation: string;
  checked_via: 'abstract' | 'pdf' | 'skipped' | 'failed';
  bib_entry: {
    key: string;
    fields: Record<string, string>;
  } | null;
  usages: CitationUsage[];
}

export interface VerifierState {
  approved_citations: string[];
}
```

**Step 2: Add API methods to ApiClient class**

Add to the ApiClient class before the health check section:

```typescript
// ===========================================================================
// Literature Verifier Operations
// ===========================================================================

/**
 * Get verifier state (approved citations)
 */
async getVerifierState(projectPath: string): Promise<VerifierState> {
  await this.ensureInitialized();

  const url = `${this.baseUrl}/api/verify-references/state?project_path=${encodeURIComponent(projectPath)}`;
  console.log('[API] getVerifierState:', url);

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Approve a citation manually
 */
async approveCitation(projectPath: string, citeKey: string): Promise<{ success: boolean }> {
  await this.ensureInitialized();

  const url = `${this.baseUrl}/api/verify-references/approve`;
  console.log('[API] approveCitation:', url, { citeKey });

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_path: projectPath,
      cite_key: citeKey,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Remove approval from a citation
 */
async unapproveCitation(projectPath: string, citeKey: string): Promise<{ success: boolean }> {
  await this.ensureInitialized();

  const url = `${this.baseUrl}/api/verify-references/unapprove`;
  console.log('[API] unapproveCitation:', url, { citeKey });

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_path: projectPath,
      cite_key: citeKey,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get base URL for SSE streaming
 */
getVerifyReferencesUrl(projectPath: string): string {
  return `${this.baseUrl}/api/verify-references`;
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/zhongzhiyi/Aura/app && npm run build 2>&1 | head -20`
Expected: No errors related to api.ts

**Step 4: Commit**

```bash
git add app/lib/api.ts
git commit -m "feat(verifier): Add API client methods for literature verifier"
```

---

## Task 9: Frontend - CitationVerifierPanel Component

**Files:**
- Create: `app/components/CitationVerifierPanel.tsx`

**Step 1: Create the component**

```tsx
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Trash2,
  Check,
} from 'lucide-react';
import { api, VerificationResult } from '../lib/api';

interface CitationVerifierPanelProps {
  projectPath: string;
  onClose: () => void;
}

interface VerifierStats {
  verified: number;
  warnings: number;
  errors: number;
}

export default function CitationVerifierPanel({
  projectPath,
  onClose,
}: CitationVerifierPanelProps) {
  const [results, setResults] = useState<Map<string, VerificationResult>>(new Map());
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [stats, setStats] = useState<VerifierStats>({ verified: 0, warnings: 0, errors: 0 });
  const [isRunning, setIsRunning] = useState(false);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load initial state
  useEffect(() => {
    const loadState = async () => {
      try {
        const state = await api.getVerifierState(projectPath);
        setApproved(new Set(state.approved_citations));
      } catch (e) {
        console.error('Failed to load verifier state:', e);
      }
    };
    loadState();
  }, [projectPath]);

  // Run verification
  const runVerification = useCallback(async () => {
    if (isRunning) return;

    setIsRunning(true);
    setResults(new Map());
    setStats({ verified: 0, warnings: 0, errors: 0 });

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(api.getVerifyReferencesUrl(projectPath), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());

              if (data.cite_key) {
                // This is a verification result
                setResults((prev) => {
                  const next = new Map(prev);
                  next.set(data.cite_key, data as VerificationResult);
                  return next;
                });
              } else if (data.verified !== undefined) {
                // This is the final stats
                setStats(data);
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name !== 'AbortError') {
        console.error('Verification error:', error);
      }
    } finally {
      setIsRunning(false);
      abortControllerRef.current = null;
    }
  }, [projectPath, isRunning]);

  // Auto-run on mount
  useEffect(() => {
    runVerification();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Approve a citation
  const handleApprove = async (citeKey: string) => {
    try {
      await api.approveCitation(projectPath, citeKey);
      setApproved((prev) => new Set([...prev, citeKey]));
      setResults((prev) => {
        const next = new Map(prev);
        const result = next.get(citeKey);
        if (result) {
          next.set(citeKey, { ...result, status: 'verified' });
        }
        return next;
      });
    } catch (e) {
      console.error('Failed to approve:', e);
    }
  };

  // Toggle expansion
  const toggleExpand = (citeKey: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(citeKey)) {
        next.delete(citeKey);
      } else {
        next.add(citeKey);
      }
      return next;
    });
  };

  // Sort results: errors first, then warnings, then verified
  const sortedResults = Array.from(results.values()).sort((a, b) => {
    const order = { error: 0, warning: 1, pending: 2, verified: 3 };
    return order[a.status] - order[b.status];
  });

  return (
    <div className="h-full flex flex-col bg-fill-secondary">
      {/* Header */}
      <div className="panel-header bg-white border-b border-black/6">
        <div className="flex items-center justify-between w-full">
          <h2 className="typo-h4 flex items-center gap-2">
            📚 Reference Verification
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={runVerification}
              disabled={isRunning}
              className="btn-ghost typo-small flex items-center gap-1.5"
            >
              <RefreshCw size={14} className={isRunning ? 'animate-spin' : ''} />
              {isRunning ? 'Verifying...' : 'Run Again'}
            </button>
            <button
              onClick={onClose}
              className="btn-ghost typo-small"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="px-4 py-2 bg-white border-b border-black/6 flex items-center gap-4">
        <span className="typo-small flex items-center gap-1.5 text-success">
          <CheckCircle size={14} />
          {stats.verified} verified
        </span>
        <span className="typo-small flex items-center gap-1.5 text-orange1">
          <AlertTriangle size={14} />
          {stats.warnings} warnings
        </span>
        <span className="typo-small flex items-center gap-1.5 text-error">
          <XCircle size={14} />
          {stats.errors} errors
        </span>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sortedResults.length === 0 && isRunning && (
          <div className="text-center py-8 text-secondary">
            <Loader2 size={24} className="animate-spin mx-auto mb-2" />
            <p className="typo-small">Verifying references...</p>
          </div>
        )}

        {sortedResults.map((result) => (
          <CitationCard
            key={result.cite_key}
            result={result}
            isExpanded={expandedKeys.has(result.cite_key)}
            isApproved={approved.has(result.cite_key)}
            onToggleExpand={() => toggleExpand(result.cite_key)}
            onApprove={() => handleApprove(result.cite_key)}
          />
        ))}
      </div>
    </div>
  );
}

// Individual citation card
function CitationCard({
  result,
  isExpanded,
  isApproved,
  onToggleExpand,
  onApprove,
}: {
  result: VerificationResult;
  isExpanded: boolean;
  isApproved: boolean;
  onToggleExpand: () => void;
  onApprove: () => void;
}) {
  const statusIcon = {
    verified: <CheckCircle size={16} className="text-success" />,
    warning: <AlertTriangle size={16} className="text-orange1" />,
    error: <XCircle size={16} className="text-error" />,
    pending: <Loader2 size={16} className="text-tertiary animate-spin" />,
  }[result.status];

  const statusClass = {
    verified: 'border-success/20 bg-success/5',
    warning: 'border-orange1/20 bg-orange1/5',
    error: 'border-error/20 bg-error/5',
    pending: 'border-black/6 bg-white',
  }[result.status];

  return (
    <div className={`rounded-yw-lg border p-3 ${statusClass}`}>
      {/* Header row */}
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={onToggleExpand}
      >
        {isExpanded ? (
          <ChevronDown size={14} className="text-tertiary" />
        ) : (
          <ChevronRight size={14} className="text-tertiary" />
        )}
        {statusIcon}
        <span className="typo-small-strong flex-1 font-mono">{result.cite_key}</span>

        {/* Actions */}
        {result.status !== 'verified' && !isApproved && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onApprove();
            }}
            className="btn-ghost typo-ex-small flex items-center gap-1 text-success"
          >
            <Check size={12} />
            Approve
          </button>
        )}
      </div>

      {/* Title */}
      {result.matched_paper && (
        <div className="mt-1 ml-6 typo-small text-secondary">
          "{result.matched_paper.title}" ({result.matched_paper.year || 'n.d.'})
        </div>
      )}

      {/* Issues */}
      {result.metadata_issues.length > 0 && (
        <div className="mt-1 ml-6 typo-ex-small text-orange1">
          {result.metadata_issues.join(', ')}
        </div>
      )}

      {/* Context score */}
      {result.checked_via !== 'skipped' && (
        <div className="mt-1 ml-6 typo-ex-small text-tertiary">
          {result.usages.length} usage{result.usages.length !== 1 ? 's' : ''} ·
          Context: {result.context_explanation || `${(result.context_score * 100).toFixed(0)}% confidence`}
        </div>
      )}

      {/* Expanded details */}
      {isExpanded && (
        <div className="mt-3 ml-6 space-y-2">
          {/* Paper link */}
          {result.matched_paper?.url && (
            <a
              href={result.matched_paper.url}
              target="_blank"
              rel="noopener noreferrer"
              className="typo-small text-green1 flex items-center gap-1 hover:underline"
            >
              <ExternalLink size={12} />
              View on Semantic Scholar
            </a>
          )}

          {/* Usages */}
          {result.usages.length > 0 && (
            <div>
              <div className="typo-ex-small text-tertiary mb-1">Usages in document:</div>
              {result.usages.map((usage, i) => (
                <div key={i} className="typo-ex-small bg-white rounded p-2 mb-1 border border-black/6">
                  <div className="text-tertiary">Line {usage.line_number}</div>
                  <div className="text-primary italic">"{usage.claim}"</div>
                </div>
              ))}
            </div>
          )}

          {/* BibTeX info */}
          {result.bib_entry && (
            <div>
              <div className="typo-ex-small text-tertiary mb-1">BibTeX fields:</div>
              <pre className="typo-ex-small bg-white rounded p-2 border border-black/6 overflow-x-auto font-mono">
                {JSON.stringify(result.bib_entry.fields, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/zhongzhiyi/Aura/app && npx tsc --noEmit 2>&1 | grep -i error | head -10`
Expected: No errors

**Step 3: Commit**

```bash
git add app/components/CitationVerifierPanel.tsx
git commit -m "feat(verifier): Add CitationVerifierPanel component"
```

---

## Task 10: Frontend - Register Slash Command

**Files:**
- Modify: `app/lib/commands.ts`

**Step 1: Add the literature-verifier command**

Add to the commands array after the `clean-bib` command:

```typescript
{
  name: 'literature-verifier',
  description: 'Verify all citations are real and used correctly',
  icon: 'BookCheck',
  category: 'writing',
  requiresArg: false,
  executionType: 'api',
  execute: async ({ projectPath }) => {
    // This command switches the UI to verifier mode
    // The actual verification is handled by AgentPanel
    return {
      success: true,
      message: 'Opening literature verifier...',
      switchMode: 'verifier' as any,  // We'll add this mode
    };
  },
},
```

**Step 2: Update CommandResult type to support verifier mode**

Find the `CommandResult` interface and update:

```typescript
export interface CommandResult {
  success: boolean;
  message?: string;
  switchMode?: 'chat' | 'vibe' | 'verifier';
  vibeSessionId?: string;
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/zhongzhiyi/Aura/app && npx tsc --noEmit 2>&1 | grep -i error | head -10`
Expected: No errors

**Step 4: Commit**

```bash
git add app/lib/commands.ts
git commit -m "feat(verifier): Register /literature-verifier slash command"
```

---

## Task 11: Frontend - Integrate into AgentPanel

**Files:**
- Modify: `app/components/AgentPanel.tsx`

**Step 1: Import the CitationVerifierPanel**

Add to imports:

```typescript
import CitationVerifierPanel from './CitationVerifierPanel';
```

**Step 2: Update AgentMode type**

Find the `AgentMode` type and update:

```typescript
type AgentMode = 'chat' | 'vibe' | 'verifier';
```

**Step 3: Handle verifier mode in command execution**

Find the `executeCommand` function and update the mode switch handling:

```typescript
if (result.switchMode) {
  setMode(result.switchMode);
  if (result.vibeSessionId) {
    setSelectedVibeSession(result.vibeSessionId);
  }
}
```

**Step 4: Add verifier tab to mode toggle**

Find the mode toggle buttons section and add a third button:

```tsx
<button
  onClick={() => setMode('verifier')}
  disabled={isStreaming}
  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-yw-md typo-small transition-all whitespace-nowrap ${
    mode === 'verifier'
      ? 'bg-white text-green1 shadow-sm'
      : 'text-secondary hover:text-primary'
  } ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
>
  <BookOpen size={14} className="flex-shrink-0" />
  <span className="hidden sm:inline">Verify</span>
</button>
```

And add the import for `BookOpen`:

```typescript
import {
  // ... existing imports
  BookOpen,
} from 'lucide-react';
```

**Step 5: Add verifier mode content**

Find the content rendering section (after the Vibe Research Mode section) and add:

```tsx
{mode === 'verifier' && projectPath && (
  <CitationVerifierPanel
    projectPath={projectPath}
    onClose={() => setMode('chat')}
  />
)}
```

**Step 6: Verify the build works**

Run: `cd /Users/zhongzhiyi/Aura/app && npm run build 2>&1 | tail -5`
Expected: Build successful

**Step 7: Commit**

```bash
git add app/components/AgentPanel.tsx
git commit -m "feat(verifier): Integrate CitationVerifierPanel into AgentPanel"
```

---

## Task 12: Integration Test

**Step 1: Start the backend**

Run: `cd /Users/zhongzhiyi/Aura/backend && uvicorn main:app --reload --port 8001 &`

**Step 2: Start the frontend**

Run: `cd /Users/zhongzhiyi/Aura/app && npm run dev &`

**Step 3: Test the full flow**

1. Open a project with a .bib file
2. Type `/literature-verifier` in the chat input
3. Verify the panel opens and shows citation verification results
4. Click "Approve" on a warning to verify it persists
5. Click "Run Again" to verify approved citations are remembered

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Complete literature verifier implementation

- Add ReferenceVerifier service with Semantic Scholar lookup
- Add context validation using Haiku LLM
- Add SSE streaming API endpoints
- Add CitationVerifierPanel UI component
- Add /literature-verifier slash command
- Integrate into AgentPanel with mode switching
- Store approvals in isolated memory namespace"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Data models | `backend/services/reference_verifier.py` |
| 2 | Citation context extraction | `backend/services/reference_verifier.py` |
| 3 | Paper lookup via S2 | `backend/services/reference_verifier.py` |
| 4 | Context validation with LLM | `backend/services/reference_verifier.py` |
| 5 | ReferenceVerifier class | `backend/services/reference_verifier.py` |
| 6 | Memory namespace | `backend/services/memory.py` |
| 7 | API endpoints | `backend/main.py` |
| 8 | API client methods | `app/lib/api.ts` |
| 9 | CitationVerifierPanel | `app/components/CitationVerifierPanel.tsx` |
| 10 | Slash command | `app/lib/commands.ts` |
| 11 | AgentPanel integration | `app/components/AgentPanel.tsx` |
| 12 | Integration test | - |
