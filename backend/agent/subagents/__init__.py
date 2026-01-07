"""
Subagents Module

Specialized agents that handle specific domain tasks.
The main agent delegates to these subagents for focused work.

Available Subagents:
    - research: Search arXiv and Semantic Scholar for papers
    - compiler: Fix LaTeX compilation errors

Usage:
    from agent.subagents import get_subagent, run_subagent, list_subagents

    # List available subagents
    available = list_subagents()

    # Run a subagent directly
    result = await run_subagent(
        "research",
        "Find recent papers on large language models",
    )

    # Or get a subagent instance
    agent = get_subagent("compiler", project_path="/path/to/project")
    result = await agent.run("Fix the undefined control sequence error")
"""

# Base classes
from agent.subagents.base import (
    Subagent,
    SubagentConfig,
    SubagentResult,
    get_subagent,
    list_subagents,
    register_subagent,
    run_subagent,
)

# Import subagent implementations to register them
from agent.subagents import research
from agent.subagents import compiler

# Re-export specific subagents for direct access
from agent.subagents.research import ResearchAgent
from agent.subagents.compiler import CompilerAgent


__all__ = [
    # Base classes
    "Subagent",
    "SubagentConfig",
    "SubagentResult",
    # Registry functions
    "get_subagent",
    "list_subagents",
    "register_subagent",
    "run_subagent",
    # Specific subagents
    "ResearchAgent",
    "CompilerAgent",
]
