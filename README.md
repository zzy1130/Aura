# Aura: Local-First LaTeX IDE with AI Agent

Aura is a macOS desktop application for academic writing. It combines an Overleaf-style LaTeX editor with an embedded AI agent that can search papers, write content, fix compilation errors, and sync with Overleaf.

## Features

- **Overleaf-style UI**: Monaco editor + live PDF preview + file tree
- **AI Agent**: Claude-powered assistant with autonomous tool use
- **Research Tools**: Search arXiv, Semantic Scholar, read papers
- **Docker LaTeX**: Isolated compilation environment
- **Overleaf Sync**: Git-based push/pull to Overleaf projects
- **Local-first**: All files stored locally, no database

## Architecture

```
Electron App
├── Next.js UI (Monaco, PDF viewer, Agent panel)
└── Python Backend (FastAPI)
    ├── Pydantic AI Agent (Claude Sonnet 4.5 via Colorist)
    └── Tools (pluggy auto-discovery)
        ├── latex/compile
        ├── research/arxiv, semantic, pdf_reader
        ├── files/read, edit
        └── git/overleaf
```

## Prerequisites

- macOS
- Python 3.11+
- Node.js 18+
- Docker

## Getting Started

See [docs/plans/2026-01-06-aura-design.md](docs/plans/2026-01-06-aura-design.md) for the detailed design specification.

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd app
npm install
npm run dev
```

## License

MIT
