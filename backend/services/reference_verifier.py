"""
Reference Verification Service

Verifies that bibliography entries are real papers with correct metadata
and are cited in appropriate context.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Optional
from services.latex_parser import BibEntry
from services.semantic_scholar import Paper


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
