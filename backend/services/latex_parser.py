"""
LaTeX Parser Service

Parses LaTeX documents to extract structure, citations, and elements.
Uses regex for speed, with pylatexenc AST fallback for complex cases.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DocumentSection:
    """A section in the document hierarchy."""
    level: int                          # 0=document, 1=section, 2=subsection, 3=subsubsection
    name: str                           # "Introduction", "Methods", etc.
    command: str                        # r"\section", r"\subsection", etc.
    line_start: int
    line_end: int
    label: Optional[str] = None         # r"\label{sec:intro}" if present
    children: list["DocumentSection"] = field(default_factory=list)


@dataclass
class DocumentElement:
    """A figure, table, algorithm, or other floating element."""
    type: str                           # "figure", "table", "algorithm", "equation", "listing"
    label: Optional[str] = None
    caption: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    content: str = ""                   # Raw LaTeX content


@dataclass
class CitationInfo:
    """Information about a citation in the document."""
    key: str                            # "vaswani2017attention"
    locations: list[int] = field(default_factory=list)  # Line numbers where cited
    command: str = "cite"               # "cite", "citep", "citet", "autocite", etc.


@dataclass
class BibEntry:
    """A bibliography entry from a .bib file."""
    key: str
    entry_type: str                     # "article", "inproceedings", "book", etc.
    fields: dict[str, str] = field(default_factory=dict)  # title, author, year, etc.
    raw: str = ""                       # Original BibTeX string


@dataclass
class DocumentStructure:
    """Complete parsed structure of a LaTeX document."""
    sections: list[DocumentSection] = field(default_factory=list)
    elements: list[DocumentElement] = field(default_factory=list)
    citations: list[CitationInfo] = field(default_factory=list)
    citation_style: str = "unknown"     # "biblatex" or "bibtex"
    bib_file: Optional[str] = None      # Path to .bib file
    packages: list[str] = field(default_factory=list)
