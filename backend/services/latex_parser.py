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

# Section commands with their levels (by command name)
SECTION_LEVELS = {
    "part": 0,
    "chapter": 0,
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
    "paragraph": 4,
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

            # Extract command name and determine level
            cmd_match = re.match(r"\\([a-z]+)", full_match)
            if cmd_match:
                command = "\\" + cmd_match.group(1)
                cmd_name = cmd_match.group(1)
                level = SECTION_LEVELS.get(cmd_name, 1)
            else:
                command = r"\section"
                level = 1

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


# =============================================================================
# Element Parsing (Figures, Tables, Algorithms)
# =============================================================================

# Environment patterns
ENVIRONMENT_START = re.compile(r"\\begin\{(\w+)\}")
ENVIRONMENT_END = re.compile(r"\\end\{(\w+)\}")
CAPTION_REGEX = re.compile(r"\\caption\{([^}]+)\}")

# Element types we track
ELEMENT_TYPES = {"figure", "table", "algorithm", "lstlisting", "equation", "align"}


def parse_elements(content: str) -> list[DocumentElement]:
    """
    Parse figures, tables, algorithms from LaTeX content.

    Extracts:
    - Environment type
    - Caption text
    - Label
    - Line numbers
    """
    lines = content.split("\n")
    elements: list[DocumentElement] = []

    # Track open environments
    env_stack: list[tuple[str, int, list[str]]] = []  # (type, start_line, content_lines)

    for i, line in enumerate(lines, start=1):
        # Check for environment start
        start_match = ENVIRONMENT_START.search(line)
        if start_match:
            env_type = start_match.group(1)
            if env_type in ELEMENT_TYPES:
                env_stack.append((env_type, i, [line]))
                continue

        # Check for environment end
        end_match = ENVIRONMENT_END.search(line)
        if end_match and env_stack:
            env_type = end_match.group(1)
            if env_stack[-1][0] == env_type:
                start_type, start_line, content_lines = env_stack.pop()
                content_lines.append(line)
                full_content = "\n".join(content_lines)

                # Extract caption and label
                caption_match = CAPTION_REGEX.search(full_content)
                label_match = LABEL_REGEX.search(full_content)

                elements.append(DocumentElement(
                    type=start_type,
                    label=label_match.group(1) if label_match else None,
                    caption=caption_match.group(1) if caption_match else None,
                    line_start=start_line,
                    line_end=i,
                    content=full_content,
                ))
                continue

        # Accumulate content for open environments
        if env_stack:
            env_stack[-1][2].append(line)

    return elements


# =============================================================================
# Citation Parsing
# =============================================================================

# Citation command patterns (BibLaTeX and natbib variants)
CITATION_COMMANDS = [
    "cite", "citep", "citet", "citeauthor", "citeyear",
    "autocite", "textcite", "parencite", "footcite",
    "fullcite", "nocite",
]
CITATION_REGEX = re.compile(
    r"\\(" + "|".join(CITATION_COMMANDS) + r")\{([^}]+)\}"
)

# Package detection
USEPACKAGE_REGEX = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
BIBRESOURCE_REGEX = re.compile(r"\\addbibresource\{([^}]+)\}")
BIBLIOGRAPHY_REGEX = re.compile(r"\\bibliography\{([^}]+)\}")


def find_citations(content: str) -> list[CitationInfo]:
    """
    Find all citations in the document.

    Returns list of CitationInfo with keys and their locations.
    """
    lines = content.split("\n")
    citations_map: dict[str, CitationInfo] = {}

    for i, line in enumerate(lines, start=1):
        for match in CITATION_REGEX.finditer(line):
            command = match.group(1)
            keys_str = match.group(2)

            # Handle multiple keys in one citation: \cite{key1,key2}
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]

            for key in keys:
                if key in citations_map:
                    if i not in citations_map[key].locations:
                        citations_map[key].locations.append(i)
                else:
                    citations_map[key] = CitationInfo(
                        key=key,
                        locations=[i],
                        command=command,
                    )

    return list(citations_map.values())


def detect_citation_style(content: str) -> tuple[str, Optional[str]]:
    """
    Detect citation style and bibliography file.

    Returns:
        (style, bib_file) where style is "biblatex" or "bibtex"
    """
    # Check for biblatex (must be in \usepackage or have \addbibresource)
    if BIBRESOURCE_REGEX.search(content) or re.search(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*biblatex", content):
        bib_match = BIBRESOURCE_REGEX.search(content)
        bib_file = bib_match.group(1) if bib_match else None
        return "biblatex", bib_file

    # Check for natbib or traditional bibtex
    bib_match = BIBLIOGRAPHY_REGEX.search(content)
    if bib_match:
        bib_file = bib_match.group(1)
        if not bib_file.endswith(".bib"):
            bib_file += ".bib"
        return "bibtex", bib_file

    return "unknown", None


def find_packages(content: str) -> list[str]:
    """Find all packages used in the document."""
    packages = []
    for match in USEPACKAGE_REGEX.finditer(content):
        # Handle multiple packages: \usepackage{pkg1,pkg2}
        pkgs = [p.strip() for p in match.group(1).split(",")]
        packages.extend(pkgs)
    return packages
