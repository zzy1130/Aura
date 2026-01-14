# Phase 8: Writing Intelligence Design

> **Status**: Approved
> **Priority**: After Phase 7 (Vibe Research) - Complete
> **Estimated Effort**: ~9 days

## Overview

Writing Intelligence makes Aura understand LaTeX structure and academic writing conventions. Instead of treating documents as raw text, the agent understands sections, citations, figures, and can make contextually appropriate edits.

## Design Decisions

| Aspect | Choice |
|--------|--------|
| Priority order | A (Citations) → B (Structure) → C (Content) → D (Quality) |
| Citation style | Support both BibLaTeX and BibTeX (auto-detect) |
| Structure parsing | Hybrid (regex + AST for complex cases) |
| Content generation | Extended (TikZ, pgfplots, booktabs, algorithm2e, listings, forest) |
| Writing quality | Full suite (consistency, style matching, clarity) |
| Architecture | Hybrid (core tools on main agent, complex ops on WritingAgent) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Main Agent                               │
│                     (pydantic_agent.py)                          │
├─────────────────────────────────────────────────────────────────┤
│  Existing Tools:                                                 │
│  - read_file, edit_file, write_file, list_files, find_files     │
│  - compile_latex, check_latex_syntax, get_compilation_log        │
│  - delegate_to_subagent, think, planning tools                   │
│                                                                  │
│  NEW Core Writing Tools:                                         │
│  - add_citation          (add paper to .bib + insert \cite)     │
│  - analyze_structure     (parse document structure)              │
│  - create_figure         (generate TikZ/pgfplots)               │
│  - create_table          (generate booktabs table)              │
│  - create_algorithm      (generate algorithm2e pseudocode)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ delegate_to_subagent("writing", ...)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       WritingAgent                               │
│                  (subagents/writing.py)                          │
├─────────────────────────────────────────────────────────────────┤
│  Complex Operations:                                             │
│  - analyze_writing_style   (extract patterns from reference)    │
│  - check_consistency       (terminology, notation, tense)       │
│  - suggest_improvements    (clarity, passive voice, jargon)     │
│  - refactor_document       (reorganize sections)                │
│  - clean_bibliography      (remove unused, deduplicate)         │
│  - suggest_citations       (find claims needing citations)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LaTeX Parser Service                        │
│                   (services/latex_parser.py)                     │
├─────────────────────────────────────────────────────────────────┤
│  - parse_structure()      (regex-based section/figure/table)    │
│  - parse_environment()    (AST-based for complex envs)          │
│  - detect_citation_style()(BibLaTeX vs BibTeX)                  │
│  - parse_bibliography()   (extract .bib entries)                │
│  - find_citations()       (all \cite{} in document)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component 1: LaTeX Parser Service

**File:** `backend/services/latex_parser.py`

### Data Structures

```python
@dataclass
class DocumentSection:
    level: int              # 0=document, 1=section, 2=subsection, 3=subsubsection
    name: str               # "Introduction", "Methods", etc.
    command: str            # "\section", "\subsection", etc.
    line_start: int
    line_end: int
    label: str | None       # \label{sec:intro} if present
    children: list["DocumentSection"]

@dataclass
class DocumentElement:
    type: str               # "figure", "table", "algorithm", "equation", "listing"
    label: str | None
    caption: str | None
    line_start: int
    line_end: int
    content: str            # Raw LaTeX content

@dataclass
class CitationInfo:
    key: str                # "vaswani2017attention"
    locations: list[int]    # Line numbers where cited
    style: str              # "cite", "citep", "citet", "autocite", etc.

@dataclass
class BibEntry:
    key: str
    type: str               # "article", "inproceedings", "book", etc.
    fields: dict[str, str]  # title, author, year, etc.
    raw: str                # Original BibTeX string

@dataclass
class DocumentStructure:
    sections: list[DocumentSection]
    elements: list[DocumentElement]
    citations: list[CitationInfo]
    citation_style: str     # "biblatex" or "bibtex"
    bib_file: str | None    # Path to .bib file
    packages: list[str]     # Detected packages
```

### Parsing Methods

| Method | Approach | Purpose |
|--------|----------|---------|
| `parse_structure(tex_content)` | Regex | Extract section hierarchy |
| `parse_elements(tex_content)` | Regex + AST | Find figures, tables, algorithms |
| `find_citations(tex_content)` | Regex | Find all `\cite{}` variants |
| `detect_citation_style(tex_content)` | Regex | Check for biblatex vs natbib |
| `parse_bib_file(bib_content)` | Regex | Parse .bib entries |
| `parse_environment(tex_content, env_name)` | AST (pylatexenc) | Deep parse for complex envs |

### AST Fallback Triggers

- Nested environments (`\begin{figure}\begin{tikzpicture}...`)
- Custom commands (`\newcommand` definitions)
- Complex argument parsing (optional args, nested braces)

---

## Component 2: Citation Management (Priority A)

### Main Agent Tool

```python
@aura_agent.tool
async def add_citation(
    ctx: RunContext[AuraDeps],
    paper_id: str,              # "arxiv:2301.07041" or "s2:abc123" or search query
    cite_key: str | None,       # Optional custom key, auto-generated if None
    context: str | None,        # Where to insert (e.g., "after line 42" or "in introduction")
    cite_style: str = "cite",   # "cite", "citep", "citet", "autocite", etc.
) -> str:
    """
    Add a citation to the document.

    1. Fetches paper metadata (from arXiv/S2 or memory)
    2. Generates BibTeX entry
    3. Appends to .bib file (deduplicates if exists)
    4. Optionally inserts \cite{} at specified location
    """
```

### WritingAgent Tools

```python
async def clean_bibliography(ctx) -> str:
    """
    Remove unused citations from .bib file.

    1. Parse all \cite{} in document
    2. Parse all entries in .bib
    3. Identify orphaned entries
    4. Remove them (with confirmation)
    """

async def suggest_citations(ctx, section: str | None) -> str:
    """
    Find claims that might need citations.

    Looks for patterns like:
    - "Studies show that..."
    - "It has been demonstrated..."
    - "According to recent research..."
    - Quantitative claims without source

    Returns list of suggestions with line numbers.
    """

async def deduplicate_bibliography(ctx) -> str:
    """
    Find and merge duplicate .bib entries.

    Detects duplicates by:
    - Same DOI
    - Same arXiv ID
    - Similar title (fuzzy match)
    """
```

### BibTeX Generation

```python
def generate_bibtex(paper: Paper, cite_key: str | None = None) -> BibEntry:
    """
    Generate BibTeX from paper metadata.

    Auto-generates cite_key as: {first_author_lastname}{year}{first_title_word}
    e.g., "vaswani2017attention"

    Handles:
    - arXiv papers (@misc with eprint field)
    - Conference papers (@inproceedings)
    - Journal articles (@article)
    """
```

### Integration with Vibe Research

When a Vibe Research session completes, the agent can:
1. List papers from `vibe_state.papers`
2. Offer to add top papers as citations
3. Use `add_citation` with paper IDs already in memory

---

## Component 3: Document Structure Analysis (Priority B)

### Main Agent Tool

```python
@aura_agent.tool
async def analyze_structure(
    ctx: RunContext[AuraDeps],
    filepath: str = "main.tex",
) -> str:
    """
    Analyze document structure and return overview.

    Returns:
    - Section hierarchy (with line numbers)
    - Figure/table inventory
    - Citation count per section
    - Detected issues (missing labels, empty sections, etc.)
    """
```

### Example Output

```
Document Structure: main.tex

SECTIONS:
├── 1. Introduction (L12-45) [3 citations]
│   └── 1.1 Contributions (L38-45) [0 citations]
├── 2. Related Work (L47-89) [12 citations]
├── 3. Methods (L91-156) [2 citations]
│   ├── 3.1 Problem Formulation (L95-112)
│   └── 3.2 Our Approach (L114-156)
├── 4. Experiments (L158-234) [4 citations]
│   ├── 4.1 Setup (L162-189)
│   └── 4.2 Results (L191-234)
├── 5. Conclusion (L236-258) [0 citations]
└── References (L260+)

ELEMENTS:
- Figure 1: "Architecture Overview" (L120) ✓ labeled
- Figure 2: "Results Comparison" (L205) ⚠ no label
- Table 1: "Dataset Statistics" (L170) ✓ labeled
- Algorithm 1: "Training Procedure" (L145) ✓ labeled

ISSUES:
- Section 1.1 has no citations (claims may need support)
- Figure 2 missing \label{} (cannot be referenced)
- Section 5 (Conclusion) has no citations

PACKAGES: amsmath, graphicx, algorithm2e, booktabs, biblatex
CITATION STYLE: biblatex (biber backend)
BIB FILE: refs.bib (47 entries, 21 cited)
```

### WritingAgent Tools

```python
async def refactor_document(
    ctx,
    operation: str,  # "split", "merge", "move", "extract"
    target: str,     # Section name or line range
    destination: str | None,
) -> str:
    """
    Restructure document organization.

    Operations:
    - split: Break a section into subsections
    - merge: Combine adjacent sections
    - move: Relocate a section
    - extract: Move section to separate file + \input{}
    """

async def detect_structure_issues(ctx) -> str:
    """
    Find structural problems:
    - Orphaned labels (defined but never referenced)
    - Missing labels on figures/tables
    - Inconsistent section numbering
    - Very long sections (>500 lines)
    - Empty sections
    - Sections with no citations (in literature-heavy areas)
    """
```

### Section-Aware Context

When the user asks to "improve the introduction", the agent:
1. Calls `analyze_structure()` to find Introduction bounds (L12-45)
2. Reads only that section
3. Understands section purpose (intro = hook → gap → contribution)
4. Makes contextually appropriate edits

---

## Component 4: Content Generation (Priority C)

### Main Agent Tools

```python
@aura_agent.tool
async def create_figure(
    ctx: RunContext[AuraDeps],
    description: str,           # "A flowchart showing the training pipeline"
    figure_type: str = "tikz",  # "tikz", "pgfplots", "pgfplots-bar", "pgfplots-line"
    data: str | None = None,    # CSV or JSON data for plots
    insert_at: str | None = None,  # "after line 120" or "in methods section"
) -> str:
    """
    Generate a LaTeX figure from description.

    For TikZ: Generates diagram code
    For pgfplots: Generates plot with provided data
    """

@aura_agent.tool
async def create_table(
    ctx: RunContext[AuraDeps],
    description: str,           # "Comparison of model accuracy across datasets"
    data: str,                  # CSV, JSON, or markdown table
    style: str = "booktabs",    # "booktabs", "basic", "colored"
    insert_at: str | None = None,
) -> str:
    """
    Generate a LaTeX table from data.

    Handles:
    - Auto column alignment
    - Number formatting
    - Caption and label generation
    """

@aura_agent.tool
async def create_algorithm(
    ctx: RunContext[AuraDeps],
    description: str,           # "Pseudocode for the attention mechanism"
    style: str = "algorithm2e", # "algorithm2e", "algorithmic", "lstlisting"
    insert_at: str | None = None,
) -> str:
    """
    Generate pseudocode or code listing.
    """
```

### LaTeX Templates

**TikZ Flowchart:**
```latex
\begin{figure}[htbp]
    \centering
    \begin{tikzpicture}[
        node distance=1.5cm,
        box/.style={rectangle, draw, rounded corners, minimum width=2cm, minimum height=0.8cm},
        arrow/.style={->, >=stealth, thick}
    ]
        {nodes}
        {edges}
    \end{tikzpicture}
    \caption{{{caption}}}
    \label{{fig:{label}}}
\end{figure}
```

**Booktabs Table:**
```latex
\begin{table}[htbp]
    \centering
    \caption{{{caption}}}
    \label{{tab:{label}}}
    \begin{tabular}{{{alignment}}}
        \toprule
        {header}
        \midrule
        {rows}
        \bottomrule
    \end{tabular}
\end{table}
```

**Algorithm2e:**
```latex
\begin{algorithm}[htbp]
    \caption{{{caption}}}
    \label{{alg:{label}}}
    \KwIn{{{inputs}}}
    \KwOut{{{outputs}}}
    {body}
\end{algorithm}
```

### Supported Content Types

| Type | Package | Use Case |
|------|---------|----------|
| TikZ diagrams | tikz | Flowcharts, architectures, neural networks |
| pgfplots charts | pgfplots | Bar charts, line plots, scatter plots |
| booktabs tables | booktabs | Professional data tables |
| algorithm2e | algorithm2e | Pseudocode with keywords |
| listings | listings | Code blocks with syntax highlighting |
| forest | forest | Tree structures, hierarchies |

---

## Component 5: Writing Quality (Priority D)

### WritingAgent Tools

```python
async def check_consistency(
    ctx,
    scope: str = "full",  # "full", "section:Methods", "lines:50-100"
) -> str:
    """
    Check for inconsistencies in the document.

    Categories:
    - Terminology: "Transformer" vs "transformer", "dataset" vs "data set"
    - Notation: "x_i" vs "x^i", "θ" vs "\theta"
    - Capitalization: "Attention mechanism" vs "attention mechanism"
    - Tense: Past vs present in same section
    - Acronyms: Defined before use? Used consistently?

    Returns list of issues with line numbers and suggested fixes.
    """

async def analyze_writing_style(
    ctx,
    reference_file: str,  # Path to a paper whose style to analyze
) -> str:
    """
    Extract style patterns from a reference document.

    Analyzes:
    - Average sentence length
    - Paragraph structure
    - Transition word usage
    - Formality level (contractions, personal pronouns)
    - Technical density (equations per paragraph)
    - Citation density per section type

    Stores style profile in project memory for later use.
    """

async def apply_writing_style(
    ctx,
    section: str,         # Which section to improve
    style_profile: str,   # Name of saved style profile
) -> str:
    """
    Rewrite section to match a style profile.

    Adjusts:
    - Sentence length (split or combine)
    - Formality (remove contractions, adjust pronouns)
    - Transitions between paragraphs
    """

async def suggest_improvements(
    ctx,
    scope: str = "full",
) -> str:
    """
    Suggest clarity and quality improvements.

    Detects:
    - Passive voice overuse ("was computed" → "we computed")
    - Jargon without explanation
    - Very long sentences (>40 words)
    - Vague language ("some", "various", "etc.")
    - Redundancy ("in order to" → "to")
    - Weak claims ("might possibly" → "may")

    Returns prioritized list with before/after examples.
    """
```

### Consistency Check Output Example

```
Consistency Analysis: main.tex

TERMINOLOGY (5 issues):
  L23: "Transformer" → L89: "transformer" (use "Transformer" consistently?)
  L45: "dataset" → L102: "data set" → L156: "data-set" (standardize to "dataset"?)
  L67: "self-attention" → L134: "self attention" (use "self-attention"?)

NOTATION (2 issues):
  L78: "x_i" → L145: "x^{(i)}" (same variable, different notation)
  L92: "\theta" → L203: "θ" (use LaTeX command consistently)

TENSE (3 issues):
  L34-45 (Introduction): Mixed present/past
    "We propose..." (L34) vs "We showed..." (L42)
    Suggestion: Use present tense in Introduction

ACRONYMS (1 issue):
  L89: "NLP" used before definition
  L112: "Natural Language Processing (NLP)" defined
  Suggestion: Move definition to first use

CAPITALIZATION (2 issues):
  L56: "attention Mechanism" → should be "Attention Mechanism" or "attention mechanism"

──────────────────────────────
Total: 13 issues found
Run: /fix-consistency to apply suggested fixes
```

### Style Profile Data Structure

```python
@dataclass
class StyleProfile:
    name: str
    source_file: str

    # Sentence metrics
    avg_sentence_length: float      # words per sentence
    sentence_length_variance: float

    # Paragraph metrics
    avg_paragraph_length: float     # sentences per paragraph

    # Vocabulary
    formality_score: float          # 0-1, higher = more formal
    uses_contractions: bool
    uses_first_person: bool         # "we" vs passive

    # Structure
    transition_word_frequency: float
    citation_density_by_section: dict[str, float]

    # Technical
    equations_per_page: float
    figures_per_page: float
```

---

## File Structure

### New Files

```
backend/
├── services/
│   └── latex_parser.py          # Core parsing service
├── agent/
│   ├── subagents/
│   │   └── writing.py           # WritingAgent subagent
│   └── tools/
│       ├── citations.py         # Citation management helpers
│       ├── content_gen.py       # Figure/table/algorithm generators
│       └── templates/           # LaTeX templates
│           ├── figure_tikz.tex
│           ├── figure_pgfplots.tex
│           ├── table_booktabs.tex
│           └── algorithm.tex
```

### Modified Files

```
backend/
├── agent/
│   ├── pydantic_agent.py        # Add new core tools
│   └── subagents/base.py        # Register WritingAgent
├── main.py                      # Add new API endpoints
└── requirements.txt             # Add pylatexenc
```

---

## Dependencies

```
pylatexenc>=2.10        # AST parsing for complex LaTeX
```

---

## Implementation Plan

| Phase | Task | Effort | Depends On |
|-------|------|--------|------------|
| 1.1 | `latex_parser.py` - regex-based structure parsing | 1 day | - |
| 1.2 | `latex_parser.py` - bib file parsing + citation detection | 0.5 day | 1.1 |
| 1.3 | `latex_parser.py` - AST integration for complex envs | 0.5 day | 1.1 |
| 2.1 | `add_citation` tool on main agent | 0.5 day | 1.2 |
| 2.2 | `analyze_structure` tool on main agent | 0.5 day | 1.1 |
| 2.3 | Content generation tools (figure/table/algorithm) | 1 day | 1.1 |
| 3.1 | `WritingAgent` subagent scaffold | 0.5 day | - |
| 3.2 | `clean_bibliography`, `suggest_citations` | 0.5 day | 1.2, 3.1 |
| 3.3 | `check_consistency` | 1 day | 1.1, 3.1 |
| 3.4 | `analyze_writing_style`, `apply_writing_style` | 1 day | 3.1 |
| 3.5 | `suggest_improvements`, `refactor_document` | 1 day | 1.1, 3.1 |
| 4.1 | API endpoints for new capabilities | 0.5 day | 2.*, 3.* |
| 4.2 | Integration testing | 0.5 day | 4.1 |

**Total: ~9 days**

---

## API Endpoints

```python
# Document analysis
POST /api/analyze-structure      # Get document structure
POST /api/check-consistency      # Run consistency check

# Citations
POST /api/add-citation           # Add citation to document
POST /api/clean-bibliography     # Remove unused entries
POST /api/suggest-citations      # Find claims needing citations

# Content
POST /api/create-figure          # Generate figure
POST /api/create-table           # Generate table

# Writing quality
POST /api/analyze-style          # Analyze reference document
POST /api/suggest-improvements   # Get improvement suggestions
```

---

## Success Criteria

| Feature | Metric |
|---------|--------|
| Citation Management | Add citation in <2 tool calls, no duplicate entries |
| Structure Analysis | Parse 95%+ of standard academic papers correctly |
| Content Generation | Generated figures/tables compile without errors |
| Consistency Check | Detect 90%+ of terminology inconsistencies |
| Style Analysis | Profile extraction completes in <5 seconds |

---

## Future Enhancements (Out of Scope)

- Real-time consistency checking (as-you-type)
- Visual figure editor integration
- Multi-file project support (beyond \input{})
- Collaborative editing awareness
- Citation recommendation based on content
