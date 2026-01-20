"""
Reference Verification Service

Verifies that bibliography entries are real papers with correct metadata
and are cited in appropriate context.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx

from services.latex_parser import BibEntry
from services.semantic_scholar import Paper, SemanticScholarClient


# Citation patterns (same as latex_parser but we need the positions)
CITATION_COMMANDS = [
    "cite", "citep", "citet", "citeauthor", "citeyear",
    "autocite", "textcite", "parencite", "footcite",
    "fullcite", "nocite",
]
CITATION_REGEX = re.compile(
    r"\\(" + "|".join(CITATION_COMMANDS) + r")\{([^}]+)\}"
)


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
