"""
Agent Core

The main agentic loop using Claude via Colorist gateway.
Handles tool execution and streaming responses.
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Any
from dataclasses import dataclass

from backend.agent.colorist import get_colorist_client, ColoristClient
from backend.agent.context import AgentContext
from backend.agent.prompts import get_system_prompt
from backend.tools.manager import get_tool_manager, ToolManager

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Event emitted during agent execution."""
    type: str  # "text", "tool_call", "tool_result", "error", "done"
    content: Any = None

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content}


class AuraAgent:
    """
    The Aura AI agent.

    Runs an agentic loop that can use tools to help with LaTeX documents.
    """

    MAX_ITERATIONS = 20  # Safety limit on tool call loops

    def __init__(
        self,
        client: ColoristClient | None = None,
        tool_manager: ToolManager | None = None,
    ):
        self.client = client or get_colorist_client()
        self.tool_manager = tool_manager or get_tool_manager()

    async def run(
        self,
        message: str,
        context: AgentContext,
    ) -> AsyncIterator[StreamEvent]:
        """
        Run the agent on a message.

        Yields streaming events as the agent works.
        """
        # Add user message to context
        context.add_user_message(message)

        # Get system prompt
        system_prompt = get_system_prompt(
            project_name=context.project_name,
            project_path=context.project_path,
        )

        # Get tools in Anthropic format
        tools = self.tool_manager.get_anthropic_tools()

        # Inject project_path into tool calls
        # (The LLM doesn't need to specify it each time)
        project_path = context.project_path

        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.info(f"Agent iteration {iteration}")

            try:
                # Call Claude
                response = await self.client.create_message(
                    system=system_prompt,
                    messages=context.get_messages(),
                    tools=tools,
                    max_tokens=4096,
                )

                # Process response content
                assistant_content = []
                tool_calls = []

                for block in response.content:
                    if block.type == "text":
                        # Yield text content
                        yield StreamEvent(type="text", content=block.text)
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })

                    elif block.type == "tool_use":
                        # Collect tool calls
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                        # Yield tool call event
                        yield StreamEvent(
                            type="tool_call",
                            content={
                                "id": block.id,
                                "name": block.name,
                                "args": block.input,
                            },
                        )

                # Add assistant message to history
                context.add_assistant_message(assistant_content)

                # If no tool calls, we're done
                if not tool_calls:
                    yield StreamEvent(type="done", content={"iterations": iteration})
                    return

                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["input"]

                    # Inject project_path if not provided
                    if "project_path" not in tool_input:
                        tool_input["project_path"] = project_path

                    # Execute tool
                    logger.info(f"Executing tool: {tool_name}")
                    result = await self.tool_manager.execute_tool(
                        tool_name,
                        **tool_input,
                    )

                    # Yield tool result event
                    yield StreamEvent(
                        type="tool_result",
                        content={
                            "id": tool_call["id"],
                            "name": tool_name,
                            "output": result[:2000],  # Limit output size
                        },
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": result,
                    })

                # Add tool results to history as user message
                context.history.append({
                    "role": "user",
                    "content": tool_results,
                })

                # Check stop reason
                if response.stop_reason == "end_turn":
                    yield StreamEvent(type="done", content={"iterations": iteration})
                    return

            except Exception as e:
                logger.error(f"Agent error: {e}")
                yield StreamEvent(type="error", content=str(e))
                return

        # Hit iteration limit
        yield StreamEvent(
            type="error",
            content=f"Reached maximum iterations ({self.MAX_ITERATIONS})",
        )

    async def run_simple(
        self,
        message: str,
        context: AgentContext,
    ) -> str:
        """
        Run the agent and return just the final text response.

        Useful for simple interactions without streaming.
        """
        full_response = []

        async for event in self.run(message, context):
            if event.type == "text":
                full_response.append(event.content)
            elif event.type == "error":
                return f"Error: {event.content}"

        return "".join(full_response)


# Global agent instance
_agent: AuraAgent | None = None


def get_agent() -> AuraAgent:
    """Get or create the global agent instance."""
    global _agent
    if _agent is None:
        _agent = AuraAgent()
    return _agent


async def run_agent_stream(
    message: str,
    project_path: str,
    history: list | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Convenience function to run the agent with streaming.

    Args:
        message: User message
        project_path: Path to the LaTeX project
        history: Optional conversation history

    Yields:
        StreamEvent objects
    """
    from pathlib import Path

    context = AgentContext(
        project_path=project_path,
        project_name=Path(project_path).name,
        history=history or [],
    )

    agent = get_agent()

    async for event in agent.run(message, context):
        yield event

    # Return updated history through the context
    # (Caller can access context.history if needed)
