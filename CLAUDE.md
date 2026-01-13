# Aura Project Instructions

## Project Overview

Aura is a **local-first macOS desktop LaTeX IDE** with an embedded AI agent. Think "Overleaf + Claude Code" as a native app.

**Current Status**: Phase 7 complete (Vibe Research Engine).

## Architecture Summary

```
Electron (.app) → Next.js UI → FastAPI Backend → Pydantic AI Agent
                                      ↓
                              Tools (decorator-based)
                                      ↓
                    Docker (LaTeX) | arXiv API | PDF Reader | Git
                                      ↓
                         ResearchAgent (CHAT | VIBE mode)
```

## Quick Reference

| Component | Location | Entry Point |
|-----------|----------|-------------|
| FastAPI Backend | `backend/` | `main.py` |
| Main Agent | `backend/agent/` | `pydantic_agent.py` |
| Subagents | `backend/agent/subagents/` | `research.py`, `compiler.py`, `planner.py` |
| Services | `backend/services/` | `docker.py`, `project.py`, `memory.py` |
| Tools | `backend/agent/tools/` | `pdf_reader.py` |

## Colorist API Configuration

**IMPORTANT**: Use Colorist gateway, not direct Anthropic API.

```python
from anthropic import AsyncAnthropic
import httpx

# Key points:
# 1. Use auth_token (not api_key)
# 2. No /v1 suffix on base_url
# 3. Shared httpx.AsyncClient for connection pooling

http_client = httpx.AsyncClient()
client = AsyncAnthropic(
    auth_token="vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336",
    base_url="https://colorist-gateway-staging.arco.ai",
    http_client=http_client,
)
```

**Default Model**: `claude-4-5-sonnet-by-all` (Colorist gateway format)

## Project Structure (Current)

```
Aura/
├── backend/
│   ├── main.py                    # FastAPI app with all endpoints
│   ├── agent/
│   │   ├── pydantic_agent.py      # Main agent (17 tools)
│   │   ├── streaming.py           # SSE streaming
│   │   ├── compression.py         # Message compression
│   │   ├── hitl.py                # Human-in-the-loop approval
│   │   ├── steering.py            # Mid-conversation steering
│   │   ├── planning.py            # Structured planning system
│   │   ├── providers/
│   │   │   └── colorist.py        # Colorist gateway provider
│   │   ├── subagents/
│   │   │   ├── base.py            # Subagent base class
│   │   │   ├── research.py        # arXiv/Semantic Scholar + PDF
│   │   │   ├── compiler.py        # LaTeX error fixing
│   │   │   └── planner.py         # Task planning
│   │   └── tools/
│   │       └── pdf_reader.py      # PDF text extraction
│   └── services/
│       ├── docker.py              # LaTeX compilation
│       └── project.py             # Project management
├── sandbox/
│   └── Dockerfile                 # texlive image
├── docs/plans/
│   ├── 2026-01-06-aura-design.md           # Main design doc
│   └── 2026-01-06-phase3-advanced-agent.md # Phase 3 details
└── projects/                      # User LaTeX projects (gitignored)
```

## Tool Registration Pattern (PydanticAI)

Tools are registered via decorators on the agent:

```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

@dataclass
class MyDeps:
    project_path: str

agent = Agent(model=..., deps_type=MyDeps)

@agent.tool
async def my_tool(ctx: RunContext[MyDeps], arg1: str, arg2: int = 10) -> str:
    """
    Tool description shown to the LLM.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2 (default: 10)

    Returns:
        Result description
    """
    project = ctx.deps.project_path
    return f"Result for {arg1}"
```

## Subagent Pattern

```python
from agent.subagents.base import Subagent, SubagentConfig, register_subagent

@register_subagent("my_subagent")
class MySubagent(Subagent[MyDeps]):
    def __init__(self):
        config = SubagentConfig(
            name="my_subagent",
            description="What this subagent does",
            use_haiku=True,  # Use cheaper model
        )
        super().__init__(config)

    @property
    def system_prompt(self) -> str:
        return "You are a specialized agent for..."

    def _create_agent(self) -> Agent:
        agent = Agent(model=self._get_model(), ...)
        # Register tools with @agent.tool
        return agent
```

## Common Commands

```bash
# Backend dev server
cd /Users/zhongzhiyi/Aura/backend && uvicorn main:app --reload --port 8000

# Run inline Python tests (preferred pattern)
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import asyncio
from agent.subagents.research import ResearchAgent
# ... test code
asyncio.run(test_function())
EOF

# Build Docker LaTeX image
cd /Users/zhongzhiyi/Aura/sandbox && docker build -t aura-texlive .

# Install backend dependencies
cd /Users/zhongzhiyi/Aura/backend && pip install -r requirements.txt
```

## Import Conventions

When running from `backend/` directory, use relative imports:

```python
# Correct (from backend/)
from agent.pydantic_agent import aura_agent
from agent.subagents.research import ResearchAgent
from agent.tools.pdf_reader import read_arxiv_paper
from services.docker import get_docker_latex

# NOT: from backend.agent...
```

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | SSE streaming agent responses |
| `/api/compile` | POST | Compile LaTeX project |
| `/api/projects` | GET/POST | List/create projects |
| `/api/subagents` | GET | List available subagents |
| `/api/planning/create` | POST | Create execution plan |
| `/api/hitl/approve` | POST | Approve pending tool call |
| `/api/steering/add` | POST | Add steering message |

## Key Dependencies

Backend (`requirements.txt`):
- `pydantic-ai>=0.0.14` - Agent framework
- `anthropic>=0.40.0` - LLM client (Colorist gateway)
- `PyMuPDF>=1.24.0` - PDF text extraction
- `httpx>=0.26.0` - HTTP client
- `arxiv>=2.1.0` - arXiv API
- `docker>=7.0.0` - LaTeX compilation
- `sse-starlette>=1.8.0` - SSE streaming

## Agent Tools (17 total)

Main agent (`pydantic_agent.py`):
- `read_file`, `edit_file`, `write_file`, `list_files`, `find_files`
- `compile_latex`, `check_latex_syntax`, `get_compilation_log`
- `think` (reasoning tool)
- `delegate_to_subagent` (handoff to research/compiler/planner)
- Planning tools: `plan_task`, `get_current_plan`, `start_plan_execution`, `complete_plan_step`, `fail_plan_step`, `skip_plan_step`, `abandon_plan`

Research subagent:
- `search_arxiv`, `search_semantic_scholar`, `read_arxiv_paper`, `read_pdf_url`, `think`

## Build Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Docker LaTeX sandbox + FastAPI skeleton |
| 2 | ✅ | Colorist client + Pydantic AI agent + tools |
| 3A-3F | ✅ | Advanced agent (compression, HITL, steering, subagents, planning) |
| 3.5 | ✅ | PDF reader tool |
| 4 | ✅ | Electron shell + UI components |
| 5 | ✅ | Git/Overleaf sync + packaging |
| 6 | ✅ | Project memory system |
| 7 | ✅ | Vibe Research Engine (see `docs/plans/2026-01-13-vibe-research-implementation.md`) |

## Phase 7: Vibe Research (Complete)

Extends ResearchAgent with two modes:
- **CHAT mode**: Quick searches, paper summaries (current behavior)
- **VIBE mode**: Autonomous deep research with hypothesis generation

Key components:
- `VibeResearchState` - Dual-ledger tracking (Task + Progress)
- `SemanticScholarClient` - Citation graph traversal
- New tools: `explore_citations`, `record_gap`, `generate_hypothesis`, `score_hypothesis`, etc.
- 5-phase workflow: SCOPING → DISCOVERY → SYNTHESIS → IDEATION → EVALUATION

## Git Workflow

- Always pull from origin before committing
- Do not cite Claude Code in commit messages
- Use descriptive commit messages with bullet points
- Current branch: `phase3e-subagents`

## Reference Projects

- **Paintress** (`/Users/zhongzhiyi/Desktop/paintress`): Agent architecture patterns
- **Appraiser** (`/Users/zhongzhiyi/Desktop/appraiser`): Colorist API integration
