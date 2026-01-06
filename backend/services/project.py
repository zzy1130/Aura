"""
Project management service.

Handles local project storage in ~/aura-projects/
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime

PROJECTS_DIR = Path.home() / "aura-projects"


@dataclass
class ProjectConfig:
    """Project configuration stored in .aura/config.json"""
    overleaf_url: Optional[str] = None
    default_compiler: str = "pdflatex"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ProjectInfo:
    """Basic project information."""
    name: str
    path: str
    has_overleaf: bool = False
    last_modified: Optional[str] = None


class ProjectService:
    """
    Manages LaTeX projects on the local filesystem.

    Projects are stored in ~/aura-projects/<project-name>/
    Each project has a .aura/ folder for metadata.
    """

    def __init__(self):
        PROJECTS_DIR.mkdir(exist_ok=True)

    def list_all(self) -> list[ProjectInfo]:
        """List all projects."""
        projects = []

        for p in PROJECTS_DIR.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                # Check if it has a .tex file
                tex_files = list(p.glob("*.tex"))
                if tex_files:
                    config = self._load_config(p)

                    # Get last modified time
                    try:
                        mtime = max(f.stat().st_mtime for f in p.glob("*.tex"))
                        last_modified = datetime.fromtimestamp(mtime).isoformat()
                    except:
                        last_modified = None

                    projects.append(ProjectInfo(
                        name=p.name,
                        path=str(p),
                        has_overleaf=config.overleaf_url is not None,
                        last_modified=last_modified,
                    ))

        # Sort by last modified
        projects.sort(key=lambda x: x.last_modified or "", reverse=True)
        return projects

    def create(self, name: str, template: str = "article") -> ProjectInfo:
        """Create a new project with starter template."""
        project_path = PROJECTS_DIR / name

        if project_path.exists():
            raise ValueError(f"Project '{name}' already exists")

        project_path.mkdir(parents=True)
        aura_dir = project_path / ".aura"
        aura_dir.mkdir()

        # Create starter main.tex
        if template == "article":
            starter_tex = self._article_template(name)
        else:
            starter_tex = self._minimal_template(name)

        (project_path / "main.tex").write_text(starter_tex)

        # Create empty refs.bib
        (project_path / "refs.bib").write_text("% Bibliography file\n")

        # Save config
        config = ProjectConfig(
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._save_config(project_path, config)

        return ProjectInfo(
            name=name,
            path=str(project_path),
            has_overleaf=False,
            last_modified=datetime.now().isoformat(),
        )

    def get_files(self, project_path: str) -> list[dict]:
        """Get file tree for a project."""
        project_path = Path(project_path)
        files = []

        for f in sorted(project_path.rglob("*")):
            if f.is_file() and not any(p.startswith(".") for p in f.relative_to(project_path).parts):
                rel_path = str(f.relative_to(project_path))
                files.append({
                    "name": f.name,
                    "path": rel_path,
                    "type": self._get_file_type(f.suffix),
                    "size": f.stat().st_size,
                })

        return files

    def read_file(self, project_path: str, filename: str) -> str:
        """Read a file from the project."""
        file_path = Path(project_path) / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        return file_path.read_text()

    def write_file(self, project_path: str, filename: str, content: str) -> None:
        """Write content to a file in the project."""
        file_path = Path(project_path) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        # Update project config timestamp
        config = self._load_config(Path(project_path))
        config.updated_at = datetime.now().isoformat()
        self._save_config(Path(project_path), config)

    def load_history(self, project_path: str) -> list:
        """Load conversation history for a project."""
        history_file = Path(project_path) / ".aura" / "history.json"
        if history_file.exists():
            try:
                return json.loads(history_file.read_text())
            except:
                return []
        return []

    def save_history(self, project_path: str, history: list) -> None:
        """Save conversation history for a project."""
        aura_dir = Path(project_path) / ".aura"
        aura_dir.mkdir(exist_ok=True)
        (aura_dir / "history.json").write_text(json.dumps(history, indent=2))

    def _load_config(self, project_path: Path) -> ProjectConfig:
        """Load project config."""
        config_file = project_path / ".aura" / "config.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                return ProjectConfig(**data)
            except:
                pass
        return ProjectConfig()

    def _save_config(self, project_path: Path, config: ProjectConfig) -> None:
        """Save project config."""
        aura_dir = project_path / ".aura"
        aura_dir.mkdir(exist_ok=True)
        (aura_dir / "config.json").write_text(json.dumps(asdict(config), indent=2))

    def _get_file_type(self, suffix: str) -> str:
        """Get file type from extension."""
        types = {
            ".tex": "latex",
            ".bib": "bibtex",
            ".sty": "style",
            ".cls": "class",
            ".pdf": "pdf",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".eps": "image",
            ".svg": "image",
        }
        return types.get(suffix.lower(), "other")

    def _article_template(self, title: str) -> str:
        """Generate article template."""
        return f'''\\documentclass[12pt]{{article}}

% Packages
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{amsmath, amssymb, amsthm}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}
\\usepackage{{cleveref}}
\\usepackage{{booktabs}}
\\usepackage[backend=biber, style=numeric]{{biblatex}}

\\addbibresource{{refs.bib}}

% Title
\\title{{{title}}}
\\author{{Author Name}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
Your abstract here.
\\end{{abstract}}

\\section{{Introduction}}

Your introduction here.

\\section{{Related Work}}

% TODO: Add related work

\\section{{Methodology}}

% TODO: Add methodology

\\section{{Experiments}}

% TODO: Add experiments

\\section{{Conclusion}}

% TODO: Add conclusion

\\printbibliography

\\end{{document}}
'''

    def _minimal_template(self, title: str) -> str:
        """Generate minimal template."""
        return f'''\\documentclass{{article}}

\\title{{{title}}}
\\author{{}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\section{{Introduction}}

Your content here.

\\end{{document}}
'''
