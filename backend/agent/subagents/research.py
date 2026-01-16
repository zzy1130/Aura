"""
Research Subagent

Specialized agent for academic research tasks with two modes:
- CHAT mode: Quick searches, paper summaries, single-turn help
- VIBE mode: Deep autonomous research with hypothesis generation

IMPORTANT: This agent NEVER makes up citations. It only reports real papers
found through the APIs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from xml.etree import ElementTree

import httpx
from pydantic_ai import Agent, RunContext

from agent.subagents.base import (
    Subagent,
    SubagentConfig,
    SubagentResult,
    register_subagent,
)
from agent.providers.colorist import get_haiku_model
from agent.vibe_state import VibeResearchState, ResearchPhase
from services.semantic_scholar import SemanticScholarClient

logger = logging.getLogger(__name__)


# =============================================================================
# Mode and Dependencies
# =============================================================================

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


# =============================================================================
# arXiv API
# =============================================================================

ARXIV_API_URL = "https://export.arxiv.org/api/query"


async def search_arxiv_api(
    query: str,
    http_client: httpx.AsyncClient,
    max_results: int = 10,
) -> list[dict]:
    """
    Search arXiv API for papers.

    Args:
        query: Search query
        http_client: HTTP client
        max_results: Maximum number of results

    Returns:
        List of paper dictionaries
    """
    try:
        response = await http_client.get(
            ARXIV_API_URL,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=30.0,
        )
        response.raise_for_status()

        # Parse XML response
        root = ElementTree.fromstring(response.text)

        # Define namespaces
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        papers = []
        for entry in root.findall("atom:entry", ns):
            # Extract paper info
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            id_elem = entry.find("atom:id", ns)
            published_elem = entry.find("atom:published", ns)

            # Get authors
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None and name.text:
                    authors.append(name.text)

            # Get categories
            categories = []
            for category in entry.findall("atom:category", ns):
                term = category.get("term")
                if term:
                    categories.append(term)

            paper = {
                "title": title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Unknown",
                "authors": authors[:5],  # Limit to first 5 authors
                "abstract": summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else "",
                "arxiv_id": id_elem.text.split("/")[-1] if id_elem is not None and id_elem.text else "",
                "url": id_elem.text if id_elem is not None else "",
                "published": published_elem.text[:10] if published_elem is not None and published_elem.text else "",
                "categories": categories[:3],
            }
            papers.append(paper)

        return papers

    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        raise


# =============================================================================
# Semantic Scholar API (legacy, for backward compatibility)
# =============================================================================

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


async def search_semantic_scholar_api(
    query: str,
    http_client: httpx.AsyncClient,
    max_results: int = 10,
) -> list[dict]:
    """
    Search Semantic Scholar API for papers.

    Args:
        query: Search query
        http_client: HTTP client
        max_results: Maximum number of results

    Returns:
        List of paper dictionaries
    """
    try:
        response = await http_client.get(
            SEMANTIC_SCHOLAR_API_URL,
            params={
                "query": query,
                "limit": max_results,
                "fields": "title,authors,abstract,year,citationCount,url,paperId",
            },
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        papers = []

        for item in data.get("data", []):
            authors = [
                a.get("name", "Unknown")
                for a in item.get("authors", [])[:5]
            ]

            paper = {
                "title": item.get("title", "Unknown"),
                "authors": authors,
                "abstract": item.get("abstract", "")[:500] if item.get("abstract") else "",
                "year": item.get("year"),
                "citation_count": item.get("citationCount", 0),
                "url": item.get("url", ""),
                "paper_id": item.get("paperId", ""),
            }
            papers.append(paper)

        return papers

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Semantic Scholar rate limit hit")
            return []
        raise
    except Exception as e:
        logger.error(f"Semantic Scholar API error: {e}")
        raise


# =============================================================================
# System Prompts
# =============================================================================

RESEARCH_SYSTEM_PROMPT_CHAT = """You are a specialized academic research assistant.

Your capabilities:
- Search arXiv for relevant papers
- Search Semantic Scholar for papers and citations
- Read and extract text from academic PDFs
- Summarize paper abstracts and full text
- Extract key findings and contributions
- Find related work for a topic

CRITICAL RULES:
1. NEVER make up citations or paper titles - only cite papers found through the APIs
2. Always include paper titles, authors, and years when citing
3. Focus on relevance to the user's research topic
4. If no papers are found, say so honestly
5. Provide concise summaries of key points

Tools for reading papers:
- Use `read_arxiv_paper` to read full text of arXiv papers by ID
- Use `read_pdf_url` to read PDFs from other URLs (preprints, etc.)

When reporting papers, format them as:
- **Title** by Authors (Year)
  Brief summary of key contribution
  [arXiv:ID] or [Semantic Scholar link]
"""

RESEARCH_SYSTEM_PROMPT_VIBE = """You are an autonomous research agent conducting deep literature exploration.

{state_context}

## CRITICAL: Tool Usage Required

You MUST use tools to perform actions. DO NOT just describe what you would do - ACTUALLY CALL THE TOOLS.
Every action should result in a tool call, not just text output.

## Your Mission

Autonomously explore the literature on the given topic, identify research gaps, and generate novel hypotheses.

## Workflow Phases

### Phase 1: SCOPING (Current if phase is scoping)
Clarify the research parameters:
- Domain focus (NLP, vision, robotics, etc.)
- Specific constraints (efficiency, accuracy, scale, etc.)
- Desired output (survey, novel angle, idea validation)

**REQUIRED ACTION**: Call `define_scope` with the clarified parameters, then call `advance_phase` to move to DISCOVERY.

### Phase 2: DISCOVERY
Search comprehensively using tools:
1. Call `search_arxiv` with multiple query variations (at least 5-10 different queries)
2. Call `search_semantic_scholar` for citation-rich papers
3. Call `explore_citations` to follow seminal paper trails
4. Goal: Find 50-100+ relevant papers

**REQUIRED**: After each search, call `update_progress` to track findings.
When you have enough papers (50+), call `advance_phase` to move to SYNTHESIS.

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

Look for:
- Main methodological approaches
- Areas of agreement/disagreement
- Evolution of the field over time

When you meet the minimum requirements and themes are clear, call `advance_phase` to move to IDEATION.

### Phase 4: IDEATION
Find what's missing and propose new directions:
1. Call `record_gap` for each underexplored area found
2. Call `generate_hypothesis` to propose how to address each gap
3. Consider:
   - What combinations haven't been tried?
   - What domains lack application?
   - What assumptions could be challenged?

When you have enough hypotheses (3-5), call `advance_phase` to move to EVALUATION.

### Phase 5: EVALUATION
Score and rank your hypotheses:
1. Call `score_hypothesis` with novelty, feasibility, impact (1-10 each)
2. Identify similar existing work for each
3. Explain differentiation from prior work
4. Call `generate_report` to synthesize all findings

## Progress Rules

- ALWAYS call `update_progress` after each significant action
- If stalled (3 actions with no new info), change strategy or advance phase
- Use `advance_phase` when ready to move forward

## Critical Rules

1. NEVER fabricate citations - only cite papers from API results
2. Be thorough - explore widely before concluding
3. Be self-critical - identify weaknesses in your hypotheses
4. Every response should include at least one tool call
5. If unsure about scope, make reasonable assumptions and proceed
"""


# =============================================================================
# Research Agent
# =============================================================================

@register_subagent("research")
class ResearchAgent(Subagent[ResearchDeps]):
    """
    Research subagent for academic paper search and analysis.

    Supports two modes:
    - CHAT: Quick searches, paper summaries (cheaper model, faster)
    - VIBE: Deep autonomous research with hypothesis generation (stronger model, longer)

    Tools (CHAT mode):
        - search_arxiv: Search arXiv for papers
        - search_semantic_scholar: Search Semantic Scholar
        - read_arxiv_paper: Read full paper text
        - read_pdf_url: Read PDF from URL
        - think: Reasoning tool

    Additional tools (VIBE mode):
        - define_scope: Clarify research parameters
        - explore_citations: Follow citation trails
        - record_theme: Track identified themes
        - record_gap: Document research gaps
        - generate_hypothesis: Propose novel ideas
        - score_hypothesis: Evaluate novelty/feasibility/impact
        - update_progress: Track progress with stall detection
        - advance_phase: Move through workflow
        - generate_report: Synthesize final report
        - save_to_memory: Persist findings
    """

    def __init__(self, mode: ResearchMode = ResearchMode.CHAT, **kwargs):
        self.mode = mode
        self._vibe_state_override: Optional["VibeResearchState"] = None

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

    def _get_model(self):
        """Get the appropriate model for this subagent.

        Both modes use Haiku for cost efficiency and better rate limits.
        """
        return get_haiku_model()

    async def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        *,
        project_path: str | None = None,
        mode: ResearchMode | None = None,
        vibe_state: Optional["VibeResearchState"] = None,
    ) -> "SubagentResult":
        """
        Run the research agent on a task.

        This override handles vibe-mode specific parameters.

        Args:
            task: The task to perform
            context: Optional context dictionary
            project_path: Path to the project (for vibe mode)
            mode: Override the mode (CHAT or VIBE)
            vibe_state: VibeResearchState for vibe mode

        Returns:
            SubagentResult with output and metadata
        """
        # Build context from kwargs
        ctx = context or {}

        if project_path is not None:
            ctx["project_path"] = project_path

        if mode is not None:
            ctx["mode"] = "vibe" if mode == ResearchMode.VIBE else "chat"
            self.mode = mode  # Update mode for system prompt

        if vibe_state is not None:
            self._vibe_state_override = vibe_state
            ctx["session_id"] = vibe_state.session_id

        # Call parent run
        return await super().run(task, ctx)

    @property
    def system_prompt(self) -> str:
        if self.mode == ResearchMode.VIBE:
            return RESEARCH_SYSTEM_PROMPT_VIBE
        return RESEARCH_SYSTEM_PROMPT_CHAT

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._http_client

    def _get_s2_client(self) -> SemanticScholarClient:
        """Get or create Semantic Scholar client."""
        if self._s2_client is None:
            self._s2_client = SemanticScholarClient(self._get_http_client())
        return self._s2_client

    def _create_deps(self, context: dict[str, Any]) -> ResearchDeps:
        """Create dependencies for research agent."""
        mode_str = context.get("mode", "chat")
        mode = ResearchMode.VIBE if mode_str == "vibe" else ResearchMode.CHAT

        # For vibe mode, create or load state
        vibe_state = None
        if mode == ResearchMode.VIBE:
            # First check for override (passed directly via run())
            if self._vibe_state_override is not None:
                vibe_state = self._vibe_state_override
            else:
                # Try to load from file
                project_path = context.get("project_path", "")
                session_id = context.get("session_id")

                if session_id and project_path:
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

    def _create_agent(self) -> Agent[ResearchDeps, str]:
        """Create the research agent with tools."""

        # Create agent with appropriate base prompt
        if self.mode == ResearchMode.VIBE:
            # For vibe mode, use the base vibe prompt (state will be injected dynamically)
            agent = Agent(
                model=self._get_model(),
                system_prompt=RESEARCH_SYSTEM_PROMPT_VIBE.format(state_context=""),
                deps_type=ResearchDeps,
                retries=2,
            )

            # Add dynamic system prompt that injects current state
            @agent.system_prompt
            def inject_vibe_state(ctx: RunContext[ResearchDeps]) -> str:
                """Inject current vibe state into the context."""
                if ctx.deps.vibe_state:
                    return f"\n## Current Research State\n{ctx.deps.vibe_state.to_context()}"
                return ""
        else:
            agent = Agent(
                model=self._get_model(),
                system_prompt=RESEARCH_SYSTEM_PROMPT_CHAT,
                deps_type=ResearchDeps,
                retries=2,
            )

        # === CORE TOOLS (both modes) ===
        self._register_core_tools(agent)

        # === VIBE TOOLS (primarily for vibe mode, but available in both) ===
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

            # Set activity before starting
            if ctx.deps.vibe_state and ctx.deps.project_path:
                ctx.deps.vibe_state.set_activity(f"Searching arXiv for '{query}'...")
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            try:
                papers = await search_arxiv_api(
                    query=query,
                    http_client=ctx.deps.http_client,
                    max_results=max_results,
                )

                if not papers:
                    return f"No papers found on arXiv for query: '{query}'"

                # In vibe mode, add to state and save
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
                    # Save state so UI can show progress
                    if ctx.deps.project_path:
                        ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity before starting
            if ctx.deps.vibe_state and ctx.deps.project_path:
                ctx.deps.vibe_state.set_activity(f"Searching Semantic Scholar for '{query}'...")
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            try:
                papers = await search_semantic_scholar_api(
                    query=query,
                    http_client=ctx.deps.http_client,
                    max_results=max_results,
                )

                if not papers:
                    return f"No papers found on Semantic Scholar for query: '{query}'"

                # In vibe mode, add to state and save
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
                    # Save state so UI can show progress
                    if ctx.deps.project_path:
                        ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity before starting
            if ctx.deps.vibe_state and ctx.deps.project_path:
                ctx.deps.vibe_state.set_activity(f"Reading paper {arxiv_id}...")
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            try:
                doc = await _read_arxiv(
                    arxiv_id=arxiv_id,
                    http_client=ctx.deps.http_client,
                    max_pages=max_pages,
                    max_chars=50000,
                )

                # In vibe mode, mark as read and save
                if ctx.deps.mode == ResearchMode.VIBE and ctx.deps.vibe_state:
                    if arxiv_id not in ctx.deps.vibe_state.papers_read:
                        ctx.deps.vibe_state.papers_read.append(arxiv_id)
                    # Save state so UI can show progress
                    if ctx.deps.project_path:
                        ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity before starting
            if ctx.deps.vibe_state and ctx.deps.project_path:
                ctx.deps.vibe_state.set_activity(f"Reading PDF from URL...")
                ctx.deps.vibe_state.save(ctx.deps.project_path)

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
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available. Are you in VIBE mode?"

            # Set activity
            ctx.deps.vibe_state.set_activity("Defining research scope...")

            ctx.deps.vibe_state.scope = {
                "domain": domain,
                "constraints": constraints,
                "goal": goal,
                "notes": additional_notes,
            }

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            return f"Scope defined:\n- Domain: {domain}\n- Constraints: {constraints}\n- Goal: {goal}\n\nProceed to DISCOVERY phase with `advance_phase`."

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
            # Set activity before starting
            if ctx.deps.vibe_state and ctx.deps.project_path:
                ctx.deps.vibe_state.set_activity(f"Exploring citations for paper {paper_id}...")
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            s2_client = SemanticScholarClient(ctx.deps.http_client)

            try:
                papers = await s2_client.explore_citation_graph(
                    paper_id=paper_id,
                    direction=direction,  # type: ignore
                    depth=1,
                    max_papers_per_level=max_results,
                )
            except Exception as e:
                return f"Error exploring citations: {str(e)}"

            if not papers:
                return f"No connected papers found for {paper_id}"

            # Add to state if in vibe mode and save
            if ctx.deps.vibe_state:
                for paper in papers:
                    ctx.deps.vibe_state.add_paper(paper.to_dict(), source="citation_graph")
                # Save state so UI can show progress
                if ctx.deps.project_path:
                    ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity
            ctx.deps.vibe_state.set_activity(f"Recording theme: {name}...")

            ids = [p.strip() for p in paper_ids.split(",") if p.strip()]
            theme_id = ctx.deps.vibe_state.add_theme(name, description, ids)

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            if confidence not in ("low", "medium", "high"):
                confidence = "medium"

            # Set activity
            ctx.deps.vibe_state.set_activity(f"Recording gap: {title}...")

            gap_id = ctx.deps.vibe_state.add_gap(title, evidence, confidence)

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity
            ctx.deps.vibe_state.set_activity(f"Generating hypothesis: {title}...")

            hypo_id = ctx.deps.vibe_state.add_hypothesis(
                gap_id=gap_id,
                title=title,
                description=description,
                rationale=rationale,
                building_blocks=building_blocks,
                suggested_experiments=suggested_experiments,
            )

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Set activity
            ctx.deps.vibe_state.set_activity(f"Scoring hypothesis {hypothesis_id}...")

            # Clamp scores
            novelty = max(1, min(10, novelty))
            feasibility = max(1, min(10, feasibility))
            impact = max(1, min(10, impact))

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

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

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

            # Save state
            if ctx.deps.project_path:
                ctx.deps.vibe_state.save(ctx.deps.project_path)

            state = ctx.deps.vibe_state
            msg = f"Progress: {state.current_phase.value.upper()} at {phase_progress}%"
            msg += f"\nPapers: {len(state.papers)} found, {len(state.papers_read)} read"
            msg += f"\nThemes: {len(state.themes)} | Gaps: {len(state.gaps)} | Hypotheses: {len(state.hypotheses)}"

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
                valid = ", ".join([p.value for p in ResearchPhase])
                return f"Error: Invalid phase '{next_phase}'. Valid phases: {valid}"

            # Set activity
            ctx.deps.vibe_state.set_activity(f"Advancing to {next_phase} phase...")

            current = ctx.deps.vibe_state.current_phase
            state = ctx.deps.vibe_state

            # Enforce minimum requirements for phase transitions
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

            success = state.advance_phase(phase)

            if not success:
                return f"Error: Cannot advance from {current.value} to {next_phase}. Follow the workflow order."

            # Save state
            if ctx.deps.project_path:
                state.save(ctx.deps.project_path)

            return f"Advanced to {next_phase.upper()} phase.\n\nPrevious phase ({current.value}) summary:\n{summary[:500]}"

        @agent.tool
        async def generate_report(
            ctx: RunContext[ResearchDeps],
        ) -> str:
            """
            Generate the final research report as a LaTeX document with citations.

            Call this in the EVALUATION phase after scoring hypotheses.

            Returns:
                Confirmation that report was generated
            """
            if not ctx.deps.vibe_state:
                return "Error: No vibe state available"

            state = ctx.deps.vibe_state

            # Generate summary-based filename from research findings
            state.finalize_report_slug()

            # Set activity
            state.set_activity("Generating final research report...")
            if ctx.deps.project_path:
                state.save(ctx.deps.project_path)

            ranked = state.get_ranked_hypotheses()

            # Helper to escape LaTeX special characters
            def escape_latex(text: str) -> str:
                if not text:
                    return ""
                replacements = [
                    ('\\', r'\textbackslash{}'),
                    ('&', r'\&'),
                    ('%', r'\%'),
                    ('$', r'\$'),
                    ('#', r'\#'),
                    ('_', r'\_'),
                    ('{', r'\{'),
                    ('}', r'\}'),
                    ('~', r'\textasciitilde{}'),
                    ('^', r'\textasciicircum{}'),
                ]
                for old, new in replacements:
                    text = text.replace(old, new)
                return text

            # Helper to create citation key from paper
            def make_cite_key(paper: dict) -> str:
                authors = paper.get('authors', [])
                first_author = authors[0].split()[-1] if authors else 'unknown'
                year = paper.get('year', 'nd')
                # Clean the key
                key = f"{first_author}{year}".lower()
                key = ''.join(c for c in key if c.isalnum())
                return key

            # Helper to strip version number from paper ID (e.g., "2410.07348v1" -> "2410.07348")
            def strip_version(paper_id: str) -> str:
                import re
                return re.sub(r'v\d+$', '', paper_id)

            # Build BibTeX entries
            bib_entries = []
            cite_keys = {}  # paper_id -> cite_key
            cite_keys_by_base = {}  # base_paper_id (no version) -> cite_key

            for paper in state.papers:
                paper_id = paper.get('paper_id', '')
                if not paper_id:
                    continue

                cite_key = make_cite_key(paper)
                # Handle duplicates
                base_key = cite_key
                counter = 1
                while cite_key in cite_keys.values():
                    cite_key = f"{base_key}{chr(ord('a') + counter - 1)}"
                    counter += 1

                cite_keys[paper_id] = cite_key
                # Also map base ID (without version) for flexible lookup
                base_id = strip_version(paper_id)
                if base_id not in cite_keys_by_base:
                    cite_keys_by_base[base_id] = cite_key

                authors = paper.get('authors', [])
                author_str = ' and '.join(authors[:5])
                if len(authors) > 5:
                    author_str += ' and others'

                title = paper.get('title', 'Unknown Title')
                year = paper.get('year', '')
                abstract = paper.get('abstract', '')[:500]

                bib_entry = f"""@article{{{cite_key},
  author = {{{author_str}}},
  title = {{{title}}},
  year = {{{year}}},
  note = {{Paper ID: {paper_id}}}
}}"""
                bib_entries.append(bib_entry)

            # Build LaTeX document
            topic_escaped = escape_latex(state.topic)
            date_str = datetime.now().strftime('%B %d, %Y')

            latex_lines = [
                r"\documentclass[11pt,a4paper]{article}",
                r"\usepackage[utf8]{inputenc}",
                r"\usepackage[T1]{fontenc}",
                r"\usepackage{lmodern}",
                r"\usepackage[margin=1in]{geometry}",
                r"\usepackage{hyperref}",
                r"\usepackage{natbib}",
                r"\usepackage{booktabs}",
                r"\usepackage{enumitem}",
                r"\usepackage{xcolor}",
                r"",
                r"\definecolor{hypoblue}{RGB}{0,102,204}",
                r"\definecolor{gapred}{RGB}{204,51,51}",
                r"",
                r"\title{Vibe Research Report:\\",
                f"  {topic_escaped}}}",
                r"\author{Generated by Aura Vibe Research}",
                f"\\date{{{date_str}}}",
                r"",
                r"\begin{document}",
                r"\maketitle",
                r"",
                r"\begin{abstract}",
                f"This report presents the findings of an automated literature review on \\textbf{{{topic_escaped}}}. ",
                f"We analyzed {len(state.papers)} papers, identified {len(state.themes)} major themes, ",
                f"discovered {len(state.gaps)} research gaps, and generated {len(state.hypotheses)} novel research hypotheses.",
                r"\end{abstract}",
                r"",
                r"\tableofcontents",
                r"\newpage",
                r"",
            ]

            # Research Scope
            if state.scope:
                latex_lines.extend([
                    r"\section{Research Scope}",
                    r"",
                    r"\begin{itemize}",
                    f"  \\item \\textbf{{Domain}}: {escape_latex(state.scope.get('domain', 'General'))}",
                    f"  \\item \\textbf{{Constraints}}: {escape_latex(state.scope.get('constraints', 'None specified'))}",
                    f"  \\item \\textbf{{Goal}}: {escape_latex(state.scope.get('goal', 'Exploration'))}",
                ])
                if state.scope.get('notes'):
                    latex_lines.append(f"  \\item \\textbf{{Notes}}: {escape_latex(state.scope.get('notes'))}")
                latex_lines.extend([
                    r"\end{itemize}",
                    r"",
                ])

            # Literature Landscape (Themes)
            if state.themes:
                latex_lines.extend([
                    r"\section{Literature Landscape}",
                    r"",
                ])
                for theme in state.themes:
                    theme_name = escape_latex(theme.get('name', 'Unnamed Theme'))
                    theme_desc = escape_latex(theme.get('description', ''))
                    paper_ids = theme.get('paper_ids', [])

                    latex_lines.extend([
                        f"\\subsection{{{theme_name}}}",
                        r"",
                        theme_desc,
                        r"",
                    ])

                    # Add citations for papers in this theme (try exact match first, then base ID)
                    valid_cites = []
                    for pid in paper_ids:
                        cite_key = cite_keys.get(pid) or cite_keys_by_base.get(strip_version(pid))
                        if cite_key and cite_key not in valid_cites:
                            valid_cites.append(cite_key)
                    if valid_cites:
                        cite_str = ', '.join(valid_cites[:10])  # Limit citations
                        latex_lines.append(f"Key works in this area include \\cite{{{cite_str}}}.")
                        latex_lines.append(r"")

            # Research Gaps
            if state.gaps:
                latex_lines.extend([
                    r"\section{Identified Research Gaps}",
                    r"",
                ])
                for gap in state.gaps:
                    gap_title = escape_latex(gap.get('title', 'Unnamed Gap'))
                    gap_evidence = escape_latex(gap.get('evidence', ''))
                    confidence = gap.get('confidence', 'medium').upper()

                    latex_lines.extend([
                        f"\\subsection{{\\textcolor{{gapred}}{{{gap_title}}}}}",
                        r"",
                        f"\\textbf{{Confidence}}: {confidence}",
                        r"",
                        gap_evidence,
                        r"",
                    ])

            # Hypotheses
            if ranked:
                latex_lines.extend([
                    r"\section{Research Hypotheses}",
                    r"",
                    r"The following hypotheses are ranked by total score (Novelty + Feasibility + Impact).",
                    r"",
                ])
                for i, hypo in enumerate(ranked, 1):
                    n = hypo.get('novelty_score', 0)
                    f_score = hypo.get('feasibility_score', 0)
                    imp = hypo.get('impact_score', 0)
                    total = n + f_score + imp

                    title = escape_latex(hypo.get('title', 'Untitled'))
                    desc = escape_latex(hypo.get('description', ''))
                    rationale = escape_latex(hypo.get('rationale', ''))
                    building = escape_latex(hypo.get('building_blocks', ''))
                    experiments = escape_latex(hypo.get('suggested_experiments', ''))
                    similar = escape_latex(hypo.get('similar_work', ''))
                    diff = escape_latex(hypo.get('differentiation', ''))

                    latex_lines.extend([
                        f"\\subsection{{\\textcolor{{hypoblue}}{{Hypothesis {i}: {title}}}}}",
                        r"",
                        r"\begin{tabular}{lccc}",
                        r"\toprule",
                        r"Novelty & Feasibility & Impact & \textbf{Total} \\",
                        r"\midrule",
                        f"{n}/10 & {f_score}/10 & {imp}/10 & \\textbf{{{total}/30}} \\\\",
                        r"\bottomrule",
                        r"\end{tabular}",
                        r"",
                        r"\paragraph{Description}",
                        desc,
                        r"",
                        r"\paragraph{Rationale}",
                        rationale,
                        r"",
                        r"\paragraph{Building Blocks}",
                        building,
                        r"",
                    ])
                    if experiments:
                        latex_lines.extend([
                            r"\paragraph{Suggested Experiments}",
                            experiments,
                            r"",
                        ])
                    if similar:
                        latex_lines.extend([
                            r"\paragraph{Similar Work}",
                            similar,
                            r"",
                        ])
                    if diff:
                        latex_lines.extend([
                            r"\paragraph{Differentiation}",
                            diff,
                            r"",
                        ])

            # Bibliography
            # Use the report filename for bibliography reference
            report_base = state.get_report_filename()
            latex_lines.extend([
                r"",
                r"\bibliographystyle{plainnat}",
                f"\\bibliography{{{report_base}}}",
                r"",
                r"\end{document}",
            ])

            report_tex = "\n".join(latex_lines)
            report_bib = "\n\n".join(bib_entries)

            # Save state
            state.report = report_tex
            state.is_complete = True
            state.current_phase = ResearchPhase.COMPLETE

            # Save files
            if ctx.deps.project_path:
                from pathlib import Path

                state.save(ctx.deps.project_path)

                # Create report directory
                report_dir = Path(ctx.deps.project_path) / "report"
                report_dir.mkdir(exist_ok=True)

                # Use topic-based filename from state
                base_filename = state.get_report_filename()

                # Save .tex file
                tex_filename = f"{base_filename}.tex"
                tex_path = report_dir / tex_filename
                tex_path.write_text(report_tex, encoding="utf-8")

                # Save .bib file
                bib_filename = f"{base_filename}.bib"
                bib_path = report_dir / bib_filename
                bib_path.write_text(report_bib, encoding="utf-8")

                logger.info(f"Report saved to: {tex_path}")
                logger.info(f"Bibliography saved to: {bib_path}")

                return f"Report generated successfully!\n\nFiles created:\n- report/{tex_filename}\n- report/{bib_filename}\n\nThe report includes {len(bib_entries)} citations from the analyzed papers."

            return "Report generated but could not save files (no project path)"

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

            try:
                from services.memory import MemoryService

                svc = MemoryService(ctx.deps.project_path)
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                tag_list.append(entry_type)

                if entry_type == "paper":
                    # Save as paper entry
                    svc.add_entry("papers", {
                        "title": title,
                        "authors": [],
                        "summary": content,
                        "tags": tag_list,
                        "arxiv_id": "",
                    })
                else:
                    # Save as note
                    svc.add_entry("notes", {
                        "content": f"[{entry_type.upper()}] {title}\n\n{content}",
                        "tags": tag_list,
                    })

                return f"Saved to memory: [{entry_type}] {title}"

            except Exception as e:
                return f"Error saving to memory: {str(e)}"
