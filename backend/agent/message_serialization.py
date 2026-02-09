"""
Shared Message Serialization / Deserialization

Converts PydanticAI messages (ModelRequest/ModelResponse) to/from
JSON-serializable dicts. Handles all 4 part types:
- UserPromptPart
- TextPart
- ToolCallPart
- ToolReturnPart

Used by both ChatSession (streaming.py) and VibeResearchState (vibe_state.py).
"""

import logging
from datetime import datetime, timezone

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

logger = logging.getLogger(__name__)


def serialize_messages(pydantic_messages: list) -> list[dict]:
    """
    Serialize PydanticAI messages to JSON-serializable dicts.

    Handles ModelRequest (with UserPromptPart, ToolReturnPart) and
    ModelResponse (with TextPart, ToolCallPart).

    Args:
        pydantic_messages: List of ModelRequest/ModelResponse objects

    Returns:
        List of serialized message dicts
    """
    serialized = []
    for msg in pydantic_messages:
        if isinstance(msg, ModelRequest):
            parts_data = []
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    parts_data.append({
                        "type": "user_prompt",
                        "content": part.content,
                        "timestamp": part.timestamp.isoformat() if part.timestamp else None,
                    })
                elif isinstance(part, ToolReturnPart):
                    parts_data.append({
                        "type": "tool_return",
                        "tool_name": part.tool_name,
                        "tool_call_id": part.tool_call_id,
                        "content": part.content,
                        "timestamp": part.timestamp.isoformat() if part.timestamp else None,
                    })
                elif hasattr(part, "to_dict"):
                    parts_data.append(part.to_dict())
                else:
                    parts_data.append({
                        "type": part.__class__.__name__,
                        "data": str(part),
                    })
            serialized.append({
                "type": "ModelRequest",
                "parts": parts_data,
            })
        elif isinstance(msg, ModelResponse):
            parts_data = []
            for part in msg.parts:
                if isinstance(part, TextPart):
                    parts_data.append({
                        "type": "text",
                        "content": part.content,
                    })
                elif isinstance(part, ToolCallPart):
                    try:
                        args = part.args_as_dict()
                    except Exception as e:
                        logger.error(f"Failed to serialize tool call args: {e}")
                        args = {"_parse_error": str(e)}
                    parts_data.append({
                        "type": "tool_call",
                        "tool_name": part.tool_name,
                        "tool_call_id": part.tool_call_id,
                        "args": args,
                    })
                elif hasattr(part, "to_dict"):
                    parts_data.append(part.to_dict())
                else:
                    parts_data.append({
                        "type": part.__class__.__name__,
                        "data": str(part),
                    })
            serialized.append({
                "type": "ModelResponse",
                "parts": parts_data,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "model_name": getattr(msg, "model_name", None),
            })
        else:
            serialized.append({
                "type": msg.__class__.__name__,
                "data": str(msg),
            })
    return serialized


def deserialize_messages(serialized: list[dict]) -> list:
    """
    Reconstruct PydanticAI messages from serialized dicts.

    Handles all 4 part types: UserPromptPart, TextPart, ToolCallPart,
    ToolReturnPart.

    Args:
        serialized: List of serialized message dicts

    Returns:
        List of ModelRequest/ModelResponse objects
    """
    reconstructed = []
    for msg in serialized:
        msg_type = msg.get("type", "")

        if msg_type == "ModelRequest":
            parts = []
            for part_data in msg.get("parts", []):
                part_type = part_data.get("type", "")
                if part_type == "user_prompt":
                    ts = part_data.get("timestamp")
                    timestamp = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
                    parts.append(UserPromptPart(
                        content=part_data.get("content", ""),
                        timestamp=timestamp,
                    ))
                elif part_type == "tool_return":
                    ts = part_data.get("timestamp")
                    timestamp = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
                    parts.append(ToolReturnPart(
                        tool_name=part_data.get("tool_name", ""),
                        tool_call_id=part_data.get("tool_call_id", ""),
                        content=part_data.get("content", ""),
                        timestamp=timestamp,
                    ))

            if parts:
                reconstructed.append(ModelRequest(parts=parts))

        elif msg_type == "ModelResponse":
            parts = []
            for part_data in msg.get("parts", []):
                part_type = part_data.get("type", "")
                if part_type == "text":
                    parts.append(TextPart(content=part_data.get("content", "")))
                elif part_type == "tool_call":
                    parts.append(ToolCallPart(
                        tool_name=part_data.get("tool_name", ""),
                        tool_call_id=part_data.get("tool_call_id", ""),
                        args=part_data.get("args", {}),
                    ))

            if parts:
                ts = msg.get("timestamp")
                timestamp = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
                reconstructed.append(ModelResponse(
                    parts=parts,
                    timestamp=timestamp,
                    model_name=msg.get("model_name", "history"),
                ))

    # Ensure proper alternation - PydanticAI requires history ending with ModelRequest
    if reconstructed and isinstance(reconstructed[-1], ModelResponse):
        reconstructed = reconstructed[:-1]

    return reconstructed
