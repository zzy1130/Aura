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
    SteeringEvent,
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
from agent.steering import (
    SteeringManager,
    SteeringConfig,
    SteeringMessage,
    get_steering_manager,
    check_and_inject_steering,
)
from agent.subagents import (
    Subagent,
    SubagentConfig,
    SubagentResult,
    get_subagent,
    list_subagents,
    run_subagent,
    ResearchAgent,
    CompilerAgent,
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
    "SteeringEvent",
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
    # Steering
    "SteeringManager",
    "SteeringConfig",
    "SteeringMessage",
    "get_steering_manager",
    "check_and_inject_steering",
    # Subagents
    "Subagent",
    "SubagentConfig",
    "SubagentResult",
    "get_subagent",
    "list_subagents",
    "run_subagent",
    "ResearchAgent",
    "CompilerAgent",
]
