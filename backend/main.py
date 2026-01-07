"""
Aura Backend API

FastAPI server providing:
- LaTeX compilation via Docker
- Project management
- Agent chat streaming (PydanticAI)
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

from services.docker import DockerLatex, CompileResult
from services.project import ProjectService, ProjectInfo

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
    from services.project import PROJECTS_DIR

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
    from services.project import PROJECTS_DIR

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

    Uses PydanticAI-based agent with streaming support.
    """
    from agent.streaming import stream_agent_sse

    async def event_generator():
        try:
            async for sse_data in stream_agent_sse(
                message=request.message,
                project_path=request.project_path,
                message_history=request.history,
            ):
                # SSE data is already formatted as "data: {...}\n\n"
                # Parse it to get event type and content
                if sse_data.startswith("data: "):
                    data = json.loads(sse_data[6:].strip())
                    yield {
                        "event": data.get("type", "message"),
                        "data": json.dumps(data),
                    }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())


@app.post("/api/chat/simple")
async def chat_simple(request: ChatRequest) -> dict:
    """
    Simple non-streaming chat endpoint.

    Returns the complete response after agent finishes.
    Uses PydanticAI-based agent.
    """
    from agent.streaming import run_agent

    try:
        result = await run_agent(
            message=request.message,
            project_path=request.project_path,
            message_history=request.history,
        )
        return {
            "response": result["output"],
            "usage": result["usage"],
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools")
async def list_tools() -> list[dict]:
    """List all available agent tools."""
    from agent.pydantic_agent import aura_agent

    # Get tool definitions from PydanticAI agent
    tools = []
    toolset = aura_agent._function_toolset
    if toolset and hasattr(toolset, '_tools'):
        for name, tool in toolset._tools.items():
            tools.append({
                "name": name,
                "description": tool.description or "",
            })
    return tools


# ============ Compression Endpoints ============

class CompressionStatsRequest(BaseModel):
    history: list


@app.post("/api/compression/stats")
async def get_compression_stats(request: CompressionStatsRequest) -> dict:
    """
    Get compression statistics for a message history.

    Returns token estimates and whether compression would be triggered.
    """
    from agent.compression import get_compressor

    compressor = get_compressor()
    return compressor.get_compression_stats(request.history)


@app.post("/api/compression/compress")
async def compress_history(request: CompressionStatsRequest) -> dict:
    """
    Manually compress a message history.

    Returns the compressed history and statistics.
    """
    from agent.compression import get_compressor

    compressor = get_compressor()
    stats_before = compressor.get_compression_stats(request.history)

    if not compressor.should_compress(request.history):
        return {
            "compressed": False,
            "reason": "History does not meet compression threshold",
            "stats": stats_before,
        }

    try:
        compressed = await compressor.compress(request.history)
        stats_after = compressor.get_compression_stats(compressed)

        return {
            "compressed": True,
            "original_messages": len(request.history),
            "compressed_messages": len(compressed),
            "tokens_before": stats_before["estimated_tokens"],
            "tokens_after": stats_after["estimated_tokens"],
            "tokens_saved": stats_before["estimated_tokens"] - stats_after["estimated_tokens"],
            "history": compressed,
        }
    except Exception as e:
        logger.error(f"Compression error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Run Server ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
