# Aura Project Instructions

## Project Overview

Aura is a **local-first macOS desktop LaTeX IDE** with an embedded AI agent. Think "Overleaf + Claude Code" as a native app.

## Architecture Summary

```
Electron (.app) → Next.js UI → FastAPI Backend → Pydantic AI Agent
                                      ↓
                              Tools (pluggy auto-discovery)
                                      ↓
                    Docker (LaTeX) | arXiv API | Git (Overleaf)
```

## Key Technical Decisions

1. **Desktop**: Electron (not native Swift, not Tauri)
2. **Agent Framework**: Pydantic AI (not raw Anthropic API, not Claude Agent SDK)
3. **LLM**: Claude Sonnet 4.5 via **Colorist gateway** (not direct Anthropic API)
4. **Tool System**: Pluggy for auto-discovery (inspired by Paintress project)
5. **LaTeX**: Docker isolation with texlive image
6. **Storage**: Local filesystem (`~/aura-projects/`), no database
7. **Streaming**: SSE from FastAPI to React

## Colorist API Configuration

**IMPORTANT**: Use Colorist gateway, not direct Anthropic API.

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    api_key="vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336",
    base_url="https://colorist-gateway-staging.arco.ai/v1",
)
```

Environment variables:
- `COLORIST_API_KEY`: `vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336`
- `COLORIST_GATEWAY_URL`: `https://colorist-gateway-staging.arco.ai`

## Default Model

Use `claude-sonnet-4-5-20250514` as the default model for the agent.

## Project Structure

```
Aura/
├── app/                    # Electron + Next.js frontend
│   ├── main/               # Electron main process
│   └── renderer/           # Next.js app
├── backend/                # Python FastAPI
│   ├── agent/              # Pydantic AI agent
│   ├── tools/              # Auto-discovered tools (pluggy)
│   └── services/           # Docker, Git, Project management
├── sandbox/                # Docker LaTeX environment
└── docs/plans/             # Design documents
```

## Tool Registration Pattern

Tools are auto-discovered via pluggy. Each tool file exports:

```python
from backend.tools.manager import hookimpl

@hookimpl
def register_tools() -> list[Tool]:
    return [Tool(my_function, description="...")]
```

Place tools in `backend/tools/<category>/<tool_name>.py`.

## Reference Projects

- **Paintress** (`/Users/zhongzhiyi/Desktop/paintress`): Reference for agent architecture, tool system (pluggy), streaming patterns
- **Appraiser** (`/Users/zhongzhiyi/Desktop/appraiser`): Reference for Colorist API integration

## Agent Capabilities (Priority Order)

1. Writing assistant - Draft/edit LaTeX, fix errors
2. Research helper - Search arXiv/Semantic Scholar, summarize papers
3. Compiler fixer - Auto-fix LaTeX compilation errors
4. Vibe matching - Mimic writing style (future)

## Build Order

See `docs/plans/2026-01-06-aura-design.md` for detailed 17-phase build plan.

Quick summary:
1. Phase 1: Docker LaTeX sandbox + FastAPI skeleton
2. Phase 2: Colorist client + Pydantic AI agent + tools
3. Phase 3: Research tools (arXiv, Semantic Scholar, PDF reader)
4. Phase 4: Electron shell + UI components
5. Phase 5: Git/Overleaf sync + packaging

## UI Layout

```
┌──────────┬─────────────────────┬─────────────┬──────────────┐
│ File Tree│   Monaco Editor     │ PDF Preview │ Agent Panel  │
│  200px   │     flexible        │    ~40%     │    350px     │
└──────────┴─────────────────────┴─────────────┴──────────────┘
```

## Key Dependencies

Backend:
- `pydantic-ai` - Agent framework
- `anthropic` - LLM client (pointed at Colorist)
- `pluggy` - Tool auto-discovery
- `docker` - LaTeX compilation
- `gitpython` - Overleaf sync

Frontend:
- `electron` - Desktop shell
- `next` - React framework
- `@monaco-editor/react` - LaTeX editor
- `react-pdf` - PDF viewer

## Common Commands

```bash
# Backend dev
cd backend && uvicorn main:app --reload --port 8000

# Frontend dev
cd app && npm run dev

# Build Docker image
cd sandbox && docker build -t aura-texlive .

# Full dev (both)
cd app && npm run dev  # runs concurrently
```

## Git Workflow

When committing:
- Always pull from origin main/master first
- Do not cite Claude Code in commit messages
