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
    from agent.planning import PlanManager, Plan


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

    # Planning support (optional)
    plan_manager: Optional["PlanManager"] = None
    session_id: str = "default"

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

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"HITL check for {tool_name}: manager={hitl_manager}, needs_approval={hitl_manager.needs_approval(tool_name) if hitl_manager else 'N/A'}")

    if not hitl_manager or not hitl_manager.needs_approval(tool_name):
        return True, None, None

    from agent.hitl import ApprovalStatus
    import uuid

    logger.info(f"Requesting approval for {tool_name}")

    # Request approval
    approval = await hitl_manager.request_approval(
        tool_name=tool_name,
        tool_args=tool_args,
        tool_call_id=str(uuid.uuid4()),
    )

    logger.info(f"Approval result: {approval.status}")

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
        {"filepath": filepath, "old_string": old_string, "new_string": new_string}
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
        {"filepath": filepath, "content": content}
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


@aura_agent.tool
async def search_in_file(
    ctx: RunContext[AuraDeps],
    filepath: str,
    pattern: str,
    context_lines: int = 2,
) -> str:
    """
    Search for a pattern within a file and return matching lines with context.

    This is like grep - use it to find specific content without reading the entire file.
    ALWAYS use this tool first when looking for specific content in a file.

    Args:
        filepath: Path relative to project root (e.g., "main.tex")
        pattern: Text or regex pattern to search for (case-insensitive)
        context_lines: Number of lines to show before/after each match (default: 2)

    Returns:
        Matching lines with line numbers and context
    """
    import re

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
        lines = content.split('\n')

        # Compile pattern (case-insensitive)
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # If invalid regex, treat as literal string
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        # Find matching lines
        matches = []
        for i, line in enumerate(lines):
            if regex.search(line):
                matches.append(i)

        if not matches:
            return f"No matches found for '{pattern}' in {filepath}"

        # Build output with context
        output = [f"Found {len(matches)} matches for '{pattern}' in {filepath}:\n"]

        shown_lines = set()
        for match_idx in matches:
            start = max(0, match_idx - context_lines)
            end = min(len(lines), match_idx + context_lines + 1)

            # Add separator if there's a gap
            if shown_lines and start > max(shown_lines) + 1:
                output.append("  ---")

            for i in range(start, end):
                if i not in shown_lines:
                    marker = ">>>" if i == match_idx else "   "
                    output.append(f"{marker} {i+1:4}│ {lines[i]}")
                    shown_lines.add(i)

        return "\n".join(output)

    except Exception as e:
        return f"Error searching file: {e}"


@aura_agent.tool
async def read_file_lines(
    ctx: RunContext[AuraDeps],
    filepath: str,
    start_line: int,
    end_line: int,
) -> str:
    """
    Read specific lines from a file.

    Use this when you know which lines you need, to avoid reading the entire file.

    Args:
        filepath: Path relative to project root
        start_line: First line to read (1-indexed)
        end_line: Last line to read (inclusive)

    Returns:
        Requested lines with line numbers
    """
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
        lines = content.split('\n')

        # Validate line numbers
        if start_line < 1:
            start_line = 1
        if end_line > len(lines):
            end_line = len(lines)
        if start_line > end_line:
            return f"Error: start_line ({start_line}) > end_line ({end_line})"

        # Extract lines (convert to 0-indexed)
        selected = lines[start_line - 1:end_line]
        numbered = [f"{i:4}│ {line}" for i, line in enumerate(selected, start=start_line)]

        return f"File: {filepath} (lines {start_line}-{end_line} of {len(lines)}):\n" + "\n".join(numbered)

    except Exception as e:
        return f"Error reading file: {e}"


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

    Use this for internal reasoning AFTER gathering information. Good for:
    - Planning multi-file edits
    - Debugging compilation errors
    - Considering mathematical proofs
    - Weighing different approaches

    IMPORTANT: Only use this tool to reason about information you have ALREADY
    retrieved via read_file or other tools. NEVER use this to imagine or guess
    what files might contain - always read files first.

    The thought content helps you reason but is not shown to the user.

    Args:
        thought: Your step-by-step reasoning process

    Returns:
        Acknowledgment to continue
    """
    # The thought is captured in the tool call for context
    # This helps Claude's reasoning chain
    return "Thinking recorded. Continue with your analysis or take action."


# =============================================================================
# Subagent Delegation
# =============================================================================

@aura_agent.tool
async def delegate_to_subagent(
    ctx: RunContext[AuraDeps],
    subagent: str,
    task: str,
) -> str:
    """
    Delegate a task to a specialized subagent.

    Subagents are focused agents with specific expertise:
    - "research": Search arXiv and Semantic Scholar for academic papers
    - "compiler": Fix LaTeX compilation errors with deep knowledge of common issues

    Use delegation when:
    - You need to find academic papers (delegate to "research")
    - You have a complex compilation error that needs iterative fixing (delegate to "compiler")

    The subagent will work autonomously and return a result.

    Args:
        subagent: Name of the subagent ("research" or "compiler")
        task: Detailed description of what you want the subagent to do

    Returns:
        Result from the subagent's work
    """
    from agent.subagents import get_subagent, list_subagents

    # Validate subagent name
    available = list_subagents()
    available_names = [s["name"] for s in available]

    if subagent not in available_names:
        return f"Unknown subagent: '{subagent}'. Available: {', '.join(available_names)}"

    try:
        # Create context for subagent
        context = {
            "project_path": ctx.deps.project_path,
            "project_name": ctx.deps.project_name,
        }

        # Get and run subagent
        agent = get_subagent(subagent, project_path=ctx.deps.project_path)
        result = await agent.run(task, context)

        if result.success:
            return f"[{subagent.upper()} AGENT RESULT]\n\n{result.output}"
        else:
            return f"[{subagent.upper()} AGENT ERROR]\n\n{result.error}: {result.output}"

    except Exception as e:
        return f"Subagent error: {str(e)}"


# =============================================================================
# Planning Tools
# =============================================================================

@aura_agent.tool
async def plan_task(
    ctx: RunContext[AuraDeps],
    task_description: str,
) -> str:
    """
    Create a structured plan for a complex task.

    Use this BEFORE starting any complex task that involves:
    - Multiple file changes
    - Several sequential steps
    - Refactoring or restructuring
    - Adding new features
    - Any task you're unsure how to approach

    The planner will analyze the task and create a step-by-step plan.

    Args:
        task_description: Detailed description of what you need to accomplish

    Returns:
        The created plan in markdown format, or error message
    """
    from agent.subagents.planner import create_plan_for_task
    from agent.planning import get_plan_manager

    try:
        # Create the plan using PlannerAgent
        plan = await create_plan_for_task(
            task=task_description,
            project_path=ctx.deps.project_path,
            project_name=ctx.deps.project_name,
        )

        if not plan:
            return "Error: Failed to create plan. Please try again with more details."

        # Store the plan in the manager
        plan_manager = ctx.deps.plan_manager or get_plan_manager()
        session_id = ctx.deps.session_id

        # Register the plan
        await plan_manager.create_plan(
            goal=plan.goal,
            original_request=task_description,
            steps=[s.to_dict() for s in plan.steps],
            session_id=session_id,
            context=plan.context,
            complexity=plan.complexity,
            estimated_files=plan.estimated_files,
            risks=plan.risks,
            assumptions=plan.assumptions,
        )

        # Return the plan in markdown format
        return f"""# Plan Created Successfully

{plan.to_markdown()}

---

**Next Steps:**
1. Review the plan above
2. Use `get_current_plan` to see the plan at any time
3. Use `start_plan_execution` when ready to begin
4. Use `complete_plan_step` after finishing each step
"""

    except Exception as e:
        return f"Planning error: {str(e)}"


@aura_agent.tool
async def get_current_plan(ctx: RunContext[AuraDeps]) -> str:
    """
    View the current plan and its progress.

    Use this to:
    - See what steps remain
    - Check progress on the plan
    - Review the overall goal

    Returns:
        Current plan in markdown format, or message if no plan exists
    """
    from agent.planning import get_plan_manager

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan. Use `plan_task` to create one."

    return plan.to_markdown()


@aura_agent.tool
async def start_plan_execution(ctx: RunContext[AuraDeps]) -> str:
    """
    Start executing the current plan.

    This marks the plan as in-progress and returns the first step to work on.

    Returns:
        First step to execute, or error if no plan exists
    """
    from agent.planning import get_plan_manager, PlanStatus

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan. Use `plan_task` to create one first."

    if plan.status not in [PlanStatus.DRAFT, PlanStatus.APPROVED]:
        return f"Plan is already {plan.status.value}. Cannot start."

    # Approve and start
    await plan_manager.approve_plan(session_id)

    # Get first step
    step = await plan_manager.start_next_step(session_id)

    if not step:
        return "No steps to execute in this plan."

    return f"""# Starting Plan Execution

**Now working on Step {step.step_number}: {step.title}**

{step.description}

Files: {', '.join(step.files) if step.files else 'None specified'}
Verification: {step.verification or 'None specified'}

---

After completing this step, use `complete_plan_step` with a summary of what you did.
If this step fails, use `fail_plan_step` with the error.
"""


@aura_agent.tool
async def complete_plan_step(
    ctx: RunContext[AuraDeps],
    summary: str,
) -> str:
    """
    Mark the current plan step as completed and move to the next.

    Call this after successfully completing a step in the plan.

    Args:
        summary: Brief summary of what was accomplished

    Returns:
        Next step to work on, or completion message
    """
    from agent.planning import get_plan_manager, StepStatus, PlanStatus

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan."

    current = plan.current_step
    if not current:
        return "No step currently in progress."

    # Complete the current step
    await plan_manager.complete_current_step(summary, session_id)

    # Refresh plan
    plan = await plan_manager.get_plan(session_id)

    # Check if plan is complete
    if plan.status == PlanStatus.COMPLETED:
        return f"""# Plan Completed! ✅

All {len(plan.steps)} steps have been completed.

**Summary:**
{chr(10).join(f'- Step {s.step_number}: {s.title} ✅' for s in plan.steps)}

The task "{plan.goal}" has been accomplished.
"""

    # Start next step
    next_step = await plan_manager.start_next_step(session_id)

    if not next_step:
        progress = plan.progress
        return f"""Step completed, but no more steps available.

Progress: {progress['completed']}/{progress['total']} steps completed
Remaining pending: {progress['pending']}

Check the plan with `get_current_plan` for details.
"""

    return f"""# Step Completed ✅

**Completed:** {current.title}
Summary: {summary}

---

**Now working on Step {next_step.step_number}: {next_step.title}**

{next_step.description}

Files: {', '.join(next_step.files) if next_step.files else 'None specified'}
Verification: {next_step.verification or 'None specified'}
"""


@aura_agent.tool
async def fail_plan_step(
    ctx: RunContext[AuraDeps],
    error: str,
) -> str:
    """
    Mark the current plan step as failed.

    Use this when a step cannot be completed due to an error.

    Args:
        error: Description of what went wrong

    Returns:
        Status update and options for proceeding
    """
    from agent.planning import get_plan_manager, StepStatus

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan."

    current = plan.current_step
    if not current:
        return "No step currently in progress."

    # Mark as failed
    await plan_manager.fail_current_step(error, session_id)

    return f"""# Step Failed ❌

**Failed:** Step {current.step_number}: {current.title}
Error: {error}

---

**Options:**
1. Try to fix the issue and retry by using `start_plan_execution` again
2. Skip this step with `skip_plan_step` and continue
3. Abandon the plan with `abandon_plan`

Use `get_current_plan` to see the full plan status.
"""


@aura_agent.tool
async def skip_plan_step(
    ctx: RunContext[AuraDeps],
    reason: str,
) -> str:
    """
    Skip the current plan step and move to the next.

    Use this when a step is not needed or should be skipped.

    Args:
        reason: Why this step is being skipped

    Returns:
        Next step to work on
    """
    from agent.planning import get_plan_manager, StepStatus

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan."

    current = plan.current_step
    if not current:
        return "No step currently in progress."

    # Mark as skipped
    await plan_manager.update_step(
        current.step_id, StepStatus.SKIPPED, reason, session_id=session_id
    )

    # Get next step
    next_step = await plan_manager.start_next_step(session_id)

    if not next_step:
        return f"Step skipped. No more steps available. Use `get_current_plan` to see status."

    return f"""# Step Skipped ⏭️

**Skipped:** {current.title}
Reason: {reason}

---

**Now working on Step {next_step.step_number}: {next_step.title}**

{next_step.description}
"""


@aura_agent.tool
async def abandon_plan(ctx: RunContext[AuraDeps]) -> str:
    """
    Abandon the current plan.

    Use this to cancel the current plan and start fresh.

    Returns:
        Confirmation message
    """
    from agent.planning import get_plan_manager

    plan_manager = ctx.deps.plan_manager or get_plan_manager()
    session_id = ctx.deps.session_id

    plan = await plan_manager.get_plan(session_id)

    if not plan:
        return "No active plan to abandon."

    await plan_manager.cancel_plan(session_id)

    return f"""# Plan Abandoned

The plan "{plan.goal}" has been cancelled.

Progress at time of abandonment:
- Completed: {plan.progress['completed']} steps
- Failed: {plan.progress['failed']} steps
- Pending: {plan.progress['pending']} steps

You can create a new plan with `plan_task`.
"""
