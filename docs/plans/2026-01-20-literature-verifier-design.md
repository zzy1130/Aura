# Literature Verifier Design

**Date**: 2026-01-20
**Status**: Approved
**Trigger**: `/literature-verifier` slash command

## Overview

A reference verification system that checks if citations in a LaTeX paper are:
1. **Real** - the paper exists in academic databases
2. **Accurate** - metadata (title, authors, year) matches the source
3. **Contextually valid** - the citation supports the claim being made

## Architecture

```
/literature-verifier command
         ↓
    Parse .bib file → Extract BibEntry list
         ↓
    Parse .tex file → Extract citation usages with context
         ↓
    For each citation:
    ┌─────────────────────────────────────────┐
    │ 1. Lookup via DOI/arXiv (if present)    │
    │    └─ or search Semantic Scholar by title│
    │ 2. Compare metadata (title, authors, year)│
    │ 3. Extract claim context from .tex       │
    │ 4. Compare claim vs abstract             │
    │    └─ if uncertain → fetch PDF, analyze │
    └─────────────────────────────────────────┘
         ↓
    Return VerificationResult per citation
         ↓
    Frontend renders CitationVerifierPanel
    (list view with status badges + actions)
```

## Data Models

### CitationContext

```python
@dataclass
class CitationContext:
    """A citation usage in the document."""
    cite_key: str
    line_number: int
    surrounding_text: str  # ~200 chars around \cite{}
    claim: str  # Extracted claim being made
```

### VerificationResult

```python
@dataclass
class VerificationResult:
    cite_key: str
    status: Literal["verified", "warning", "error", "pending"]

    # Existence check
    exists: bool
    matched_paper: Optional[Paper]  # From Semantic Scholar

    # Metadata check
    metadata_issues: list[str]  # e.g., ["Year mismatch: 2019 vs 2020"]

    # Context check
    context_score: float  # 0-1 confidence
    context_explanation: str  # Why it matches/doesn't
    checked_via: Literal["abstract", "pdf", "failed"]

    # Original data
    bib_entry: BibEntry
    usages: list[CitationContext]
```

## Context Validation

### Claim Extraction

```python
def extract_citation_context(tex_content: str, cite_key: str) -> list[CitationContext]:
    """Find all usages of a citation and extract surrounding context."""
    # Find \cite{key}, \citep{key}, etc.
    # Extract ~100 chars before the citation (the claim)
    # Return list since same ref may be cited multiple times
```

### Validation Prompt (Haiku)

```
Given this claim from a paper:
"{claim}"

And this abstract from the cited paper "{title}":
"{abstract}"

Does the abstract support this claim? Respond with:
- SUPPORTED: The abstract clearly supports this claim
- PLAUSIBLE: The abstract is related but doesn't directly confirm
- UNSUPPORTED: The abstract contradicts or doesn't relate to this claim
- UNCERTAIN: Cannot determine from abstract alone

One sentence explanation.
```

### Hybrid Escalation

- `SUPPORTED` → score 0.9, done
- `PLAUSIBLE` → score 0.6, done
- `UNSUPPORTED` → score 0.2, flag as error
- `UNCERTAIN` → fetch PDF via `read_pdf_url`, re-run with full text

## API Endpoints

### POST /api/verify-references

Streams verification results as SSE:

```
event: started
data: {"total_citations": 15, "bib_file": "references.bib"}

event: progress
data: {"cite_key": "vaswani2017attention", "status": "verifying", "step": "lookup"}

event: result
data: {"cite_key": "vaswani2017attention", "status": "verified", ...}

event: complete
data: {"verified": 12, "warnings": 2, "errors": 1}
```

### GET /api/verify-references/state

Load saved approvals for this project.

### POST /api/verify-references/approve

Save manual approval to project memory.

## Frontend Component

### CitationVerifierPanel

```
┌─────────────────────────────────────────────────────┐
│ 📚 Reference Verification          [Run Again]      │
├─────────────────────────────────────────────────────┤
│ ✅ vaswani2017attention                  [Approve]  │
│    "Attention Is All You Need" (2017)               │
│    3 usages · Context: supported                    │
├─────────────────────────────────────────────────────┤
│ ⚠️  smith2020deep                        [Approve]  │
│    Year mismatch: bib says 2020, found 2019        │
│    1 usage · Context: plausible                     │
├─────────────────────────────────────────────────────┤
│ ❌ jones2023fake                         [Remove]   │
│    Paper not found in any database                  │
│    2 usages                                         │
├─────────────────────────────────────────────────────┤
│ ⏳ brown2022transformers                            │
│    Verifying... (checking context)                  │
└─────────────────────────────────────────────────────┘
```

### Status Badges

- ✅ `verified` - exists, metadata correct, context supported
- ⚠️ `warning` - exists but metadata issues or context plausible
- ❌ `error` - doesn't exist or context unsupported
- ⏳ `pending` - still verifying

### Actions

- **Approve** - mark as manually verified (persists to project memory)
- **View Details** - expand to show all usages, full context analysis
- **Remove** - remove citation from .bib file
- **Fix** - auto-correct metadata based on found paper

## Memory Scope

Verification state is isolated from main agent:

```python
{
    "project_id": "...",
    "agent_memory": { ... },  # Normal agent context - unchanged

    "literature_verifier": {  # Separate namespace
        "approved_citations": ["vaswani2017attention", "brown2020gpt3"],
        "last_run": "2026-01-20T10:30:00Z",
        "cached_results": { ... }
    }
}
```

The main agent (`pydantic_agent.py`) never sees or loads this data.

## Files to Create

| File | Purpose |
|------|---------|
| `backend/services/reference_verifier.py` | Core verification logic |
| `app/components/CitationVerifierPanel.tsx` | UI component |

## Files to Modify

| File | Change |
|------|--------|
| `backend/services/memory.py` | Add `literature_verifier` namespace |
| `backend/main.py` | Register new endpoints |
| `app/components/AgentPanel.tsx` | Conditional render for verifier mode |
| `app/lib/commands.ts` | Register `/literature-verifier` command |

## Dependencies

Uses existing infrastructure:
- `SemanticScholarClient` for paper lookups
- `latex_parser.py` for bib/tex parsing
- `read_pdf_url` for PDF fallback
- Haiku model for context validation (cheap/fast)
