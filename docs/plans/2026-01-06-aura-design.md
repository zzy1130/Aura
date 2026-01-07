# Aura: Local-First LaTeX IDE with AI Agent

## Overview

Aura is a **macOS desktop application** for academic writing. It combines an Overleaf-style LaTeX editor with an embedded AI agent that can search papers, write content, fix compilation errors, and sync with Overleaf.

### Core Principles

- **Local-first**: All files stored on disk (`~/aura-projects/`), no database
- **Single-user**: Personal tool, no auth required
- **Agent-native**: Claude-powered agent with autonomous tool use
- **Overleaf-compatible**: Git sync to Overleaf projects

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Electron App (.app on macOS)                       │
│  ┌─────────────────────────────────────────────────┐│
│  │  Next.js UI                                     ││
│  │  - Monaco Editor + PDF Preview                  ││
│  │  - Agent Panel (SSE streaming)                  ││
│  │  - File Tree                                    ││
│  └─────────────────────────────────────────────────┘│
│                         ↓ SSE                       │
│  ┌─────────────────────────────────────────────────┐│
│  │  Python Backend (FastAPI)                       ││
│  │  ┌─────────────────────────────────────────────┐││
│  │  │  Pydantic AI Agent                          │││
│  │  │  - Colorist gateway (Claude Sonnet 4.5)     │││
│  │  │  - Streaming iterator                       │││
│  │  │  - Tool manager (pluggy)                    │││
│  │  └─────────────────────────────────────────────┘││
│  │  ┌─────────────────────────────────────────────┐││
│  │  │  Tools (auto-discovered)                    │││
│  │  │  - latex/compile, latex/lint                │││
│  │  │  - research/arxiv, research/semantic        │││
│  │  │  - files/read, files/edit                   │││
│  │  │  - git/sync                                 │││
│  │  └─────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
         ↓                           ↓
    Local Files                 Docker (texlive)
    ~/aura-projects/
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Desktop shell | Electron |
| Frontend | Next.js 14 + Tailwind CSS |
| Editor | Monaco Editor |
| Backend | Python + FastAPI |
| Agent framework | Pydantic AI |
| LLM | Claude Sonnet 4.5 (`claude-4-5-sonnet-by-all`) via Colorist gateway |
| Tool system | Pluggy (auto-discovery) |
| LaTeX compilation | Docker + texlive |
| Git sync | GitPython |
| Storage | Local filesystem |

---

## UI Layout

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ ● ● ●                              Aura - my-research-paper                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  📁 Open   📄 New   ▶ Compile   ⟳ Sync to Overleaf                          ⚙ Settings │
├──────────┬────────────────────────────────────┬──────────────────┬─────────────────────┤
│ FILES    │ main.tex                        ×  │                  │ AGENT              │
│──────────│────────────────────────────────────│                  │─────────────────────│
│          │  1│ \documentclass[12pt]{article}  │                  │                     │
│ ▼ my-paper│  2│ \usepackage{amsmath}          │                  │ You: Add a related  │
│   main.tex│  3│ \usepackage{biblatex}         │                  │ work section about  │
│   refs.bib│  4│ \addbibresource{refs.bib}     │   ┌──────────┐   │ transformer models  │
│  ▶ figures│  5│                               │   │          │   │                     │
│           │  6│ \title{My Research Paper}     │   │   PDF    │   │─────────────────────│
│           │  7│ \author{Author Name}          │   │ Preview  │   │                     │
│           │  8│ \date{\today}                 │   │          │   │ Agent:              │
│           │  9│                               │   │  Page 1  │   │ ▶ search_arxiv      │
│           │ 10│ \begin{document}              │   │   of 3   │   │   query="transformer│
│           │ 11│ \maketitle                    │   │          │   │   attention NLP"    │
│           │ 12│                               │   │          │   │                     │
│           │ 13│ \section{Introduction}        │   └──────────┘   │ ✓ Found 5 papers    │
│           │ 14│                               │                  │   - Attention Is... │
│           │ 15│ Deep learning has revolutio..│                  │   - BERT: Pre-tra...│
│           │ 16│                               │   ◀  1/3  ▶     │   - GPT-3: Language. │
│           │ 17│ \section{Related Work}        │                  │                     │
│           │ 18│ % TODO: Add content here      │   [Zoom: 100%]   │ ▶ read_file         │
│           │ 19│                               │                  │   "main.tex"        │
│           │ 20│ \section{Methodology}         │                  │                     │
│           │ 21│                               │                  │ ▶ edit_file         │
│           │ 22│ \end{document}                │                  │   adding section... │
│           │   │                               │                  │                     │
│           │   │                               │                  │ ✓ Done. Added 3     │
│           │   │                               │                  │   citations.        │
│           │───│───────────────────────────────│                  │                     │
│           │ Ln 17, Col 1      UTF-8    LaTeX  │                  │─────────────────────│
├──────────┴────────────────────────────────────┴──────────────────┤                     │
│ ✓ Compiled successfully                              12:34 PM    │ [Ask the agent... ] │
└──────────────────────────────────────────────────────────────────┴─────────────────────┘
```

### Panel Sizes

| Panel | Width |
|-------|-------|
| File Tree | 200px |
| Editor | flexible |
| PDF Preview | ~40% |
| Agent Panel | 350px |

---

## Project Structure

```
Aura/
├── app/                          # Electron + Next.js
│   ├── main/
│   │   ├── index.ts              # Electron entry
│   │   ├── python.ts             # Spawn/kill Python backend
│   │   ├── ipc.ts                # IPC handlers
│   │   └── preload.ts            # IPC bridge
│   ├── renderer/
│   │   ├── components/
│   │   │   ├── Editor/           # Monaco LaTeX editor
│   │   │   ├── FileTree/         # Project browser
│   │   │   ├── PDFViewer/        # Compiled output
│   │   │   ├── AgentPanel/       # Chat + streaming events
│   │   │   └── Toolbar/          # Compile, sync buttons
│   │   ├── hooks/
│   │   │   └── useAgentStream.ts # SSE consumer hook
│   │   └── app/
│   │       └── page.tsx          # Main layout
│   └── package.json
│
├── backend/
│   ├── main.py                   # FastAPI + SSE endpoints
│   ├── agent/
│   │   ├── core.py               # Pydantic AI agent setup
│   │   ├── colorist.py           # Colorist gateway client
│   │   ├── context.py            # AgentContext dataclass
│   │   └── prompts.py            # System prompts
│   ├── tools/
│   │   ├── manager.py            # Pluggy-based discovery
│   │   ├── latex/
│   │   │   ├── compile.py        # run_latex
│   │   │   └── parse_log.py      # extract_errors
│   │   ├── research/
│   │   │   ├── arxiv.py          # search_arxiv
│   │   │   ├── semantic.py       # search_semantic_scholar
│   │   │   └── pdf_reader.py     # read_paper
│   │   ├── files/
│   │   │   ├── read.py           # read_file
│   │   │   ├── edit.py           # edit_file
│   │   │   └── glob.py           # find_files
│   │   └── git/
│   │       └── overleaf.py       # pull_overleaf, push_overleaf
│   ├── services/
│   │   ├── docker.py             # Container management
│   │   ├── git_sync.py           # Overleaf Git operations
│   │   └── project.py            # Project CRUD (filesystem)
│   └── requirements.txt
│
├── sandbox/
│   └── Dockerfile                # texlive image
│
├── docs/
│   └── plans/
│       └── 2026-01-06-aura-design.md
│
└── projects/                     # User's LaTeX projects (gitignored)
    └── example-paper/
        ├── main.tex
        ├── refs.bib
        └── .aura/
            ├── config.json       # Overleaf URL, preferences
            └── history.json      # Conversation history
```

---

## Agent Architecture

### Agent Loop

The agent runs as a **tool-use loop** using Pydantic AI:

```
User Message ──→ Claude API ──→ Tool Calls? ──→ No ───→ Response
                    ↑              │                      │
                    │             Yes                     │
                    │              ↓                      │
                    └─── Execute Tools ←──────────────────┘
                         (loop until done)
```

### Colorist Integration

LLM calls route through Colorist gateway:

```python
from anthropic import AsyncAnthropic

class ColoristClient:
    def __init__(self):
        self.client = AsyncAnthropic(
            api_key="vk_...",  # Colorist API key
            base_url="https://colorist-gateway-staging.arco.ai/v1",
        )
```

### Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read .tex, .bib, or any project file |
| `edit_file` | Replace text in files |
| `find_files` | Glob pattern search |
| `run_latex` | Compile in Docker, return logs |
| `search_arxiv` | Search papers, return abstracts |
| `search_semantic_scholar` | Search with citation data |
| `read_paper` | Download and parse PDF to text |
| `pull_overleaf` | Pull from Overleaf |
| `push_overleaf` | Push to Overleaf |

### Tool Manager (Pluggy)

Tools are auto-discovered from `backend/tools/*/`:

```python
class ToolManager:
    def __init__(self):
        self.pm = pluggy.PluginManager("aura")
        self._discover_tools()  # Scan tools/*/*.py

    def get_all_tools(self) -> list[Tool]:
        return self.pm.hook.register_tools()
```

Each tool file exports:

```python
@hookimpl
def register_tools() -> list[Tool]:
    return [Tool(my_function, description="...")]
```

---

## Agent Capabilities (Priority Order)

1. **Writing assistant** - Draft/edit LaTeX content, fix errors, improve clarity
2. **Research helper** - Search arXiv/Semantic Scholar, summarize papers, suggest citations
3. **Compiler fixer** - Auto-detect and fix LaTeX compilation errors
4. **Vibe matching** - Mimic writing style from reference papers (future)

---

## Streaming Architecture

### Backend (SSE)

```python
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for event in run_agent_stream(...):
            if hasattr(event, "text_delta"):
                yield {"event": "text", "data": json.dumps({...})}
            elif hasattr(event, "tool_call"):
                yield {"event": "tool_call", "data": json.dumps({...})}
            # ...

    return EventSourceResponse(event_generator())
```

### Frontend (React Hook)

```typescript
export function useAgentStream(backendUrl: string) {
  const sendMessage = useCallback(async (message, projectPath) => {
    const response = await fetch(`${backendUrl}/api/chat/stream`, {...});
    const reader = response.body?.getReader();

    while (reader) {
      const { done, value } = await reader.read();
      // Parse SSE events, update state
    }
  }, []);

  return { messages, isStreaming, sendMessage };
}
```

---

## Docker LaTeX Sandbox

### Dockerfile

```dockerfile
FROM texlive/texlive:latest

RUN tlmgr update --self && tlmgr install \
    biblatex biber algorithm2e booktabs \
    hyperref cleveref todonotes xcolor tikz pgfplots

WORKDIR /workspace
CMD ["/bin/bash"]
```

### Compilation Service

```python
class DockerLatex:
    async def compile(self, project_path: str, filename: str) -> CompileResult:
        container = self.client.containers.run(
            "aura-texlive",
            command=f"pdflatex -interaction=nonstopmode {filename}",
            volumes={project_path: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            remove=True,
        )
        # Return success/failure + logs
```

---

## Git/Overleaf Sync

### Setup

```python
async def setup(self, overleaf_git_url: str):
    repo = Repo.init(self.project_path)
    repo.create_remote("overleaf", overleaf_git_url)
```

### Pull/Push

```python
async def pull(self):
    repo.remotes.overleaf.fetch()
    repo.git.merge("overleaf/master", allow_unrelated_histories=True)

async def push(self, commit_message: str):
    repo.index.add("*")
    repo.index.commit(commit_message)
    repo.remotes.overleaf.push(refspec="HEAD:master")
```

---

## Electron Shell

### Main Process

```typescript
function startPythonBackend() {
  pythonProcess = spawn('python', ['-m', 'uvicorn', 'main:app', '--port', '8000'], {
    cwd: backendPath,
    env: {
      ...process.env,
      COLORIST_API_KEY: '...',
      COLORIST_GATEWAY_URL: 'https://colorist-gateway-staging.arco.ai',
    },
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  setTimeout(createWindow, 2000);  // Wait for backend
});

app.on('before-quit', () => {
  pythonProcess?.kill();
});
```

### IPC Bridge

```typescript
// Expose to renderer
contextBridge.exposeInMainWorld('aura', {
  openProject: () => ipcRenderer.invoke('open-project'),
  newProject: (name) => ipcRenderer.invoke('new-project', name),
  getBackendUrl: () => 'http://localhost:8000',
});
```

---

## Dependencies

### Backend (requirements.txt)

```
fastapi>=0.109.0
uvicorn>=0.27.0
sse-starlette>=1.8.0
pydantic>=2.5.0
pydantic-ai>=0.0.14
anthropic>=0.40.0
pluggy>=1.3.0
httpx>=0.26.0
arxiv>=2.1.0
marker-pdf>=0.2.0
docker>=7.0.0
gitpython>=3.1.41
python-multipart>=0.0.6
```

### Frontend (package.json)

```json
{
  "dependencies": {
    "next": "14.1.0",
    "react": "^18",
    "@monaco-editor/react": "^4.6.0",
    "lucide-react": "^0.300.0",
    "react-pdf": "^7.7.0"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.9.0",
    "concurrently": "^8.2.0",
    "tailwindcss": "^3.3.0",
    "typescript": "^5"
  }
}
```

---

## Build Order

### Phase 1: Foundation ✅ COMPLETED (2026-01-06)

1. **Project scaffolding** ✅
   - Create directory structure
   - Initialize package.json, requirements.txt

2. **Docker LaTeX sandbox** ✅
   - Build Dockerfile with texlive
   - Test pdflatex compilation

3. **Backend skeleton** ✅
   - FastAPI app with /api/compile endpoint
   - DockerLatex service
   - ProjectService for file management

**Commits:**
- `8aaa85b` Add project directory structure
- `1aa4c0f` Simplify Docker LaTeX sandbox
- `09018b3` Add backend services for Phase 1
- `9b73c33` Add FastAPI endpoints for compilation and projects

### Phase 2: Agent Core (COMPLETE)

4. **Colorist client** ✓
   - Anthropic SDK with gateway URL (auth_token, no /v1 suffix)
   - Model: `claude-4-5-sonnet-by-all` (Colorist gateway format)
   - Test basic message creation

5. **Tool manager (pluggy)** ✓
   - Auto-discovery from tools/
   - File tools: read_file, edit_file, write_file, find_files, list_directory
   - LaTeX tools: compile_latex, check_latex_syntax, get_compilation_log

6. **Pydantic AI agent** ✓
   - Agent loop with tools (backend/agent/core.py)
   - SSE streaming endpoint (/api/chat/stream)
   - AgentContext for state management

**Files created:**
- `backend/agent/colorist.py` - Colorist gateway client
- `backend/agent/core.py` - Agentic loop with tool execution
- `backend/agent/context.py` - AgentContext dataclass
- `backend/agent/prompts.py` - System prompts
- `backend/tools/manager.py` - Pluggy-based tool manager
- `backend/tools/files/operations.py` - File tools
- `backend/tools/latex/compile.py` - LaTeX tools

### Phase 3: Advanced Agent Features ✅ COMPLETED

**See detailed doc:** `docs/plans/2026-01-06-phase3-advanced-agent.md`

| Sub-Phase | Feature | Status |
|-----------|---------|--------|
| 3A | PydanticAI migration + Colorist provider | ✅ |
| 3B | Message compression | ✅ |
| 3C | HITL (Human-in-the-loop) | ✅ |
| 3D | Steering messages | ✅ |
| 3E | Multi-agent (subagents: research, compiler) | ✅ |
| 3F | Planning system (PlannerAgent) | ✅ |

**Key files:**
- `backend/agent/pydantic_agent.py` - Main agent (17 tools including planning)
- `backend/agent/streaming.py` - SSE streaming with events
- `backend/agent/compression.py` - Message compression
- `backend/agent/hitl.py` - Human-in-the-loop approval
- `backend/agent/steering.py` - Mid-conversation guidance
- `backend/agent/planning.py` - Structured planning system
- `backend/agent/subagents/` - Research, Compiler, Planner agents

### Phase 3.5: Research Tools ✅ COMPLETED

7. **PDF reader tool** ✅
   - PyMuPDF (fitz) for PDF text extraction
   - Extract text from academic papers with page structure
   - arXiv PDF download with caching
   - URL-based PDF download
   - Integrated into ResearchAgent as `read_arxiv_paper` and `read_pdf_url` tools

**Files created:**
- `backend/agent/tools/pdf_reader.py` - PDF extraction module

### Phase 4: Electron App (IN PROGRESS)

8. **Electron shell** ✅
    - Main process with Python backend spawning
    - IPC bridge (preload script)
    - macOS titlebar integration

9. **Monaco editor component** ✅
    - LaTeX syntax highlighting (custom tokenizer)
    - Aura dark theme
    - Save keybinding (⌘S)

10. **File tree component** ✅
    - Tree view with expand/collapse
    - File type icons
    - Selection state

11. **PDF viewer component** ✅
    - react-pdf integration
    - Page navigation
    - Zoom controls

12. **Agent panel component** ✅
    - SSE streaming consumer
    - Message display (user/assistant)
    - Tool call visualization with expandable details

12. **Backend API wiring** ✅
    - API client utility (app/lib/api.ts)
    - File operations (read, write, list)
    - Compilation with PDF display
    - Error handling with dismissible banners

**Remaining:**
- Test full Electron app flow end-to-end
- Polish and error handling

### Phase 5: Git & Polish

13. **Git/Overleaf sync**
    - Setup, pull, push
    - Conflict detection

14. **Toolbar & settings**
    - Compile button
    - Sync button
    - Overleaf URL config

15. **Packaging**
    - electron-builder config
    - Bundle Python backend
    - Create .dmg for macOS

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `COLORIST_API_KEY` | API key for Colorist gateway |
| `COLORIST_GATEWAY_URL` | Gateway URL (default: staging) |

### Project Config (`.aura/config.json`)

```json
{
  "overleaf_url": "https://git.overleaf.com/PROJECT_ID",
  "default_compiler": "pdflatex",
  "vibe_references": []
}
```

---

## Success Criteria

- **Zero-Error Compilation**: Agent-submitted code must compile
- **Fact-Groundedness**: All citations must be real (no hallucinations)
- **Responsive UI**: Streaming events render in <100ms
- **Reliable Sync**: Git operations handle conflicts gracefully

---

## Development Scripts

### Starting the Application

```bash
# Start both backend and frontend
./scripts/start.sh

# Start backend only
./scripts/start.sh --backend-only

# Start frontend only (assumes backend running)
./scripts/start.sh --frontend-only

# Start backend and run tests
./scripts/start.sh --test
```

### Testing the API

```bash
# Run full API test suite (requires backend running)
python scripts/test_api.py

# Verbose output
python scripts/test_api.py --verbose

# Custom backend URL
python scripts/test_api.py --base-url http://localhost:8080
```

### Test Coverage

The test suite validates:
- Health & info endpoints (4 tests)
- Project operations (3 tests)
- File operations (3 tests)
- HITL endpoints (2 tests)
- Steering endpoints (2 tests)
- Planning endpoints (2 tests)
- Compression endpoints (1 test)
