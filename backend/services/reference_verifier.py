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
