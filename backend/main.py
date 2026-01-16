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
from services.memory import MemoryService
from services.latex_parser import parse_document, parse_bib_file_path, find_unused_citations

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


# ============ Health Check ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint for Electron app."""
    return {"status": "ok", "service": "aura-backend"}


@app.get("/api/info")
async def get_info():
    """Get information about the Aura backend."""
    from agent.subagents import list_subagents

    return {
        "name": "Aura Backend",
        "version": "0.1.0",
        "description": "Local-first LaTeX IDE with AI agent",
        "docker_available": docker_latex.is_available(),
        "subagents": [s["name"] for s in list_subagents()],
        "features": {
            "compilation": True,
            "streaming": True,
            "hitl": True,
            "planning": True,
            "steering": True,
            "compression": True,
        },
    }


# ============ Request/Response Models ============

class CompileRequest(BaseModel):
    project_path: str
    filename: str = "main.tex"


class CompileResponse(BaseModel):
    success: bool
    pdf_path: Optional[str] = None
    error_summary: str = ""
    log_output: str = ""
    docker_not_available: bool = False  # True if Docker is not installed/running


class CreateProjectRequest(BaseModel):
    name: str
    path: Optional[str] = None  # Custom path, if None uses ~/aura-projects/
    template: Optional[str] = None  # If None, creates empty project


class FileReadRequest(BaseModel):
    project_path: str
    filename: str


class FileWriteRequest(BaseModel):
    project_path: str
    filename: str
    content: str


class FileDeleteRequest(BaseModel):
    project_path: str
    filename: str


class FileRenameRequest(BaseModel):
    project_path: str
    old_filename: str
    new_filename: str


class FileCopyRequest(BaseModel):
    project_path: str
    source_filename: str
    dest_filename: str


class FileListRequest(BaseModel):
    project_path: str


class ChatRequest(BaseModel):
    message: str
    project_path: str
    history: Optional[list] = None


# ============ Memory Models ============

class MemoryEntryRequest(BaseModel):
    project_path: str


class AddPaperRequest(BaseModel):
    project_path: str
    title: str
    authors: list[str]
    arxiv_id: str = ""
    summary: str = ""
    tags: list[str] = []


class AddCitationRequest(BaseModel):
    project_path: str
    bibtex_key: str
    reason: str
    paper_id: Optional[str] = None


class AddConventionRequest(BaseModel):
    project_path: str
    rule: str
    example: str = ""


class AddTodoRequest(BaseModel):
    project_path: str
    task: str
    priority: str = "medium"
    status: str = "pending"


class AddNoteRequest(BaseModel):
    project_path: str
    content: str
    tags: list[str] = []


class UpdateEntryRequest(BaseModel):
    project_path: str
    data: dict


# ============ Vibe Research Models ============

class VibeResearchStartRequest(BaseModel):
    project_path: str
    topic: str
    max_papers: int = 100
    max_papers_to_read: int = 30
    target_hypotheses: int = 5


class VibeResearchRunRequest(BaseModel):
    project_path: str


class VibeResearchSessionRequest(BaseModel):
    project_path: str


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
        docker_not_available=result.docker_not_available,
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
    Serve the compiled PDF file from ~/aura-projects/.
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


class PdfRequest(BaseModel):
    project_path: str
    filename: str = "main.pdf"


@app.post("/api/pdf/serve")
async def serve_pdf(request: PdfRequest):
    """
    Serve a PDF file from any project path.
    """
    from pathlib import Path

    pdf_path = Path(request.project_path) / request.filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {request.filename}")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=request.filename,
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
        project = project_service.create(
            name=request.name,
            path=request.path,
            template=request.template,
        )
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


@app.post("/api/files/delete")
async def delete_file(request: FileDeleteRequest) -> dict:
    """Delete a file from a project."""
    from pathlib import Path

    project_path = Path(request.project_path)
    file_path = project_path / request.filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

    # Safety check: ensure file is within project directory
    try:
        file_path.resolve().relative_to(project_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if file_path.is_dir():
        import shutil
        shutil.rmtree(file_path)
    else:
        file_path.unlink()

    return {"success": True}


@app.post("/api/files/rename")
async def rename_file(request: FileRenameRequest) -> dict:
    """Rename a file in a project."""
    from pathlib import Path

    project_path = Path(request.project_path)
    old_path = project_path / request.old_filename
    new_path = project_path / request.new_filename

    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.old_filename}")

    if new_path.exists():
        raise HTTPException(status_code=400, detail=f"File already exists: {request.new_filename}")

    # Safety check: ensure both paths are within project directory
    try:
        old_path.resolve().relative_to(project_path.resolve())
        new_path.resolve().relative_to(project_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Create parent directory if needed
    new_path.parent.mkdir(parents=True, exist_ok=True)

    old_path.rename(new_path)

    return {"success": True, "new_path": str(new_path.relative_to(project_path))}


@app.post("/api/files/copy")
async def copy_file(request: FileCopyRequest) -> dict:
    """Copy a file or directory in a project."""
    from pathlib import Path
    import shutil

    project_path = Path(request.project_path)
    source_path = project_path / request.source_filename
    dest_path = project_path / request.dest_filename

    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Source not found: {request.source_filename}")

    if dest_path.exists():
        raise HTTPException(status_code=400, detail=f"Destination already exists: {request.dest_filename}")

    # Safety check: ensure both paths are within project directory
    try:
        source_path.resolve().relative_to(project_path.resolve())
        dest_path.resolve().relative_to(project_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Create parent directory if needed
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        shutil.copytree(source_path, dest_path)
    else:
        shutil.copy2(source_path, dest_path)

    return {"success": True, "new_path": str(dest_path.relative_to(project_path))}


@app.post("/api/files/list")
async def list_files(request: FileListRequest) -> list[dict]:
    """
    List files in a project directory.

    Works with any directory path, not just projects in ~/aura-projects/.
    """
    from pathlib import Path

    project_path = Path(request.project_path)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.project_path}")
    if not project_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {request.project_path}")

    return project_service.get_files(str(project_path))


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

    # Use project_path as session_id for conversation continuity
    session_id = request.project_path or "default"

    async def event_generator():
        try:
            async for sse_data in stream_agent_sse(
                message=request.message,
                project_path=request.project_path,
                message_history=request.history,
                session_id=session_id,
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

    # Use project_path as session_id for conversation continuity
    session_id = request.project_path or "default"

    try:
        result = await run_agent(
            message=request.message,
            project_path=request.project_path,
            message_history=request.history,
            session_id=session_id,
        )
        return {
            "response": result["output"],
            "usage": result["usage"],
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ClearChatRequest(BaseModel):
    project_path: str


@app.post("/api/chat/clear")
async def clear_chat_history(request: ClearChatRequest) -> dict:
    """
    Clear conversation history for a project.

    Use this to start a fresh conversation.
    """
    from agent.streaming import clear_session_history

    session_id = request.project_path or "default"
    clear_session_history(session_id)

    return {
        "success": True,
        "message": f"Cleared chat history for session: {session_id}",
    }


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


# ============ HITL (Human-in-the-Loop) Endpoints ============

class HITLApproveRequest(BaseModel):
    request_id: str
    modified_args: Optional[dict] = None


class HITLRejectRequest(BaseModel):
    request_id: str
    reason: str = "User rejected"


@app.get("/api/hitl/pending")
async def get_pending_approvals() -> list[dict]:
    """
    Get all pending HITL approval requests.

    Returns list of pending requests that need user approval.
    """
    from agent.hitl import get_hitl_manager

    manager = get_hitl_manager()
    pending = await manager.get_pending()

    return [req.to_dict() for req in pending]


@app.get("/api/hitl/request/{request_id}")
async def get_approval_request(request_id: str) -> dict:
    """
    Get a specific approval request by ID.
    """
    from agent.hitl import get_hitl_manager

    manager = get_hitl_manager()
    request = await manager.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return request.to_dict()


@app.post("/api/hitl/approve")
async def approve_request(request: HITLApproveRequest) -> dict:
    """
    Approve a pending HITL request.

    The tool will continue execution after approval.
    Optionally provide modified_args to change the tool arguments.
    """
    from agent.hitl import get_hitl_manager

    manager = get_hitl_manager()
    success = await manager.approve(
        request_id=request.request_id,
        modified_args=request.modified_args,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Request not found or already resolved"
        )

    return {
        "success": True,
        "request_id": request.request_id,
        "status": "approved" if not request.modified_args else "modified",
    }


@app.post("/api/hitl/reject")
async def reject_request(request: HITLRejectRequest) -> dict:
    """
    Reject a pending HITL request.

    The tool will return a rejection message to the agent.
    """
    from agent.hitl import get_hitl_manager

    manager = get_hitl_manager()
    success = await manager.reject(
        request_id=request.request_id,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Request not found or already resolved"
        )

    return {
        "success": True,
        "request_id": request.request_id,
        "status": "rejected",
        "reason": request.reason,
    }


@app.get("/api/hitl/config")
async def get_hitl_config() -> dict:
    """
    Get the current HITL configuration.

    Shows which tools require approval.
    """
    from agent.hitl import get_hitl_manager

    manager = get_hitl_manager()

    return {
        "approval_required": list(manager.config.approval_required),
        "preview_only": list(manager.config.preview_only),
        "approval_timeout": manager.config.approval_timeout,
        "auto_approve_on_timeout": manager.config.auto_approve_on_timeout,
    }


# ============ Steering Endpoints ============

class SteeringAddRequest(BaseModel):
    content: str
    priority: int = 0
    session_id: Optional[str] = None


@app.post("/api/steering/add")
async def add_steering(request: SteeringAddRequest) -> dict:
    """
    Add a steering message to guide the agent.

    Steering messages are injected into the next agent request
    to redirect or guide the agent's behavior.

    Priority levels:
        0 - Normal (default)
        1 - High (processed before normal)
        2 - Urgent (should interrupt if possible)
    """
    from agent.steering import get_steering_manager

    manager = get_steering_manager()
    message = await manager.add(
        content=request.content,
        priority=request.priority,
        session_id=request.session_id,
    )

    return {
        "success": True,
        "message_id": message.message_id,
        "priority": message.priority,
        "queue_size": manager.queue_size(),
    }


@app.get("/api/steering/pending")
async def get_pending_steering(session_id: Optional[str] = None) -> dict:
    """
    Get pending steering messages without removing them.

    Useful for UI to display what steering is queued.
    """
    from agent.steering import get_steering_manager

    manager = get_steering_manager()
    messages = await manager.peek(session_id=session_id)

    return {
        "count": len(messages),
        "messages": [msg.to_dict() for msg in messages],
    }


@app.delete("/api/steering/clear")
async def clear_steering(session_id: Optional[str] = None) -> dict:
    """
    Clear all pending steering messages.

    Optionally filter by session_id to clear only for a specific session.
    """
    from agent.steering import get_steering_manager

    manager = get_steering_manager()
    cleared = await manager.clear(session_id=session_id)

    return {
        "success": True,
        "cleared_count": cleared,
    }


@app.get("/api/steering/config")
async def get_steering_config() -> dict:
    """
    Get the current steering configuration.
    """
    from agent.steering import get_steering_manager

    manager = get_steering_manager()

    return {
        "max_queue_size": manager.config.max_queue_size,
        "default_priority": manager.config.default_priority,
        "combine_messages": manager.config.combine_messages,
        "current_queue_size": manager.queue_size(),
    }


# ============ Subagent Endpoints ============

class SubagentRunRequest(BaseModel):
    subagent: str
    task: str
    project_path: Optional[str] = None


@app.get("/api/subagents")
async def get_available_subagents() -> list[dict]:
    """
    List all available subagents.

    Returns a list of subagents with their names and descriptions.
    """
    from agent.subagents import list_subagents

    return list_subagents()


@app.post("/api/subagents/run")
async def run_subagent_endpoint(request: SubagentRunRequest) -> dict:
    """
    Run a subagent directly (for testing/debugging).

    This endpoint bypasses the main agent and runs a subagent directly.
    Useful for testing subagent behavior.

    Args:
        subagent: Name of the subagent ("research" or "compiler")
        task: Task description for the subagent
        project_path: Optional project path (required for compiler)

    Returns:
        Result from the subagent
    """
    from agent.subagents import run_subagent, list_subagents

    # Validate subagent name
    available = list_subagents()
    available_names = [s["name"] for s in available]

    if request.subagent not in available_names:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown subagent: '{request.subagent}'. Available: {', '.join(available_names)}"
        )

    try:
        context = {}
        if request.project_path:
            context["project_path"] = request.project_path

        result = await run_subagent(
            name=request.subagent,
            task=request.task,
            context=context,
            project_path=request.project_path or "",
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Subagent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Planning Endpoints ============

class CreatePlanRequest(BaseModel):
    task: str
    project_path: str
    project_name: Optional[str] = None
    session_id: Optional[str] = None


class UpdateStepRequest(BaseModel):
    step_id: str
    status: str  # "completed", "failed", "skipped"
    output: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None


class PlanSessionRequest(BaseModel):
    session_id: Optional[str] = None


@app.post("/api/planning/create")
async def create_plan_endpoint(request: CreatePlanRequest) -> dict:
    """
    Create a structured plan for a complex task.

    Uses the PlannerAgent to analyze the task and generate
    a step-by-step execution plan.

    Returns:
        The created plan with steps and metadata
    """
    from agent.subagents.planner import create_plan_for_task
    from agent.planning import get_plan_manager

    try:
        plan = await create_plan_for_task(
            task=request.task,
            project_path=request.project_path,
            project_name=request.project_name or "",
        )

        if not plan:
            raise HTTPException(
                status_code=500,
                detail="Failed to create plan. Please try with more details."
            )

        # Register the plan with the manager
        plan_manager = get_plan_manager()
        await plan_manager.create_plan(
            goal=plan.goal,
            original_request=request.task,
            steps=[s.to_dict() for s in plan.steps],
            session_id=request.session_id or "default",
            context=plan.context,
            complexity=plan.complexity,
            estimated_files=plan.estimated_files,
            risks=plan.risks,
            assumptions=plan.assumptions,
        )

        return {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "status": plan.status.value,
            "complexity": plan.complexity,
            "steps": [s.to_dict() for s in plan.steps],
            "estimated_files": plan.estimated_files,
            "risks": plan.risks,
            "assumptions": plan.assumptions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Planning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/planning/current")
async def get_current_plan_endpoint(session_id: Optional[str] = None) -> dict:
    """
    Get the current active plan for a session.

    Returns:
        The current plan with progress info, or empty if no plan
    """
    from agent.planning import get_plan_manager

    plan_manager = get_plan_manager()
    plan = await plan_manager.get_plan(session_id or "default")

    if not plan:
        return {
            "has_plan": False,
            "message": "No active plan",
        }

    return {
        "has_plan": True,
        "plan_id": plan.plan_id,
        "goal": plan.goal,
        "status": plan.status.value,
        "progress": plan.progress,
        "current_step": plan.current_step.to_dict() if plan.current_step else None,
        "steps": [s.to_dict() for s in plan.steps],
        "markdown": plan.to_markdown(),
    }


@app.post("/api/planning/start")
async def start_plan_endpoint(request: PlanSessionRequest) -> dict:
    """
    Start executing the current plan.

    Marks the plan as in-progress and returns the first step.
    """
    from agent.planning import get_plan_manager, PlanStatus

    plan_manager = get_plan_manager()
    session_id = request.session_id or "default"
    plan = await plan_manager.get_plan(session_id)

    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    if plan.status not in [PlanStatus.DRAFT, PlanStatus.APPROVED]:
        raise HTTPException(
            status_code=400,
            detail=f"Plan is already {plan.status.value}"
        )

    # Approve and start
    await plan_manager.approve_plan(session_id)
    step = await plan_manager.start_next_step(session_id)

    return {
        "success": True,
        "status": "in_progress",
        "current_step": step.to_dict() if step else None,
    }


@app.post("/api/planning/step/complete")
async def complete_step_endpoint(request: UpdateStepRequest) -> dict:
    """
    Mark the current step as completed.

    Automatically advances to the next step if available.
    """
    from agent.planning import get_plan_manager, PlanStatus

    plan_manager = get_plan_manager()
    session_id = request.session_id or "default"

    plan = await plan_manager.get_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    current = plan.current_step
    if not current:
        raise HTTPException(status_code=400, detail="No step in progress")

    # Complete current step
    await plan_manager.complete_current_step(
        output=request.output or "",
        session_id=session_id,
    )

    # Refresh plan
    plan = await plan_manager.get_plan(session_id)

    # Start next step if plan not complete
    next_step = None
    if plan.status != PlanStatus.COMPLETED:
        next_step = await plan_manager.start_next_step(session_id)

    return {
        "success": True,
        "completed_step": current.to_dict(),
        "plan_status": plan.status.value,
        "next_step": next_step.to_dict() if next_step else None,
        "progress": plan.progress,
    }


@app.post("/api/planning/step/fail")
async def fail_step_endpoint(request: UpdateStepRequest) -> dict:
    """
    Mark the current step as failed.
    """
    from agent.planning import get_plan_manager

    plan_manager = get_plan_manager()
    session_id = request.session_id or "default"

    plan = await plan_manager.get_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    current = plan.current_step
    if not current:
        raise HTTPException(status_code=400, detail="No step in progress")

    # Fail current step
    await plan_manager.fail_current_step(
        error=request.error or "Step failed",
        session_id=session_id,
    )

    return {
        "success": True,
        "failed_step": current.to_dict(),
        "error": request.error,
    }


@app.post("/api/planning/step/skip")
async def skip_step_endpoint(request: UpdateStepRequest) -> dict:
    """
    Skip the current step.
    """
    from agent.planning import get_plan_manager, StepStatus

    plan_manager = get_plan_manager()
    session_id = request.session_id or "default"

    plan = await plan_manager.get_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    current = plan.current_step
    if not current:
        raise HTTPException(status_code=400, detail="No step in progress")

    # Skip current step
    await plan_manager.update_step(
        current.step_id,
        StepStatus.SKIPPED,
        request.output or "Skipped",
        session_id=session_id,
    )

    # Start next step
    next_step = await plan_manager.start_next_step(session_id)

    return {
        "success": True,
        "skipped_step": current.to_dict(),
        "next_step": next_step.to_dict() if next_step else None,
    }


@app.post("/api/planning/cancel")
async def cancel_plan_endpoint(request: PlanSessionRequest) -> dict:
    """
    Cancel/abandon the current plan.
    """
    from agent.planning import get_plan_manager

    plan_manager = get_plan_manager()
    session_id = request.session_id or "default"

    plan = await plan_manager.get_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    progress = plan.progress
    await plan_manager.cancel_plan(session_id)

    return {
        "success": True,
        "cancelled_goal": plan.goal,
        "progress_at_cancellation": progress,
    }


@app.get("/api/planning/history")
async def get_plan_history_endpoint(
    session_id: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Get recent plan history for a session.

    Returns completed/cancelled plans for reference.
    """
    from agent.planning import get_plan_manager

    plan_manager = get_plan_manager()
    history = await plan_manager.get_history(session_id or "default", limit=limit)

    return {
        "count": len(history),
        "plans": [
            {
                "plan_id": p.plan_id,
                "goal": p.goal,
                "status": p.status.value,
                "progress": p.progress,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }
            for p in history
        ],
    }


# ============ Memory Endpoints ============

@app.get("/api/memory")
async def get_memory(project_path: str):
    """Get all memory entries for a project."""
    service = MemoryService(project_path)
    memory = service.load()
    stats = service.get_stats()

    return {
        "entries": {
            "papers": memory.papers,
            "citations": memory.citations,
            "conventions": memory.conventions,
            "todos": memory.todos,
            "notes": memory.notes,
        },
        "stats": stats,
    }


@app.get("/api/memory/stats")
async def get_memory_stats(project_path: str):
    """Get memory token count and warning status."""
    service = MemoryService(project_path)
    return service.get_stats()


@app.post("/api/memory/papers")
async def add_paper(request: AddPaperRequest):
    """Add a paper entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("papers", {
        "title": request.title,
        "authors": request.authors,
        "arxiv_id": request.arxiv_id,
        "summary": request.summary,
        "tags": request.tags,
    })
    return entry


@app.post("/api/memory/citations")
async def add_citation(request: AddCitationRequest):
    """Add a citation entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("citations", {
        "bibtex_key": request.bibtex_key,
        "reason": request.reason,
        "paper_id": request.paper_id,
    })
    return entry


@app.post("/api/memory/conventions")
async def add_convention(request: AddConventionRequest):
    """Add a convention entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("conventions", {
        "rule": request.rule,
        "example": request.example,
    })
    return entry


@app.post("/api/memory/todos")
async def add_todo(request: AddTodoRequest):
    """Add a todo entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("todos", {
        "task": request.task,
        "priority": request.priority,
        "status": request.status,
    })
    return entry


@app.post("/api/memory/notes")
async def add_note(request: AddNoteRequest):
    """Add a note entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("notes", {
        "content": request.content,
        "tags": request.tags,
    })
    return entry


@app.put("/api/memory/{entry_type}/{entry_id}")
async def update_memory_entry(
    entry_type: str,
    entry_id: str,
    request: UpdateEntryRequest,
):
    """Update a memory entry."""
    if entry_type not in ["papers", "citations", "conventions", "todos", "notes"]:
        raise HTTPException(status_code=400, detail=f"Invalid entry type: {entry_type}")

    service = MemoryService(request.project_path)
    entry = service.update_entry(entry_type, entry_id, request.data)

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry


@app.delete("/api/memory/{entry_type}/{entry_id}")
async def delete_memory_entry(
    entry_type: str,
    entry_id: str,
    project_path: str,
):
    """Delete a memory entry."""
    if entry_type not in ["papers", "citations", "conventions", "todos", "notes"]:
        raise HTTPException(status_code=400, detail=f"Invalid entry type: {entry_type}")

    service = MemoryService(project_path)
    success = service.delete_entry(entry_type, entry_id)

    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"success": True}


class ClearMemoryRequest(BaseModel):
    project_path: str


@app.post("/api/memory/clear")
async def clear_memory(request: ClearMemoryRequest):
    """Clear all memory entries for a project."""
    from services.memory import MemoryData

    service = MemoryService(request.project_path)
    # Create a fresh empty memory
    empty_memory = MemoryData()
    service.save(empty_memory)

    return {"success": True, "message": "Memory cleared"}


# ============ Git/Overleaf Sync Endpoints ============

class SyncSetupRequest(BaseModel):
    project_path: str
    overleaf_url: str
    username: Optional[str] = None
    password: Optional[str] = None


class SyncRequest(BaseModel):
    project_path: str
    commit_message: Optional[str] = None


class SyncStatusRequest(BaseModel):
    project_path: str


@app.post("/api/sync/status")
async def get_sync_status(request: SyncStatusRequest) -> dict:
    """
    Get synchronization status for a project.

    Returns information about git state, remote connection,
    and pending changes.
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    status = await sync.get_status()

    return status.to_dict()


@app.post("/api/sync/setup")
async def setup_sync(request: SyncSetupRequest) -> dict:
    """
    Set up Git/Overleaf synchronization for a project.

    Args:
        project_path: Path to the LaTeX project
        overleaf_url: Overleaf git URL (https://git.overleaf.com/<project_id>)
        username: Overleaf email (optional)
        password: Overleaf password or token (optional)

    The Overleaf git URL can be found in:
    Project Settings > Git Integration > Clone URL
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    result = await sync.setup(
        overleaf_url=request.overleaf_url,
        username=request.username,
        password=request.password,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.to_dict()


@app.post("/api/sync/pull")
async def sync_pull(request: SyncRequest) -> dict:
    """
    Pull changes from Overleaf.

    Downloads new changes from the Overleaf server and merges
    them with local files. Local uncommitted changes are stashed
    and reapplied after the pull.
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    result = await sync.pull()

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.to_dict()


@app.post("/api/sync/push")
async def sync_push(request: SyncRequest) -> dict:
    """
    Push local changes to Overleaf.

    Commits any uncommitted changes and pushes them to Overleaf.
    If the remote has new changes, you'll need to pull first.
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    result = await sync.push(commit_message=request.commit_message)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.to_dict()


@app.post("/api/sync")
async def sync_project(request: SyncRequest) -> dict:
    """
    Full sync: pull then push.

    This is the recommended sync operation as it handles
    both incoming and outgoing changes in one operation.
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    result = await sync.sync(commit_message=request.commit_message)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.to_dict()


class ResolveConflictRequest(BaseModel):
    project_path: str
    filepath: str
    keep: str = "ours"  # "ours" or "theirs"


@app.post("/api/sync/resolve")
async def resolve_conflict(request: ResolveConflictRequest) -> dict:
    """
    Resolve a merge conflict by choosing a version.

    Args:
        filepath: Path to the conflicted file
        keep: "ours" (local version) or "theirs" (remote version)
    """
    from services.git_sync import GitSyncService

    if request.keep not in ("ours", "theirs"):
        raise HTTPException(
            status_code=400,
            detail="keep must be 'ours' or 'theirs'"
        )

    sync = GitSyncService(request.project_path)
    result = await sync.resolve_conflict(request.filepath, keep=request.keep)

    return result.to_dict()


@app.post("/api/sync/abort")
async def abort_merge(request: SyncRequest) -> dict:
    """
    Abort an in-progress merge.

    Use this to cancel a merge that has conflicts and start fresh.
    """
    from services.git_sync import GitSyncService

    sync = GitSyncService(request.project_path)
    result = await sync.abort_merge()

    return result.to_dict()


# ============ Vibe Research Endpoints ============

@app.post("/api/vibe-research/start")
async def start_vibe_research(request: VibeResearchStartRequest) -> dict:
    """
    Start a new vibe research session.

    Vibe research is AI-led autonomous research that:
    1. Clarifies scope with the user
    2. Discovers relevant papers via arXiv and Semantic Scholar
    3. Synthesizes themes from the literature
    4. Identifies research gaps
    5. Generates novel hypotheses
    6. Evaluates and ranks hypotheses

    Args:
        project_path: Path to the LaTeX project
        topic: Research topic or question
        max_papers: Maximum papers to discover (default: 100)
        max_papers_to_read: Maximum papers to read in full (default: 30)
        target_hypotheses: Target number of hypotheses (default: 5)

    Returns:
        Session info including session_id
    """
    from agent.vibe_state import VibeResearchState

    # Create new state
    state = VibeResearchState(
        topic=request.topic,
        max_papers=request.max_papers,
        max_papers_to_read=request.max_papers_to_read,
        target_hypotheses=request.target_hypotheses,
    )

    # Save to project
    state.save(request.project_path)

    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "phase": state.current_phase.value,
        "created_at": state.created_at,
        "config": {
            "max_papers": state.max_papers,
            "max_papers_to_read": state.max_papers_to_read,
            "target_hypotheses": state.target_hypotheses,
        },
    }


@app.get("/api/vibe-research/sessions")
async def list_vibe_sessions(project_path: str) -> dict:
    """
    List all vibe research sessions for a project.

    Returns sessions sorted by creation date (newest first).
    """
    from agent.vibe_state import VibeResearchState

    sessions = VibeResearchState.list_sessions(project_path)

    return {
        "count": len(sessions),
        "sessions": sessions,
    }


@app.get("/api/vibe-research/status/{session_id}")
async def get_vibe_status(session_id: str, project_path: str) -> dict:
    """
    Get status summary for a vibe research session.

    Returns phase, progress, and counts.
    """
    from agent.vibe_state import VibeResearchState

    state = VibeResearchState.load(project_path, session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "phase": state.current_phase.value,
        "progress": state.phase_progress.get(state.current_phase.value, 0),
        "is_complete": state.is_complete,
        "stall_count": state.stall_count,
        "papers_found": len(state.papers),
        "papers_read": len(state.papers_read),
        "themes_count": len(state.themes),
        "gaps_count": len(state.gaps),
        "hypotheses_count": len(state.hypotheses),
    }


@app.get("/api/vibe-research/state/{session_id}")
async def get_vibe_state(session_id: str, project_path: str) -> dict:
    """
    Get full state for a vibe research session.

    Returns complete state including papers, themes, gaps, and hypotheses.
    """
    from agent.vibe_state import VibeResearchState

    state = VibeResearchState.load(project_path, session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return state.to_dict()


@app.get("/api/vibe-research/report/{session_id}")
async def get_vibe_report(session_id: str, project_path: str) -> dict:
    """
    Get the final report for a completed vibe research session.

    Returns the generated report and ranked hypotheses.
    """
    from agent.vibe_state import VibeResearchState
    from pathlib import Path

    state = VibeResearchState.load(project_path, session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not state.is_complete:
        return {
            "session_id": state.session_id,
            "is_complete": False,
            "phase": state.current_phase.value,
            "message": "Research is still in progress",
            "report": "",
            "report_path": None,
            "hypotheses": [],
        }

    # Check if report files exist in subdirectory
    base_filename = state.get_report_filename()
    report_dir = Path(project_path) / "report" / base_filename
    tex_filename = f"{base_filename}.tex"
    bib_filename = f"{base_filename}.bib"
    tex_path = report_dir / tex_filename
    bib_path = report_dir / bib_filename

    return {
        "session_id": state.session_id,
        "is_complete": True,
        "topic": state.topic,
        "report": state.report,
        "report_path": str(tex_path) if tex_path.exists() else None,
        "report_filename": f"report/{base_filename}/{tex_filename}",
        "bib_path": str(bib_path) if bib_path.exists() else None,
        "bib_filename": f"report/{base_filename}/{bib_filename}",
        "hypotheses": state.get_ranked_hypotheses(),
        "papers_count": len(state.papers),
        "themes_count": len(state.themes),
        "gaps_count": len(state.gaps),
    }


@app.post("/api/vibe-research/run/{session_id}")
async def run_vibe_iteration(session_id: str, request: VibeResearchRunRequest) -> dict:
    """
    Run one iteration of vibe research.

    The research agent will perform one action based on current state.
    Call this repeatedly until is_complete=True or use streaming endpoint.

    Returns:
        Updated status and the action taken
    """
    from agent.vibe_state import VibeResearchState, ResearchPhase
    from agent.subagents.research import ResearchAgent, ResearchMode

    state = VibeResearchState.load(request.project_path, session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if state.is_complete:
        return {
            "session_id": state.session_id,
            "is_complete": True,
            "message": "Research already complete",
            "phase": state.current_phase.value,
        }

    # Run one iteration via research agent in VIBE mode
    try:
        # Mark session as running
        _running_vibe_sessions[session_id] = True

        # Create agent in VIBE mode (uses longer timeout)
        agent = ResearchAgent(mode=ResearchMode.VIBE)

        # Determine task based on phase
        phase_tasks = {
            ResearchPhase.SCOPING: f"Clarify the scope for research on: {state.topic}",
            ResearchPhase.DISCOVERY: f"Search for papers on: {state.topic}",
            ResearchPhase.SYNTHESIS: "Analyze papers and identify themes",
            ResearchPhase.IDEATION: "Identify gaps and generate hypotheses",
            ResearchPhase.EVALUATION: "Score and rank hypotheses",
        }
        task = phase_tasks.get(state.current_phase, f"Continue research on: {state.topic}")

        result = await agent.run(
            task=task,
            project_path=request.project_path,
            mode=ResearchMode.VIBE,
            vibe_state=state,
        )

        # Check if stopped
        if not _running_vibe_sessions.get(session_id, True):
            return {
                "session_id": session_id,
                "is_complete": False,
                "stopped": True,
                "message": "Research stopped by user",
                "phase": state.current_phase.value,
            }

        # Reload state (agent may have modified it)
        state = VibeResearchState.load(request.project_path, session_id)

        return {
            "session_id": state.session_id,
            "is_complete": state.is_complete,
            "phase": state.current_phase.value,
            "progress": state.phase_progress.get(state.current_phase.value, 0),
            "last_action": state.last_action,
            "output": result.output if result else "",
            "papers_found": len(state.papers),
            "hypotheses_count": len(state.hypotheses),
        }

    except Exception as e:
        logger.error(f"Vibe research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up running state
        _running_vibe_sessions.pop(session_id, None)


@app.post("/api/vibe-research/stream/{session_id}")
async def stream_vibe_research(session_id: str, request: VibeResearchRunRequest):
    """
    Stream vibe research progress via Server-Sent Events.

    Runs the research agent continuously until completion or error,
    streaming progress updates.
    """
    from agent.vibe_state import VibeResearchState, ResearchPhase
    from agent.subagents.research import ResearchAgent, ResearchMode

    state = VibeResearchState.load(request.project_path, session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    async def event_generator():
        nonlocal state

        try:
            # Create agent in VIBE mode (uses longer timeout)
            agent = ResearchAgent(mode=ResearchMode.VIBE)

            while not state.is_complete:
                # Yield current status
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "type": "status",
                        "phase": state.current_phase.value,
                        "progress": state.phase_progress.get(state.current_phase.value, 0),
                        "papers_found": len(state.papers),
                        "hypotheses_count": len(state.hypotheses),
                    }),
                }

                # Determine task
                phase_tasks = {
                    ResearchPhase.SCOPING: f"Clarify the scope for research on: {state.topic}",
                    ResearchPhase.DISCOVERY: f"Search for papers on: {state.topic}",
                    ResearchPhase.SYNTHESIS: "Analyze papers and identify themes",
                    ResearchPhase.IDEATION: "Identify gaps and generate hypotheses",
                    ResearchPhase.EVALUATION: "Score and rank hypotheses",
                }
                task = phase_tasks.get(state.current_phase, f"Continue research on: {state.topic}")

                # Run iteration
                result = await agent.run(
                    task=task,
                    project_path=request.project_path,
                    mode=ResearchMode.VIBE,
                    vibe_state=state,
                )

                # Reload state
                state = VibeResearchState.load(request.project_path, session_id)

                # Yield action
                yield {
                    "event": "action",
                    "data": json.dumps({
                        "type": "action",
                        "action": state.last_action,
                        "output": result.output[:500] if result else "",
                    }),
                }

            # Complete
            yield {
                "event": "complete",
                "data": json.dumps({
                    "type": "complete",
                    "session_id": state.session_id,
                    "hypotheses_count": len(state.hypotheses),
                }),
            }

        except Exception as e:
            logger.error(f"Vibe research stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "message": str(e),
                }),
            }

    return EventSourceResponse(event_generator())


# Track running vibe research sessions for cancellation
_running_vibe_sessions: dict[str, bool] = {}


@app.delete("/api/vibe-research/{session_id}")
async def delete_vibe_session(session_id: str, project_path: str) -> dict:
    """
    Delete a vibe research session.

    Args:
        session_id: The session ID to delete
        project_path: Path to the project

    Returns:
        Confirmation of deletion
    """
    from pathlib import Path

    # Check if session exists
    aura_dir = Path(project_path) / ".aura"
    state_file = aura_dir / f"vibe_research_{session_id}.json"

    if not state_file.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Mark as stopped if running
    _running_vibe_sessions[session_id] = False

    # Delete the file
    state_file.unlink()

    return {
        "success": True,
        "message": f"Session {session_id} deleted",
    }


@app.post("/api/vibe-research/stop/{session_id}")
async def stop_vibe_session(session_id: str) -> dict:
    """
    Stop a running vibe research session.

    This sets a flag that will be checked by the running agent.
    The agent will stop after completing its current action.

    Args:
        session_id: The session ID to stop

    Returns:
        Confirmation that stop was requested
    """
    _running_vibe_sessions[session_id] = False

    return {
        "success": True,
        "message": f"Stop requested for session {session_id}",
    }


def is_session_running(session_id: str) -> bool:
    """Check if a session should continue running."""
    return _running_vibe_sessions.get(session_id, True)


def mark_session_running(session_id: str):
    """Mark a session as running."""
    _running_vibe_sessions[session_id] = True


def mark_session_stopped(session_id: str):
    """Mark a session as stopped."""
    _running_vibe_sessions.pop(session_id, None)


# ============ Writing Intelligence Endpoints ============

class AnalyzeStructureRequest(BaseModel):
    project_path: str
    filepath: str = "main.tex"


class CreateTableRequest(BaseModel):
    project_path: str
    data: str
    caption: str
    label: str = ""
    style: str = "booktabs"


class CreateFigureRequest(BaseModel):
    project_path: str
    description: str
    figure_type: str = "tikz"
    caption: str = ""
    label: str = ""
    data: str = ""


@app.post("/api/analyze-structure")
async def api_analyze_structure(request: AnalyzeStructureRequest):
    """Analyze document structure."""
    from pathlib import Path

    filepath = Path(request.project_path) / request.filepath

    # SECURITY: Path traversal check
    try:
        filepath.resolve().relative_to(Path(request.project_path).resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filepath")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content = filepath.read_text()
    structure = parse_document(content)

    return {
        "sections": [
            {
                "name": s.name,
                "level": s.level,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "label": s.label,
            }
            for s in structure.sections
        ],
        "elements": [
            {
                "type": e.type,
                "caption": e.caption,
                "label": e.label,
                "line_start": e.line_start,
                "line_end": e.line_end,
            }
            for e in structure.elements
        ],
        "citations": [
            {
                "key": c.key,
                "locations": c.locations,
                "command": c.command,
            }
            for c in structure.citations
        ],
        "citation_style": structure.citation_style,
        "bib_file": structure.bib_file,
        "packages": structure.packages,
    }


@app.post("/api/clean-bibliography")
async def api_clean_bibliography(request: AnalyzeStructureRequest):
    """Find unused bibliography entries."""
    from pathlib import Path

    filepath = Path(request.project_path) / request.filepath

    # SECURITY: Path traversal check
    try:
        filepath.resolve().relative_to(Path(request.project_path).resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filepath")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content = filepath.read_text()
    structure = parse_document(content)

    if not structure.bib_file:
        return {"unused": [], "message": "No bibliography file detected"}

    bib_path = Path(request.project_path) / structure.bib_file

    # SECURITY: Path traversal check for bib file
    try:
        bib_path.resolve().relative_to(Path(request.project_path).resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bibliography path")

    if not bib_path.exists():
        raise HTTPException(status_code=404, detail=f"Bibliography file not found: {structure.bib_file}")

    bib_entries = parse_bib_file_path(bib_path)
    unused = find_unused_citations(structure.citations, bib_entries)

    return {
        "unused": [
            {
                "key": e.key,
                "title": e.fields.get("title", ""),
                "year": e.fields.get("year", ""),
            }
            for e in unused
        ],
        "total_entries": len(bib_entries),
        "cited_count": len(structure.citations),
    }


# ============ Run Server ============

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Aura Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
