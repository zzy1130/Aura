# Phase 8: Writing Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LaTeX-aware intelligence to Aura - structure analysis, citation management, content generation, and writing quality tools.

**Architecture:** Hybrid approach with core tools on main agent and complex operations delegated to WritingAgent subagent. All LaTeX parsing centralized in `latex_parser.py` service using regex for speed + pylatexenc AST for complex cases.

**Tech Stack:** Python 3.11+, PydanticAI, pylatexenc (LaTeX AST), regex patterns

**Design Doc:** `docs/plans/2026-01-14-phase8-writing-intelligence.md`

---

## Task 1: LaTeX Parser Service - Data Structures

**Files:**
- Create: `backend/services/latex_parser.py`

**Step 1: Create the data structures**

```python
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
```

**Step 2: Verify the module imports**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 -c "from services.latex_parser import DocumentSection, DocumentStructure; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add LaTeX parser data structures"
```

---

## Task 2: LaTeX Parser - Section Parsing

**Files:**
- Modify: `backend/services/latex_parser.py`

**Step 1: Add section parsing with regex**

Add after the dataclasses:

```python
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
```

**Step 2: Test section parsing**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import parse_sections, build_section_tree

test_doc = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
\label{sec:intro}
Some intro text.

\subsection{Motivation}
Why we do this.

\subsection{Contributions}
What we contribute.

\section{Methods}
\label{sec:methods}

\subsection{Problem Setup}
The problem.

\section{Conclusion}
Done.

\end{document}
"""

sections = parse_sections(test_doc)
print(f"Found {len(sections)} sections:")
for s in sections:
    print(f"  L{s.line_start}-{s.line_end}: {s.command}{{{s.name}}} (level {s.level}, label={s.label})")

tree = build_section_tree(sections)
print(f"\nTree structure ({len(tree)} top-level):")
for s in tree:
    print(f"  {s.name} ({len(s.children)} children)")
    for c in s.children:
        print(f"    - {c.name}")
EOF
```

Expected output should show:
- 6 sections found (Introduction, Motivation, Contributions, Methods, Problem Setup, Conclusion)
- Labels detected for Introduction and Methods
- Tree with 3 top-level sections, Introduction with 2 children, Methods with 1 child

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add section parsing with regex"
```

---

## Task 3: LaTeX Parser - Element Parsing (Figures/Tables)

**Files:**
- Modify: `backend/services/latex_parser.py`

**Step 1: Add element parsing**

Add after `build_section_tree`:

```python
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
```

**Step 2: Test element parsing**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import parse_elements

test_doc = r"""
\begin{figure}[htbp]
    \centering
    \includegraphics{diagram.png}
    \caption{System Architecture}
    \label{fig:architecture}
\end{figure}

Some text here.

\begin{table}[htbp]
    \centering
    \caption{Results Comparison}
    \label{tab:results}
    \begin{tabular}{lcc}
        Model & Accuracy & F1 \\
        BERT & 85.2 & 84.1 \\
    \end{tabular}
\end{table}

\begin{algorithm}
    \caption{Training Loop}
    \label{alg:train}
    \For{epoch in epochs}{...}
\end{algorithm}
"""

elements = parse_elements(test_doc)
print(f"Found {len(elements)} elements:")
for e in elements:
    print(f"  {e.type}: '{e.caption}' (L{e.line_start}-{e.line_end}, label={e.label})")
EOF
```

Expected: 3 elements (figure, table, algorithm) with captions and labels

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add element parsing (figures, tables, algorithms)"
```

---

## Task 4: LaTeX Parser - Citation Parsing

**Files:**
- Modify: `backend/services/latex_parser.py`

**Step 1: Add citation detection and style detection**

Add after `parse_elements`:

```python
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
            keys = [k.strip() for k in keys_str.split(",")]

            for key in keys:
                if key in citations_map:
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
    # Check for biblatex
    if "biblatex" in content or BIBRESOURCE_REGEX.search(content):
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
```

**Step 2: Test citation parsing**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import find_citations, detect_citation_style, find_packages

test_biblatex = r"""
\documentclass{article}
\usepackage{amsmath,graphicx}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}

Transformers \cite{vaswani2017attention} revolutionized NLP.
See also \citep{devlin2019bert,brown2020gpt3}.
According to \citet{vaswani2017attention}, attention is all you need.
"""

test_bibtex = r"""
\documentclass{article}
\usepackage{natbib}

As shown by \citep{smith2020}.
\bibliography{references}
"""

print("=== BibLaTeX document ===")
cites = find_citations(test_biblatex)
print(f"Citations: {len(cites)}")
for c in cites:
    print(f"  {c.key}: lines {c.locations} (via \\{c.command})")

style, bib = detect_citation_style(test_biblatex)
print(f"Style: {style}, Bib file: {bib}")
print(f"Packages: {find_packages(test_biblatex)}")

print("\n=== BibTeX document ===")
style, bib = detect_citation_style(test_bibtex)
print(f"Style: {style}, Bib file: {bib}")
EOF
```

Expected:
- 3 unique citation keys found (vaswani2017attention appears twice)
- biblatex style detected with refs.bib
- bibtex style detected with references.bib

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add citation and package detection"
```

---

## Task 5: LaTeX Parser - BibTeX Parsing

**Files:**
- Modify: `backend/services/latex_parser.py`

**Step 1: Add BibTeX file parsing**

Add after `find_packages`:

```python
# =============================================================================
# BibTeX Parsing
# =============================================================================

# BibTeX entry pattern
BIB_ENTRY_REGEX = re.compile(
    r"@(\w+)\s*\{\s*([^,]+)\s*,",
    re.IGNORECASE
)
BIB_FIELD_REGEX = re.compile(
    r"(\w+)\s*=\s*[{\"]([^}\"]+)[}\"]",
    re.IGNORECASE
)


def parse_bib_file(content: str) -> list[BibEntry]:
    """
    Parse a .bib file and extract all entries.

    Handles standard BibTeX format with @type{key, field={value}, ...}
    """
    entries: list[BibEntry] = []

    # Split into individual entries (rough split on @)
    parts = re.split(r"(?=@\w+\{)", content)

    for part in parts:
        part = part.strip()
        if not part.startswith("@"):
            continue

        # Extract entry type and key
        entry_match = BIB_ENTRY_REGEX.match(part)
        if not entry_match:
            continue

        entry_type = entry_match.group(1).lower()
        key = entry_match.group(2).strip()

        # Skip comments and preambles
        if entry_type in ("comment", "preamble", "string"):
            continue

        # Extract fields
        fields: dict[str, str] = {}
        for field_match in BIB_FIELD_REGEX.finditer(part):
            field_name = field_match.group(1).lower()
            field_value = field_match.group(2).strip()
            fields[field_name] = field_value

        entries.append(BibEntry(
            key=key,
            entry_type=entry_type,
            fields=fields,
            raw=part,
        ))

    return entries


def find_unused_citations(
    document_citations: list[CitationInfo],
    bib_entries: list[BibEntry],
) -> list[BibEntry]:
    """Find bibliography entries that are not cited in the document."""
    cited_keys = {c.key for c in document_citations}
    return [e for e in bib_entries if e.key not in cited_keys]


def find_missing_citations(
    document_citations: list[CitationInfo],
    bib_entries: list[BibEntry],
) -> list[str]:
    """Find citation keys used in document but not in bibliography."""
    bib_keys = {e.key for e in bib_entries}
    return [c.key for c in document_citations if c.key not in bib_keys]
```

**Step 2: Test BibTeX parsing**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import parse_bib_file, find_unused_citations, find_missing_citations, CitationInfo

test_bib = """
@article{vaswani2017attention,
    title={Attention Is All You Need},
    author={Vaswani, Ashish and others},
    journal={NeurIPS},
    year={2017}
}

@inproceedings{devlin2019bert,
    title={BERT: Pre-training of Deep Bidirectional Transformers},
    author={Devlin, Jacob and others},
    booktitle={NAACL},
    year={2019}
}

@misc{unused2020paper,
    title={This Paper Is Never Cited},
    author={Nobody},
    year={2020}
}
"""

entries = parse_bib_file(test_bib)
print(f"Parsed {len(entries)} entries:")
for e in entries:
    print(f"  @{e.entry_type}{{{e.key}}}: {e.fields.get('title', 'No title')[:50]}")

# Simulate document citations
doc_citations = [
    CitationInfo(key="vaswani2017attention", locations=[10]),
    CitationInfo(key="devlin2019bert", locations=[15]),
    CitationInfo(key="missing2021", locations=[20]),  # Not in bib
]

unused = find_unused_citations(doc_citations, entries)
print(f"\nUnused entries: {[e.key for e in unused]}")

missing = find_missing_citations(doc_citations, entries)
print(f"Missing from bib: {missing}")
EOF
```

Expected:
- 3 entries parsed
- unused2020paper identified as unused
- missing2021 identified as missing from bib

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add BibTeX file parsing"
```

---

## Task 6: LaTeX Parser - Main Parse Function

**Files:**
- Modify: `backend/services/latex_parser.py`

**Step 1: Add main parse function and file loading**

Add at the end of the file:

```python
# =============================================================================
# Main Parser Interface
# =============================================================================

def parse_document(content: str) -> DocumentStructure:
    """
    Parse a LaTeX document and return complete structure.

    This is the main entry point for document analysis.
    """
    sections = parse_sections(content)
    elements = parse_elements(content)
    citations = find_citations(content)
    packages = find_packages(content)
    style, bib_file = detect_citation_style(content)

    return DocumentStructure(
        sections=sections,
        elements=elements,
        citations=citations,
        citation_style=style,
        bib_file=bib_file,
        packages=packages,
    )


def parse_document_file(filepath: str | Path) -> DocumentStructure:
    """Parse a LaTeX document from file path."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_document(content)


def parse_bib_file_path(filepath: str | Path) -> list[BibEntry]:
    """Parse a .bib file from file path."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_bib_file(content)


def get_section_by_name(
    structure: DocumentStructure,
    name: str,
) -> Optional[DocumentSection]:
    """Find a section by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for section in structure.sections:
        if name_lower in section.name.lower():
            return section
    return None


def get_section_content(
    content: str,
    section: DocumentSection,
) -> str:
    """Extract the content of a specific section."""
    lines = content.split("\n")
    return "\n".join(lines[section.line_start - 1:section.line_end])


def count_citations_per_section(
    structure: DocumentStructure,
    content: str,
) -> dict[str, int]:
    """Count how many citations appear in each section."""
    counts: dict[str, int] = {}

    for section in structure.sections:
        count = 0
        for citation in structure.citations:
            for loc in citation.locations:
                if section.line_start <= loc <= section.line_end:
                    count += 1
        counts[section.name] = count

    return counts
```

**Step 2: Integration test**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import parse_document, count_citations_per_section, get_section_by_name

full_doc = r"""
\documentclass{article}
\usepackage{amsmath,graphicx}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}

\begin{document}

\section{Introduction}
\label{sec:intro}
Deep learning has revolutionized AI \cite{lecun2015deep}.
Transformers \cite{vaswani2017attention} are particularly impactful.

\subsection{Contributions}
We contribute three things.

\section{Related Work}
\label{sec:related}
Prior work includes \cite{devlin2019bert,brown2020gpt3}.
Also see \citep{raffel2020t5} for a unified approach.

\begin{table}[htbp]
    \caption{Comparison}
    \label{tab:comparison}
    \begin{tabular}{lc}
        Model & Score \\
        Ours & 95.2 \\
    \end{tabular}
\end{table}

\section{Conclusion}
We showed good results.

\end{document}
"""

structure = parse_document(full_doc)
print(f"=== Document Structure ===")
print(f"Sections: {len(structure.sections)}")
print(f"Elements: {len(structure.elements)}")
print(f"Citations: {len(structure.citations)}")
print(f"Style: {structure.citation_style}")
print(f"Bib file: {structure.bib_file}")
print(f"Packages: {structure.packages}")

print(f"\n=== Sections ===")
for s in structure.sections:
    print(f"  L{s.line_start:3d}-{s.line_end:3d}: {s.command}{{{s.name}}}")

print(f"\n=== Citations per Section ===")
counts = count_citations_per_section(structure, full_doc)
for name, count in counts.items():
    print(f"  {name}: {count} citations")

print(f"\n=== Find Section ===")
intro = get_section_by_name(structure, "intro")
if intro:
    print(f"Found: {intro.name} at L{intro.line_start}-{intro.line_end}")
EOF
```

Expected: Complete structure analysis showing sections, elements, citations by section

**Step 3: Commit**

```bash
git add backend/services/latex_parser.py
git commit -m "feat(writing): Add main document parsing interface"
```

---

## Task 7: Add pylatexenc for AST Parsing

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/services/latex_parser.py`

**Step 1: Add pylatexenc dependency**

Add to `backend/requirements.txt`:
```
pylatexenc>=2.10
```

**Step 2: Install the dependency**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && pip install pylatexenc>=2.10
```

**Step 3: Add AST parsing for complex environments**

Add after the import section in `latex_parser.py`:

```python
from typing import Optional, Any

# Optional AST parsing (for complex cases)
try:
    from pylatexenc.latexwalker import LatexWalker, LatexEnvironmentNode, LatexMacroNode
    HAS_PYLATEXENC = True
except ImportError:
    HAS_PYLATEXENC = False
```

Add after `count_citations_per_section`:

```python
# =============================================================================
# AST-based Parsing (for complex cases)
# =============================================================================

def parse_environment_ast(content: str, env_name: str) -> list[dict[str, Any]]:
    """
    Parse a specific environment using AST for complex nested structures.

    Use this when regex fails on nested environments.
    Falls back to regex if pylatexenc not available.
    """
    if not HAS_PYLATEXENC:
        # Fallback: use regex-based parsing
        return _parse_environment_regex(content, env_name)

    results: list[dict[str, Any]] = []

    try:
        walker = LatexWalker(content)
        nodes, _, _ = walker.get_latex_nodes()

        for node in _walk_nodes(nodes):
            if isinstance(node, LatexEnvironmentNode):
                if node.environmentname == env_name:
                    results.append({
                        "type": env_name,
                        "content": node.latex_verbatim(),
                        "pos": node.pos,
                        "children": _extract_child_info(node),
                    })
    except Exception as e:
        # AST parsing failed, fall back to regex
        return _parse_environment_regex(content, env_name)

    return results


def _walk_nodes(nodes):
    """Recursively walk all nodes in the AST."""
    if nodes is None:
        return
    for node in nodes:
        yield node
        if hasattr(node, "nodelist") and node.nodelist:
            yield from _walk_nodes(node.nodelist)


def _extract_child_info(node) -> list[dict]:
    """Extract info about child nodes."""
    children = []
    if hasattr(node, "nodelist") and node.nodelist:
        for child in node.nodelist:
            if isinstance(child, LatexMacroNode):
                children.append({
                    "type": "macro",
                    "name": child.macroname,
                })
            elif isinstance(child, LatexEnvironmentNode):
                children.append({
                    "type": "environment",
                    "name": child.environmentname,
                })
    return children


def _parse_environment_regex(content: str, env_name: str) -> list[dict[str, Any]]:
    """Fallback regex-based environment parsing."""
    pattern = re.compile(
        rf"\\begin\{{{env_name}\}}(.*?)\\end\{{{env_name}\}}",
        re.DOTALL
    )
    results = []
    for match in pattern.finditer(content):
        results.append({
            "type": env_name,
            "content": match.group(0),
            "pos": match.start(),
            "children": [],
        })
    return results
```

**Step 4: Test AST parsing**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from services.latex_parser import parse_environment_ast, HAS_PYLATEXENC

print(f"pylatexenc available: {HAS_PYLATEXENC}")

test_nested = r"""
\begin{figure}[htbp]
    \centering
    \begin{tikzpicture}
        \node (a) {A};
        \node (b) [right of=a] {B};
        \draw[->] (a) -- (b);
    \end{tikzpicture}
    \caption{A TikZ diagram}
    \label{fig:tikz}
\end{figure}
"""

figures = parse_environment_ast(test_nested, "figure")
print(f"\nFound {len(figures)} figure(s)")
for f in figures:
    print(f"  Type: {f['type']}")
    print(f"  Children: {f['children']}")
    print(f"  Content length: {len(f['content'])} chars")
EOF
```

Expected: 1 figure found with tikzpicture as child environment

**Step 5: Commit**

```bash
git add backend/requirements.txt backend/services/latex_parser.py
git commit -m "feat(writing): Add pylatexenc AST parsing for complex environments"
```

---

## Task 8: BibTeX Generation Helper

**Files:**
- Create: `backend/agent/tools/citations.py`

**Step 1: Create citation helper module**

```python
"""
Citation Management Tools

Helpers for generating and managing BibTeX entries.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PaperMetadata:
    """Paper metadata from arXiv or Semantic Scholar."""
    title: str
    authors: list[str]
    year: int
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None


def generate_cite_key(paper: PaperMetadata) -> str:
    """
    Generate a citation key from paper metadata.

    Format: {first_author_lastname}{year}{first_significant_word}
    Example: vaswani2017attention
    """
    # Extract first author's last name
    if paper.authors:
        first_author = paper.authors[0]
        # Handle "Last, First" or "First Last" format
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts = first_author.split()
            last_name = parts[-1] if parts else "unknown"
    else:
        last_name = "unknown"

    # Clean the last name
    last_name = re.sub(r"[^a-zA-Z]", "", last_name).lower()

    # Extract first significant word from title (skip articles)
    skip_words = {"a", "an", "the", "on", "in", "of", "for", "to", "and", "with"}
    title_words = re.findall(r"[a-zA-Z]+", paper.title.lower())
    first_word = "paper"
    for word in title_words:
        if word not in skip_words and len(word) > 2:
            first_word = word
            break

    return f"{last_name}{paper.year}{first_word}"


def generate_bibtex(
    paper: PaperMetadata,
    cite_key: Optional[str] = None,
) -> str:
    """
    Generate BibTeX entry from paper metadata.

    Determines entry type based on available metadata:
    - @misc for arXiv papers
    - @article for papers with DOI and no venue
    - @inproceedings for papers with venue
    """
    if cite_key is None:
        cite_key = generate_cite_key(paper)

    # Determine entry type
    if paper.arxiv_id:
        entry_type = "misc"
    elif paper.venue:
        entry_type = "inproceedings"
    else:
        entry_type = "article"

    # Build fields
    fields = []

    # Title (escape special chars)
    title = paper.title.replace("&", r"\&")
    fields.append(f'    title = {{{title}}}')

    # Authors
    if paper.authors:
        authors_str = " and ".join(paper.authors[:10])  # Limit to 10 authors
        if len(paper.authors) > 10:
            authors_str += " and others"
        fields.append(f'    author = {{{authors_str}}}')

    # Year
    fields.append(f'    year = {{{paper.year}}}')

    # arXiv specific
    if paper.arxiv_id:
        fields.append(f'    eprint = {{{paper.arxiv_id}}}')
        fields.append('    archivePrefix = {arXiv}')
        fields.append('    primaryClass = {cs.CL}')  # Default, could be detected

    # Venue
    if paper.venue:
        if entry_type == "inproceedings":
            fields.append(f'    booktitle = {{{paper.venue}}}')
        else:
            fields.append(f'    journal = {{{paper.venue}}}')

    # DOI
    if paper.doi:
        fields.append(f'    doi = {{{paper.doi}}}')

    # URL
    if paper.url:
        fields.append(f'    url = {{{paper.url}}}')

    # Build entry
    fields_str = ",\n".join(fields)
    return f"@{entry_type}{{{cite_key},\n{fields_str}\n}}"


def format_citation_command(
    cite_key: str,
    style: str = "cite",
    prenote: Optional[str] = None,
    postnote: Optional[str] = None,
) -> str:
    """
    Format a citation command.

    Examples:
        format_citation_command("vaswani2017") -> r"\cite{vaswani2017}"
        format_citation_command("vaswani2017", "citep", postnote="p. 5") -> r"\citep[p. 5]{vaswani2017}"
    """
    if prenote and postnote:
        return f"\\{style}[{prenote}][{postnote}]{{{cite_key}}}"
    elif postnote:
        return f"\\{style}[{postnote}]{{{cite_key}}}"
    elif prenote:
        return f"\\{style}[{prenote}][]{{{cite_key}}}"
    else:
        return f"\\{style}{{{cite_key}}}"
```

**Step 2: Test citation generation**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
from agent.tools.citations import PaperMetadata, generate_cite_key, generate_bibtex, format_citation_command

# Test with arXiv paper
paper = PaperMetadata(
    title="Attention Is All You Need",
    authors=["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"],
    year=2017,
    arxiv_id="1706.03762",
)

key = generate_cite_key(paper)
print(f"Generated key: {key}")

bibtex = generate_bibtex(paper)
print(f"\nBibTeX entry:\n{bibtex}")

# Test citation formatting
print(f"\nCitation commands:")
print(f"  cite: {format_citation_command(key)}")
print(f"  citep: {format_citation_command(key, 'citep')}")
print(f"  with note: {format_citation_command(key, 'citep', postnote='p. 5')}")
EOF
```

Expected: Well-formatted BibTeX entry with arXiv fields

**Step 3: Commit**

```bash
git add backend/agent/tools/citations.py
git commit -m "feat(writing): Add BibTeX generation helper"
```

---

## Task 9: Add analyze_structure Tool to Main Agent

**Files:**
- Modify: `backend/agent/pydantic_agent.py`

**Step 1: Add import for latex_parser**

Find the imports section and add:

```python
from services.latex_parser import (
    parse_document,
    parse_bib_file_path,
    build_section_tree,
    count_citations_per_section,
    find_unused_citations,
    find_missing_citations,
    DocumentStructure,
)
```

**Step 2: Add analyze_structure tool**

Add after the existing file tools (after `find_files`):

```python
# =============================================================================
# Document Analysis Tools
# =============================================================================

@aura_agent.tool
async def analyze_structure(
    ctx: RunContext[AuraDeps],
    filepath: str = "main.tex",
) -> str:
    """
    Analyze the structure of a LaTeX document.

    Returns section hierarchy, figures/tables, citation statistics,
    and any structural issues detected.

    Args:
        filepath: Path to the .tex file to analyze (default: main.tex)

    Returns:
        Formatted structure analysis with sections, elements, and issues
    """
    from pathlib import Path

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        structure = parse_document(content)
        tree = build_section_tree(structure.sections)
        cite_counts = count_citations_per_section(structure, content)

        # Format output
        lines = [f"Document Structure: {filepath}", ""]

        # Section hierarchy
        lines.append("SECTIONS:")
        def format_tree(sections, prefix=""):
            result = []
            for i, s in enumerate(sections):
                is_last = i == len(sections) - 1
                current_prefix = "└── " if is_last else "├── "
                cite_count = cite_counts.get(s.name, 0)
                label_info = f" [{s.label}]" if s.label else ""
                result.append(f"{prefix}{current_prefix}{s.name} (L{s.line_start}-{s.line_end}) [{cite_count} citations]{label_info}")
                if s.children:
                    child_prefix = prefix + ("    " if is_last else "│   ")
                    result.extend(format_tree(s.children, child_prefix))
            return result

        lines.extend(format_tree(tree))
        lines.append("")

        # Elements
        lines.append("ELEMENTS:")
        if structure.elements:
            for e in structure.elements:
                label_status = "✓ labeled" if e.label else "⚠ no label"
                caption_preview = e.caption[:40] + "..." if e.caption and len(e.caption) > 40 else (e.caption or "no caption")
                lines.append(f"  - {e.type}: \"{caption_preview}\" (L{e.line_start}) {label_status}")
        else:
            lines.append("  (none found)")
        lines.append("")

        # Citation info
        lines.append(f"CITATIONS: {len(structure.citations)} unique keys")
        lines.append(f"STYLE: {structure.citation_style}")
        lines.append(f"BIB FILE: {structure.bib_file or 'not detected'}")
        lines.append(f"PACKAGES: {', '.join(structure.packages[:10])}")
        lines.append("")

        # Issues
        issues = []

        # Check for sections without citations in expected places
        for s in structure.sections:
            name_lower = s.name.lower()
            if "related" in name_lower or "background" in name_lower:
                if cite_counts.get(s.name, 0) < 3:
                    issues.append(f"Section '{s.name}' has few citations ({cite_counts.get(s.name, 0)}) - expected more for this section type")

        # Check for unlabeled figures/tables
        unlabeled = [e for e in structure.elements if not e.label]
        if unlabeled:
            issues.append(f"{len(unlabeled)} element(s) missing \\label{{}}")

        # Check bib file if available
        if structure.bib_file:
            bib_path = Path(project_path) / structure.bib_file
            if bib_path.exists():
                bib_entries = parse_bib_file_path(bib_path)
                unused = find_unused_citations(structure.citations, bib_entries)
                missing = find_missing_citations(structure.citations, bib_entries)
                if unused:
                    issues.append(f"{len(unused)} unused entries in bibliography")
                if missing:
                    issues.append(f"{len(missing)} citations not in bibliography: {', '.join(missing[:5])}")

        if issues:
            lines.append("ISSUES:")
            for issue in issues:
                lines.append(f"  ⚠ {issue}")
        else:
            lines.append("ISSUES: None detected ✓")

        return "\n".join(lines)

    except Exception as e:
        return f"Error analyzing document: {e}"
```

**Step 3: Test the tool**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
# Create a test project
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    # Write test document
    (Path(tmpdir) / "main.tex").write_text(r"""
\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}

\section{Introduction}
\label{sec:intro}
Deep learning is great \cite{lecun2015}.

\section{Related Work}
Prior work \cite{smith2020}.

\begin{figure}
    \caption{Architecture}
    \label{fig:arch}
\end{figure}

\begin{table}
    \caption{Results}
\end{table}

\section{Conclusion}
We did it.
\end{document}
""")

    # Write test bib
    (Path(tmpdir) / "refs.bib").write_text("""
@article{lecun2015,
    title={Deep Learning},
    author={LeCun, Yann},
    year={2015}
}
@article{unused2020,
    title={Unused Paper},
    author={Nobody},
    year={2020}
}
""")

    # Test the tool
    import asyncio
    from agent.pydantic_agent import analyze_structure, AuraDeps
    from pydantic_ai import RunContext
    from unittest.mock import MagicMock

    # Create mock context
    ctx = MagicMock()
    ctx.deps = AuraDeps(project_path=tmpdir)

    result = asyncio.run(analyze_structure(ctx, "main.tex"))
    print(result)
EOF
```

Expected: Complete analysis showing sections, elements, citations, and issues (unlabeled table, unused bib entry, missing citation)

**Step 4: Commit**

```bash
git add backend/agent/pydantic_agent.py
git commit -m "feat(writing): Add analyze_structure tool to main agent"
```

---

## Task 10: Add add_citation Tool to Main Agent

**Files:**
- Modify: `backend/agent/pydantic_agent.py`

**Step 1: Add add_citation tool**

Add after `analyze_structure`:

```python
@aura_agent.tool
async def add_citation(
    ctx: RunContext[AuraDeps],
    paper_id: str,
    cite_key: Optional[str] = None,
    insert_after_line: Optional[int] = None,
    cite_style: str = "cite",
) -> str:
    """
    Add a citation to the document.

    Fetches paper metadata, generates BibTeX entry, adds to .bib file,
    and optionally inserts the citation command in the document.

    Args:
        paper_id: Paper identifier - can be:
                  - arXiv ID (e.g., "2301.07041" or "arxiv:2301.07041")
                  - Semantic Scholar ID (e.g., "s2:abc123")
                  - Search query (will search and use first result)
        cite_key: Optional custom citation key (auto-generated if not provided)
        insert_after_line: Line number after which to insert \\cite{} command
        cite_style: Citation style - "cite", "citep", "citet", "autocite", etc.

    Returns:
        Confirmation with the cite key and BibTeX entry
    """
    from pathlib import Path
    import httpx
    from agent.tools.citations import PaperMetadata, generate_bibtex, generate_cite_key, format_citation_command

    project_path = ctx.deps.project_path

    # Determine paper source and fetch metadata
    paper = None

    if paper_id.startswith("arxiv:") or paper_id.replace(".", "").replace("v", "").isdigit():
        # arXiv paper
        arxiv_id = paper_id.replace("arxiv:", "").strip()
        paper = await _fetch_arxiv_metadata(arxiv_id)
    elif paper_id.startswith("s2:"):
        # Semantic Scholar ID
        s2_id = paper_id.replace("s2:", "").strip()
        paper = await _fetch_s2_metadata(s2_id)
    else:
        # Treat as search query - search arXiv
        paper = await _search_arxiv_for_paper(paper_id)

    if not paper:
        return f"Error: Could not find paper: {paper_id}"

    # Generate cite key if not provided
    if cite_key is None:
        cite_key = generate_cite_key(paper)

    # Generate BibTeX entry
    bibtex = generate_bibtex(paper, cite_key)

    # Find and update .bib file
    main_tex = Path(project_path) / "main.tex"
    if main_tex.exists():
        content = main_tex.read_text()
        structure = parse_document(content)
        bib_file = structure.bib_file or "refs.bib"
    else:
        bib_file = "refs.bib"

    bib_path = Path(project_path) / bib_file

    # Check if entry already exists
    if bib_path.exists():
        existing_content = bib_path.read_text()
        if cite_key in existing_content:
            return f"Citation key '{cite_key}' already exists in {bib_file}. Use a different cite_key."
        # Append entry
        with open(bib_path, "a") as f:
            f.write("\n\n" + bibtex)
    else:
        # Create new .bib file
        bib_path.write_text(bibtex + "\n")

    result = f"Added citation to {bib_file}:\n\n{bibtex}\n\nUse: {format_citation_command(cite_key, cite_style)}"

    # Insert citation in document if requested
    if insert_after_line is not None and main_tex.exists():
        content = main_tex.read_text()
        lines = content.split("\n")
        if 0 < insert_after_line <= len(lines):
            cite_cmd = format_citation_command(cite_key, cite_style)
            lines[insert_after_line - 1] += f" {cite_cmd}"
            main_tex.write_text("\n".join(lines))
            result += f"\n\nInserted {cite_cmd} after line {insert_after_line}"

    return result


async def _fetch_arxiv_metadata(arxiv_id: str) -> Optional[PaperMetadata]:
    """Fetch paper metadata from arXiv."""
    import httpx

    # Clean ID
    arxiv_id = arxiv_id.split("v")[0]  # Remove version

    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

            # Parse Atom XML (simple regex extraction)
            import re
            content = response.text

            title_match = re.search(r"<title>([^<]+)</title>", content)
            if not title_match or "Error" in title_match.group(1):
                return None

            title = title_match.group(1).strip().replace("\n", " ")

            # Extract authors
            authors = re.findall(r"<name>([^<]+)</name>", content)

            # Extract year from published date
            pub_match = re.search(r"<published>(\d{4})", content)
            year = int(pub_match.group(1)) if pub_match else 2024

            # Extract abstract
            abs_match = re.search(r"<summary>([^<]+)</summary>", content, re.DOTALL)
            abstract = abs_match.group(1).strip() if abs_match else None

            return PaperMetadata(
                title=title,
                authors=authors[:10],
                year=year,
                arxiv_id=arxiv_id,
                abstract=abstract,
                url=f"https://arxiv.org/abs/{arxiv_id}",
            )
    except Exception:
        return None


async def _fetch_s2_metadata(s2_id: str) -> Optional[PaperMetadata]:
    """Fetch paper metadata from Semantic Scholar."""
    import httpx

    url = f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}"
    params = {"fields": "title,authors,year,abstract,externalIds,venue"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

            return PaperMetadata(
                title=data.get("title", "Unknown"),
                authors=[a.get("name", "") for a in data.get("authors", [])[:10]],
                year=data.get("year", 2024),
                arxiv_id=data.get("externalIds", {}).get("ArXiv"),
                doi=data.get("externalIds", {}).get("DOI"),
                venue=data.get("venue"),
                abstract=data.get("abstract"),
            )
    except Exception:
        return None


async def _search_arxiv_for_paper(query: str) -> Optional[PaperMetadata]:
    """Search arXiv and return first result."""
    import httpx
    import urllib.parse

    encoded_query = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results=1"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

            import re
            content = response.text

            # Extract arXiv ID from first result
            id_match = re.search(r"<id>http://arxiv.org/abs/([^<]+)</id>", content)
            if not id_match:
                return None

            arxiv_id = id_match.group(1)
            return await _fetch_arxiv_metadata(arxiv_id)
    except Exception:
        return None
```

**Step 2: Test add_citation tool**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
import tempfile
from pathlib import Path

async def test():
    from agent.pydantic_agent import add_citation, AuraDeps
    from unittest.mock import MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test document
        (Path(tmpdir) / "main.tex").write_text(r"""
\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}
\section{Introduction}
Transformers are important.
\end{document}
""")

        # Create mock context
        ctx = MagicMock()
        ctx.deps = AuraDeps(project_path=tmpdir)

        # Test adding arXiv paper
        result = await add_citation(ctx, "1706.03762")  # Attention Is All You Need
        print(result)

        # Check bib file was created
        bib_content = (Path(tmpdir) / "refs.bib").read_text()
        print(f"\n=== refs.bib ===\n{bib_content}")

asyncio.run(test())
EOF
```

Expected: BibTeX entry for "Attention Is All You Need" added to refs.bib

**Step 3: Commit**

```bash
git add backend/agent/pydantic_agent.py
git commit -m "feat(writing): Add add_citation tool to main agent"
```

---

## Task 11: Create WritingAgent Subagent Scaffold

**Files:**
- Create: `backend/agent/subagents/writing.py`
- Modify: `backend/agent/subagents/__init__.py`

**Step 1: Create WritingAgent**

```python
"""
WritingAgent - Handles complex writing operations.

Delegated from main agent for:
- Style analysis and application
- Consistency checking
- Document refactoring
- Bibliography management
"""

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic_ai import Agent, RunContext

from agent.subagents.base import Subagent, SubagentConfig, register_subagent
from agent.providers.colorist import get_default_model, get_haiku_model


WRITING_SYSTEM_PROMPT = """You are an expert academic writing assistant specialized in LaTeX documents.

Your capabilities:
- Analyze writing style and suggest improvements
- Check for consistency in terminology, notation, and tense
- Manage bibliography (clean unused, deduplicate)
- Suggest claims that need citations
- Refactor document structure

When analyzing text:
1. Be specific with line numbers
2. Provide concrete before/after examples
3. Prioritize issues by impact

When making changes:
1. Preserve existing citations and references
2. Maintain the author's voice
3. Follow academic writing conventions
"""


@dataclass
class WritingDeps:
    """Dependencies for WritingAgent."""
    project_path: str
    http_client: httpx.AsyncClient


@register_subagent("writing")
class WritingAgent(Subagent[WritingDeps]):
    """Agent for complex writing operations."""

    def __init__(self):
        config = SubagentConfig(
            name="writing",
            description="Handles style analysis, consistency checking, and document refactoring",
            max_iterations=10,
            timeout=120.0,
            use_haiku=True,  # Use cheaper model for analysis
        )
        super().__init__(config)
        self._http_client: httpx.AsyncClient | None = None

    @property
    def system_prompt(self) -> str:
        return WRITING_SYSTEM_PROMPT

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    def _create_deps(self, context: dict[str, Any]) -> WritingDeps:
        return WritingDeps(
            project_path=context.get("project_path", ""),
            http_client=self._get_http_client(),
        )

    def _create_agent(self) -> Agent[WritingDeps, str]:
        agent = Agent(
            model=self._get_model(),
            system_prompt=self.system_prompt,
            deps_type=WritingDeps,
            retries=2,
        )

        self._register_tools(agent)
        return agent

    def _register_tools(self, agent: Agent):
        """Register writing-specific tools."""

        @agent.tool
        async def read_document(
            ctx: RunContext[WritingDeps],
            filepath: str = "main.tex",
        ) -> str:
            """
            Read a LaTeX document for analysis.

            Args:
                filepath: Path to the file relative to project

            Returns:
                File contents with line numbers
            """
            from pathlib import Path

            full_path = Path(ctx.deps.project_path) / filepath
            if not full_path.exists():
                return f"Error: File not found: {filepath}"

            content = full_path.read_text()
            lines = content.split("\n")
            numbered = [f"{i+1:4}│ {line}" for i, line in enumerate(lines)]
            return "\n".join(numbered)

        @agent.tool
        async def analyze_document_structure(
            ctx: RunContext[WritingDeps],
            filepath: str = "main.tex",
        ) -> str:
            """
            Get document structure for navigation.

            Args:
                filepath: Path to the .tex file

            Returns:
                Section hierarchy with line numbers
            """
            from pathlib import Path
            from services.latex_parser import parse_document, build_section_tree

            full_path = Path(ctx.deps.project_path) / filepath
            if not full_path.exists():
                return f"Error: File not found: {filepath}"

            content = full_path.read_text()
            structure = parse_document(content)
            tree = build_section_tree(structure.sections)

            lines = []
            for s in structure.sections:
                indent = "  " * s.level
                lines.append(f"{indent}{s.name} (L{s.line_start}-{s.line_end})")

            return "\n".join(lines)

        @agent.tool
        async def check_consistency(
            ctx: RunContext[WritingDeps],
            filepath: str = "main.tex",
        ) -> str:
            """
            Check for consistency issues in the document.

            Checks:
            - Terminology variations (dataset vs data set)
            - Notation inconsistencies
            - Tense mixing
            - Acronym usage

            Args:
                filepath: Path to the .tex file

            Returns:
                List of consistency issues with line numbers
            """
            from pathlib import Path
            import re

            full_path = Path(ctx.deps.project_path) / filepath
            if not full_path.exists():
                return f"Error: File not found: {filepath}"

            content = full_path.read_text()
            lines = content.split("\n")
            issues = []

            # Check common terminology variations
            term_patterns = [
                (r"\bdataset\b", r"\bdata set\b", "dataset/data set"),
                (r"\bdeep learning\b", r"\bdeeplearning\b", "deep learning"),
                (r"\bself-attention\b", r"\bself attention\b", "self-attention/self attention"),
                (r"\bmulti-head\b", r"\bmultihead\b", "multi-head/multihead"),
            ]

            for p1, p2, name in term_patterns:
                locs1 = [i+1 for i, line in enumerate(lines) if re.search(p1, line, re.I)]
                locs2 = [i+1 for i, line in enumerate(lines) if re.search(p2, line, re.I)]
                if locs1 and locs2:
                    issues.append(f"TERMINOLOGY: '{name}' used inconsistently - variant 1 at L{locs1[:3]}, variant 2 at L{locs2[:3]}")

            # Check for undefined acronyms (simple heuristic)
            acronyms = re.findall(r"\b([A-Z]{2,})\b", content)
            acronym_counts = {}
            for acr in acronyms:
                acronym_counts[acr] = acronym_counts.get(acr, 0) + 1

            for acr, count in acronym_counts.items():
                if count >= 3:
                    # Check if it's defined somewhere
                    definition_pattern = rf"\([^)]*{acr}[^)]*\)|{acr}\s*\([^)]+\)"
                    if not re.search(definition_pattern, content):
                        first_use = next(i+1 for i, line in enumerate(lines) if acr in line)
                        issues.append(f"ACRONYM: '{acr}' used {count} times but never defined (first use: L{first_use})")

            if not issues:
                return "No consistency issues found ✓"

            return "Consistency issues found:\n\n" + "\n".join(f"• {issue}" for issue in issues)

        @agent.tool
        async def clean_bibliography(
            ctx: RunContext[WritingDeps],
            tex_file: str = "main.tex",
        ) -> str:
            """
            Find and remove unused bibliography entries.

            Args:
                tex_file: Main .tex file to check citations in

            Returns:
                Report of unused entries (does not modify files - use edit_file for that)
            """
            from pathlib import Path
            from services.latex_parser import (
                parse_document, parse_bib_file_path,
                find_unused_citations, find_missing_citations
            )

            tex_path = Path(ctx.deps.project_path) / tex_file
            if not tex_path.exists():
                return f"Error: File not found: {tex_file}"

            content = tex_path.read_text()
            structure = parse_document(content)

            if not structure.bib_file:
                return "No bibliography file detected in document"

            bib_path = Path(ctx.deps.project_path) / structure.bib_file
            if not bib_path.exists():
                return f"Bibliography file not found: {structure.bib_file}"

            bib_entries = parse_bib_file_path(bib_path)
            unused = find_unused_citations(structure.citations, bib_entries)
            missing = find_missing_citations(structure.citations, bib_entries)

            lines = [f"Bibliography analysis for {structure.bib_file}:", ""]
            lines.append(f"Total entries: {len(bib_entries)}")
            lines.append(f"Cited in document: {len(structure.citations)}")
            lines.append("")

            if unused:
                lines.append(f"UNUSED ENTRIES ({len(unused)}):")
                for e in unused:
                    title = e.fields.get("title", "No title")[:50]
                    lines.append(f"  • {e.key}: {title}")
                lines.append("")
                lines.append("To remove these, edit the .bib file and delete the unused entries.")
            else:
                lines.append("No unused entries ✓")

            if missing:
                lines.append("")
                lines.append(f"MISSING FROM BIB ({len(missing)}):")
                for key in missing:
                    lines.append(f"  • {key}")

            return "\n".join(lines)

        @agent.tool
        async def suggest_citations(
            ctx: RunContext[WritingDeps],
            filepath: str = "main.tex",
        ) -> str:
            """
            Find claims that might need citations.

            Looks for patterns like:
            - "Studies show that..."
            - "It has been demonstrated..."
            - "Research indicates..."
            - Quantitative claims

            Args:
                filepath: Path to the .tex file

            Returns:
                List of claims that might need citations with line numbers
            """
            from pathlib import Path
            import re

            full_path = Path(ctx.deps.project_path) / filepath
            if not full_path.exists():
                return f"Error: File not found: {filepath}"

            content = full_path.read_text()
            lines = content.split("\n")
            suggestions = []

            # Patterns that suggest a claim needs citation
            claim_patterns = [
                (r"studies (show|have shown|indicate|suggest)", "Studies claim"),
                (r"research (shows|has shown|indicates|suggests)", "Research claim"),
                (r"it (has been|is|was) (shown|demonstrated|proven)", "Passive claim"),
                (r"according to (recent )?(research|studies|work)", "Attribution needed"),
                (r"(\d+\.?\d*)\s*%", "Percentage claim"),
                (r"state-of-the-art", "SOTA claim"),
                (r"(recent|previous|prior) work", "Prior work reference"),
            ]

            for i, line in enumerate(lines, start=1):
                # Skip if line already has a citation
                if r"\cite" in line:
                    continue

                # Skip comments and commands
                if line.strip().startswith("%") or line.strip().startswith("\\"):
                    continue

                for pattern, claim_type in claim_patterns:
                    if re.search(pattern, line, re.I):
                        snippet = line.strip()[:60] + "..." if len(line.strip()) > 60 else line.strip()
                        suggestions.append(f"L{i} [{claim_type}]: \"{snippet}\"")
                        break

            if not suggestions:
                return "No claims found that obviously need citations ✓"

            return f"Claims that may need citations ({len(suggestions)}):\n\n" + "\n".join(suggestions)
```

**Step 2: Register in __init__.py**

Add to `backend/agent/subagents/__init__.py`:

```python
from agent.subagents.writing import WritingAgent
```

**Step 3: Test WritingAgent**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
import tempfile
from pathlib import Path

async def test():
    from agent.subagents.writing import WritingAgent

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test document
        (Path(tmpdir) / "main.tex").write_text(r"""
\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}

\section{Introduction}
Studies show that deep learning is important.
Recent research indicates that transformers achieve 95% accuracy.
The NLP field has seen major advances. NLP is now everywhere.

\section{Methods}
We use a dataset for training.
Our data set contains 1M examples.

\end{document}
""")

        (Path(tmpdir) / "refs.bib").write_text("""
@article{cited2020,
    title={Cited Paper},
    author={Author},
    year={2020}
}
@article{unused2020,
    title={Unused Paper},
    author={Nobody},
    year={2020}
}
""")

        agent = WritingAgent()

        # Test consistency check
        result = await agent.run(
            task="Check the document for consistency issues",
            context={"project_path": tmpdir},
        )
        print("=== Consistency Check ===")
        print(result.output)

        # Test citation suggestions
        result = await agent.run(
            task="Find claims that need citations",
            context={"project_path": tmpdir},
        )
        print("\n=== Citation Suggestions ===")
        print(result.output)

asyncio.run(test())
EOF
```

Expected: Consistency issues found (dataset/data set, NLP undefined) and citation suggestions

**Step 4: Commit**

```bash
git add backend/agent/subagents/writing.py backend/agent/subagents/__init__.py
git commit -m "feat(writing): Add WritingAgent subagent with consistency and citation tools"
```

---

## Task 12: Content Generation Tools - create_table

**Files:**
- Modify: `backend/agent/pydantic_agent.py`

**Step 1: Add create_table tool**

Add after `add_citation`:

```python
@aura_agent.tool
async def create_table(
    ctx: RunContext[AuraDeps],
    data: str,
    caption: str,
    label: str = "",
    style: str = "booktabs",
) -> str:
    """
    Generate a LaTeX table from data.

    Args:
        data: Table data in CSV or markdown format:
              CSV: "Header1,Header2\\nValue1,Value2"
              Markdown: "| H1 | H2 |\\n| v1 | v2 |"
        caption: Table caption
        label: Label for referencing (e.g., "results" -> \\label{tab:results})
        style: Table style - "booktabs" (professional) or "basic"

    Returns:
        Complete LaTeX table code ready to paste
    """
    import re

    # Parse data
    lines = data.strip().split("\n")
    rows = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("|--") or line.startswith("|-"):
            continue

        # Handle markdown format
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
        # Handle CSV format
        else:
            cells = [c.strip() for c in line.split(",")]

        if cells:
            rows.append(cells)

    if not rows:
        return "Error: Could not parse table data"

    # Determine column count and alignment
    num_cols = max(len(row) for row in rows)

    # Detect numeric columns for right-alignment
    alignments = []
    for col in range(num_cols):
        is_numeric = True
        for row in rows[1:]:  # Skip header
            if col < len(row):
                val = row[col].strip()
                # Check if it's a number (including decimals, percentages)
                if not re.match(r"^[\d.,]+%?$", val) and val:
                    is_numeric = False
                    break
        alignments.append("r" if is_numeric else "l")

    # First column usually left-aligned
    if alignments:
        alignments[0] = "l"

    alignment_str = "".join(alignments)

    # Build table
    if style == "booktabs":
        table_lines = [
            r"\begin{table}[htbp]",
            r"    \centering",
            f"    \\caption{{{caption}}}",
        ]
        if label:
            table_lines.append(f"    \\label{{tab:{label}}}")
        table_lines.extend([
            f"    \\begin{{tabular}}{{{alignment_str}}}",
            r"        \toprule",
        ])

        # Header row
        if rows:
            header = " & ".join(f"\\textbf{{{cell}}}" for cell in rows[0])
            table_lines.append(f"        {header} \\\\")
            table_lines.append(r"        \midrule")

        # Data rows
        for row in rows[1:]:
            # Pad row if needed
            while len(row) < num_cols:
                row.append("")
            row_str = " & ".join(row)
            table_lines.append(f"        {row_str} \\\\")

        table_lines.extend([
            r"        \bottomrule",
            r"    \end{tabular}",
            r"\end{table}",
        ])
    else:
        # Basic style
        table_lines = [
            r"\begin{table}[htbp]",
            r"    \centering",
            f"    \\caption{{{caption}}}",
        ]
        if label:
            table_lines.append(f"    \\label{{tab:{label}}}")
        table_lines.extend([
            f"    \\begin{{tabular}}{{|{alignment_str}|}}",
            r"        \hline",
        ])

        for i, row in enumerate(rows):
            while len(row) < num_cols:
                row.append("")
            row_str = " & ".join(row)
            table_lines.append(f"        {row_str} \\\\")
            table_lines.append(r"        \hline")

        table_lines.extend([
            r"    \end{tabular}",
            r"\end{table}",
        ])

    return "\n".join(table_lines)
```

**Step 2: Test create_table**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
from agent.pydantic_agent import create_table, AuraDeps
from unittest.mock import MagicMock

async def test():
    ctx = MagicMock()
    ctx.deps = AuraDeps(project_path="/tmp")

    # Test CSV data
    csv_data = """Model,Accuracy,F1 Score
BERT,85.2,84.1
GPT-2,79.3,78.5
T5,89.7,88.9"""

    result = await create_table(
        ctx,
        data=csv_data,
        caption="Model comparison on benchmark dataset",
        label="model-comparison",
    )
    print("=== CSV Table ===")
    print(result)

    # Test markdown data
    md_data = """| Method | Time (s) | Memory (GB) |
| Baseline | 1.2 | 4.5 |
| Ours | 0.8 | 3.2 |"""

    result = await create_table(
        ctx,
        data=md_data,
        caption="Resource comparison",
        label="resources",
    )
    print("\n=== Markdown Table ===")
    print(result)

asyncio.run(test())
EOF
```

Expected: Well-formatted booktabs tables with proper alignment

**Step 3: Commit**

```bash
git add backend/agent/pydantic_agent.py
git commit -m "feat(writing): Add create_table tool with booktabs support"
```

---

## Task 13: Content Generation Tools - create_figure

**Files:**
- Modify: `backend/agent/pydantic_agent.py`

**Step 1: Add create_figure tool**

Add after `create_table`:

```python
@aura_agent.tool
async def create_figure(
    ctx: RunContext[AuraDeps],
    description: str,
    figure_type: str = "tikz",
    caption: str = "",
    label: str = "",
    data: str = "",
) -> str:
    """
    Generate a LaTeX figure from description.

    Args:
        description: What the figure should show (e.g., "flowchart of training pipeline")
        figure_type: Type of figure:
                    - "tikz": General diagrams
                    - "pgfplots-bar": Bar chart
                    - "pgfplots-line": Line plot
                    - "pgfplots-scatter": Scatter plot
        caption: Figure caption
        label: Label for referencing (e.g., "architecture" -> \\label{fig:architecture})
        data: For plots, provide data as CSV: "x,y1,y2\\n1,2,3\\n2,4,5"

    Returns:
        Complete LaTeX figure code
    """
    # For complex figure generation, we provide templates
    # The LLM will customize based on description

    if figure_type == "tikz":
        # Generic TikZ template
        figure_code = r"""
\begin{figure}[htbp]
    \centering
    \begin{tikzpicture}[
        node distance=2cm,
        box/.style={rectangle, draw, rounded corners, minimum width=2.5cm, minimum height=1cm, align=center},
        arrow/.style={->, >=stealth, thick}
    ]
        % Nodes - customize based on your needs
        \node[box] (input) {Input};
        \node[box, right of=input] (process) {Process};
        \node[box, right of=process] (output) {Output};

        % Arrows
        \draw[arrow] (input) -- (process);
        \draw[arrow] (process) -- (output);
    \end{tikzpicture}
    \caption{CAPTION_PLACEHOLDER}
    \label{fig:LABEL_PLACEHOLDER}
\end{figure}
"""
    elif figure_type == "pgfplots-bar":
        # Parse data for bar chart
        if data:
            lines = data.strip().split("\n")
            headers = lines[0].split(",") if lines else ["Category", "Value"]

            coords = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 2:
                    coords.append(f"({parts[0]}, {parts[1]})")
            coords_str = " ".join(coords)
        else:
            coords_str = "(A, 10) (B, 20) (C, 15)"

        figure_code = rf"""
\begin{{figure}}[htbp]
    \centering
    \begin{{tikzpicture}}
        \begin{{axis}}[
            ybar,
            xlabel={{{headers[0] if data else 'Category'}}},
            ylabel={{{headers[1] if data and len(headers) > 1 else 'Value'}}},
            symbolic x coords={{A, B, C}},
            xtick=data,
            nodes near coords,
            width=0.8\textwidth,
            height=6cm,
        ]
            \addplot coordinates {{{coords_str}}};
        \end{{axis}}
    \end{{tikzpicture}}
    \caption{{CAPTION_PLACEHOLDER}}
    \label{{fig:LABEL_PLACEHOLDER}}
\end{{figure}}
"""
    elif figure_type == "pgfplots-line":
        # Parse data for line plot
        if data:
            lines = data.strip().split("\n")
            headers = lines[0].split(",") if lines else ["x", "y"]

            coords = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 2:
                    coords.append(f"({parts[0]}, {parts[1]})")
            coords_str = " ".join(coords)
        else:
            coords_str = "(0, 0) (1, 2) (2, 4) (3, 3) (4, 5)"

        figure_code = rf"""
\begin{{figure}}[htbp]
    \centering
    \begin{{tikzpicture}}
        \begin{{axis}}[
            xlabel={{{headers[0] if data else 'x'}}},
            ylabel={{{headers[1] if data and len(headers) > 1 else 'y'}}},
            legend pos=north west,
            grid=major,
            width=0.8\textwidth,
            height=6cm,
        ]
            \addplot[color=blue, mark=*] coordinates {{{coords_str}}};
            \legend{{Data}}
        \end{{axis}}
    \end{{tikzpicture}}
    \caption{{CAPTION_PLACEHOLDER}}
    \label{{fig:LABEL_PLACEHOLDER}}
\end{{figure}}
"""
    elif figure_type == "pgfplots-scatter":
        coords_str = "(1, 2) (2, 3) (3, 2.5) (4, 4) (5, 4.5)"
        if data:
            lines = data.strip().split("\n")
            coords = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 2:
                    coords.append(f"({parts[0]}, {parts[1]})")
            if coords:
                coords_str = " ".join(coords)

        figure_code = rf"""
\begin{{figure}}[htbp]
    \centering
    \begin{{tikzpicture}}
        \begin{{axis}}[
            xlabel={{X}},
            ylabel={{Y}},
            only marks,
            width=0.8\textwidth,
            height=6cm,
        ]
            \addplot[color=blue, mark=o] coordinates {{{coords_str}}};
        \end{{axis}}
    \end{{tikzpicture}}
    \caption{{CAPTION_PLACEHOLDER}}
    \label{{fig:LABEL_PLACEHOLDER}}
\end{{figure}}
"""
    else:
        return f"Error: Unknown figure type '{figure_type}'. Use: tikz, pgfplots-bar, pgfplots-line, pgfplots-scatter"

    # Replace placeholders
    if caption:
        figure_code = figure_code.replace("CAPTION_PLACEHOLDER", caption)
    else:
        figure_code = figure_code.replace("CAPTION_PLACEHOLDER", description[:50])

    if label:
        figure_code = figure_code.replace("LABEL_PLACEHOLDER", label)
    else:
        # Generate label from description
        import re
        label_text = re.sub(r"[^a-z0-9]+", "-", description.lower())[:20]
        figure_code = figure_code.replace("LABEL_PLACEHOLDER", label_text)

    return figure_code.strip()
```

**Step 2: Test create_figure**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
from agent.pydantic_agent import create_figure, AuraDeps
from unittest.mock import MagicMock

async def test():
    ctx = MagicMock()
    ctx.deps = AuraDeps(project_path="/tmp")

    # Test TikZ diagram
    result = await create_figure(
        ctx,
        description="Training pipeline flowchart",
        figure_type="tikz",
        caption="Overview of our training pipeline",
        label="pipeline",
    )
    print("=== TikZ Diagram ===")
    print(result)

    # Test bar chart
    data = """Model,Accuracy
BERT,85.2
GPT,79.3
T5,89.7"""

    result = await create_figure(
        ctx,
        description="Model accuracy comparison",
        figure_type="pgfplots-bar",
        caption="Accuracy comparison across models",
        label="accuracy-comparison",
        data=data,
    )
    print("\n=== Bar Chart ===")
    print(result)

asyncio.run(test())
EOF
```

Expected: Valid LaTeX figure code for both TikZ and pgfplots

**Step 3: Commit**

```bash
git add backend/agent/pydantic_agent.py
git commit -m "feat(writing): Add create_figure tool with TikZ and pgfplots support"
```

---

## Task 14: Content Generation Tools - create_algorithm

**Files:**
- Modify: `backend/agent/pydantic_agent.py`

**Step 1: Add create_algorithm tool**

Add after `create_figure`:

```python
@aura_agent.tool
async def create_algorithm(
    ctx: RunContext[AuraDeps],
    name: str,
    inputs: str,
    outputs: str,
    steps: str,
    caption: str = "",
    label: str = "",
) -> str:
    """
    Generate an algorithm/pseudocode block.

    Args:
        name: Algorithm name
        inputs: Input parameters (comma-separated)
        outputs: Output values (comma-separated)
        steps: Algorithm steps (one per line, use indentation for nesting)
        caption: Algorithm caption
        label: Label for referencing

    Returns:
        Complete algorithm2e LaTeX code

    Example steps format:
        "Initialize parameters
        for each epoch:
            for each batch:
                Compute loss
                Update weights
        return model"
    """
    # Parse steps and convert to algorithm2e syntax
    step_lines = steps.strip().split("\n")
    formatted_steps = []

    for line in step_lines:
        # Count leading spaces/tabs for indentation level
        stripped = line.lstrip()
        if not stripped:
            continue

        indent = len(line) - len(stripped)
        indent_level = indent // 4  # Assume 4 spaces per level

        # Convert common patterns to algorithm2e commands
        lower = stripped.lower()

        if lower.startswith("for ") and ":" in lower:
            # for X in Y: or for each X:
            parts = stripped[4:].split(":")
            formatted_steps.append(f"\\For{{{parts[0].strip()}}}")
            formatted_steps.append("{")
        elif lower.startswith("while ") and ":" in lower:
            parts = stripped[6:].split(":")
            formatted_steps.append(f"\\While{{{parts[0].strip()}}}")
            formatted_steps.append("{")
        elif lower.startswith("if ") and ":" in lower:
            parts = stripped[3:].split(":")
            formatted_steps.append(f"\\If{{{parts[0].strip()}}}")
            formatted_steps.append("{")
        elif lower.startswith("else:"):
            formatted_steps.append("}")
            formatted_steps.append("\\Else{")
        elif lower.startswith("return "):
            formatted_steps.append(f"\\Return{{{stripped[7:]}}}")
        elif stripped.endswith(":"):
            # Generic block start
            formatted_steps.append(f"\\tcp*[l]{{{stripped[:-1]}}}")
        else:
            # Regular statement
            formatted_steps.append(f"    {stripped}\\;")

    # Close any open blocks (simple heuristic)
    open_braces = sum(1 for s in formatted_steps if s == "{") - sum(1 for s in formatted_steps if s == "}")
    formatted_steps.extend(["}"] * open_braces)

    steps_str = "\n        ".join(formatted_steps)

    algorithm_code = rf"""
\begin{{algorithm}}[htbp]
    \caption{{{caption or name}}}
    \label{{alg:{label or name.lower().replace(' ', '-')}}}
    \KwIn{{{inputs}}}
    \KwOut{{{outputs}}}

        {steps_str}
\end{{algorithm}}
"""

    return algorithm_code.strip()
```

**Step 2: Test create_algorithm**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
from agent.pydantic_agent import create_algorithm, AuraDeps
from unittest.mock import MagicMock

async def test():
    ctx = MagicMock()
    ctx.deps = AuraDeps(project_path="/tmp")

    steps = """Initialize weights randomly
for each epoch:
    for each batch in data:
        Compute forward pass
        Calculate loss
        Compute gradients
        Update weights
    Validate on dev set
return trained model"""

    result = await create_algorithm(
        ctx,
        name="Training Procedure",
        inputs="Dataset $D$, learning rate $\\eta$, epochs $E$",
        outputs="Trained model $\\theta$",
        steps=steps,
        caption="Our training procedure",
        label="training",
    )
    print(result)

asyncio.run(test())
EOF
```

Expected: Valid algorithm2e code with proper structure

**Step 3: Commit**

```bash
git add backend/agent/pydantic_agent.py
git commit -m "feat(writing): Add create_algorithm tool with algorithm2e support"
```

---

## Task 15: API Endpoints for Writing Features

**Files:**
- Modify: `backend/main.py`

**Step 1: Add imports and endpoints**

Add to imports:
```python
from services.latex_parser import parse_document, parse_bib_file_path, find_unused_citations
```

Add endpoints after the vibe research endpoints:

```python
# ============ Writing Intelligence Endpoints ============

class AnalyzeStructureRequest(BaseModel):
    project_path: str
    filepath: str = "main.tex"


class AddCitationRequest(BaseModel):
    project_path: str
    paper_id: str
    cite_key: Optional[str] = None
    insert_after_line: Optional[int] = None
    cite_style: str = "cite"


class CreateTableRequest(BaseModel):
    project_path: str
    data: str
    caption: str
    label: str = ""
    style: str = "booktabs"


class CreateFigureRequest(BaseModel):
    project_path: str
    description: str
    figure_type: str = "tikz"
    caption: str = ""
    label: str = ""
    data: str = ""


@app.post("/api/analyze-structure")
async def api_analyze_structure(request: AnalyzeStructureRequest):
    """Analyze document structure."""
    from pathlib import Path

    filepath = Path(request.project_path) / request.filepath
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content = filepath.read_text()
    structure = parse_document(content)

    return {
        "sections": [
            {
                "name": s.name,
                "level": s.level,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "label": s.label,
            }
            for s in structure.sections
        ],
        "elements": [
            {
                "type": e.type,
                "caption": e.caption,
                "label": e.label,
                "line_start": e.line_start,
                "line_end": e.line_end,
            }
            for e in structure.elements
        ],
        "citations": [
            {
                "key": c.key,
                "locations": c.locations,
                "command": c.command,
            }
            for c in structure.citations
        ],
        "citation_style": structure.citation_style,
        "bib_file": structure.bib_file,
        "packages": structure.packages,
    }


@app.post("/api/clean-bibliography")
async def api_clean_bibliography(request: AnalyzeStructureRequest):
    """Find unused bibliography entries."""
    from pathlib import Path

    filepath = Path(request.project_path) / request.filepath
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content = filepath.read_text()
    structure = parse_document(content)

    if not structure.bib_file:
        return {"unused": [], "message": "No bibliography file detected"}

    bib_path = Path(request.project_path) / structure.bib_file
    if not bib_path.exists():
        raise HTTPException(status_code=404, detail=f"Bibliography file not found: {structure.bib_file}")

    bib_entries = parse_bib_file_path(bib_path)
    unused = find_unused_citations(structure.citations, bib_entries)

    return {
        "unused": [
            {
                "key": e.key,
                "title": e.fields.get("title", ""),
                "year": e.fields.get("year", ""),
            }
            for e in unused
        ],
        "total_entries": len(bib_entries),
        "cited_count": len(structure.citations),
    }
```

**Step 2: Test endpoints**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && python3 << 'EOF'
import asyncio
import tempfile
from pathlib import Path

async def test():
    from main import api_analyze_structure, api_clean_bibliography, AnalyzeStructureRequest

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.tex").write_text(r"""
\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}
\section{Intro}
Hello \cite{cited2020}.
\begin{figure}
\caption{A figure}
\label{fig:test}
\end{figure}
\end{document}
""")

        (Path(tmpdir) / "refs.bib").write_text("""
@article{cited2020, title={Cited}, year={2020}}
@article{unused2020, title={Unused}, year={2020}}
""")

        req = AnalyzeStructureRequest(project_path=tmpdir)

        result = await api_analyze_structure(req)
        print("=== Structure ===")
        print(f"Sections: {len(result['sections'])}")
        print(f"Elements: {len(result['elements'])}")
        print(f"Citations: {result['citations']}")

        result = await api_clean_bibliography(req)
        print("\n=== Bibliography ===")
        print(f"Unused: {result['unused']}")

asyncio.run(test())
EOF
```

Expected: Structure parsed and unused citations identified

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(writing): Add API endpoints for document analysis"
```

---

## Task 16: Integration Testing

**Files:**
- Create: `backend/tests/test_writing.py`

**Step 1: Create integration tests**

```python
"""
Integration tests for Writing Intelligence features.
"""

import asyncio
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def test_project():
    """Create a temporary test project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Main document
        (Path(tmpdir) / "main.tex").write_text(r"""
\documentclass{article}
\usepackage{amsmath,graphicx}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}

\begin{document}

\section{Introduction}
\label{sec:intro}
Deep learning has transformed AI \cite{lecun2015deep}.
Transformers \cite{vaswani2017attention} are particularly important.

\subsection{Contributions}
We make three contributions.

\section{Related Work}
\label{sec:related}
Prior work includes BERT \cite{devlin2019bert}.

\begin{table}[htbp]
    \caption{Results}
    \label{tab:results}
    \begin{tabular}{lc}
        Model & Score \\
        Ours & 95.2 \\
    \end{tabular}
\end{table}

\begin{figure}[htbp]
    \centering
    \caption{Architecture}
\end{figure}

\section{Conclusion}
We did great work.

\end{document}
""")

        # Bibliography
        (Path(tmpdir) / "refs.bib").write_text("""
@article{lecun2015deep,
    title={Deep Learning},
    author={LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
    journal={Nature},
    year={2015}
}

@article{vaswani2017attention,
    title={Attention Is All You Need},
    author={Vaswani, Ashish and others},
    journal={NeurIPS},
    year={2017}
}

@article{devlin2019bert,
    title={BERT: Pre-training of Deep Bidirectional Transformers},
    author={Devlin, Jacob and others},
    booktitle={NAACL},
    year={2019}
}

@article{unused2020,
    title={This Paper Is Never Cited},
    author={Nobody, Someone},
    year={2020}
}
""")

        yield tmpdir


class TestLatexParser:
    """Test LaTeX parsing functionality."""

    def test_parse_sections(self, test_project):
        from services.latex_parser import parse_document

        content = (Path(test_project) / "main.tex").read_text()
        structure = parse_document(content)

        assert len(structure.sections) == 4  # Intro, Contributions, Related, Conclusion
        assert structure.sections[0].name == "Introduction"
        assert structure.sections[0].label == "sec:intro"

    def test_parse_elements(self, test_project):
        from services.latex_parser import parse_document

        content = (Path(test_project) / "main.tex").read_text()
        structure = parse_document(content)

        assert len(structure.elements) == 2  # table and figure

        table = next(e for e in structure.elements if e.type == "table")
        assert table.label == "tab:results"
        assert "Results" in table.caption

    def test_parse_citations(self, test_project):
        from services.latex_parser import parse_document

        content = (Path(test_project) / "main.tex").read_text()
        structure = parse_document(content)

        assert len(structure.citations) == 4  # lecun, vaswani (x2?), devlin
        keys = {c.key for c in structure.citations}
        assert "lecun2015deep" in keys
        assert "vaswani2017attention" in keys

    def test_detect_citation_style(self, test_project):
        from services.latex_parser import parse_document

        content = (Path(test_project) / "main.tex").read_text()
        structure = parse_document(content)

        assert structure.citation_style == "biblatex"
        assert structure.bib_file == "refs.bib"

    def test_find_unused_citations(self, test_project):
        from services.latex_parser import (
            parse_document, parse_bib_file_path, find_unused_citations
        )

        content = (Path(test_project) / "main.tex").read_text()
        structure = parse_document(content)

        bib_entries = parse_bib_file_path(Path(test_project) / "refs.bib")
        unused = find_unused_citations(structure.citations, bib_entries)

        assert len(unused) == 1
        assert unused[0].key == "unused2020"


class TestCitationTools:
    """Test citation generation tools."""

    def test_generate_cite_key(self):
        from agent.tools.citations import PaperMetadata, generate_cite_key

        paper = PaperMetadata(
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish", "Shazeer, Noam"],
            year=2017,
        )

        key = generate_cite_key(paper)
        assert key == "vaswani2017attention"

    def test_generate_bibtex(self):
        from agent.tools.citations import PaperMetadata, generate_bibtex

        paper = PaperMetadata(
            title="Test Paper",
            authors=["Smith, John"],
            year=2024,
            arxiv_id="2401.12345",
        )

        bibtex = generate_bibtex(paper)
        assert "@misc{" in bibtex
        assert "eprint = {2401.12345}" in bibtex
        assert "archivePrefix = {arXiv}" in bibtex


class TestContentGeneration:
    """Test content generation tools."""

    @pytest.mark.asyncio
    async def test_create_table(self):
        from agent.pydantic_agent import create_table, AuraDeps
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.deps = AuraDeps(project_path="/tmp")

        result = await create_table(
            ctx,
            data="Model,Accuracy\nBERT,85.2\nGPT,79.3",
            caption="Test table",
            label="test",
        )

        assert r"\begin{table}" in result
        assert r"\toprule" in result
        assert "BERT" in result
        assert r"\label{tab:test}" in result

    @pytest.mark.asyncio
    async def test_create_figure(self):
        from agent.pydantic_agent import create_figure, AuraDeps
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.deps = AuraDeps(project_path="/tmp")

        result = await create_figure(
            ctx,
            description="Test diagram",
            figure_type="tikz",
            caption="A test figure",
            label="test",
        )

        assert r"\begin{figure}" in result
        assert r"\begin{tikzpicture}" in result
        assert r"\label{fig:test}" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Step 2: Run tests**

Run:
```bash
cd /Users/zhongzhiyi/Aura/.worktrees/phase8-writing-intelligence/backend && source .venv/bin/activate && pip install pytest pytest-asyncio -q && python -m pytest tests/test_writing.py -v
```

Expected: All tests passing

**Step 3: Commit**

```bash
git add backend/tests/test_writing.py
git commit -m "test(writing): Add integration tests for Writing Intelligence"
```

---

## Task 17: Final Integration and Documentation

**Files:**
- Modify: `backend/CLAUDE.md` (or create if needed)

**Step 1: Update CLAUDE.md with new tools**

Add to the agent tools section:

```markdown
## Phase 8: Writing Intelligence (New)

New tools added to main agent:
- `analyze_structure` - Parse document structure (sections, elements, citations)
- `add_citation` - Add paper to .bib and insert \cite{}
- `create_table` - Generate booktabs table from CSV/markdown
- `create_figure` - Generate TikZ or pgfplots figure
- `create_algorithm` - Generate algorithm2e pseudocode

WritingAgent subagent tools (via delegate_to_subagent):
- `check_consistency` - Find terminology/notation inconsistencies
- `clean_bibliography` - Find unused .bib entries
- `suggest_citations` - Find claims needing citations
```

**Step 2: Final commit**

```bash
git add -A
git commit -m "docs: Update CLAUDE.md with Phase 8 Writing Intelligence tools"
```

**Step 3: Summary commit for the branch**

```bash
git log --oneline -15
```

---

## Summary

This plan implements Phase 8: Writing Intelligence in 17 tasks:

| Task | Component | Key Files |
|------|-----------|-----------|
| 1-7 | LaTeX Parser Service | `services/latex_parser.py` |
| 8 | Citation Helper | `agent/tools/citations.py` |
| 9-10 | Main Agent Tools | `agent/pydantic_agent.py` |
| 11 | WritingAgent Subagent | `agent/subagents/writing.py` |
| 12-14 | Content Generation | `agent/pydantic_agent.py` |
| 15 | API Endpoints | `main.py` |
| 16-17 | Testing & Docs | `tests/test_writing.py` |

**New Tools:**
- Main agent: `analyze_structure`, `add_citation`, `create_table`, `create_figure`, `create_algorithm`
- WritingAgent: `check_consistency`, `clean_bibliography`, `suggest_citations`

**New Dependencies:**
- `pylatexenc>=2.10`
