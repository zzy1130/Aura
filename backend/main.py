"""
Aura Backend API

FastAPI server providing:
- LaTeX compilation via Docker
- Project management
- Agent chat streaming
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import logging
import json

from backend.services.docker import DockerLatex, CompileResult
from backend.services.project import ProjectService, ProjectInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Aura Backend API",
    description="Local-first LaTeX IDE with AI agent",
    version="0.1.0"
)

# CORS for Electron app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
docker_latex = DockerLatex()
project_service = ProjectService()


# ============ Request/Response Models ============

class CompileRequest(BaseModel):
    project_path: str
    filename: str = "main.tex"


class CompileResponse(BaseModel):
    success: bool
    pdf_path: Optional[str] = None
    error_summary: str = ""
    log_output: str = ""


class CreateProjectRequest(BaseModel):
    name: str
    template: str = "article"


class FileReadRequest(BaseModel):
    project_path: str
    filename: str


class FileWriteRequest(BaseModel):
    project_path: str
    filename: str
    content: str


class ChatRequest(BaseModel):
    message: str
    project_path: str
    history: Optional[list] = None


# ============ Health Check ============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Aura Backend",
        "version": "0.1.0",
        "docker_available": docker_latex.is_available(),
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "docker": docker_latex.is_available(),
    }


# ============ Compilation Endpoints ============

@app.post("/api/compile", response_model=CompileResponse)
async def compile_latex(request: CompileRequest):
    """
    Compile a LaTeX project to PDF.

    Runs pdflatex in Docker container with bibliography support.
    """
    logger.info(f"Compiling {request.filename} in {request.project_path}")

    result: CompileResult = await docker_latex.compile(
        project_path=request.project_path,
        filename=request.filename,
    )

    return CompileResponse(
        success=result.success,
        pdf_path=result.pdf_path,
        error_summary=result.error_summary,
        log_output=result.log_output[-5000:] if result.log_output else "",  # Limit log size
    )


@app.post("/api/check-syntax", response_model=CompileResponse)
async def check_syntax(request: CompileRequest):
    """
    Quick syntax check without full compilation.
    """
    result = await docker_latex.check_syntax(
        project_path=request.project_path,
        filename=request.filename,
    )

    return CompileResponse(
        success=result.success,
        error_summary=result.error_summary,
        log_output=result.log_output[-2000:] if result.log_output else "",
    )


@app.get("/api/pdf/{project_name}")
async def get_pdf(project_name: str, filename: str = "main.pdf"):
    """
    Serve the compiled PDF file.
    """
    from backend.services.project import PROJECTS_DIR

    pdf_path = PROJECTS_DIR / project_name / filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
    )


# ============ Project Endpoints ============

@app.get("/api/projects")
async def list_projects() -> list[dict]:
    """List all projects."""
    projects = project_service.list_all()
    return [
        {
            "name": p.name,
            "path": p.path,
            "has_overleaf": p.has_overleaf,
            "last_modified": p.last_modified,
        }
        for p in projects
    ]


@app.post("/api/projects")
async def create_project(request: CreateProjectRequest) -> dict:
    """Create a new project."""
    try:
        project = project_service.create(name=request.name, template=request.template)
        return {
            "name": project.name,
            "path": project.path,
            "has_overleaf": project.has_overleaf,
            "last_modified": project.last_modified,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects/{project_name}/files")
async def get_project_files(project_name: str) -> list[dict]:
    """Get file tree for a project."""
    from backend.services.project import PROJECTS_DIR

    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    return project_service.get_files(str(project_path))


@app.post("/api/files/read")
async def read_file(request: FileReadRequest) -> dict:
    """Read a file from a project."""
    try:
        content = project_service.read_file(request.project_path, request.filename)
        return {"content": content}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/files/write")
async def write_file(request: FileWriteRequest) -> dict:
    """Write to a file in a project."""
    project_service.write_file(
        request.project_path,
        request.filename,
        request.content,
    )
    return {"success": True}


# ============ Agent Chat Endpoints ============

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream agent responses via Server-Sent Events.

    The agent will process the message and may use tools to help
    with LaTeX editing, compilation, and research.
    """
    from backend.agent.core import run_agent_stream

    async def event_generator():
        try:
            async for event in run_agent_stream(
                message=request.message,
                project_path=request.project_path,
                history=request.history,
            ):
                yield {
                    "event": event.type,
                    "data": json.dumps(event.content) if event.content else "",
                }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@app.post("/api/chat/simple")
async def chat_simple(request: ChatRequest) -> dict:
    """
    Simple non-streaming chat endpoint.

    Returns the complete response after agent finishes.
    """
    from backend.agent.core import get_agent
    from backend.agent.context import AgentContext

    context = AgentContext(
        project_path=request.project_path,
        history=request.history or [],
    )

    agent = get_agent()
    response = await agent.run_simple(request.message, context)

    return {
        "response": response,
        "history": context.history,
    }


@app.get("/api/tools")
async def list_tools() -> list[dict]:
    """List all available agent tools."""
    from backend.tools.manager import get_tool_manager

    manager = get_tool_manager()
    return [
        {
            "name": tool.name,
            "description": tool.description,
        }
        for tool in manager.get_all_tools()
    ]


# ============ Run Server ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
