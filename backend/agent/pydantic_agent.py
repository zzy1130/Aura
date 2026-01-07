"""
PydanticAI-based Aura Agent

Main agent implementation using PydanticAI framework.
Replaces the raw Anthropic SDK implementation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from pydantic_ai import Agent, RunContext

from agent.providers.colorist import get_default_model
from agent.prompts import get_system_prompt
from agent.processors import default_history_processor

if TYPE_CHECKING:
    from agent.hitl import HITLManager, ApprovalStatus


@dataclass
class AuraDeps:
    """
    Dependencies injected into agent tools.

    These are passed to every tool call via RunContext.
    """
    project_path: str
    project_name: str = ""

    # HITL support (optional)
    hitl_manager: Optional["HITLManager"] = None

    def __post_init__(self):
        if not self.project_name and self.project_path:
            self.project_name = Path(self.project_path).name


async def _check_hitl(
    ctx: RunContext[AuraDeps],
    tool_name: str,
    tool_args: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """
    Check HITL approval for a tool call.

    Returns:
        (should_proceed, rejection_message, modified_args)
    """
    hitl_manager = ctx.deps.hitl_manager
    if not hitl_manager or not hitl_manager.needs_approval(tool_name):
        return True, None, None

    from agent.hitl import ApprovalStatus
    import uuid

    # Request approval
    approval = await hitl_manager.request_approval(
        tool_name=tool_name,
        tool_args=tool_args,
        tool_call_id=str(uuid.uuid4()),
    )

    if approval.status == ApprovalStatus.REJECTED:
        return False, f"Operation cancelled: {approval.rejection_reason}", None

    if approval.status == ApprovalStatus.TIMEOUT:
        return False, "Operation cancelled: Approval timeout", None

    # Return modified args if user edited them
    modified = approval.modified_args if approval.status == ApprovalStatus.MODIFIED else None
    return True, None, modified


# Create the main Aura agent
aura_agent = Agent(
    model=get_default_model(),
    deps_type=AuraDeps,
    retries=3,
    instructions=get_system_prompt,  # Dynamic instructions based on RunContext
    history_processors=[default_history_processor],  # Clean up message history
)


# =============================================================================
# File Tools
# =============================================================================

@aura_agent.tool
async def read_file(ctx: RunContext[AuraDeps], filepath: str) -> str:
    """
    Read a file from the LaTeX project.

    Args:
        filepath: Path relative to project root (e.g., "main.tex", "sections/intro.tex")

    Returns:
        File contents with line numbers
    """
    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    if not full_path.is_file():
        return f"Error: Not a file: {filepath}"

    # Security: ensure path is within project
    try:
        full_path.resolve().relative_to(Path(project_path).resolve())
    except ValueError:
        return f"Error: Path escapes project directory: {filepath}"

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
    # HITL check - wait for approval if enabled
    should_proceed, rejection_msg, modified_args = await _check_hitl(
        ctx, "edit_file",
        {"filepath": filepath, "old_string": old_string[:200], "new_string": new_string[:200]}
    )
    if not should_proceed:
        return rejection_msg

    # Use modified args if user edited them
    if modified_args:
        filepath = modified_args.get("filepath", filepath)
        old_string = modified_args.get("old_string", old_string)
        new_string = modified_args.get("new_string", new_string)

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    # Security: ensure path is within project
    try:
        full_path.resolve().relative_to(Path(project_path).resolve())
    except ValueError:
        return f"Error: Path escapes project directory: {filepath}"

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
    # HITL check - wait for approval if enabled
    should_proceed, rejection_msg, modified_args = await _check_hitl(
        ctx, "write_file",
        {"filepath": filepath, "content_preview": content[:500] + "..." if len(content) > 500 else content}
    )
    if not should_proceed:
        return rejection_msg

    # Use modified args if user edited them
    if modified_args:
        filepath = modified_args.get("filepath", filepath)
        if "content" in modified_args:
            content = modified_args["content"]

    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    # Security: ensure path is within project
    try:
        full_path.resolve().relative_to(Path(project_path).resolve())
    except ValueError:
        return f"Error: Path escapes project directory: {filepath}"

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote {filepath} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file: {e}"


@aura_agent.tool
async def list_files(ctx: RunContext[AuraDeps], directory: str = ".") -> str:
    """
    List files in a directory.

    Args:
        directory: Directory relative to project root (default: root)

    Returns:
        List of files and directories
    """
    project_path = ctx.deps.project_path
    full_path = Path(project_path) / directory

    if not full_path.exists():
        return f"Error: Directory not found: {directory}"

    if not full_path.is_dir():
        return f"Error: Not a directory: {directory}"

    try:
        items = []
        for item in sorted(full_path.iterdir()):
            if item.name.startswith('.'):
                continue  # Skip hidden files
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"📄 {item.name} ({size} bytes)")

        return f"Contents of {directory}:\n" + "\n".join(items) if items else f"Directory {directory} is empty"
    except Exception as e:
        return f"Error listing directory: {e}"


@aura_agent.tool
async def find_files(ctx: RunContext[AuraDeps], pattern: str) -> str:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "*.tex", "**/*.bib")

    Returns:
        List of matching files
    """
    project_path = Path(ctx.deps.project_path)

    try:
        matches = list(project_path.glob(pattern))
        if not matches:
            return f"No files found matching: {pattern}"

        # Make paths relative and sort
        relative = sorted([str(m.relative_to(project_path)) for m in matches if m.is_file()])
        return f"Found {len(relative)} files matching '{pattern}':\n" + "\n".join(f"  {f}" for f in relative[:50])
    except Exception as e:
        return f"Error searching files: {e}"


# =============================================================================
# LaTeX Tools
# =============================================================================

@aura_agent.tool
async def compile_latex(
    ctx: RunContext[AuraDeps],
    main_file: str = "main.tex",
) -> str:
    """
    Compile the LaTeX project using Docker.

    Args:
        main_file: Main .tex file to compile (default: main.tex)

    Returns:
        Compilation result with any errors
    """
    from services.docker import get_docker_latex

    docker = get_docker_latex()
    project_path = ctx.deps.project_path

    result = await docker.compile(project_path, main_file)

    if result.success:
        return f"Compilation successful! Output: {result.pdf_path}"
    else:
        # Return last 2000 chars of log
        return f"Compilation failed:\n{result.log[-2000:]}"


@aura_agent.tool
async def check_latex_syntax(
    ctx: RunContext[AuraDeps],
    filepath: str,
) -> str:
    """
    Check a LaTeX file for common syntax errors.

    This is a quick check without full compilation.

    Args:
        filepath: Path to the .tex file

    Returns:
        List of potential issues or "No issues found"
    """
    project_path = ctx.deps.project_path
    full_path = Path(project_path) / filepath

    if not full_path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = full_path.read_text()
        issues = []

        # Check for unmatched braces
        brace_count = content.count('{') - content.count('}')
        if brace_count != 0:
            issues.append(f"Unmatched braces: {'+' if brace_count > 0 else ''}{brace_count}")

        # Check for unmatched environments
        import re
        begins = re.findall(r'\\begin\{(\w+)\}', content)
        ends = re.findall(r'\\end\{(\w+)\}', content)
        for env in set(begins):
            diff = begins.count(env) - ends.count(env)
            if diff != 0:
                issues.append(f"Unmatched \\begin{{{env}}}: {'+' if diff > 0 else ''}{diff}")

        # Check for common mistakes
        if '\\cite{}' in content:
            issues.append("Empty \\cite{} command found")
        if '\\ref{}' in content:
            issues.append("Empty \\ref{} command found")

        if issues:
            return f"Found {len(issues)} potential issues in {filepath}:\n" + "\n".join(f"  - {i}" for i in issues)
        else:
            return f"No syntax issues found in {filepath}"
    except Exception as e:
        return f"Error checking syntax: {e}"


# =============================================================================
# Thinking Tool
# =============================================================================

@aura_agent.tool
async def think(ctx: RunContext[AuraDeps], thought: str) -> str:
    """
    Think through a complex problem step-by-step.

    Use this for internal reasoning before taking action. Good for:
    - Planning multi-file edits
    - Debugging compilation errors
    - Considering mathematical proofs
    - Weighing different approaches

    The thought content helps you reason but is not shown to the user.

    Args:
        thought: Your step-by-step reasoning process

    Returns:
        Acknowledgment to continue
    """
    # The thought is captured in the tool call for context
    # This helps Claude's reasoning chain
    return "Thinking recorded. Continue with your analysis or take action."
