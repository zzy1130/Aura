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


# ============ Health Check ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint for Electron app."""
    return {"status": "ok", "service": "aura-backend"}


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


class FileListRequest(BaseModel):
    project_path: str


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


# ============ Run Server ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
