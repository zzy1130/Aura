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


# =============================================================================
# Regex Patterns
# =============================================================================

# Section commands with their levels
SECTION_PATTERNS = {
    r"\\part\{": 0,
    r"\\chapter\{": 0,
    r"\\section\{": 1,
    r"\\subsection\{": 2,
    r"\\subsubsection\{": 3,
    r"\\paragraph\{": 4,
}

# Combined pattern to find any section
SECTION_REGEX = re.compile(
    r"^[ \t]*(\\(?:part|chapter|section|subsection|subsubsection|paragraph)\{([^}]+)\})",
    re.MULTILINE
)

# Label pattern
LABEL_REGEX = re.compile(r"\\label\{([^}]+)\}")


# =============================================================================
# Section Parsing
# =============================================================================

def parse_sections(content: str) -> list[DocumentSection]:
    """
    Parse section hierarchy from LaTeX content.

    Returns a flat list of sections with line numbers.
    Use build_section_tree() to get nested structure.
    """
    lines = content.split("\n")
    sections: list[DocumentSection] = []

    for i, line in enumerate(lines, start=1):
        match = SECTION_REGEX.match(line)
        if match:
            full_match = match.group(1)
            name = match.group(2)

            # Determine level
            level = 1  # default to section
            for pattern, lvl in SECTION_PATTERNS.items():
                if re.match(pattern, full_match):
                    level = lvl
                    break

            # Extract command
            cmd_match = re.match(r"(\\[a-z]+)", full_match)
            command = cmd_match.group(1) if cmd_match else r"\section"

            # Look for label on same or next line
            label = None
            label_match = LABEL_REGEX.search(line)
            if not label_match and i < len(lines):
                label_match = LABEL_REGEX.search(lines[i])
            if label_match:
                label = label_match.group(1)

            sections.append(DocumentSection(
                level=level,
                name=name,
                command=command,
                line_start=i,
                line_end=i,  # Will be updated later
                label=label,
            ))

    # Calculate line_end for each section (start of next section - 1)
    for i, section in enumerate(sections):
        if i + 1 < len(sections):
            section.line_end = sections[i + 1].line_start - 1
        else:
            section.line_end = len(lines)

    return sections


def build_section_tree(sections: list[DocumentSection]) -> list[DocumentSection]:
    """
    Build nested section hierarchy from flat list.

    Returns only top-level sections with children nested.
    """
    if not sections:
        return []

    root: list[DocumentSection] = []
    stack: list[DocumentSection] = []

    for section in sections:
        # Pop sections from stack that are same level or deeper
        while stack and stack[-1].level >= section.level:
            stack.pop()

        if stack:
            # Add as child of parent
            stack[-1].children.append(section)
        else:
            # Top-level section
            root.append(section)

        stack.append(section)

    return root
