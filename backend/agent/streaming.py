"""
Streaming Runner for PydanticAI Agent

Provides SSE (Server-Sent Events) streaming for the Aura agent.
Streams text deltas and tool events to the frontend.

Features:
- Text streaming with deltas
- Tool call and result events
- Automatic message compression for long conversations
- Human-in-the-loop (HITL) approval for dangerous operations
- Steering messages for mid-conversation guidance
"""

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Literal, Optional
import json
import logging

from pydantic_ai.agent import ModelRequestNode, CallToolsNode, UserPromptNode
from pydantic_ai.run import End
from pydantic_ai.messages import ToolCallPart, TextPart

from agent.pydantic_agent import aura_agent, AuraDeps
from agent.compression import compress_if_needed, get_compressor

logger = logging.getLogger(__name__)


# =============================================================================
# Stream Event Types
# =============================================================================

@dataclass
class StreamEvent:
    """Base class for stream events sent via SSE."""
    type: str

    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {json.dumps(self.to_dict())}\n\n"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        raise NotImplementedError


@dataclass
class TextDeltaEvent(StreamEvent):
    """Text chunk from the model."""
    type: Literal["text_delta"] = "text_delta"
    content: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content}


@dataclass
class ToolCallEvent(StreamEvent):
    """Tool is being called."""
    type: Literal["tool_call"] = "tool_call"
    tool_name: str = ""
    args: dict = None

    def __post_init__(self):
        if self.args is None:
            self.args = {}

    def to_dict(self) -> dict:
        return {"type": self.type, "tool_name": self.tool_name, "args": self.args}


@dataclass
class ToolResultEvent(StreamEvent):
    """Tool execution result."""
    type: Literal["tool_result"] = "tool_result"
    tool_name: str = ""
    result: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "tool_name": self.tool_name, "result": self.result}


@dataclass
class DoneEvent(StreamEvent):
    """Stream is complete."""
    type: Literal["done"] = "done"
    output: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "output": self.output,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            }
        }


@dataclass
class ErrorEvent(StreamEvent):
    """Error occurred during streaming."""
    type: Literal["error"] = "error"
    message: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message}


@dataclass
class CompressionEvent(StreamEvent):
    """History was compressed to save context space."""
    type: Literal["compression"] = "compression"
    original_messages: int = 0
    compressed_messages: int = 0
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "original_messages": self.original_messages,
            "compressed_messages": self.compressed_messages,
            "tokens_saved": self.estimated_tokens_before - self.estimated_tokens_after,
        }


@dataclass
class ApprovalRequiredEvent(StreamEvent):
    """Tool requires user approval before execution."""
    type: Literal["approval_required"] = "approval_required"
    request_id: str = ""
    tool_name: str = ""
    tool_args: dict = None

    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = {}

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
        }


@dataclass
class ApprovalResolvedEvent(StreamEvent):
    """Tool approval was resolved (approved/rejected)."""
    type: Literal["approval_resolved"] = "approval_resolved"
    request_id: str = ""
    status: str = ""  # "approved", "rejected", "modified", "timeout"
    tool_name: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "request_id": self.request_id,
            "status": self.status,
            "tool_name": self.tool_name,
        }


@dataclass
class SteeringEvent(StreamEvent):
    """Steering message was injected into the conversation."""
    type: Literal["steering"] = "steering"
    messages_count: int = 0
    content_preview: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "messages_count": self.messages_count,
            "content_preview": self.content_preview,
        }


# =============================================================================
# Streaming Runner
# =============================================================================

async def stream_agent_response(
    message: str,
    project_path: str,
    project_name: str = "",
    message_history: list = None,
    auto_compress: bool = True,
    enable_hitl: bool = False,
    enable_steering: bool = False,
    session_id: str | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Stream agent response as events.

    This is the main entry point for streaming agent interactions.
    It yields events that can be converted to SSE format.

    Args:
        message: User's message
        project_path: Path to the LaTeX project
        project_name: Optional project name (derived from path if not given)
        message_history: Optional conversation history for context
        auto_compress: Whether to automatically compress long histories (default: True)
        enable_hitl: Whether to enable human-in-the-loop approval (default: False)
        enable_steering: Whether to check for steering messages (default: False)
        session_id: Session ID for steering isolation (optional)

    Yields:
        StreamEvent objects (TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, CompressionEvent, ApprovalRequiredEvent, SteeringEvent)

    Example:
        async for event in stream_agent_response("Read main.tex", "/path/to/project"):
            yield event.to_sse()  # For SSE endpoints
    """
    # Process steering if enabled
    effective_message = message
    if enable_steering:
        from agent.steering import get_steering_manager, check_and_inject_steering

        steering_manager = get_steering_manager()
        effective_message, steering_used = await check_and_inject_steering(
            steering_manager, message, session_id
        )

        if steering_used:
            # Emit steering event
            preview = steering_used[0].content[:100] + "..." if len(steering_used[0].content) > 100 else steering_used[0].content
            yield SteeringEvent(
                messages_count=len(steering_used),
                content_preview=preview,
            )
            logger.info(f"Steering: Injected {len(steering_used)} messages")

    # Set up HITL if enabled
    hitl_manager = None
    event_queue: Optional[asyncio.Queue] = None

    if enable_hitl:
        from agent.hitl import get_hitl_manager

        hitl_manager = get_hitl_manager()
        event_queue = asyncio.Queue()

        # Set up callback to emit approval events to stream
        async def on_approval_request(request):
            await event_queue.put(ApprovalRequiredEvent(
                request_id=request.request_id,
                tool_name=request.tool_name,
                tool_args=request.tool_args,
            ))

        hitl_manager.set_event_callback(on_approval_request)

    deps = AuraDeps(
        project_path=project_path,
        project_name=project_name,
        hitl_manager=hitl_manager,
    )

    # Handle compression if enabled and history provided
    processed_history = message_history
    if auto_compress and message_history:
        try:
            compressor = get_compressor()
            tokens_before = compressor.counter.count(message_history)
            original_count = len(message_history)

            compressed_history, was_compressed = await compress_if_needed(message_history)

            if was_compressed:
                tokens_after = compressor.counter.count(compressed_history)
                logger.info(
                    f"Compressed history: {original_count} -> {len(compressed_history)} messages, "
                    f"{tokens_before} -> {tokens_after} tokens"
                )
                yield CompressionEvent(
                    original_messages=original_count,
                    compressed_messages=len(compressed_history),
                    estimated_tokens_before=tokens_before,
                    estimated_tokens_after=tokens_after,
                )
                processed_history = compressed_history
        except Exception as e:
            logger.warning(f"Compression failed, using original history: {e}")
            # Continue with original history on compression failure

    try:
        if enable_hitl and event_queue:
            # HITL mode: Run agent with event queue for approval events
            async for event in _stream_with_hitl(
                effective_message, deps, processed_history, event_queue
            ):
                yield event
        else:
            # Standard mode: Direct streaming
            async for event in _stream_standard(effective_message, deps, processed_history):
                yield event

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield ErrorEvent(message=str(e))


async def _stream_standard(
    message: str,
    deps: AuraDeps,
    message_history: list,
) -> AsyncIterator[StreamEvent]:
    """Standard streaming without HITL."""
    async with aura_agent.iter(message, deps=deps, message_history=message_history) as run:
        async for node in run:
            if isinstance(node, UserPromptNode):
                continue

            elif isinstance(node, ModelRequestNode):
                async with node.stream(run.ctx) as stream:
                    async for text in stream.stream_text(delta=True):
                        yield TextDeltaEvent(content=text)

            elif isinstance(node, CallToolsNode):
                for part in node.model_response.parts:
                    if isinstance(part, ToolCallPart):
                        try:
                            args = part.args_as_dict()
                        except Exception:
                            args = {}
                        yield ToolCallEvent(
                            tool_name=part.tool_name,
                            args=args,
                        )

            elif isinstance(node, End):
                pass

    result = run.result
    usage = result.usage()

    yield DoneEvent(
        output=result.output or "",
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
    )


async def _stream_with_hitl(
    message: str,
    deps: AuraDeps,
    message_history: list,
    event_queue: asyncio.Queue,
) -> AsyncIterator[StreamEvent]:
    """
    Streaming with HITL support.

    Uses asyncio.Queue to receive approval events from tools while
    the agent is processing. The agent runs in a background task,
    pushing events to the queue. This generator reads from the queue
    and yields events.
    """
    # Queue for all events (both agent events and HITL events)
    done_event = asyncio.Event()
    agent_error = None

    async def run_agent_task():
        """Run agent and push events to queue."""
        nonlocal agent_error
        try:
            async with aura_agent.iter(message, deps=deps, message_history=message_history) as run:
                async for node in run:
                    if isinstance(node, UserPromptNode):
                        continue

                    elif isinstance(node, ModelRequestNode):
                        async with node.stream(run.ctx) as stream:
                            async for text in stream.stream_text(delta=True):
                                await event_queue.put(TextDeltaEvent(content=text))

                    elif isinstance(node, CallToolsNode):
                        for part in node.model_response.parts:
                            if isinstance(part, ToolCallPart):
                                try:
                                    args = part.args_as_dict()
                                except Exception:
                                    args = {}
                                await event_queue.put(ToolCallEvent(
                                    tool_name=part.tool_name,
                                    args=args,
                                ))

                    elif isinstance(node, End):
                        pass

            result = run.result
            usage = result.usage()

            await event_queue.put(DoneEvent(
                output=result.output or "",
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
            ))

        except Exception as e:
            agent_error = e
            await event_queue.put(ErrorEvent(message=str(e)))

        finally:
            done_event.set()

    # Start agent in background
    agent_task = asyncio.create_task(run_agent_task())

    try:
        # Yield events as they come
        while not done_event.is_set() or not event_queue.empty():
            try:
                # Use timeout to periodically check done_event
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event

                # If it's a done or error event, we're finished
                if isinstance(event, (DoneEvent, ErrorEvent)):
                    break

            except asyncio.TimeoutError:
                # No event yet, continue waiting
                continue

    finally:
        # Ensure agent task is cleaned up
        if not agent_task.done():
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass


async def stream_agent_sse(
    message: str,
    project_path: str,
    project_name: str = "",
    message_history: list = None,
    enable_hitl: bool = False,
    enable_steering: bool = False,
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream agent response as SSE-formatted strings.

    Convenience wrapper for FastAPI StreamingResponse.

    Args:
        message: User's message
        project_path: Path to the LaTeX project
        project_name: Optional project name
        message_history: Optional conversation history
        enable_hitl: Whether to enable HITL approval (default: False)
        enable_steering: Whether to enable steering messages (default: False)
        session_id: Session ID for steering isolation (optional)

    Yields:
        SSE-formatted strings ready for StreamingResponse

    Example:
        @app.post("/chat/stream")
        async def chat_stream(request: ChatRequest):
            return StreamingResponse(
                stream_agent_sse(request.message, request.project_path),
                media_type="text/event-stream"
            )
    """
    async for event in stream_agent_response(
        message=message,
        project_path=project_path,
        project_name=project_name,
        message_history=message_history,
        enable_hitl=enable_hitl,
        enable_steering=enable_steering,
        session_id=session_id,
    ):
        yield event.to_sse()


# =============================================================================
# Non-streaming Runner
# =============================================================================

async def run_agent(
    message: str,
    project_path: str,
    project_name: str = "",
    message_history: list = None,
    auto_compress: bool = True,
    enable_steering: bool = False,
    session_id: str | None = None,
) -> dict:
    """
    Run agent and return complete response (non-streaming).

    Args:
        message: User's message
        project_path: Path to the LaTeX project
        project_name: Optional project name
        message_history: Optional conversation history
        auto_compress: Whether to automatically compress long histories (default: True)
        enable_steering: Whether to check for steering messages (default: False)
        session_id: Session ID for steering isolation (optional)

    Returns:
        Dictionary with output, usage, new_messages, compression_info, and steering_info
    """
    deps = AuraDeps(project_path=project_path, project_name=project_name)

    # Process steering if enabled
    effective_message = message
    steering_info = None
    if enable_steering:
        from agent.steering import get_steering_manager, check_and_inject_steering

        steering_manager = get_steering_manager()
        effective_message, steering_used = await check_and_inject_steering(
            steering_manager, message, session_id
        )

        if steering_used:
            steering_info = {
                "messages_injected": len(steering_used),
                "priorities": [m.priority for m in steering_used],
            }
            logger.info(f"Steering: Injected {len(steering_used)} messages into run_agent")

    # Handle compression if enabled and history provided
    processed_history = message_history
    compression_info = None

    if auto_compress and message_history:
        try:
            compressor = get_compressor()
            tokens_before = compressor.counter.count(message_history)
            original_count = len(message_history)

            compressed_history, was_compressed = await compress_if_needed(message_history)

            if was_compressed:
                tokens_after = compressor.counter.count(compressed_history)
                logger.info(
                    f"Compressed history: {original_count} -> {len(compressed_history)} messages, "
                    f"{tokens_before} -> {tokens_after} tokens"
                )
                compression_info = {
                    "original_messages": original_count,
                    "compressed_messages": len(compressed_history),
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "tokens_saved": tokens_before - tokens_after,
                }
                processed_history = compressed_history
        except Exception as e:
            logger.warning(f"Compression failed, using original history: {e}")

    result = await aura_agent.run(effective_message, deps=deps, message_history=processed_history)
    usage = result.usage()

    response = {
        "output": result.output,
        "usage": {
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
        },
        "new_messages": result.new_messages(),
    }

    if compression_info:
        response["compression"] = compression_info

    if steering_info:
        response["steering"] = steering_info

    return response
