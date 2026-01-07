"""
History Processors for PydanticAI

These processors clean up and optimize message history before sending to LLM.
PydanticAI calls these functions to transform message history.

Usage:
    agent = Agent(
        ...,
        history_processors=[truncate_tool_results, remove_thinking_tools],
    )
"""

from copy import deepcopy
from typing import TYPE_CHECKING

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelMessage,
    ToolReturnPart,
)

if TYPE_CHECKING:
    pass


# Type alias for message list
Messages = list[ModelRequest | ModelResponse]


# =============================================================================
# Truncation Processor
# =============================================================================

def truncate_tool_results(
    messages: Messages,
    max_chars: int = 4000,
) -> Messages:
    """
    Truncate long tool results to prevent context overflow.

    PydanticAI history processor that truncates ToolReturnPart content.

    Args:
        messages: List of ModelRequest/ModelResponse messages
        max_chars: Maximum characters for tool result content

    Returns:
        Messages with truncated tool results
    """
    result = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Check if any parts need truncation
            needs_truncation = False
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    content = _get_content_str(part.content)
                    if len(content) > max_chars:
                        needs_truncation = True
                        break

            if needs_truncation:
                # Create new message with truncated parts
                new_parts = []
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        content = _get_content_str(part.content)
                        if len(content) > max_chars:
                            truncated = content[:max_chars]
                            truncated += f"\n... [truncated {len(content) - max_chars} chars]"
                            new_part = ToolReturnPart(
                                tool_name=part.tool_name,
                                content=truncated,
                                tool_call_id=part.tool_call_id,
                                metadata=part.metadata,
                                timestamp=part.timestamp,
                            )
                            new_parts.append(new_part)
                        else:
                            new_parts.append(part)
                    else:
                        new_parts.append(part)

                msg = ModelRequest(
                    parts=new_parts,
                    timestamp=msg.timestamp,
                    instructions=msg.instructions,
                    run_id=msg.run_id,
                    metadata=msg.metadata,
                )

            result.append(msg)
        else:
            result.append(msg)

    return result


def _get_content_str(content) -> str:
    """Convert content to string for length checking."""
    if isinstance(content, str):
        return content
    return str(content)


# =============================================================================
# Thinking Tool Processor
# =============================================================================

def remove_thinking_tools(messages: Messages) -> Messages:
    """
    Remove thinking tool calls and results from history.

    The think tool is for internal reasoning and doesn't need to persist
    in history, saving context tokens.

    Args:
        messages: List of ModelRequest/ModelResponse messages

    Returns:
        Messages with thinking tool calls removed
    """
    result = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Filter out think tool return parts
            new_parts = [
                part for part in msg.parts
                if not (isinstance(part, ToolReturnPart) and part.tool_name == "think")
            ]
            if new_parts:
                msg = ModelRequest(
                    parts=new_parts,
                    timestamp=msg.timestamp,
                    instructions=msg.instructions,
                    run_id=msg.run_id,
                    metadata=msg.metadata,
                )
                result.append(msg)
            # Skip empty requests
        elif isinstance(msg, ModelResponse):
            # Filter out think tool call parts from response
            from pydantic_ai.messages import ToolCallPart

            new_parts = [
                part for part in msg.parts
                if not (isinstance(part, ToolCallPart) and part.tool_name == "think")
            ]
            if new_parts:
                msg = ModelResponse(
                    parts=new_parts,
                    usage=msg.usage,
                    model_name=msg.model_name,
                    timestamp=msg.timestamp,
                    provider_name=msg.provider_name,
                    finish_reason=msg.finish_reason,
                    run_id=msg.run_id,
                    metadata=msg.metadata,
                )
                result.append(msg)
        else:
            result.append(msg)

    return result


# =============================================================================
# Empty Message Removal
# =============================================================================

def remove_empty_messages(messages: Messages) -> Messages:
    """
    Remove messages with no meaningful content.

    Args:
        messages: List of messages

    Returns:
        Messages with empty ones removed
    """
    result = []

    for msg in messages:
        if isinstance(msg, (ModelRequest, ModelResponse)):
            if msg.parts:
                result.append(msg)
        else:
            result.append(msg)

    return result


# =============================================================================
# Combined Pipeline
# =============================================================================

def create_history_processor(
    max_tool_result_chars: int = 4000,
    remove_thinking: bool = True,
) -> callable:
    """
    Create a combined history processor with configurable options.

    Args:
        max_tool_result_chars: Maximum chars for tool results
        remove_thinking: Whether to remove think tool calls

    Returns:
        History processor function
    """
    def process(messages: Messages) -> Messages:
        # Apply processors in sequence
        messages = truncate_tool_results(messages, max_chars=max_tool_result_chars)
        if remove_thinking:
            messages = remove_thinking_tools(messages)
        messages = remove_empty_messages(messages)
        return messages

    return process


# Default processor
default_history_processor = create_history_processor()
