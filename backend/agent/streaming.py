"""
Streaming Runner for PydanticAI Agent

Provides SSE (Server-Sent Events) streaming for the Aura agent.
Streams text deltas and tool events to the frontend.

Features:
- Text streaming with deltas
- Tool call and result events
- Automatic message compression for long conversations
"""

from dataclasses import dataclass
from typing import AsyncIterator, Literal
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


# =============================================================================
# Streaming Runner
# =============================================================================

async def stream_agent_response(
    message: str,
    project_path: str,
    project_name: str = "",
    message_history: list = None,
    auto_compress: bool = True,
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

    Yields:
        StreamEvent objects (TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, CompressionEvent)

    Example:
        async for event in stream_agent_response("Read main.tex", "/path/to/project"):
            yield event.to_sse()  # For SSE endpoints
    """
    deps = AuraDeps(project_path=project_path, project_name=project_name)

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
        async with aura_agent.iter(message, deps=deps, message_history=processed_history) as run:
            async for node in run:
                # Skip UserPromptNode - it's just our input
                if isinstance(node, UserPromptNode):
                    continue

                elif isinstance(node, ModelRequestNode):
                    # Stream text deltas from the model
                    async with node.stream(run.ctx) as stream:
                        async for text in stream.stream_text(delta=True):
                            yield TextDeltaEvent(content=text)

                elif isinstance(node, CallToolsNode):
                    # Report tool calls from the model response
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
                    # Stream is complete
                    pass

        # Get final result
        result = run.result
        usage = result.usage()

        yield DoneEvent(
            output=result.output or "",
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )

    except Exception as e:
        yield ErrorEvent(message=str(e))


async def stream_agent_sse(
    message: str,
    project_path: str,
    project_name: str = "",
    message_history: list = None,
) -> AsyncIterator[str]:
    """
    Stream agent response as SSE-formatted strings.

    Convenience wrapper for FastAPI StreamingResponse.

    Args:
        message: User's message
        project_path: Path to the LaTeX project
        project_name: Optional project name
        message_history: Optional conversation history

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
) -> dict:
    """
    Run agent and return complete response (non-streaming).

    Args:
        message: User's message
        project_path: Path to the LaTeX project
        project_name: Optional project name
        message_history: Optional conversation history
        auto_compress: Whether to automatically compress long histories (default: True)

    Returns:
        Dictionary with output, usage, new_messages, and compression_info
    """
    deps = AuraDeps(project_path=project_path, project_name=project_name)

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

    result = await aura_agent.run(message, deps=deps, message_history=processed_history)
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

    return response
