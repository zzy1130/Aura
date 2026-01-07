# Phase 3: Advanced Agent Features (PydanticAI Migration)

## Status

| Phase | Status | Description |
|-------|--------|-------------|
| 3A | ✅ Complete | PydanticAI migration with Colorist provider |
| 3B | ⏳ Pending | Message compression |
| 3C | ⏳ Pending | HITL (Human-in-the-loop) |
| 3D | ⏳ Pending | Steering messages |
| 3E | ⏳ Pending | Multi-agent (subagents) |

---

## Decision: Migrate to PydanticAI

After evaluating options (raw Anthropic SDK, OpenCode, PydanticAI), we chose **PydanticAI** because:

| Criteria | Raw SDK | OpenCode | PydanticAI |
|----------|---------|----------|------------|
| Language | Python ✅ | TypeScript ❌ | Python ✅ |
| Embeddable | Yes ✅ | No (standalone app) ❌ | Yes ✅ |
| History processors | Manual ⚠️ | Unknown | Built-in ✅ |
| HITL | Manual ⚠️ | Has it ✅ | Built-in ✅ |
| Streaming | Manual ✅ | Has it ✅ | Built-in ✅ |
| Paintress compatible | Similar | No | Same pattern ✅ |
| Keep existing work | Yes ✅ | Rewrite ❌ | Migration ✅ |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PydanticAI Agent (replaces raw SDK)                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Agent class with:                                      ││
│  │  - Colorist provider (custom)                           ││
│  │  - History processors (built-in)                        ││
│  │  - Tool registration (decorator-based)                  ││
│  │  - Streaming via agent.iter()                           ││
│  │  - Retries (built-in)                                   ││
│  └─────────────────────────────────────────────────────────┘│
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  AgentContext (enhanced)                                ││
│  │  - Token tracking                                       ││
│  │  - Steering queue                                       ││
│  │  - HITL state                                           ││
│  │  - Subagent routing                                     ││
│  └─────────────────────────────────────────────────────────┘│
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Colorist Provider (custom pydantic_ai provider)        ││
│  │  - Routes to Colorist gateway                           ││
│  │  - auth_token authentication                            ││
│  │  - Model: claude-4-5-sonnet-by-all                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 3A: PydanticAI Migration (Foundation)

### Step 1: Add PydanticAI Dependency

```bash
# pyproject.toml or requirements.txt
pydantic-ai>=0.1.0
```

### Step 2: Create Colorist Provider

**File: `backend/agent/providers/colorist.py`**

```python
"""
Colorist Provider for PydanticAI

Custom provider that routes through Colorist gateway.
Based on paintress/models/colorist.py pattern.
"""

import os
import httpx
from typing import Any
from anthropic import AsyncAnthropic
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.models import infer_model

# Shared HTTP client for connection pooling
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


def colorist_provider() -> AnthropicProvider:
    """
    Create a PydanticAI provider for Colorist gateway.

    Usage:
        from pydantic_ai import Agent
        from pydantic_ai.models import infer_model

        agent = Agent(
            model=infer_model("anthropic:claude-4-5-sonnet-by-all", colorist_provider),
            ...
        )
    """
    api_key = os.getenv(
        "COLORIST_API_KEY",
        "vk_06fc67ee1bbf1d3083ca3ec21ef5b7606005a7b5492d4c361773c13308ec8336"
    )
    base_url = os.getenv(
        "COLORIST_GATEWAY_URL",
        "https://colorist-gateway-staging.arco.ai"
    )

    client = AsyncAnthropic(
        auth_token=api_key,
        base_url=base_url,
        http_client=get_http_client(),
    )

    return AnthropicProvider(anthropic_client=client)


def get_colorist_model(model_name: str = "claude-4-5-sonnet-by-all"):
    """
    Get a PydanticAI model configured for Colorist.

    Args:
        model_name: Colorist model name (e.g., "claude-4-5-sonnet-by-all")

    Returns:
        Configured model for use with PydanticAI Agent
    """
    return infer_model(f"anthropic:{model_name}", colorist_provider)
```

### Step 3: Create PydanticAI Agent

**File: `backend/agent/pydantic_agent.py`**

```python
"""
PydanticAI-based Aura Agent

Replaces the raw Anthropic SDK implementation with PydanticAI.
"""

from dataclasses import dataclass
from typing import AsyncIterator, Any
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

from backend.agent.providers.colorist import get_colorist_model
from backend.agent.context import AgentContext
from backend.agent.prompts import get_system_prompt


@dataclass
class AuraDeps:
    """Dependencies injected into agent tools."""
    context: AgentContext
    project_path: str


# Create the main agent
aura_agent = Agent(
    model=get_colorist_model("claude-4-5-sonnet-by-all"),
    deps_type=AuraDeps,
    retries=3,
    # History processors added in Phase 3A.2
)


# Tool registration using PydanticAI decorators
@aura_agent.tool
async def read_file(ctx: RunContext[AuraDeps], filepath: str) -> str:
    """
    Read a file from the LaTeX project.

    Args:
        filepath: Path relative to project root (e.g., "main.tex", "sections/intro.tex")

    Returns:
        File contents with line numbers
    """
    from pathlib import Path

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    if not full_path.is_file():
        return f"Error: Not a file: {filepath}"

    try:
        content = full_path.read_text()
        lines = content.split('\n')
        numbered = [f"{i+1:4}│ {line}" for i, line in enumerate(lines)]
        return f"File: {filepath} ({len(lines)} lines)\n" + "\n".join(numbered)
    except Exception as e:
        return f"Error reading file: {e}"


@aura_agent.tool
async def edit_file(
    ctx: RunContext[AuraDeps],
    filepath: str,
    old_string: str,
    new_string: str,
) -> str:
    """
    Edit a file by replacing text.

    Args:
        filepath: Path relative to project root
        old_string: Exact text to find and replace
        new_string: Text to replace with

    Returns:
        Success message or error
    """
    from pathlib import Path

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = full_path.read_text()

        if old_string not in content:
            return f"Error: Could not find the specified text in {filepath}"

        count = content.count(old_string)
        if count > 1:
            return f"Error: Found {count} occurrences. Please provide more context for unique match."

        new_content = content.replace(old_string, new_string, 1)
        full_path.write_text(new_content)

        return f"Successfully edited {filepath}"
    except Exception as e:
        return f"Error editing file: {e}"


@aura_agent.tool
async def write_file(
    ctx: RunContext[AuraDeps],
    filepath: str,
    content: str,
) -> str:
    """
    Write content to a file (creates or overwrites).

    Args:
        filepath: Path relative to project root
        content: Content to write

    Returns:
        Success message or error
    """
    from pathlib import Path

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote {filepath} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file: {e}"


@aura_agent.tool
async def compile_latex(
    ctx: RunContext[AuraDeps],
    main_file: str = "main.tex",
) -> str:
    """
    Compile the LaTeX project.

    Args:
        main_file: Main .tex file to compile (default: main.tex)

    Returns:
        Compilation result with any errors
    """
    from backend.services.docker import get_docker_latex

    docker = get_docker_latex()
    project_path = ctx.deps.project_path

    result = await docker.compile(project_path, main_file)

    if result.success:
        return f"Compilation successful! Output: {result.pdf_path}"
    else:
        return f"Compilation failed:\n{result.log[-2000:]}"


@aura_agent.tool
async def think(ctx: RunContext[AuraDeps], thought: str) -> str:
    """
    Think through a complex problem step-by-step.

    Use this for internal reasoning before taking action. Good for:
    - Planning multi-file edits
    - Debugging compilation errors
    - Considering mathematical proofs
    - Weighing different approaches

    Args:
        thought: Your step-by-step reasoning process

    Returns:
        Acknowledgment to continue
    """
    # The thought is captured in the tool call for context
    return "Thinking recorded. Continue with your analysis or take action."


@aura_agent.tool
async def list_files(ctx: RunContext[AuraDeps], directory: str = ".") -> str:
    """
    List files in a directory.

    Args:
        directory: Directory relative to project root (default: root)

    Returns:
        List of files and directories
    """
    from pathlib import Path

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / directory

    if not full_path.exists():
        return f"Error: Directory not found: {directory}"

    if not full_path.is_dir():
        return f"Error: Not a directory: {directory}"

    try:
        items = []
        for item in sorted(full_path.iterdir()):
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"📄 {item.name} ({size} bytes)")

        return f"Contents of {directory}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"
```

### Step 4: Create Streaming Runner

**File: `backend/agent/runner.py`**

```python
"""
Agent Runner

Handles running the PydanticAI agent with streaming.
"""

import logging
from dataclasses import dataclass
from typing import AsyncIterator, Any
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

from backend.agent.pydantic_agent import aura_agent, AuraDeps
from backend.agent.context import AgentContext
from backend.agent.prompts import get_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Event emitted during agent execution."""
    type: str  # "text", "tool_call", "tool_result", "thinking", "error", "done"
    content: Any = None

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content}


async def run_agent_stream(
    message: str,
    project_path: str,
    history: list[dict] | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Run the agent with streaming output.

    Args:
        message: User message
        project_path: Path to the LaTeX project
        history: Optional conversation history

    Yields:
        StreamEvent objects
    """
    from pathlib import Path

    # Create context and dependencies
    context = AgentContext(
        project_path=project_path,
        project_name=Path(project_path).name,
        history=history or [],
    )

    deps = AuraDeps(
        context=context,
        project_path=project_path,
    )

    # Get system prompt
    system_prompt = get_system_prompt(
        project_name=context.project_name,
        project_path=project_path,
    )

    # Convert history to PydanticAI format if needed
    message_history = _convert_history(history) if history else None

    try:
        # Run agent with streaming
        async with aura_agent.iter(
            message,
            deps=deps,
            message_history=message_history,
            # system_prompt injected via agent configuration
        ) as run:
            async for event in run:
                # Process different event types
                if hasattr(event, 'part'):
                    part = event.part

                    if isinstance(part, TextPart):
                        yield StreamEvent(type="text", content=part.content)

                    elif isinstance(part, ToolCallPart):
                        # Check if it's a thinking tool
                        if part.tool_name == "think":
                            yield StreamEvent(
                                type="thinking",
                                content=part.args.get("thought", ""),
                            )
                        else:
                            yield StreamEvent(
                                type="tool_call",
                                content={
                                    "id": part.tool_call_id,
                                    "name": part.tool_name,
                                    "args": part.args,
                                },
                            )

                    elif isinstance(part, ToolReturnPart):
                        yield StreamEvent(
                            type="tool_result",
                            content={
                                "id": part.tool_call_id,
                                "output": str(part.content)[:2000],
                            },
                        )

        yield StreamEvent(type="done", content={"status": "success"})

    except Exception as e:
        logger.error(f"Agent error: {e}")
        yield StreamEvent(type="error", content=str(e))


def _convert_history(history: list[dict]) -> list:
    """Convert Anthropic-format history to PydanticAI format."""
    # PydanticAI uses similar format, may need adjustment
    # For now, return as-is and adjust if needed
    return history
```

### Step 5: Update FastAPI Endpoints

**File: `backend/main.py` (updated chat endpoint)**

```python
from backend.agent.runner import run_agent_stream, StreamEvent

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream agent responses via SSE."""

    async def event_generator():
        async for event in run_agent_stream(
            message=request.message,
            project_path=request.project_path,
            history=request.history,
        ):
            yield {
                "event": event.type,
                "data": json.dumps(event.content) if event.content else "",
            }

    return EventSourceResponse(event_generator())
```

### Step 6: Add History Processors

**File: `backend/agent/processors.py`**

```python
"""
History Processors for PydanticAI

These processors clean up and optimize message history before sending to LLM.
"""

from typing import Any
from pydantic_ai.messages import ModelMessage


def truncate_tool_results(
    messages: list[ModelMessage],
    max_chars: int = 4000,
) -> list[ModelMessage]:
    """
    Truncate long tool results to prevent context overflow.

    This is a PydanticAI history processor.
    """
    result = []
    for msg in messages:
        if hasattr(msg, 'parts'):
            new_parts = []
            for part in msg.parts:
                if hasattr(part, 'content') and isinstance(part.content, str):
                    if len(part.content) > max_chars:
                        # Create truncated version
                        truncated = part.content[:max_chars]
                        truncated += f"\n... [truncated {len(part.content) - max_chars} chars]"
                        # Recreate part with truncated content
                        part = part.__class__(
                            **{**part.__dict__, 'content': truncated}
                        )
                new_parts.append(part)
            msg = msg.__class__(parts=new_parts)
        result.append(msg)
    return result


def remove_empty_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Remove messages with no meaningful content."""
    result = []
    for msg in messages:
        if hasattr(msg, 'parts') and msg.parts:
            # Filter out empty text parts
            non_empty = [
                p for p in msg.parts
                if not (hasattr(p, 'content') and not p.content.strip())
            ]
            if non_empty:
                result.append(msg)
        else:
            result.append(msg)
    return result


# Combined processor pipeline
def process_history(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Apply all history processors in sequence."""
    messages = truncate_tool_results(messages)
    messages = remove_empty_messages(messages)
    return messages
```

### Step 7: Update Agent with Processors

```python
# In backend/agent/pydantic_agent.py

from backend.agent.processors import process_history

aura_agent = Agent(
    model=get_colorist_model("claude-4-5-sonnet-by-all"),
    deps_type=AuraDeps,
    retries=3,
    history_processors=[process_history],  # Add processors
)
```

---

## Phase 3A Files Summary

```
backend/agent/
├── providers/
│   ├── __init__.py
│   └── colorist.py          # Colorist provider for PydanticAI
├── pydantic_agent.py         # Main agent with tools
├── runner.py                 # Streaming runner
├── processors.py             # History processors
├── context.py                # (existing, enhanced)
└── prompts.py                # (existing)
```

### Migration Checklist

- [x] Add `pydantic-ai` to dependencies
- [x] Create `providers/colorist.py`
- [x] Create `pydantic_agent.py` with tools
- [x] Create `streaming.py` for streaming
- [x] Create `processors.py`
- [x] Update `main.py` endpoints
- [x] Test end-to-end
- [ ] Remove old `core.py` (or keep as fallback)

---

## Phase 3B: Message Compression

With PydanticAI foundation in place, add compression as a history processor.

**File: `backend/agent/compression.py`**

```python
"""
Message Compression

Automatically compress old messages when approaching context limit.
"""

from dataclasses import dataclass
from pydantic_ai.messages import ModelMessage


@dataclass
class CompressionConfig:
    max_tokens: int = 200_000
    compress_threshold: float = 0.65  # 65% = ~130K tokens
    keep_recent_turns: int = 4
    compactor_model: str = "claude-4-5-haiku-by-all"


class TokenCounter:
    """Estimate token count for messages."""

    CHARS_PER_TOKEN = 4  # Rough estimate

    def count(self, messages: list[ModelMessage]) -> int:
        """Count approximate tokens in message list."""
        total = 0
        for msg in messages:
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if hasattr(part, 'content'):
                        total += len(str(part.content)) // self.CHARS_PER_TOKEN
        return total


class MessageCompressor:
    """Compress message history when needed."""

    def __init__(self, config: CompressionConfig | None = None):
        self.config = config or CompressionConfig()
        self.counter = TokenCounter()

    def should_compress(self, messages: list[ModelMessage]) -> bool:
        """Check if compression is needed."""
        tokens = self.counter.count(messages)
        threshold = self.config.max_tokens * self.config.compress_threshold
        return tokens > threshold

    async def compress(
        self,
        messages: list[ModelMessage],
        compactor_agent,  # Separate agent for compression
    ) -> list[ModelMessage]:
        """Compress old messages, keeping recent turns."""
        if len(messages) <= self.config.keep_recent_turns * 2:
            return messages  # Too short to compress

        # Split into old and recent
        keep_count = self.config.keep_recent_turns * 2
        old_messages = messages[:-keep_count]
        recent_messages = messages[-keep_count:]

        # Summarize old messages
        summary = await self._summarize(old_messages, compactor_agent)

        # Create summary message
        from pydantic_ai.messages import UserPrompt, ModelTextResponse

        summary_messages = [
            UserPrompt(content=f"[Previous conversation summary]\n{summary}"),
            ModelTextResponse(content="I understand. I'll continue from where we left off."),
        ]

        return summary_messages + recent_messages

    async def _summarize(
        self,
        messages: list[ModelMessage],
        compactor_agent,
    ) -> str:
        """Use a smaller model to summarize messages."""
        # Format messages for summarization
        formatted = self._format_for_summary(messages)

        result = await compactor_agent.run(
            f"Summarize this conversation in 2-3 paragraphs:\n\n{formatted}"
        )

        return result.data

    def _format_for_summary(self, messages: list[ModelMessage]) -> str:
        """Format messages as text for summarization."""
        lines = []
        for msg in messages:
            role = msg.__class__.__name__
            if hasattr(msg, 'parts'):
                content = " ".join(
                    str(p.content) for p in msg.parts if hasattr(p, 'content')
                )
                lines.append(f"{role}: {content[:500]}...")
        return "\n\n".join(lines)


# History processor that compresses when needed
def create_compression_processor(compressor: MessageCompressor):
    """Create a history processor for compression."""

    async def compress_if_needed(messages: list[ModelMessage]) -> list[ModelMessage]:
        if compressor.should_compress(messages):
            # Note: This needs async handling, may need different integration
            pass
        return messages

    return compress_if_needed
```

---

## Phase 3C: HITL (Human-in-the-Loop)

PydanticAI has built-in HITL support. We leverage it.

**File: `backend/agent/hitl.py`**

```python
"""
Human-in-the-Loop Support

Uses PydanticAI's built-in HITL capabilities.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


@dataclass
class ApprovalRequest:
    """A pending approval request."""
    tool_call_id: str
    tool_name: str
    tool_args: dict
    status: ApprovalStatus = ApprovalStatus.PENDING
    modified_args: Optional[dict] = None
    rejection_reason: Optional[str] = None


@dataclass
class HITLManager:
    """Manages human-in-the-loop approvals."""

    # Tools requiring approval
    approval_required: set[str] = field(default_factory=lambda: {
        "write_file",
        "edit_file",
    })

    # Pending approvals by tool_call_id
    pending: dict[str, ApprovalRequest] = field(default_factory=dict)

    # Events for async waiting
    _events: dict[str, asyncio.Event] = field(default_factory=dict)

    def needs_approval(self, tool_name: str) -> bool:
        """Check if tool requires user approval."""
        return tool_name in self.approval_required

    async def request_approval(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict,
        timeout: float = 300.0,
    ) -> ApprovalRequest:
        """
        Request approval and wait for user response.

        Returns after user approves/rejects or timeout.
        """
        request = ApprovalRequest(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        self.pending[tool_call_id] = request
        self._events[tool_call_id] = asyncio.Event()

        try:
            await asyncio.wait_for(
                self._events[tool_call_id].wait(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.REJECTED
            request.rejection_reason = "Approval timeout"
        finally:
            self._events.pop(tool_call_id, None)

        return self.pending.pop(tool_call_id)

    def approve(
        self,
        tool_call_id: str,
        modified_args: dict | None = None,
    ):
        """Approve a pending request."""
        if tool_call_id in self.pending:
            request = self.pending[tool_call_id]
            if modified_args:
                request.status = ApprovalStatus.MODIFIED
                request.modified_args = modified_args
            else:
                request.status = ApprovalStatus.APPROVED

            if tool_call_id in self._events:
                self._events[tool_call_id].set()

    def reject(self, tool_call_id: str, reason: str = "User rejected"):
        """Reject a pending request."""
        if tool_call_id in self.pending:
            request = self.pending[tool_call_id]
            request.status = ApprovalStatus.REJECTED
            request.rejection_reason = reason

            if tool_call_id in self._events:
                self._events[tool_call_id].set()


# Integration with runner
async def run_with_hitl(
    agent,
    message: str,
    deps,
    hitl_manager: HITLManager,
):
    """
    Run agent with HITL support.

    Pauses for approval on dangerous tools.
    """
    async with agent.iter(message, deps=deps) as run:
        async for event in run:
            if hasattr(event, 'part'):
                part = event.part

                if isinstance(part, ToolCallPart):
                    if hitl_manager.needs_approval(part.tool_name):
                        # Yield approval request
                        yield StreamEvent(
                            type="approval_request",
                            content={
                                "id": part.tool_call_id,
                                "name": part.tool_name,
                                "args": part.args,
                            },
                        )

                        # Wait for approval
                        approval = await hitl_manager.request_approval(
                            part.tool_call_id,
                            part.tool_name,
                            part.args,
                        )

                        if approval.status == ApprovalStatus.REJECTED:
                            # Return rejection to agent via deferred_tool_results
                            # PydanticAI handles this natively
                            pass

                # ... rest of event handling
```

---

## Phase 3D: Steering Messages

**File: `backend/agent/steering.py`**

```python
"""
Steering Messages

Allow users to send instructions while agent is running.
"""

import asyncio
from dataclasses import dataclass, field
from collections import deque
from typing import Optional


@dataclass
class SteeringMessage:
    """A steering message from user."""
    content: str
    priority: int = 0


class SteeringManager:
    """Manages steering messages queue."""

    def __init__(self):
        self._queue: deque[SteeringMessage] = deque()
        self._lock = asyncio.Lock()

    async def add(self, content: str, priority: int = 0):
        """Add a steering message."""
        async with self._lock:
            msg = SteeringMessage(content=content, priority=priority)
            self._queue.append(msg)
            # Sort by priority (higher first)
            self._queue = deque(
                sorted(self._queue, key=lambda m: -m.priority)
            )

    async def get_pending(self) -> list[SteeringMessage]:
        """Get and clear all pending messages."""
        async with self._lock:
            messages = list(self._queue)
            self._queue.clear()
            return messages

    async def has_pending(self) -> bool:
        """Check if there are pending messages."""
        return len(self._queue) > 0


# Integration: Check steering at each iteration
async def check_steering(
    steering_manager: SteeringManager,
    context: AgentContext,
):
    """Check for steering messages and inject into context."""
    messages = await steering_manager.get_pending()

    if messages:
        # Combine into single steering instruction
        steering = "\n\n".join([
            f"[USER INTERRUPT - Priority {m.priority}]: {m.content}"
            for m in messages
        ])

        # Add as user message
        context.add_user_message(steering)

        return True

    return False
```

---

## Phase 3E: Multi-Agent (Subagents)

**File: `backend/agent/subagents/base.py`**

```python
"""
Subagent Base

Base class for specialized subagents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
from pydantic_ai import Agent

from backend.agent.providers.colorist import get_colorist_model


@dataclass
class SubagentConfig:
    """Configuration for a subagent."""
    name: str
    model: str = "claude-4-5-sonnet-by-all"
    system_prompt: str = ""
    max_iterations: int = 10


class Subagent(ABC):
    """Base class for specialized subagents."""

    def __init__(self, config: SubagentConfig):
        self.config = config
        self.agent = self._create_agent()

    @abstractmethod
    def _create_agent(self) -> Agent:
        """Create the PydanticAI agent with appropriate tools."""
        pass

    @abstractmethod
    async def run(self, task: str, context: dict) -> str:
        """Run the subagent on a task."""
        pass
```

**File: `backend/agent/subagents/research.py`**

```python
"""
Research Subagent

Specialized for academic research tasks.
"""

from pydantic_ai import Agent, RunContext
from backend.agent.subagents.base import Subagent, SubagentConfig
from backend.agent.providers.colorist import get_colorist_model


RESEARCH_PROMPT = """You are a research assistant specialized in academic literature.

Your capabilities:
- Search arXiv for relevant papers
- Search Semantic Scholar for citations
- Summarize paper abstracts
- Extract key findings

Rules:
- NEVER make up citations - only cite real papers
- Always include paper titles, authors, and years
- Focus on relevance to the user's topic
"""


class ResearchAgent(Subagent):
    """Agent for research and literature tasks."""

    def __init__(self):
        config = SubagentConfig(
            name="research",
            system_prompt=RESEARCH_PROMPT,
        )
        super().__init__(config)

    def _create_agent(self) -> Agent:
        agent = Agent(
            model=get_colorist_model(self.config.model),
            system_prompt=self.config.system_prompt,
        )

        # Register research-specific tools
        @agent.tool
        async def search_arxiv(ctx: RunContext, query: str, max_results: int = 5) -> str:
            """Search arXiv for papers."""
            # TODO: Implement arXiv API
            return f"arXiv search for: {query}"

        @agent.tool
        async def search_semantic_scholar(ctx: RunContext, query: str) -> str:
            """Search Semantic Scholar."""
            # TODO: Implement Semantic Scholar API
            return f"Semantic Scholar search for: {query}"

        return agent

    async def run(self, task: str, context: dict) -> str:
        """Run research task."""
        result = await self.agent.run(task)
        return result.data
```

**File: `backend/agent/subagents/compiler.py`**

```python
"""
Compiler Subagent

Specialized for fixing LaTeX compilation errors.
"""

from pydantic_ai import Agent, RunContext
from backend.agent.subagents.base import Subagent, SubagentConfig
from backend.agent.providers.colorist import get_colorist_model


COMPILER_PROMPT = """You are a LaTeX compilation expert.

When given a compilation error:
1. Analyze the error message carefully
2. Identify the root cause (missing package, syntax error, etc.)
3. Propose a specific fix
4. Apply the fix
5. Verify it compiles

Common issues:
- Missing \\usepackage declarations
- Unmatched braces or environments
- Invalid characters in math mode
- Missing bibliography entries
"""


class CompilerAgent(Subagent):
    """Agent for fixing compilation errors."""

    def __init__(self, project_path: str):
        config = SubagentConfig(
            name="compiler",
            system_prompt=COMPILER_PROMPT,
        )
        self.project_path = project_path
        super().__init__(config)

    def _create_agent(self) -> Agent:
        agent = Agent(
            model=get_colorist_model(self.config.model),
            system_prompt=self.config.system_prompt,
        )

        project_path = self.project_path

        @agent.tool
        async def read_file(ctx: RunContext, filepath: str) -> str:
            """Read a file."""
            from pathlib import Path
            full_path = Path(project_path) / filepath
            if full_path.exists():
                return full_path.read_text()
            return f"File not found: {filepath}"

        @agent.tool
        async def edit_file(ctx: RunContext, filepath: str, old: str, new: str) -> str:
            """Edit a file."""
            from pathlib import Path
            full_path = Path(project_path) / filepath
            if not full_path.exists():
                return f"File not found: {filepath}"
            content = full_path.read_text()
            if old not in content:
                return "Text not found"
            content = content.replace(old, new, 1)
            full_path.write_text(content)
            return "Edit successful"

        @agent.tool
        async def compile_and_check(ctx: RunContext, main_file: str = "main.tex") -> str:
            """Compile and return result."""
            from backend.services.docker import get_docker_latex
            docker = get_docker_latex()
            result = await docker.compile(project_path, main_file)
            if result.success:
                return "Compilation successful!"
            return f"Error:\n{result.log[-2000:]}"

        return agent

    async def run(self, task: str, context: dict) -> str:
        """Fix compilation error."""
        result = await self.agent.run(task)
        return result.data
```

**Handoff Tool (in main agent):**

```python
@aura_agent.tool
async def delegate_to_subagent(
    ctx: RunContext[AuraDeps],
    subagent: str,
    task: str,
) -> str:
    """
    Delegate a task to a specialized subagent.

    Args:
        subagent: Name of subagent ("research", "compiler")
        task: The task to delegate

    Returns:
        Result from the subagent
    """
    from backend.agent.subagents.research import ResearchAgent
    from backend.agent.subagents.compiler import CompilerAgent

    if subagent == "research":
        agent = ResearchAgent()
    elif subagent == "compiler":
        agent = CompilerAgent(ctx.deps.project_path)
    else:
        return f"Unknown subagent: {subagent}"

    try:
        result = await agent.run(task, {})
        return f"[{subagent.upper()} AGENT RESULT]:\n{result}"
    except Exception as e:
        return f"Subagent error: {e}"
```

---

## Implementation Schedule

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 3A: PydanticAI Migration (3-4 days)                  │
│  ─────────────────────────────────────────────────────────  │
│  Day 1: Colorist provider + basic agent                     │
│  Day 2: Tools migration + streaming runner                  │
│  Day 3: History processors + testing                        │
│  Day 4: FastAPI integration + end-to-end test               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3B: Compression (2 days)                             │
│  ─────────────────────────────────────────────────────────  │
│  Day 5: Token counter + compressor                          │
│  Day 6: Integration + testing                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3C: HITL (3 days)                                    │
│  ─────────────────────────────────────────────────────────  │
│  Day 7: HITLManager + approval flow                         │
│  Day 8: API endpoints + SSE events                          │
│  Day 9: Testing + edge cases                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3D: Steering (2 days)                                │
│  ─────────────────────────────────────────────────────────  │
│  Day 10: SteeringManager + API                              │
│  Day 11: Integration + testing                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3E: Multi-Agent (4 days)                             │
│  ─────────────────────────────────────────────────────────  │
│  Day 12: Subagent base + research agent                     │
│  Day 13: Compiler agent                                     │
│  Day 14: Handoff tool + routing                             │
│  Day 15: Testing + refinement                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Files to Create

```
backend/agent/
├── providers/
│   ├── __init__.py
│   └── colorist.py           # Phase 3A
├── pydantic_agent.py         # Phase 3A
├── runner.py                 # Phase 3A
├── processors.py             # Phase 3A
├── compression.py            # Phase 3B
├── hitl.py                   # Phase 3C
├── steering.py               # Phase 3D
├── subagents/
│   ├── __init__.py           # Phase 3E
│   ├── base.py               # Phase 3E
│   ├── research.py           # Phase 3E
│   └── compiler.py           # Phase 3E
├── context.py                # (existing, enhanced)
└── prompts.py                # (existing)
```

---

## Success Criteria

| Phase | Feature | Success Metric |
|-------|---------|----------------|
| 3A | PydanticAI Migration | Agent runs with same capabilities as raw SDK |
| 3A | History Processors | Tool results truncated, empty messages removed |
| 3B | Compression | Can handle 50+ turn conversations |
| 3C | HITL | User can approve/reject file edits |
| 3D | Steering | User can redirect mid-conversation |
| 3E | Multi-Agent | Research delegated to subagent |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| PydanticAI API changes | Pin version, follow changelog |
| Colorist provider issues | Keep raw SDK as fallback |
| HITL async complexity | Start simple, add features |
| Subagent infinite loops | Max depth limit, timeouts |

---

## Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
pydantic-ai = ">=0.1.0"
# ... existing deps
```
