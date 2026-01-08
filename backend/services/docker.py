"""
Docker LaTeX compilation service.

Runs pdflatex in an isolated Docker container for safe, reproducible compilation.
"""

import asyncio
import docker
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

IMAGE_NAME = "aura-texlive"
DOCKERFILE_PATH = Path(__file__).parent.parent.parent / "sandbox"


@dataclass
class CompileResult:
    """Result of a LaTeX compilation."""
    success: bool
    pdf_path: Optional[str] = None
    log_output: str = ""
    error_summary: str = ""


class DockerLatex:
    """
    LaTeX compilation service using Docker.

    Compiles .tex files in an isolated texlive container.
    """

    def __init__(self):
        self.client = docker.from_env()
        self._ensure_image()

    def _ensure_image(self) -> None:
        """Build the texlive image if it doesn't exist."""
        try:
            self.client.images.get(IMAGE_NAME)
            logger.info(f"Docker image '{IMAGE_NAME}' found")
        except docker.errors.ImageNotFound:
            logger.info(f"Building Docker image '{IMAGE_NAME}'...")
            self.client.images.build(
                path=str(DOCKERFILE_PATH),
                tag=IMAGE_NAME,
                rm=True,
            )
            logger.info(f"Docker image '{IMAGE_NAME}' built successfully")

    async def compile(
        self,
        project_path: str,
        filename: str = "main.tex",
        timeout: int = 120,
        runs: int = 2,
    ) -> CompileResult:
        """
        Compile a LaTeX file to PDF.

        Args:
            project_path: Path to the project directory
            filename: Name of the .tex file to compile
            timeout: Maximum time in seconds for compilation
            runs: Number of pdflatex runs (2 for references, 3 for complex docs)

        Returns:
            CompileResult with success status, paths, and logs
        """
        project_path = Path(project_path).resolve()

        if not project_path.exists():
            return CompileResult(
                success=False,
                error_summary=f"Project path does not exist: {project_path}"
            )

        tex_file = project_path / filename
        if not tex_file.exists():
            return CompileResult(
                success=False,
                error_summary=f"TeX file not found: {filename}"
            )

        # Build compilation command (run multiple times for references)
        # Use ; instead of && because pdflatex returns non-zero on warnings
        # but still generates the PDF
        base_name = filename.rsplit(".", 1)[0]
        commands = []
        for i in range(runs):
            commands.append(f"pdflatex -interaction=nonstopmode {filename}")

        # Check for bibliography
        bib_files = list(project_path.glob("*.bib"))
        if bib_files:
            # Insert biber/bibtex after first pdflatex
            commands.insert(1, f"biber {base_name} || bibtex {base_name} || true")

        # Use ; to continue even if pdflatex has warnings
        full_command = " ; ".join(commands)

        def _run_container():
            try:
                # Capture both stdout and stderr, and don't fail on non-zero exit
                # LaTeX often exits with code 1 even when PDF is generated (due to warnings)
                output = self.client.containers.run(
                    IMAGE_NAME,
                    command=f"/bin/bash -c '{full_command} 2>&1; echo \"\\nEXIT_CODE=$?\"'",
                    volumes={str(project_path): {"bind": "/workspace", "mode": "rw"}},
                    working_dir="/workspace",
                    remove=True,
                    detach=False,
                    stdout=True,
                    stderr=True,
                    mem_limit="1g",
                    network_mode="none",  # No network access for security
                )
                return output.decode("utf-8")
            except docker.errors.ContainerError as e:
                # Even on ContainerError, the output might have useful info
                # and the PDF might have been generated
                error_output = ""
                if e.stderr:
                    error_output = e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else str(e.stderr)
                if not error_output:
                    # Try to get any output from the exception
                    error_output = str(e)
                logger.warning(f"Container exited with error but may have produced output: {e.exit_status}")
                return error_output
            except docker.errors.APIError as e:
                logger.error(f"Docker API error: {e}")
                return f"Docker API error: {e}"
            except Exception as e:
                logger.error(f"Unexpected error during compilation: {e}")
                return str(e)

        try:
            loop = asyncio.get_event_loop()
            log_output = await asyncio.wait_for(
                loop.run_in_executor(None, _run_container),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return CompileResult(
                success=False,
                log_output="",
                error_summary=f"Compilation timed out after {timeout} seconds"
            )

        # Check if PDF was generated
        pdf_path = project_path / f"{base_name}.pdf"

        if pdf_path.exists():
            # PDF generated - check for warnings in the log
            warnings = self._extract_warnings(log_output)
            return CompileResult(
                success=True,
                pdf_path=str(pdf_path),
                log_output=log_output,
                error_summary=warnings  # Include warnings even on success
            )
        else:
            return CompileResult(
                success=False,
                pdf_path=None,
                log_output=log_output,
                error_summary=self._extract_errors(log_output)
            )

    def _extract_errors(self, log: str) -> str:
        """Extract error messages from LaTeX log output."""
        errors = []
        lines = log.split("\n")

        for i, line in enumerate(lines):
            # LaTeX errors start with !
            if line.startswith("!"):
                # Get the error and next few lines for context
                error_lines = [line]
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].startswith("!") or lines[j].startswith("l."):
                        error_lines.append(lines[j])
                        if lines[j].startswith("l."):
                            break
                errors.append("\n".join(error_lines))

            # Also catch "Error:" messages
            elif "Error:" in line or "Fatal error" in line:
                errors.append(line)

        if errors:
            return "\n\n".join(errors[:5])  # Limit to first 5 errors

        # If no specific errors found, return last 500 chars of log
        return f"Compilation failed. Log tail:\n{log[-500:]}"

    def _extract_warnings(self, log: str) -> str:
        """Extract warning messages from LaTeX log output (when PDF was generated)."""
        warnings = []
        lines = log.split("\n")

        for line in lines:
            # LaTeX warnings
            if "LaTeX Warning:" in line:
                warnings.append(line.strip())
            # Package warnings
            elif "Package" in line and "Warning" in line:
                warnings.append(line.strip())
            # Undefined references/citations
            elif "undefined" in line.lower() and ("reference" in line.lower() or "citation" in line.lower()):
                warnings.append(line.strip())

        if warnings:
            # Deduplicate and limit
            unique_warnings = list(dict.fromkeys(warnings))[:5]
            return "\n".join(unique_warnings)

        return ""

    async def check_syntax(self, project_path: str, filename: str = "main.tex") -> CompileResult:
        """
        Quick syntax check without full compilation.

        Uses -draftmode for faster checking.
        """
        project_path = Path(project_path).resolve()
        tex_file = project_path / filename

        if not tex_file.exists():
            return CompileResult(
                success=False,
                error_summary=f"TeX file not found: {filename}"
            )

        def _run_check():
            try:
                output = self.client.containers.run(
                    IMAGE_NAME,
                    command=f"pdflatex -interaction=nonstopmode -draftmode -halt-on-error {filename}",
                    volumes={str(project_path): {"bind": "/workspace", "mode": "rw"}},
                    working_dir="/workspace",
                    remove=True,
                    detach=False,
                    stdout=True,
                    stderr=True,
                    mem_limit="512m",
                    network_mode="none",
                )
                return True, output.decode("utf-8")
            except docker.errors.ContainerError as e:
                return False, e.stderr.decode("utf-8") if e.stderr else str(e)

        loop = asyncio.get_event_loop()
        success, log_output = await loop.run_in_executor(None, _run_check)

        if success:
            return CompileResult(success=True, log_output=log_output)
        else:
            return CompileResult(
                success=False,
                log_output=log_output,
                error_summary=self._extract_errors(log_output)
            )

    def is_available(self) -> bool:
        """Check if Docker is available and the image exists."""
        try:
            self.client.ping()
            self.client.images.get(IMAGE_NAME)
            return True
        except:
            return False


# Singleton instance
_docker_latex: DockerLatex | None = None


def get_docker_latex() -> DockerLatex:
    """Get or create the singleton DockerLatex instance."""
    global _docker_latex
    if _docker_latex is None:
        _docker_latex = DockerLatex()
    return _docker_latex
