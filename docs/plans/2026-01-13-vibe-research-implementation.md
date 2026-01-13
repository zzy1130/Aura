# Vibe Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Vibe Research mode to Aura - an AI-led autonomous research workflow that discovers literature, identifies gaps, and generates novel hypotheses.

**Architecture:** Extend existing `ResearchAgent` with mode-aware system prompts, state tracking, and new tools. Single agent design (not multi-agent) for simplicity and efficiency.

**Key References:**
- [Magentic-One](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/) - Orchestrator pattern with Task/Progress ledgers
- [Auto-Deep-Research](https://github.com/HKUDS/Auto-Deep-Research) - Open-source deep research
- [Google AI Co-Scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) - Multi-agent hypothesis generation

---

## Overview

### What is Vibe Research?

| Mode | Human Role | AI Role | Output |
|------|-----------|---------|--------|
| **Chat** | Asks questions | Searches, summarizes | Quick answers |
| **Vibe** | Sets goal, oversees | Autonomously explores, synthesizes, ideates | Research report + hypotheses |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ResearchAgent (Enhanced)                      │
├─────────────────────────────────────────────────────────────────┤
│  mode: CHAT | VIBE                                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ VibeResearchState (Magentic-One inspired)               │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ TASK LEDGER: topic, scope, papers, themes, gaps, hypos  │   │
│  │ PROGRESS LEDGER: phase, progress%, stall_count          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Tools:                                                         │
│  ├── EXISTING: search_arxiv, search_semantic_scholar,          │
│  │             read_arxiv_paper, read_pdf_url, think           │
│  │                                                             │
│  └── NEW: explore_citations, identify_themes, identify_gaps,   │
│           generate_hypothesis, evaluate_novelty,               │
│           update_progress, advance_phase, generate_report,     │
│           save_to_memory                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task 1: Semantic Scholar Enhanced Client ✅

**Files:**
- Create: `backend/services/semantic_scholar.py`

**Step 1: Create the SemanticScholarClient class**

```python
"""
Semantic Scholar API Client

Enhanced client for Semantic Scholar API with citation graph traversal.
API docs: https://api.semanticscholar.org/api-docs/

Rate limits: 100 requests/sec (unauthenticated), 1 request/sec for bulk endpoints
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)


# API Configuration
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_FIELDS = "paperId,title,authors,abstract,year,citationCount,url,openAccessPdf"
S2_CITATION_FIELDS = "paperId,title,authors,year,citationCount"


@dataclass
class Paper:
    """Represents an academic paper."""
    paper_id: str
    title: str
    authors: list[str]
    year: Optional[int] = None
    abstract: str = ""
    citation_count: int = 0
    url: str = ""
    pdf_url: str = ""
    arxiv_id: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "Paper":
        """Create Paper from S2 API response."""
        authors = [a.get("name", "Unknown") for a in data.get("authors", [])[:5]]
        pdf_url = ""
        if data.get("openAccessPdf"):
            pdf_url = data["openAccessPdf"].get("url", "")

        return cls(
            paper_id=data.get("paperId", ""),
            title=data.get("title", "Unknown"),
            authors=authors,
            year=data.get("year"),
            abstract=data.get("abstract", "")[:500] if data.get("abstract") else "",
            citation_count=data.get("citationCount", 0),
            url=data.get("url", ""),
            pdf_url=pdf_url,
        )

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "abstract": self.abstract,
            "citation_count": self.citation_count,
            "url": self.url,
            "pdf_url": self.pdf_url,
        }


@dataclass
class CitationResult:
    """Result from citation/reference traversal."""
    source_paper_id: str
    direction: str  # "citations" or "references"
    papers: list[Paper] = field(default_factory=list)
    total_count: int = 0


class SemanticScholarClient:
    """
    Client for Semantic Scholar API with citation graph support.

    Features:
    - Paper search with relevance ranking
    - Citation graph traversal (who cites this, what this cites)
    - Paper details lookup
    - Rate limiting support
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
    ):
        self.http_client = http_client
        self.api_key = api_key
        self._request_semaphore = asyncio.Semaphore(10)  # Limit concurrent requests

    def _get_headers(self) -> dict:
        """Get request headers."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def search(
        self,
        query: str,
        limit: int = 10,
        year_range: Optional[tuple[int, int]] = None,
    ) -> list[Paper]:
        """
        Search for papers by query.

        Args:
            query: Search query
            limit: Maximum results (1-100)
            year_range: Optional (start_year, end_year) filter

        Returns:
            List of matching papers
        """
        async with self._request_semaphore:
            try:
                params = {
                    "query": query,
                    "limit": min(limit, 100),
                    "fields": S2_SEARCH_FIELDS,
                }

                if year_range:
                    params["year"] = f"{year_range[0]}-{year_range[1]}"

                response = await self.http_client.get(
                    f"{S2_API_BASE}/paper/search",
                    params=params,
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code == 429:
                    logger.warning("Semantic Scholar rate limit hit")
                    await asyncio.sleep(1.0)
                    return []

                response.raise_for_status()
                data = response.json()

                return [Paper.from_api(p) for p in data.get("data", [])]

            except httpx.HTTPStatusError as e:
                logger.error(f"S2 search error: {e}")
                return []
            except Exception as e:
                logger.error(f"S2 search error: {e}")
                return []

    async def get_paper(self, paper_id: str) -> Optional[Paper]:
        """
        Get paper details by ID.

        Args:
            paper_id: Semantic Scholar paper ID or arXiv ID (e.g., "arXiv:2301.07041")

        Returns:
            Paper details or None if not found
        """
        async with self._request_semaphore:
            try:
                response = await self.http_client.get(
                    f"{S2_API_BASE}/paper/{paper_id}",
                    params={"fields": S2_SEARCH_FIELDS},
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return Paper.from_api(response.json())

            except Exception as e:
                logger.error(f"S2 get_paper error: {e}")
                return None

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> CitationResult:
        """
        Get papers that cite this paper.

        Args:
            paper_id: Semantic Scholar paper ID
            limit: Maximum results (1-1000)
            offset: Pagination offset

        Returns:
            CitationResult with citing papers
        """
        return await self._get_connected_papers(
            paper_id, "citations", limit, offset
        )

    async def get_references(
        self,
        paper_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> CitationResult:
        """
        Get papers that this paper cites.

        Args:
            paper_id: Semantic Scholar paper ID
            limit: Maximum results (1-1000)
            offset: Pagination offset

        Returns:
            CitationResult with referenced papers
        """
        return await self._get_connected_papers(
            paper_id, "references", limit, offset
        )

    async def _get_connected_papers(
        self,
        paper_id: str,
        direction: Literal["citations", "references"],
        limit: int,
        offset: int,
    ) -> CitationResult:
        """Get papers connected via citations or references."""
        async with self._request_semaphore:
            try:
                response = await self.http_client.get(
                    f"{S2_API_BASE}/paper/{paper_id}/{direction}",
                    params={
                        "fields": S2_CITATION_FIELDS,
                        "limit": min(limit, 1000),
                        "offset": offset,
                    },
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code == 429:
                    logger.warning("Semantic Scholar rate limit hit")
                    await asyncio.sleep(1.0)
                    return CitationResult(paper_id, direction)

                if response.status_code == 404:
                    return CitationResult(paper_id, direction)

                response.raise_for_status()
                data = response.json()

                # Citations/references are nested under "citingPaper" or "citedPaper"
                key = "citingPaper" if direction == "citations" else "citedPaper"
                papers = []
                for item in data.get("data", []):
                    paper_data = item.get(key, {})
                    if paper_data and paper_data.get("paperId"):
                        papers.append(Paper.from_api(paper_data))

                return CitationResult(
                    source_paper_id=paper_id,
                    direction=direction,
                    papers=papers,
                    total_count=data.get("total", len(papers)),
                )

            except Exception as e:
                logger.error(f"S2 {direction} error: {e}")
                return CitationResult(paper_id, direction)

    async def explore_citation_graph(
        self,
        paper_id: str,
        direction: Literal["citations", "references", "both"] = "both",
        depth: int = 1,
        max_papers_per_level: int = 20,
    ) -> list[Paper]:
        """
        Explore citation graph starting from a paper.

        Args:
            paper_id: Starting paper ID
            direction: Which direction to explore
            depth: How many levels to traverse (1-2 recommended)
            max_papers_per_level: Max papers per level

        Returns:
            All discovered papers (deduplicated)
        """
        seen_ids: set[str] = {paper_id}
        all_papers: list[Paper] = []
        current_level: list[str] = [paper_id]

        for level in range(depth):
            next_level: list[str] = []

            for pid in current_level[:max_papers_per_level]:
                if direction in ("citations", "both"):
                    result = await self.get_citations(pid, limit=max_papers_per_level)
                    for paper in result.papers:
                        if paper.paper_id not in seen_ids:
                            seen_ids.add(paper.paper_id)
                            all_papers.append(paper)
                            next_level.append(paper.paper_id)

                if direction in ("references", "both"):
                    result = await self.get_references(pid, limit=max_papers_per_level)
                    for paper in result.papers:
                        if paper.paper_id not in seen_ids:
                            seen_ids.add(paper.paper_id)
                            all_papers.append(paper)
                            next_level.append(paper.paper_id)

                # Rate limiting
                await asyncio.sleep(0.1)

            current_level = next_level

        return all_papers
```

**Step 2: Test the client**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
import httpx
from services.semantic_scholar import SemanticScholarClient

async def test():
    async with httpx.AsyncClient() as client:
        s2 = SemanticScholarClient(client)

        # Test search
        papers = await s2.search("attention is all you need", limit=3)
        print(f"Search found {len(papers)} papers")
        if papers:
            print(f"First: {papers[0].title} ({papers[0].citation_count} citations)")

            # Test citations
            cites = await s2.get_citations(papers[0].paper_id, limit=5)
            print(f"Citations: {len(cites.papers)} papers")

asyncio.run(test())
EOF
```

**Step 3: Commit**

```bash
git add backend/services/semantic_scholar.py
git commit -m "feat(vibe): Add SemanticScholarClient with citation graph support"
```

---

## Task 2: VibeResearchState for Progress Tracking ✅

**Files:**
- Create: `backend/agent/vibe_state.py`

**Step 1: Create the state management module**

```python
"""
Vibe Research State Management

Tracks research progress using a dual-ledger pattern inspired by Magentic-One:
- Task Ledger: What we're researching, what we've found
- Progress Ledger: Current phase, progress %, stall detection

This state is injected into the agent's system prompt and updated via tools.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ResearchPhase(str, Enum):
    """Phases of vibe research workflow."""
    SCOPING = "scoping"       # Clarify requirements
    DISCOVERY = "discovery"   # Search and find papers
    SYNTHESIS = "synthesis"   # Read and identify themes
    IDEATION = "ideation"     # Find gaps, generate hypotheses
    EVALUATION = "evaluation" # Score and rank hypotheses
    COMPLETE = "complete"     # Report generated


@dataclass
class PaperRecord:
    """A paper discovered during research."""
    paper_id: str
    title: str
    authors: list[str]
    year: Optional[int]
    citation_count: int
    abstract: str = ""
    source: str = ""  # "arxiv", "semantic_scholar", "citation_graph"
    read_fully: bool = False
    relevance: str = ""  # Agent's assessment


@dataclass
class ThemeRecord:
    """A theme identified in the literature."""
    theme_id: str
    name: str
    description: str
    paper_ids: list[str]
    key_insight: str = ""


@dataclass
class GapRecord:
    """A research gap identified."""
    gap_id: str
    title: str
    evidence: str
    confidence: str  # "low", "medium", "high"
    related_themes: list[str] = field(default_factory=list)


@dataclass
class HypothesisRecord:
    """A generated research hypothesis."""
    hypothesis_id: str
    gap_id: str
    title: str
    description: str
    rationale: str
    building_blocks: str  # Papers/methods to build on
    suggested_experiments: str
    novelty_score: int = 0      # 1-10
    feasibility_score: int = 0  # 1-10
    impact_score: int = 0       # 1-10
    similar_work: str = ""
    differentiation: str = ""


@dataclass
class VibeResearchState:
    """
    Complete state for a vibe research session.

    Implements the dual-ledger pattern:
    - Task Ledger: topic, scope, papers, themes, gaps, hypotheses
    - Progress Ledger: phase, progress, stall detection
    """

    # === IDENTITY ===
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # === TASK LEDGER ===
    topic: str = ""
    scope: dict = field(default_factory=dict)  # Clarified parameters

    # Discovered content
    papers: list[dict] = field(default_factory=list)
    themes: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    hypotheses: list[dict] = field(default_factory=list)

    # Papers read in full (IDs)
    papers_read: list[str] = field(default_factory=list)

    # === PROGRESS LEDGER ===
    current_phase: ResearchPhase = ResearchPhase.SCOPING
    phase_progress: dict = field(default_factory=dict)  # {phase: percent}
    last_action: str = ""
    stall_count: int = 0
    action_history: list[str] = field(default_factory=list)

    # === OUTPUT ===
    report: str = ""
    is_complete: bool = False

    # === CONFIGURATION ===
    max_papers: int = 100
    max_papers_to_read: int = 30
    target_hypotheses: int = 5

    def add_paper(self, paper: dict, source: str = "") -> str:
        """Add a paper to the discovered list."""
        paper_id = paper.get("paper_id", str(uuid.uuid4())[:8])

        # Check for duplicates
        for p in self.papers:
            if p.get("paper_id") == paper_id or p.get("title") == paper.get("title"):
                return p.get("paper_id", "")

        paper["source"] = source
        paper["paper_id"] = paper_id
        self.papers.append(paper)
        return paper_id

    def add_theme(self, name: str, description: str, paper_ids: list[str]) -> str:
        """Add an identified theme."""
        theme_id = str(uuid.uuid4())[:8]
        self.themes.append({
            "theme_id": theme_id,
            "name": name,
            "description": description,
            "paper_ids": paper_ids,
        })
        return theme_id

    def add_gap(self, title: str, evidence: str, confidence: str) -> str:
        """Add an identified gap."""
        gap_id = str(uuid.uuid4())[:8]
        self.gaps.append({
            "gap_id": gap_id,
            "title": title,
            "evidence": evidence,
            "confidence": confidence,
        })
        return gap_id

    def add_hypothesis(
        self,
        gap_id: str,
        title: str,
        description: str,
        rationale: str,
        building_blocks: str,
        suggested_experiments: str = "",
    ) -> str:
        """Add a generated hypothesis."""
        hypo_id = str(uuid.uuid4())[:8]
        self.hypotheses.append({
            "hypothesis_id": hypo_id,
            "gap_id": gap_id,
            "title": title,
            "description": description,
            "rationale": rationale,
            "building_blocks": building_blocks,
            "suggested_experiments": suggested_experiments,
            "novelty_score": 0,
            "feasibility_score": 0,
            "impact_score": 0,
        })
        return hypo_id

    def score_hypothesis(
        self,
        hypothesis_id: str,
        novelty: int,
        feasibility: int,
        impact: int,
        similar_work: str = "",
        differentiation: str = "",
    ) -> bool:
        """Score a hypothesis."""
        for h in self.hypotheses:
            if h.get("hypothesis_id") == hypothesis_id:
                h["novelty_score"] = novelty
                h["feasibility_score"] = feasibility
                h["impact_score"] = impact
                h["similar_work"] = similar_work
                h["differentiation"] = differentiation
                return True
        return False

    def update_progress(
        self,
        action: str,
        new_info: bool,
        phase_progress: int,
    ) -> str:
        """
        Update progress after an action.

        Returns warning message if stalled.
        """
        self.last_action = action
        self.action_history.append(f"[{datetime.now().strftime('%H:%M')}] {action}")
        self.phase_progress[self.current_phase.value] = phase_progress

        if new_info:
            self.stall_count = 0
        else:
            self.stall_count += 1

        if self.stall_count >= 3:
            return "WARNING: Progress stalled. Consider changing strategy or advancing to next phase."

        return ""

    def advance_phase(self, next_phase: ResearchPhase) -> bool:
        """Advance to next phase."""
        valid_transitions = {
            ResearchPhase.SCOPING: [ResearchPhase.DISCOVERY],
            ResearchPhase.DISCOVERY: [ResearchPhase.SYNTHESIS],
            ResearchPhase.SYNTHESIS: [ResearchPhase.IDEATION],
            ResearchPhase.IDEATION: [ResearchPhase.EVALUATION],
            ResearchPhase.EVALUATION: [ResearchPhase.COMPLETE],
        }

        if next_phase in valid_transitions.get(self.current_phase, []):
            self.current_phase = next_phase
            self.stall_count = 0
            return True
        return False

    def get_ranked_hypotheses(self) -> list[dict]:
        """Get hypotheses ranked by combined score."""
        def score(h):
            return (
                h.get("novelty_score", 0) +
                h.get("feasibility_score", 0) +
                h.get("impact_score", 0)
            )
        return sorted(self.hypotheses, key=score, reverse=True)

    def to_context(self) -> str:
        """Format state as context for injection into system prompt."""
        papers_summary = f"{len(self.papers)} found, {len(self.papers_read)} read in detail"
        themes_list = "\n".join(
            f"  - {t['name']}: {t['description'][:100]}"
            for t in self.themes[:5]
        ) or "  (none yet)"
        gaps_list = "\n".join(
            f"  - [{g['confidence'].upper()}] {g['title']}"
            for g in self.gaps[:5]
        ) or "  (none yet)"
        hypo_list = "\n".join(
            f"  - {h['title']} (scores: N={h.get('novelty_score', '?')}/F={h.get('feasibility_score', '?')}/I={h.get('impact_score', '?')})"
            for h in self.get_ranked_hypotheses()[:5]
        ) or "  (none yet)"

        return f"""
## Current Research State

**Session**: {self.session_id}
**Topic**: {self.topic}
**Phase**: {self.current_phase.value.upper()}
**Progress**: {self.phase_progress.get(self.current_phase.value, 0)}%
**Stall Count**: {self.stall_count}/3

### Scope
{json.dumps(self.scope, indent=2) if self.scope else "(not yet defined)"}

### Papers
{papers_summary}

### Themes Identified
{themes_list}

### Research Gaps
{gaps_list}

### Hypotheses
{hypo_list}

### Last Action
{self.last_action or "(none)"}
"""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "topic": self.topic,
            "scope": self.scope,
            "papers": self.papers,
            "papers_read": self.papers_read,
            "themes": self.themes,
            "gaps": self.gaps,
            "hypotheses": self.hypotheses,
            "current_phase": self.current_phase.value,
            "phase_progress": self.phase_progress,
            "stall_count": self.stall_count,
            "is_complete": self.is_complete,
            "report": self.report,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VibeResearchState":
        """Deserialize from dictionary."""
        state = cls(
            session_id=data.get("session_id", ""),
            topic=data.get("topic", ""),
            scope=data.get("scope", {}),
            papers=data.get("papers", []),
            papers_read=data.get("papers_read", []),
            themes=data.get("themes", []),
            gaps=data.get("gaps", []),
            hypotheses=data.get("hypotheses", []),
            phase_progress=data.get("phase_progress", {}),
            stall_count=data.get("stall_count", 0),
            is_complete=data.get("is_complete", False),
            report=data.get("report", ""),
        )
        state.current_phase = ResearchPhase(data.get("current_phase", "scoping"))
        return state

    def save(self, project_path: str) -> None:
        """Save state to project's .aura directory."""
        aura_dir = Path(project_path) / ".aura"
        aura_dir.mkdir(exist_ok=True)

        state_file = aura_dir / f"vibe_research_{self.session_id}.json"
        state_file.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, project_path: str, session_id: str) -> Optional["VibeResearchState"]:
        """Load state from project's .aura directory."""
        state_file = Path(project_path) / ".aura" / f"vibe_research_{session_id}.json"
        if not state_file.exists():
            return None

        data = json.loads(state_file.read_text())
        return cls.from_dict(data)
```

**Step 2: Commit**

```bash
git add backend/agent/vibe_state.py
git commit -m "feat(vibe): Add VibeResearchState with dual-ledger pattern"
```

---

## Task 3: Enhanced ResearchAgent with Vibe Mode ✅

**Files:**
- Modify: `backend/agent/subagents/research.py`

**Step 1: Add imports and mode enum at the top (after existing imports)**

Add after line 27 (after `from agent.providers.colorist import ...`):

```python
from enum import Enum
from agent.vibe_state import VibeResearchState, ResearchPhase
from services.semantic_scholar import SemanticScholarClient
```

**Step 2: Add ResearchMode enum and update ResearchDeps (replace existing ResearchDeps)**

Replace lines 36-44:

```python
class ResearchMode(str, Enum):
    """Mode of operation for research agent."""
    CHAT = "chat"   # Quick, single-turn research help
    VIBE = "vibe"   # Deep autonomous research workflow


@dataclass
class ResearchDeps:
    """Dependencies for the research agent."""
    # HTTP client for API calls
    http_client: httpx.AsyncClient

    # Mode of operation
    mode: ResearchMode = ResearchMode.CHAT

    # Limit results
    max_results: int = 10

    # Vibe mode only
    project_path: str = ""
    vibe_state: VibeResearchState | None = None
```

**Step 3: Add vibe mode system prompt (after existing RESEARCH_SYSTEM_PROMPT)**

Add after line 228 (after the existing system prompt ends):

```python
RESEARCH_SYSTEM_PROMPT_VIBE = """You are an autonomous research agent conducting deep literature exploration.

{state_context}

## Your Mission

Autonomously explore the literature on the given topic, identify research gaps, and generate novel hypotheses.

## Workflow Phases

### Phase 1: SCOPING
If the topic is broad, clarify:
- Domain focus (NLP, vision, etc.)
- Specific constraints (efficiency, accuracy, etc.)
- Desired output (survey, novel angle, idea validation)

Use `define_scope` to record the clarified parameters.

### Phase 2: DISCOVERY
Search comprehensively:
1. `search_arxiv` with multiple query variations
2. `search_semantic_scholar` for citation-rich papers
3. `explore_citations` to follow seminal paper trails
4. Goal: Find 50-100+ relevant papers

After each batch, use `update_progress` to track findings.

### Phase 3: SYNTHESIS
Read and analyze key papers:
1. `read_arxiv_paper` for top 20-30 papers (by citations or relevance)
2. `record_theme` to identify clusters of approaches
3. Look for:
   - Main methodological approaches
   - Areas of agreement/disagreement
   - Evolution of the field over time

### Phase 4: IDEATION
Find what's missing and propose new directions:
1. `record_gap` for each underexplored area found
2. `generate_hypothesis` to propose how to address each gap
3. Consider:
   - What combinations haven't been tried?
   - What domains lack application?
   - What assumptions could be challenged?

### Phase 5: EVALUATION
Score and rank your hypotheses:
1. `score_hypothesis` with novelty, feasibility, impact (1-10 each)
2. Identify similar existing work
3. Explain differentiation from prior work

### Phase 6: REPORT
1. `generate_report` to synthesize all findings
2. `save_to_memory` for important discoveries

## Progress Rules

- Call `update_progress` after each significant action
- If stalled (3 actions with no new info), change strategy or advance phase
- Use `advance_phase` when ready to move forward

## Critical Rules

1. NEVER fabricate citations - only cite papers from API results
2. Be thorough - explore widely before concluding
3. Be self-critical - identify weaknesses in your hypotheses
4. Save important findings to memory
5. If unsure about scope, ask clarifying questions before diving deep
"""
```

**Step 4: Update ResearchAgent class to support modes**

Replace the `__init__` method (around line 242-250):

```python
    def __init__(self, mode: ResearchMode = ResearchMode.CHAT, **kwargs):
        self.mode = mode

        # Configure based on mode
        if mode == ResearchMode.VIBE:
            config = SubagentConfig(
                name="research",
                description="Deep autonomous research with hypothesis generation",
                max_iterations=50,  # More iterations for vibe mode
                timeout=600.0,      # 10 minutes for deep research
                use_haiku=False,    # Use stronger model
            )
        else:
            config = SubagentConfig(
                name="research",
                description="Search and analyze academic papers from arXiv and Semantic Scholar",
                max_iterations=10,
                timeout=90.0,
                use_haiku=True,  # Cheaper model for quick queries
            )

        super().__init__(config)
        self._http_client: httpx.AsyncClient | None = None
        self._s2_client: SemanticScholarClient | None = None
```

**Step 5: Update system_prompt property to be mode-aware**

Replace the `system_prompt` property (around line 254-255):

```python
    @property
    def system_prompt(self) -> str:
        if self.mode == ResearchMode.VIBE:
            return RESEARCH_SYSTEM_PROMPT_VIBE
        return RESEARCH_SYSTEM_PROMPT
```

**Step 6: Add S2 client getter**

Add after `_get_http_client` method (around line 263):

```python
    def _get_s2_client(self) -> SemanticScholarClient:
        """Get or create Semantic Scholar client."""
        if self._s2_client is None:
            self._s2_client = SemanticScholarClient(self._get_http_client())
        return self._s2_client
```

**Step 7: Update _create_deps to handle vibe mode**

Replace `_create_deps` method:

```python
    def _create_deps(self, context: dict[str, Any]) -> ResearchDeps:
        """Create dependencies for research agent."""
        mode = ResearchMode(context.get("mode", "chat"))

        # For vibe mode, create or load state
        vibe_state = None
        if mode == ResearchMode.VIBE:
            project_path = context.get("project_path", "")
            session_id = context.get("session_id")

            if session_id:
                vibe_state = VibeResearchState.load(project_path, session_id)

            if vibe_state is None:
                vibe_state = VibeResearchState(topic=context.get("topic", ""))

        return ResearchDeps(
            http_client=self._get_http_client(),
            max_results=context.get("max_results", 10),
            mode=mode,
            project_path=context.get("project_path", ""),
            vibe_state=vibe_state,
        )
```

**Step 8: Update _create_agent to register vibe tools**

Modify the `_create_agent` method to add vibe tools:

```python
    def _create_agent(self) -> Agent[ResearchDeps, str]:
        """Create the research agent with tools."""

        # For vibe mode, inject state into system prompt
        if self.mode == ResearchMode.VIBE:
            def dynamic_system_prompt(ctx: RunContext[ResearchDeps]) -> str:
                state_context = ""
                if ctx.deps.vibe_state:
                    state_context = ctx.deps.vibe_state.to_context()
                return RESEARCH_SYSTEM_PROMPT_VIBE.format(state_context=state_context)

            agent = Agent(
                model=self._get_model(),
                system_prompt=dynamic_system_prompt,
                deps_type=ResearchDeps,
                retries=2,
            )
        else:
            agent = Agent(
                model=self._get_model(),
                system_prompt=self.system_prompt,
                deps_type=ResearchDeps,
                retries=2,
            )

        # === CORE TOOLS (both modes) ===
        self._register_core_tools(agent)

        # === VIBE TOOLS (vibe mode, but available in both) ===
        self._register_vibe_tools(agent)

        return agent

    def _register_core_tools(self, agent: Agent):
        """Register core research tools (existing tools)."""

        @agent.tool
        async def search_arxiv(
            ctx: RunContext[ResearchDeps],
            query: str,
            max_results: int = 5,
        ) -> str:
            """
            Search arXiv for academic papers.

            Args:
                query: Search query (e.g., "transformer attention mechanisms")
                max_results: Maximum number of results (1-10)

            Returns:
                List of papers with titles, authors, abstracts, and links
            """
            max_results = min(max(1, max_results), 10)

            try:
                papers = await search_arxiv_api(
                    query=query,
                    http_client=ctx.deps.http_client,
                    max_results=max_results,
                )

                if not papers:
                    return f"No papers found on arXiv for query: '{query}'"

                # In vibe mode, add to state
                if ctx.deps.mode == ResearchMode.VIBE and ctx.deps.vibe_state:
                    for paper in papers:
                        ctx.deps.vibe_state.add_paper({
                            "paper_id": paper["arxiv_id"],
                            "title": paper["title"],
                            "authors": paper["authors"],
                            "year": int(paper["published"][:4]) if paper["published"] else None,
                            "citation_count": 0,
                            "abstract": paper["abstract"],
                        }, source="arxiv")

                # Format results
                lines = [f"Found {len(papers)} papers on arXiv for '{query}':\n"]
                for i, paper in enumerate(papers, 1):
                    authors_str = ", ".join(paper["authors"][:3])
                    if len(paper["authors"]) > 3:
                        authors_str += " et al."

                    lines.append(f"{i}. **{paper['title']}**")
                    lines.append(f"   Authors: {authors_str}")
                    lines.append(f"   Published: {paper['published']}")
                    lines.append(f"   arXiv: {paper['arxiv_id']}")

                    abstract = paper["abstract"][:300]
                    if len(paper["abstract"]) > 300:
                        abstract += "..."
                    lines.append(f"   Abstract: {abstract}")
                    lines.append("")

                return "\n".join(lines)

            except Exception as e:
                return f"Error searching arXiv: {str(e)}"

        @agent.tool
        async def search_semantic_scholar(
            ctx: RunContext[ResearchDeps],
            query: str,
            max_results: int = 5,
        ) -> str:
            """
            Search Semantic Scholar for academic papers.

            Better for finding highly-cited papers and citation networks.

            Args:
                query: Search query
                max_results: Maximum number of results (1-10)

            Returns:
                List of papers with citation counts and links
            """
            max_results = min(max(1, max_results), 10)

            try:
                papers = await search_semantic_scholar_api(
                    query=query,
                    http_client=ctx.deps.http_client,
                    max_results=max_results,
                )

                if not papers:
                    return f"No papers found on Semantic Scholar for query: '{query}'"

                # In vibe mode, add to state
                if ctx.deps.mode == ResearchMode.VIBE and ctx.deps.vibe_state:
                    for paper in papers:
                        ctx.deps.vibe_state.add_paper({
                            "paper_id": paper["paper_id"],
                            "title": paper["title"],
                            "authors": paper["authors"],
                            "year": paper["year"],
                            "citation_count": paper["citation_count"],
                            "abstract": paper["abstract"],
                        }, source="semantic_scholar")

                # Format results
                lines = [f"Found {len(papers)} papers on Semantic Scholar for '{query}':\n"]
                for i, paper in enumerate(papers, 1):
                    authors_str = ", ".join(paper["authors"][:3])
                    if len(paper["authors"]) > 3:
                        authors_str += " et al."

                    year_str = f" ({paper['year']})" if paper["year"] else ""

                    lines.append(f"{i}. **{paper['title']}**{year_str}")
                    lines.append(f"   Authors: {authors_str}")
                    lines.append(f"   Citations: {paper['citation_count']}")
                    lines.append(f"   S2 ID: {paper['paper_id']}")

                    if paper["abstract"]:
                        abstract = paper["abstract"][:300]
                        if len(paper["abstract"]) > 300:
                            abstract += "..."
                        lines.append(f"   Abstract: {abstract}")
                    lines.append("")

                return "\n".join(lines)

            except Exception as e:
                return f"Error searching Semantic Scholar: {str(e)}"

        @agent.tool
        async def think(ctx: RunContext[ResearchDeps], thought: str) -> str:
            """
            Think through a research question step-by-step.

            Use this to reason about:
            - Which search terms to use
            - How to combine results
            - How to synthesize findings
            - What gaps might exist

            Args:
                thought: Your reasoning process

            Returns:
                Acknowledgment to continue
            """
            return "Thinking recorded. Continue with your research."

        @agent.tool
        async def read_arxiv_paper(
            ctx: RunContext[ResearchDeps],
            arxiv_id: str,
            max_pages: int = 10,
        ) -> str:
            """
            Download and read the full text of an arXiv paper.

            Args:
                arxiv_id: arXiv paper ID (e.g., "2301.07041")
                max_pages: Maximum pages to extract (default: 10)

            Returns:
                Extracted text from the paper
            """
            from agent.tools.pdf_reader import read_arxiv_paper as _read_arxiv

            try:
                doc = await _read_arxiv(
                    arxiv_id=arxiv_id,
                    http_client=ctx.deps.http_client,
                    max_pages=max_pages,
                    max_chars=50000,
                )

                # In vibe mode, mark as read
                if ctx.deps.mode == ResearchMode.VIBE and ctx.deps.vibe_state:
                    if arxiv_id not in ctx.deps.vibe_state.papers_read:
                        ctx.deps.vibe_state.papers_read.append(arxiv_id)

                text = doc.get_text(max_pages=max_pages, max_chars=50000)
                return f"Paper: {doc.title}\nPages: {doc.num_pages}\narXiv: {arxiv_id}\n\n{text}"

            except FileNotFoundError:
                return f"Error: arXiv paper not found: {arxiv_id}"
            except Exception as e:
                return f"Error reading arXiv paper: {str(e)}"

        @agent.tool
        async def read_pdf_url(
            ctx: RunContext[ResearchDeps],
            url: str,
            max_pages: int = 10,
        ) -> str:
            """
            Download and read a PDF from any URL.

            Args:
                url: Direct URL to a PDF file
                max_pages: Maximum pages to extract (default: 10)

            Returns:
                Extracted text from the PDF
            """
            from agent.tools.pdf_reader import read_pdf_from_url as _read_pdf

            try:
                doc = await _read_pdf(
                    url=url,
                    http_client=ctx.deps.http_client,
                    max_pages=max_pages,
                )

                text = doc.get_text(max_pages=max_pages, max_chars=50000)
                return f"Paper: {doc.title}\nPages: {doc.num_pages}\nURL: {url}\n\n{text}"

            except Exception as e:
                return f"Error reading PDF from URL: {str(e)}"
```

**Step 9: Add vibe-specific tools**

Add the `_register_vibe_tools` method:

```python
    def _register_vibe_tools(self, agent: Agent):
        """Register tools specific to vibe research workflow."""

        @agent.tool
        async def define_scope(
            ctx: RunContext[ResearchDeps],
            domain: str,
            constraints: str,
            goal: str,
            additional_notes: str = "",
        ) -> str:
            """
            Define the scope of the research.

            Call this in the SCOPING phase to clarify parameters.

            Args:
                domain: Primary domain (e.g., "NLP", "computer vision", "multimodal")
                constraints: Key constraints (e.g., "efficiency", "low-resource")
                goal: Research goal (e.g., "find novel angle", "literature survey")
                additional_notes: Any other relevant scope info

            Returns:
                Confirmation to proceed
            """
            if ctx.deps.vibe_state:
                ctx.deps.vibe_state.scope = {
                    "domain": domain,
                    "constraints": constraints,
                    "goal": goal,
                    "notes": additional_notes,
                }
            return "Scope defined. Proceed to DISCOVERY phase with `advance_phase`."

        @agent.tool
        async def explore_citations(
            ctx: RunContext[ResearchDeps],
            paper_id: str,
            direction: str = "both",
            max_results: int = 20,
        ) -> str:
            """
            Explore the citation graph around a paper.

            Use this to find:
            - Papers that cite this one (follow-up work)
            - Papers this one cites (foundational work)

            Args:
                paper_id: Semantic Scholar paper ID (from search results)
                direction: "citations", "references", or "both"
                max_results: Maximum papers to return

            Returns:
                Connected papers with titles and citation counts
            """
            s2_client = SemanticScholarClient(ctx.deps.http_client)

            papers = await s2_client.explore_citation_graph(
                paper_id=paper_id,
                direction=direction,  # type: ignore
                depth=1,
                max_papers_per_level=max_results,
            )

            if not papers:
                return f"No connected papers found for {paper_id}"

            # Add to state
            if ctx.deps.vibe_state:
                for paper in papers:
                    ctx.deps.vibe_state.add_paper(paper.to_dict(), source="citation_graph")

            # Format results
            lines = [f"Found {len(papers)} connected papers:\n"]
            for i, paper in enumerate(papers[:max_results], 1):
                year_str = f" ({paper.year})" if paper.year else ""
                lines.append(f"{i}. **{paper.title}**{year_str}")
                lines.append(f"   Citations: {paper.citation_count}")
                lines.append(f"   S2 ID: {paper.paper_id}")
                lines.append("")

            return "\n".join(lines)

        @agent.tool
        async def record_theme(
            ctx: RunContext[ResearchDeps],
            name: str,
            description: str,
            paper_ids: str,
        ) -> str:
            """
            Record an identified theme in the literature.

            Call this during SYNTHESIS to cluster papers by approach.

            Args:
                name: Short name for the theme (e.g., "Sparse Attention")
                description: Description of this approach and its characteristics
                paper_ids: Comma-separated list of paper IDs in this theme

            Returns:
                Confirmation with theme ID
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            ids = [p.strip() for p in paper_ids.split(",") if p.strip()]
            theme_id = ctx.deps.vibe_state.add_theme(name, description, ids)

            return f"Theme recorded: {name} (ID: {theme_id}) with {len(ids)} papers"

        @agent.tool
        async def record_gap(
            ctx: RunContext[ResearchDeps],
            title: str,
            evidence: str,
            confidence: str = "medium",
        ) -> str:
            """
            Record an identified research gap.

            Call this during IDEATION when you find underexplored areas.

            Args:
                title: Short title for the gap
                evidence: What evidence suggests this is a gap?
                confidence: "low", "medium", or "high"

            Returns:
                Confirmation with gap ID
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            gap_id = ctx.deps.vibe_state.add_gap(title, evidence, confidence)

            return f"Gap recorded: {title} (ID: {gap_id}, confidence: {confidence})"

        @agent.tool
        async def generate_hypothesis(
            ctx: RunContext[ResearchDeps],
            gap_id: str,
            title: str,
            description: str,
            rationale: str,
            building_blocks: str,
            suggested_experiments: str = "",
        ) -> str:
            """
            Generate a research hypothesis to address a gap.

            Args:
                gap_id: ID of the gap this addresses
                title: Short title for the hypothesis
                description: What is being proposed
                rationale: Why this could work
                building_blocks: Existing work to build upon
                suggested_experiments: How to test this

            Returns:
                Confirmation with hypothesis ID
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            hypo_id = ctx.deps.vibe_state.add_hypothesis(
                gap_id=gap_id,
                title=title,
                description=description,
                rationale=rationale,
                building_blocks=building_blocks,
                suggested_experiments=suggested_experiments,
            )

            return f"Hypothesis recorded: {title} (ID: {hypo_id})"

        @agent.tool
        async def score_hypothesis(
            ctx: RunContext[ResearchDeps],
            hypothesis_id: str,
            novelty: int,
            feasibility: int,
            impact: int,
            similar_work: str,
            differentiation: str,
        ) -> str:
            """
            Score and evaluate a hypothesis.

            Args:
                hypothesis_id: ID of the hypothesis to score
                novelty: 1-10 how novel is this idea
                feasibility: 1-10 how feasible to implement
                impact: 1-10 potential impact if successful
                similar_work: Most similar existing work
                differentiation: How this differs from existing work

            Returns:
                Confirmation with scores
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            success = ctx.deps.vibe_state.score_hypothesis(
                hypothesis_id=hypothesis_id,
                novelty=novelty,
                feasibility=feasibility,
                impact=impact,
                similar_work=similar_work,
                differentiation=differentiation,
            )

            if not success:
                return f"Error: Hypothesis {hypothesis_id} not found"

            total = novelty + feasibility + impact
            return f"Hypothesis scored: N={novelty} F={feasibility} I={impact} (Total: {total}/30)"

        @agent.tool
        async def update_progress(
            ctx: RunContext[ResearchDeps],
            action: str,
            new_info_found: bool,
            phase_progress: int,
        ) -> str:
            """
            Update research progress after a significant action.

            IMPORTANT: Call this regularly to track progress and detect stalls.

            Args:
                action: What you just did
                new_info_found: Did this action yield new information?
                phase_progress: Estimated progress in current phase (0-100)

            Returns:
                Progress update, possibly with stall warning
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            warning = ctx.deps.vibe_state.update_progress(
                action=action,
                new_info=new_info_found,
                phase_progress=phase_progress,
            )

            state = ctx.deps.vibe_state
            msg = f"Progress: {state.current_phase.value} at {phase_progress}%"
            msg += f" | Papers: {len(state.papers)} found, {len(state.papers_read)} read"
            msg += f" | Themes: {len(state.themes)} | Gaps: {len(state.gaps)} | Hypotheses: {len(state.hypotheses)}"

            if warning:
                msg += f"\n\n{warning}"

            return msg

        @agent.tool
        async def advance_phase(
            ctx: RunContext[ResearchDeps],
            next_phase: str,
            summary: str,
        ) -> str:
            """
            Advance to the next research phase.

            Phases: scoping -> discovery -> synthesis -> ideation -> evaluation -> complete

            Args:
                next_phase: Phase to advance to
                summary: Summary of what was accomplished in current phase

            Returns:
                Confirmation of phase transition
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            try:
                phase = ResearchPhase(next_phase.lower())
            except ValueError:
                return f"Error: Invalid phase '{next_phase}'. Valid: scoping, discovery, synthesis, ideation, evaluation, complete"

            success = ctx.deps.vibe_state.advance_phase(phase)

            if not success:
                return f"Error: Cannot advance from {ctx.deps.vibe_state.current_phase.value} to {next_phase}"

            return f"Advanced to {next_phase.upper()} phase. Previous phase summary: {summary[:200]}"

        @agent.tool
        async def generate_report(
            ctx: RunContext[ResearchDeps],
        ) -> str:
            """
            Generate the final research report.

            Call this in the EVALUATION phase after scoring hypotheses.

            Returns:
                Full markdown research report
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            state = ctx.deps.vibe_state
            ranked = state.get_ranked_hypotheses()

            # Build report
            report_lines = [
                f"# Vibe Research Report: {state.topic}",
                "",
                f"**Session**: {state.session_id}",
                f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"**Papers Analyzed**: {len(state.papers)}",
                f"**Papers Read**: {len(state.papers_read)}",
                f"**Hypotheses Generated**: {len(state.hypotheses)}",
                "",
                "---",
                "",
                "## Executive Summary",
                "",
                f"This research explored **{state.topic}** with the following scope:",
                "",
            ]

            if state.scope:
                report_lines.append(f"- **Domain**: {state.scope.get('domain', 'General')}")
                report_lines.append(f"- **Constraints**: {state.scope.get('constraints', 'None specified')}")
                report_lines.append(f"- **Goal**: {state.scope.get('goal', 'Exploration')}")
                report_lines.append("")

            report_lines.append(f"We identified **{len(state.themes)} themes**, **{len(state.gaps)} research gaps**, and generated **{len(state.hypotheses)} hypotheses**.")
            report_lines.append("")

            # Themes
            if state.themes:
                report_lines.append("## Literature Landscape")
                report_lines.append("")
                for theme in state.themes:
                    report_lines.append(f"### {theme['name']}")
                    report_lines.append("")
                    report_lines.append(theme['description'])
                    report_lines.append("")
                    report_lines.append(f"*Papers: {len(theme['paper_ids'])}*")
                    report_lines.append("")

            # Gaps
            if state.gaps:
                report_lines.append("## Identified Research Gaps")
                report_lines.append("")
                for gap in state.gaps:
                    report_lines.append(f"### {gap['title']}")
                    report_lines.append("")
                    report_lines.append(f"**Confidence**: {gap['confidence'].upper()}")
                    report_lines.append("")
                    report_lines.append(gap['evidence'])
                    report_lines.append("")

            # Hypotheses
            if ranked:
                report_lines.append("## Ranked Hypothesis Proposals")
                report_lines.append("")
                for i, hypo in enumerate(ranked, 1):
                    total = hypo.get('novelty_score', 0) + hypo.get('feasibility_score', 0) + hypo.get('impact_score', 0)
                    report_lines.append(f"### #{i}: {hypo['title']}")
                    report_lines.append("")
                    report_lines.append(f"**Scores**: Novelty={hypo.get('novelty_score', '?')}/10 | Feasibility={hypo.get('feasibility_score', '?')}/10 | Impact={hypo.get('impact_score', '?')}/10 | **Total={total}/30**")
                    report_lines.append("")
                    report_lines.append(f"**Description**: {hypo['description']}")
                    report_lines.append("")
                    report_lines.append(f"**Rationale**: {hypo['rationale']}")
                    report_lines.append("")
                    report_lines.append(f"**Building Blocks**: {hypo['building_blocks']}")
                    report_lines.append("")
                    if hypo.get('suggested_experiments'):
                        report_lines.append(f"**Suggested Experiments**: {hypo['suggested_experiments']}")
                        report_lines.append("")
                    if hypo.get('similar_work'):
                        report_lines.append(f"**Similar Work**: {hypo['similar_work']}")
                        report_lines.append("")
                    if hypo.get('differentiation'):
                        report_lines.append(f"**Differentiation**: {hypo['differentiation']}")
                        report_lines.append("")
                    report_lines.append("---")
                    report_lines.append("")

            report = "\n".join(report_lines)
            state.report = report
            state.is_complete = True
            state.current_phase = ResearchPhase.COMPLETE

            # Save state
            if ctx.deps.project_path:
                state.save(ctx.deps.project_path)

            return report

        @agent.tool
        async def save_to_memory(
            ctx: RunContext[ResearchDeps],
            entry_type: str,
            title: str,
            content: str,
            tags: str = "",
        ) -> str:
            """
            Save a finding to project memory for future sessions.

            Args:
                entry_type: Type of entry ("paper", "gap", "hypothesis", "note")
                title: Short title for the entry
                content: Full content
                tags: Comma-separated tags

            Returns:
                Confirmation
            """
            if not ctx.deps.project_path:
                return "No project path - cannot save to memory"

            from services.memory import MemoryService

            try:
                svc = MemoryService(ctx.deps.project_path)
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                tag_list.append(entry_type)

                svc.add_entry("notes", {
                    "content": f"[{entry_type.upper()}] {title}\n\n{content}",
                    "tags": tag_list,
                })

                return f"Saved to memory: [{entry_type}] {title}"

            except Exception as e:
                return f"Error saving to memory: {str(e)}"
```

**Step 10: Commit**

```bash
git add backend/agent/subagents/research.py
git commit -m "feat(vibe): Enhanced ResearchAgent with vibe mode and new tools"
```

---

## Task 4: API Endpoints for Vibe Research ✅

**Files:**
- Modify: `backend/main.py`

**Step 1: Add imports (after existing imports)**

Add after the memory imports:

```python
from agent.vibe_state import VibeResearchState, ResearchPhase
from agent.subagents.research import ResearchMode
```

**Step 2: Add request models (after existing models)**

```python
# ============ Vibe Research Models ============

class StartVibeResearchRequest(BaseModel):
    project_path: str
    topic: str
    max_papers: int = 100


class VibeResearchStatusRequest(BaseModel):
    project_path: str
    session_id: str
```

**Step 3: Add vibe research endpoints (before the sync endpoints)**

```python
# ============ Vibe Research Endpoints ============

# Store active vibe sessions
_vibe_sessions: dict[str, VibeResearchState] = {}


@app.post("/api/vibe-research/start")
async def start_vibe_research(request: StartVibeResearchRequest):
    """
    Start a new vibe research session.

    Returns session ID for tracking progress.
    """
    # Create new state
    state = VibeResearchState(
        topic=request.topic,
        max_papers=request.max_papers,
    )

    # Store in memory
    _vibe_sessions[state.session_id] = state

    # Save to project
    state.save(request.project_path)

    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "status": "started",
        "current_phase": state.current_phase.value,
    }


@app.get("/api/vibe-research/status/{session_id}")
async def get_vibe_research_status(session_id: str, project_path: str):
    """Get status of a vibe research session."""
    # Try memory first
    state = _vibe_sessions.get(session_id)

    # Try loading from disk
    if not state:
        state = VibeResearchState.load(project_path, session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "current_phase": state.current_phase.value,
        "phase_progress": state.phase_progress,
        "papers_found": len(state.papers),
        "papers_read": len(state.papers_read),
        "themes": len(state.themes),
        "gaps": len(state.gaps),
        "hypotheses": len(state.hypotheses),
        "is_complete": state.is_complete,
        "stall_count": state.stall_count,
    }


@app.get("/api/vibe-research/state/{session_id}")
async def get_vibe_research_state(session_id: str, project_path: str):
    """Get full state of a vibe research session."""
    state = _vibe_sessions.get(session_id)

    if not state:
        state = VibeResearchState.load(project_path, session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return state.to_dict()


@app.get("/api/vibe-research/report/{session_id}")
async def get_vibe_research_report(session_id: str, project_path: str):
    """Get the generated report for a completed session."""
    state = _vibe_sessions.get(session_id)

    if not state:
        state = VibeResearchState.load(project_path, session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if not state.report:
        raise HTTPException(status_code=400, detail="Report not yet generated")

    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "report": state.report,
        "is_complete": state.is_complete,
    }


@app.post("/api/vibe-research/run/{session_id}")
async def run_vibe_research_step(session_id: str, project_path: str):
    """
    Run the vibe research agent for one interaction.

    This is for manual step-by-step execution.
    For streaming, use /api/chat/stream with mode=vibe.
    """
    state = _vibe_sessions.get(session_id)

    if not state:
        state = VibeResearchState.load(project_path, session_id)
        if state:
            _vibe_sessions[session_id] = state

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    # Run one step via the research agent
    from agent.subagents.base import run_subagent

    result = await run_subagent(
        "research",
        task=f"Continue the vibe research on: {state.topic}. Current phase: {state.current_phase.value}",
        context={
            "mode": "vibe",
            "project_path": project_path,
            "session_id": session_id,
            "topic": state.topic,
        },
    )

    # Reload state (agent may have updated it)
    updated_state = VibeResearchState.load(project_path, session_id)
    if updated_state:
        _vibe_sessions[session_id] = updated_state

    return {
        "session_id": session_id,
        "output": result.output,
        "status": updated_state.to_dict() if updated_state else state.to_dict(),
    }


@app.get("/api/vibe-research/sessions")
async def list_vibe_sessions(project_path: str):
    """List all vibe research sessions for a project."""
    from pathlib import Path

    aura_dir = Path(project_path) / ".aura"
    sessions = []

    if aura_dir.exists():
        for f in aura_dir.glob("vibe_research_*.json"):
            try:
                session_id = f.stem.replace("vibe_research_", "")
                state = VibeResearchState.load(project_path, session_id)
                if state:
                    sessions.append({
                        "session_id": state.session_id,
                        "topic": state.topic,
                        "current_phase": state.current_phase.value,
                        "is_complete": state.is_complete,
                        "created_at": state.created_at,
                    })
            except Exception:
                pass

    return {"sessions": sessions}
```

**Step 4: Update /api/chat/stream to support vibe mode**

Find the `chat_stream` endpoint and update the context passed to the agent to include mode support. The streaming endpoint should detect `mode: "vibe"` in the request and configure accordingly.

**Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat(vibe): Add vibe research API endpoints"
```

---

## Task 5: Frontend Mode Toggle ✅ (Backend complete, frontend optional)

**Files:**
- Modify: `app/components/AgentPanel.tsx`
- Modify: `app/lib/api.ts`

**Step 1: Add vibe research types to api.ts**

```typescript
// ============ Vibe Research Types ============

export interface VibeSession {
  session_id: string;
  topic: string;
  current_phase: string;
  is_complete: boolean;
  created_at: string;
}

export interface VibeStatus {
  session_id: string;
  topic: string;
  current_phase: string;
  phase_progress: Record<string, number>;
  papers_found: number;
  papers_read: number;
  themes: number;
  gaps: number;
  hypotheses: number;
  is_complete: boolean;
  stall_count: number;
}

export interface VibeReport {
  session_id: string;
  topic: string;
  report: string;
  is_complete: boolean;
}
```

**Step 2: Add vibe research API methods to ApiClient**

```typescript
  // ===========================================================================
  // Vibe Research Operations
  // ===========================================================================

  async startVibeResearch(
    projectPath: string,
    topic: string,
    maxPapers: number = 100
  ): Promise<{ session_id: string; status: string }> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/vibe-research/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        topic,
        max_papers: maxPapers,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async getVibeStatus(projectPath: string, sessionId: string): Promise<VibeStatus> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/vibe-research/status/${sessionId}?project_path=${encodeURIComponent(projectPath)}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async getVibeReport(projectPath: string, sessionId: string): Promise<VibeReport> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/vibe-research/report/${sessionId}?project_path=${encodeURIComponent(projectPath)}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async listVibeSessions(projectPath: string): Promise<{ sessions: VibeSession[] }> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/vibe-research/sessions?project_path=${encodeURIComponent(projectPath)}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }
```

**Step 3: Add mode toggle to AgentPanel (simplified version)**

Add a mode toggle at the top of the agent panel:

```typescript
// Add to AgentPanel.tsx

type AgentMode = 'chat' | 'vibe';

// In the component:
const [mode, setMode] = useState<AgentMode>('chat');
const [vibeSession, setVibeSession] = useState<VibeStatus | null>(null);

// Add mode toggle UI in the header:
<div className="flex items-center gap-2 px-4 py-2 border-b border-black/6">
  <button
    onClick={() => setMode('chat')}
    className={`px-3 py-1 rounded-full typo-small transition-colors ${
      mode === 'chat'
        ? 'bg-green1 text-white'
        : 'hover:bg-black/5 text-secondary'
    }`}
  >
    Chat
  </button>
  <button
    onClick={() => setMode('vibe')}
    className={`px-3 py-1 rounded-full typo-small transition-colors ${
      mode === 'vibe'
        ? 'bg-purple-600 text-white'
        : 'hover:bg-black/5 text-secondary'
    }`}
  >
    Vibe Research
  </button>
</div>
```

**Step 4: Commit**

```bash
git add app/components/AgentPanel.tsx app/lib/api.ts
git commit -m "feat(vibe): Add mode toggle and vibe research API client"
```

---

## Task 6: End-to-End Testing ✅

**Step 1: Test Semantic Scholar client**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
import httpx
from services.semantic_scholar import SemanticScholarClient

async def test():
    async with httpx.AsyncClient() as client:
        s2 = SemanticScholarClient(client)

        # Test search
        print("Testing search...")
        papers = await s2.search("attention is all you need", limit=3)
        print(f"  Found {len(papers)} papers")

        if papers:
            # Test citations
            print(f"\nTesting citation graph for: {papers[0].title[:50]}...")
            cites = await s2.get_citations(papers[0].paper_id, limit=5)
            print(f"  Found {len(cites.papers)} citing papers")

            refs = await s2.get_references(papers[0].paper_id, limit=5)
            print(f"  Found {len(refs.papers)} referenced papers")

asyncio.run(test())
EOF
```

**Step 2: Test vibe state management**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import tempfile
from agent.vibe_state import VibeResearchState, ResearchPhase

# Create state
state = VibeResearchState(topic="efficient attention mechanisms")

# Add papers
pid = state.add_paper({
    "paper_id": "abc123",
    "title": "Attention Is All You Need",
    "authors": ["Vaswani et al."],
    "year": 2017,
    "citation_count": 50000,
}, source="semantic_scholar")
print(f"Added paper: {pid}")

# Add theme
tid = state.add_theme("Sparse Attention", "Methods that reduce attention complexity", ["abc123"])
print(f"Added theme: {tid}")

# Add gap
gid = state.add_gap("Cross-modal long context", "Few papers handle multimodal 100K+", "high")
print(f"Added gap: {gid}")

# Add hypothesis
hid = state.add_hypothesis(
    gap_id=gid,
    title="Modality-aware sparse routing",
    description="Learn different sparsity patterns per modality",
    rationale="Different modalities have different attention patterns",
    building_blocks="Routing Transformer + Perceiver IO",
)
print(f"Added hypothesis: {hid}")

# Test phase advancement
state.advance_phase(ResearchPhase.DISCOVERY)
print(f"Advanced to: {state.current_phase.value}")

# Test context output
print("\n--- State Context ---")
print(state.to_context())

# Test save/load
with tempfile.TemporaryDirectory() as tmpdir:
    state.save(tmpdir)
    loaded = VibeResearchState.load(tmpdir, state.session_id)
    print(f"\nSave/load test: {'PASS' if loaded and loaded.topic == state.topic else 'FAIL'}")
EOF
```

**Step 3: Test research agent in vibe mode**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
from agent.subagents.research import ResearchAgent, ResearchMode
from agent.vibe_state import VibeResearchState

async def test():
    agent = ResearchAgent(mode=ResearchMode.VIBE)

    # Create minimal context
    state = VibeResearchState(topic="efficient attention for long sequences")

    result = await agent.run(
        task="Search for papers on efficient attention mechanisms. Find at least 5 papers.",
        context={
            "mode": "vibe",
            "project_path": "/tmp/test-vibe",
            "topic": "efficient attention",
        },
    )

    print(f"Success: {result.success}")
    print(f"Output length: {len(result.output)} chars")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"\n--- Output Preview ---")
    print(result.output[:1000])

asyncio.run(test())
EOF
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(vibe): Complete Phase 7 vibe research implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Semantic Scholar enhanced client | `backend/services/semantic_scholar.py` |
| 2 | VibeResearchState for tracking | `backend/agent/vibe_state.py` |
| 3 | Enhanced ResearchAgent with vibe mode | `backend/agent/subagents/research.py` |
| 4 | API endpoints | `backend/main.py` |
| 5 | Frontend mode toggle | `app/components/AgentPanel.tsx`, `app/lib/api.ts` |
| 6 | End-to-end testing | - |

**New Tools Added:**
- `define_scope` - Clarify research parameters
- `explore_citations` - Follow citation graph
- `record_theme` - Track identified themes
- `record_gap` - Document research gaps
- `generate_hypothesis` - Propose novel ideas
- `score_hypothesis` - Evaluate novelty/feasibility/impact
- `update_progress` - Track progress with stall detection
- `advance_phase` - Move through workflow phases
- `generate_report` - Synthesize final report
- `save_to_memory` - Persist findings

**Total commits**: 6

---

## Recent Improvements (Post-Initial Implementation)

The following enhancements were made after the initial Phase 7 implementation to improve real-time feedback, citation accuracy, and research quality.

### 1. Real-Time Activity Tracking

**Problem**: UI only updated after the full research iteration completed, leaving users with no visibility into what the agent was doing.

**Solution**: Added `current_activity` and `updated_at` fields to `VibeResearchState` for real-time status updates.

**Files Modified**:
- `backend/agent/vibe_state.py` - Added `current_activity: str` and `updated_at: str` fields
- `backend/agent/subagents/research.py` - Update `current_activity` before each tool call
- `app/components/VibeResearchView.tsx` - Display current activity with timestamp
- `app/lib/api.ts` - Added `getVibeState()` method for full state retrieval

**Key Code**:
```python
# In vibe_state.py
current_activity: str = ""  # What the agent is currently doing
updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

def set_activity(self, activity: str) -> None:
    """Set current activity and update timestamp."""
    self.current_activity = activity
    self.updated_at = datetime.now().isoformat()
```

**Frontend Polling**: Changed from 3s to 1.5s for more responsive updates.

### 2. Citation Mismatch Fix

**Problem**: LaTeX reports had missing citations (only 2 out of 35 theme papers cited) due to paper ID version mismatch. Theme paper IDs stored without version (e.g., `'2512.13930'`) but papers stored with version (e.g., `'2512.13930v1'`).

**Solution**: Added flexible paper ID matching with version stripping.

**Files Modified**:
- `backend/agent/subagents/research.py` - Added `strip_version()` helper and `cite_keys_by_base` mapping

**Key Code**:
```python
# Helper to strip version number from paper ID
def strip_version(paper_id: str) -> str:
    import re
    return re.sub(r'v\d+$', '', paper_id)

# Build both exact and base-ID cite key mappings
cite_keys = {}  # paper_id -> cite_key
cite_keys_by_base = {}  # base_paper_id (no version) -> cite_key

for paper in state.papers:
    cite_keys[paper_id] = cite_key
    base_id = strip_version(paper_id)
    if base_id not in cite_keys_by_base:
        cite_keys_by_base[base_id] = cite_key

# Flexible citation lookup in theme section
for pid in paper_ids:
    cite_key = cite_keys.get(pid) or cite_keys_by_base.get(strip_version(pid))
```

### 3. Phase Transition Enforcement

**Problem**: Agent was advancing through phases too quickly without reading enough papers (only 4 papers read out of 200+ found).

**Solution**: Added minimum requirements before phase transitions in `advance_phase` tool.

**Files Modified**:
- `backend/agent/subagents/research.py` - Added phase transition checks

**Key Code**:
```python
# In advance_phase tool
if current == ResearchPhase.DISCOVERY and phase == ResearchPhase.SYNTHESIS:
    if len(state.papers) < 30:
        return f"Cannot advance: Need at least 30 papers found (currently have {len(state.papers)}). Keep searching!"

if current == ResearchPhase.SYNTHESIS and phase == ResearchPhase.IDEATION:
    papers_read = len(state.papers_read)
    themes_count = len(state.themes)
    issues = []
    if papers_read < 10:
        issues.append(f"read at least 10 papers (currently {papers_read})")
    if themes_count < 3:
        issues.append(f"record at least 3 themes (currently {themes_count})")
    if issues:
        return f"Cannot advance: You need to {' and '.join(issues)}. Use `read_arxiv_paper` to read more papers!"
```

**System Prompt Enhancement**:
```python
### Phase 3: SYNTHESIS
**CRITICAL: You MUST read papers, not just abstracts!**

Read and analyze key papers thoroughly:
1. Call `read_arxiv_paper` for AT LEAST 15-20 papers (prioritize by citations)
2. For each paper you read, extract key findings before moving to the next
3. Call `record_theme` ONLY after reading multiple papers that share an approach
4. Themes should be based on deep understanding, not just titles/abstracts

**MINIMUM REQUIREMENT**: Do NOT advance to IDEATION until you have:
- Read at least 15 papers with `read_arxiv_paper`
- Recorded at least 5 themes with `record_theme`
```

### 4. Reports Saved in Subdirectory

**Problem**: LaTeX reports were saved in the project root, cluttering the project.

**Solution**: Reports now saved in `report/` subdirectory.

**Files Modified**:
- `backend/agent/subagents/research.py` - Create `report/` subdirectory for output

**Key Code**:
```python
# Create report directory
report_dir = Path(project_path) / "report"
report_dir.mkdir(exist_ok=True)

# Save files
tex_path = report_dir / f"vibe_research_{state.session_id}.tex"
bib_path = report_dir / f"vibe_research_{state.session_id}.bib"
```

### 5. Session Stop/Delete Functionality

**Files Modified**:
- `backend/main.py` - Added stop and delete endpoints
- `app/lib/api.ts` - Added `stopVibeSession()` and `deleteVibeSession()` methods
- `app/components/VibeResearchView.tsx` - Added stop/delete buttons

**API Endpoints**:
```python
@app.post("/api/vibe-research/stop/{session_id}")
async def stop_vibe_session(session_id: str, project_path: str):
    """Stop a running vibe research session."""

@app.delete("/api/vibe-research/{session_id}")
async def delete_vibe_session(session_id: str, project_path: str):
    """Delete a vibe research session and its files."""
```

### 6. Frontend VibeResearchView Component

**Files Created**:
- `app/components/VibeResearchView.tsx` - Full vibe research UI component

**Features**:
- Phase indicator with color-coded progress bar
- Collapsible sections for Themes, Gaps, Hypotheses
- Real-time activity display with timestamp
- Paper count (found/read)
- Run iteration and Generate Report buttons
- Stop/Delete session controls
- Stall warning display

**Phase Colors**:
| Phase | Color | Tailwind |
|-------|-------|----------|
| SCOPING | Purple | `bg-purple-100 text-purple-800` |
| DISCOVERY | Blue | `bg-blue-100 text-blue-800` |
| SYNTHESIS | Green | `bg-green-100 text-green-800` |
| IDEATION | Yellow | `bg-yellow-100 text-yellow-800` |
| EVALUATION | Orange | `bg-orange-100 text-orange-800` |
| COMPLETE | Green | `bg-green3 text-green1` |

---

## Files Summary (Complete)

| File | Purpose | Status |
|------|---------|--------|
| `backend/services/semantic_scholar.py` | S2 API client with citation graph | ✅ |
| `backend/agent/vibe_state.py` | Dual-ledger state tracking | ✅ |
| `backend/agent/subagents/research.py` | Enhanced ResearchAgent | ✅ |
| `backend/main.py` | API endpoints | ✅ |
| `app/lib/api.ts` | Frontend API client | ✅ |
| `app/components/AgentPanel.tsx` | Mode toggle UI | ✅ |
| `app/components/VibeResearchView.tsx` | Vibe research display | ✅ |

---

## Known Limitations

1. **Rate Limits**: Semantic Scholar API has rate limits (100 req/sec unauthenticated). The client has retry logic but heavy usage may hit limits.

2. **PDF Reading**: arXiv PDF extraction works well, but some papers with complex layouts may have extraction issues.

3. **Hypothesis Quality**: Hypothesis quality depends on the LLM's understanding. Users should review and refine generated hypotheses.

4. **Session Recovery**: If the backend restarts mid-session, the agent can resume from saved state but loses in-memory context.
