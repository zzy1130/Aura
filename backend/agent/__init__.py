# Agent module (Phase 2 + Phase 3)

from agent.pydantic_agent import aura_agent, AuraDeps
from agent.streaming import (
    stream_agent_response,
    stream_agent_sse,
    run_agent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
    DoneEvent,
    ErrorEvent,
    CompressionEvent,
    ApprovalRequiredEvent,
    ApprovalResolvedEvent,
)
from agent.compression import (
    MessageCompressor,
    CompressionConfig,
    TokenCounter,
    compress_if_needed,
    get_compressor,
)
from agent.hitl import (
    HITLManager,
    HITLConfig,
    ApprovalRequest,
    ApprovalStatus,
    get_hitl_manager,
)

__all__ = [
    # Agent
    "aura_agent",
    "AuraDeps",
    # Streaming
    "stream_agent_response",
    "stream_agent_sse",
    "run_agent",
    # Events
    "TextDeltaEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "DoneEvent",
    "ErrorEvent",
    "CompressionEvent",
    "ApprovalRequiredEvent",
    "ApprovalResolvedEvent",
    # Compression
    "MessageCompressor",
    "CompressionConfig",
    "TokenCounter",
    "compress_if_needed",
    "get_compressor",
    # HITL
    "HITLManager",
    "HITLConfig",
    "ApprovalRequest",
    "ApprovalStatus",
    "get_hitl_manager",
]
