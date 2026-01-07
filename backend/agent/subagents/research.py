"""
Research Subagent

Specialized agent for academic research tasks:
- Searching arXiv for papers
- Searching Semantic Scholar for citations
- Summarizing paper abstracts
- Finding related work

IMPORTANT: This agent NEVER makes up citations. It only reports real papers
found through the APIs.
"""

import logging
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

import httpx
from pydantic_ai import Agent, RunContext

from agent.subagents.base import (
    Subagent,
    SubagentConfig,
    register_subagent,
)
from agent.providers.colorist import get_default_model, get_haiku_model

logger = logging.getLogger(__name__)


# =============================================================================
# Dependencies
# =============================================================================

@dataclass
class ResearchDeps:
    """Dependencies for the research agent."""
    # HTTP client for API calls
    http_client: httpx.AsyncClient

    # Optional: limit results
    max_results: int = 10


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
# Semantic Scholar API
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
# Research Agent
# =============================================================================

RESEARCH_SYSTEM_PROMPT = """You are a specialized academic research assistant.

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


@register_subagent("research")
class ResearchAgent(Subagent[ResearchDeps]):
    """
    Research subagent for academic paper search and analysis.

    Tools:
        - search_arxiv: Search arXiv for papers
        - search_semantic_scholar: Search Semantic Scholar
        - analyze_papers: Analyze and compare multiple papers
    """

    def __init__(self, **kwargs):
        config = SubagentConfig(
            name="research",
            description="Search and analyze academic papers from arXiv and Semantic Scholar",
            max_iterations=10,
            timeout=90.0,
            use_haiku=True,  # Use cheaper model for research tasks
        )
        super().__init__(config)
        self._http_client: httpx.AsyncClient | None = None

    @property
    def system_prompt(self) -> str:
        return RESEARCH_SYSTEM_PROMPT

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._http_client

    def _create_deps(self, context: dict[str, Any]) -> ResearchDeps:
        """Create dependencies for research agent."""
        return ResearchDeps(
            http_client=self._get_http_client(),
            max_results=context.get("max_results", 10),
        )

    def _create_agent(self) -> Agent[ResearchDeps, str]:
        """Create the research agent with tools."""
        agent = Agent(
            model=self._get_model(),
            system_prompt=self.system_prompt,
            deps_type=ResearchDeps,
            retries=2,
        )

        # Register tools
        @agent.tool
        async def search_arxiv(
            ctx: RunContext[ResearchDeps],
            query: str,
            max_results: int = 5,
        ) -> str:
            """
            Search arXiv for academic papers.

            Args:
                query: Search query (e.g., "transformer language models", "attention mechanisms")
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

                # Format results
                lines = [f"Found {len(papers)} papers on arXiv for '{query}':\n"]
                for i, paper in enumerate(papers, 1):
                    authors_str = ", ".join(paper["authors"][:3])
                    if len(paper["authors"]) > 3:
                        authors_str += " et al."

                    lines.append(f"{i}. **{paper['title']}**")
                    lines.append(f"   Authors: {authors_str}")
                    lines.append(f"   Published: {paper['published']}")
                    lines.append(f"   Categories: {', '.join(paper['categories'])}")
                    lines.append(f"   arXiv: {paper['arxiv_id']}")

                    # Truncate abstract
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

                    if paper["url"]:
                        lines.append(f"   URL: {paper['url']}")

                    # Truncate abstract
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
            - How to combine results from multiple searches
            - How to synthesize findings

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

            Use this after searching to read the complete paper content.

            Args:
                arxiv_id: arXiv paper ID (e.g., "2301.07041" or "cs/0604007")
                max_pages: Maximum number of pages to extract (default: 10)

            Returns:
                Extracted text from the paper with page structure
            """
            from agent.tools.pdf_reader import read_arxiv_paper as _read_arxiv

            try:
                doc = await _read_arxiv(
                    arxiv_id=arxiv_id,
                    http_client=ctx.deps.http_client,
                    max_pages=max_pages,
                    max_chars=50000,
                )

                # Format output
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

            Use this for non-arXiv papers (conference proceedings, preprints, etc.).

            Args:
                url: Direct URL to a PDF file
                max_pages: Maximum number of pages to extract (default: 10)

            Returns:
                Extracted text from the PDF with page structure
            """
            from agent.tools.pdf_reader import read_pdf_from_url as _read_pdf

            try:
                doc = await _read_pdf(
                    url=url,
                    http_client=ctx.deps.http_client,
                    max_pages=max_pages,
                )

                # Format output
                text = doc.get_text(max_pages=max_pages, max_chars=50000)
                return f"Paper: {doc.title}\nPages: {doc.num_pages}\nURL: {url}\n\n{text}"

            except Exception as e:
                return f"Error reading PDF from URL: {str(e)}"

        return agent
