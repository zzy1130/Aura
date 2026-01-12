# Memory System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement user-controlled project memory with a dedicated UI modal, persisting across sessions.

**Architecture:** JSON file storage at `.aura/memory.json`, loaded into agent system prompt at session start. Backend service handles CRUD operations with token counting. Frontend modal provides tabbed interface for Papers, Citations, Conventions, Todos, and Notes.

**Tech Stack:** Python/FastAPI (backend), TypeScript/React (frontend), JSON (storage)

---

## Task 1: MemoryService Backend

**Files:**
- Create: `backend/services/memory.py`

**Step 1: Create the MemoryService class**

```python
"""
Memory Service

Manages project memory stored in .aura/memory.json
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal
from dataclasses import dataclass, asdict, field


# Entry types
EntryType = Literal["papers", "citations", "conventions", "todos", "notes"]

# Token estimation: ~4 chars per token for English text
CHARS_PER_TOKEN = 4
TOKEN_WARNING_THRESHOLD = 4000


@dataclass
class PaperEntry:
    id: str
    title: str
    authors: list[str]
    arxiv_id: str
    summary: str
    tags: list[str]
    created_at: str

    @classmethod
    def create(cls, title: str, authors: list[str], arxiv_id: str = "",
               summary: str = "", tags: list[str] = None) -> "PaperEntry":
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            authors=authors,
            arxiv_id=arxiv_id,
            summary=summary,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
        )


@dataclass
class CitationEntry:
    id: str
    bibtex_key: str
    paper_id: Optional[str]
    reason: str
    created_at: str

    @classmethod
    def create(cls, bibtex_key: str, reason: str, paper_id: str = None) -> "CitationEntry":
        return cls(
            id=str(uuid.uuid4()),
            bibtex_key=bibtex_key,
            paper_id=paper_id,
            reason=reason,
            created_at=datetime.now().isoformat(),
        )


@dataclass
class ConventionEntry:
    id: str
    rule: str
    example: str
    created_at: str

    @classmethod
    def create(cls, rule: str, example: str = "") -> "ConventionEntry":
        return cls(
            id=str(uuid.uuid4()),
            rule=rule,
            example=example,
            created_at=datetime.now().isoformat(),
        )


@dataclass
class TodoEntry:
    id: str
    task: str
    priority: Literal["low", "medium", "high"]
    status: Literal["pending", "in_progress", "completed"]
    created_at: str

    @classmethod
    def create(cls, task: str, priority: str = "medium",
               status: str = "pending") -> "TodoEntry":
        return cls(
            id=str(uuid.uuid4()),
            task=task,
            priority=priority,
            status=status,
            created_at=datetime.now().isoformat(),
        )


@dataclass
class NoteEntry:
    id: str
    content: str
    tags: list[str]
    created_at: str

    @classmethod
    def create(cls, content: str, tags: list[str] = None) -> "NoteEntry":
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
        )


@dataclass
class MemoryData:
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    papers: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    conventions: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


class MemoryService:
    """
    Manages project memory stored in .aura/memory.json
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.aura_dir = self.project_path / ".aura"
        self.memory_file = self.aura_dir / "memory.json"

    def _ensure_aura_dir(self) -> None:
        """Ensure .aura directory exists."""
        self.aura_dir.mkdir(exist_ok=True)

    def load(self) -> MemoryData:
        """Load memory from disk."""
        if not self.memory_file.exists():
            return MemoryData()

        try:
            data = json.loads(self.memory_file.read_text())
            return MemoryData(
                version=data.get("version", 1),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                papers=data.get("papers", []),
                citations=data.get("citations", []),
                conventions=data.get("conventions", []),
                todos=data.get("todos", []),
                notes=data.get("notes", []),
            )
        except (json.JSONDecodeError, KeyError):
            return MemoryData()

    def save(self, memory: MemoryData) -> None:
        """Save memory to disk."""
        self._ensure_aura_dir()
        memory.updated_at = datetime.now().isoformat()
        self.memory_file.write_text(json.dumps(asdict(memory), indent=2))

    def add_entry(self, entry_type: EntryType, entry_data: dict) -> dict:
        """Add a new entry of the given type."""
        memory = self.load()
        entries = getattr(memory, entry_type)

        # Create entry with ID and timestamp
        entry = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            **entry_data,
        }
        entries.append(entry)
        self.save(memory)
        return entry

    def update_entry(self, entry_type: EntryType, entry_id: str,
                     entry_data: dict) -> Optional[dict]:
        """Update an existing entry."""
        memory = self.load()
        entries = getattr(memory, entry_type)

        for i, entry in enumerate(entries):
            if entry.get("id") == entry_id:
                # Preserve id and created_at
                updated = {
                    **entry_data,
                    "id": entry_id,
                    "created_at": entry.get("created_at", datetime.now().isoformat()),
                }
                entries[i] = updated
                self.save(memory)
                return updated

        return None

    def delete_entry(self, entry_type: EntryType, entry_id: str) -> bool:
        """Delete an entry by ID."""
        memory = self.load()
        entries = getattr(memory, entry_type)

        for i, entry in enumerate(entries):
            if entry.get("id") == entry_id:
                entries.pop(i)
                self.save(memory)
                return True

        return False

    def estimate_tokens(self) -> int:
        """Estimate token count for all memory content."""
        memory = self.load()
        text = self.format_for_prompt(memory)
        return len(text) // CHARS_PER_TOKEN

    def get_stats(self) -> dict:
        """Get memory statistics."""
        token_count = self.estimate_tokens()
        return {
            "token_count": token_count,
            "warning": token_count > TOKEN_WARNING_THRESHOLD,
            "threshold": TOKEN_WARNING_THRESHOLD,
        }

    def format_for_prompt(self, memory: MemoryData = None) -> str:
        """Format memory for injection into system prompt."""
        if memory is None:
            memory = self.load()

        sections = []

        # Papers
        if memory.papers:
            lines = [f"### Papers ({len(memory.papers)} entries)"]
            for p in memory.papers:
                authors = ", ".join(p.get("authors", []))
                arxiv = f" [{p.get('arxiv_id')}]" if p.get("arxiv_id") else ""
                lines.append(f"- **{p.get('title')}** ({authors}){arxiv}")
                if p.get("summary"):
                    lines.append(f"  Summary: {p.get('summary')}")
                if p.get("tags"):
                    lines.append(f"  Tags: {', '.join(p.get('tags'))}")
            sections.append("\n".join(lines))

        # Citations
        if memory.citations:
            lines = [f"### Citations ({len(memory.citations)} entries)"]
            for c in memory.citations:
                lines.append(f"- `{c.get('bibtex_key')}` → {c.get('reason')}")
            sections.append("\n".join(lines))

        # Conventions
        if memory.conventions:
            lines = [f"### Conventions ({len(memory.conventions)} entries)"]
            for c in memory.conventions:
                example = f" (e.g., \"{c.get('example')}\")" if c.get("example") else ""
                lines.append(f"- {c.get('rule')}{example}")
            sections.append("\n".join(lines))

        # Todos
        if memory.todos:
            lines = [f"### Todos ({len(memory.todos)} entries)"]
            for t in memory.todos:
                priority = t.get("priority", "medium").upper()
                status = t.get("status", "pending")
                lines.append(f"- [{priority}] {t.get('task')} ({status})")
            sections.append("\n".join(lines))

        # Notes
        if memory.notes:
            lines = [f"### Notes ({len(memory.notes)} entries)"]
            for n in memory.notes:
                tags = " " + " ".join(f"#{t}" for t in n.get("tags", [])) if n.get("tags") else ""
                lines.append(f"- {n.get('content')}{tags}")
            sections.append("\n".join(lines))

        if not sections:
            return ""

        return "## Project Memory\n\n" + "\n\n".join(sections)
```

**Step 2: Verify the file was created**

Run: `ls -la backend/services/memory.py`
Expected: File exists

**Step 3: Commit**

```bash
git add backend/services/memory.py
git commit -m "feat(memory): Add MemoryService for project memory storage"
```

---

## Task 2: Memory API Endpoints

**Files:**
- Modify: `backend/main.py`

**Step 1: Add imports and request models at the top of main.py (after existing imports)**

Add after line ~20 (after `from services.project import ProjectService, ProjectInfo`):

```python
from services.memory import MemoryService
```

**Step 2: Add request/response models (after existing models, around line 115)**

Add after `class ChatRequest`:

```python
# ============ Memory Models ============

class MemoryEntryRequest(BaseModel):
    project_path: str


class AddPaperRequest(BaseModel):
    project_path: str
    title: str
    authors: list[str]
    arxiv_id: str = ""
    summary: str = ""
    tags: list[str] = []


class AddCitationRequest(BaseModel):
    project_path: str
    bibtex_key: str
    reason: str
    paper_id: Optional[str] = None


class AddConventionRequest(BaseModel):
    project_path: str
    rule: str
    example: str = ""


class AddTodoRequest(BaseModel):
    project_path: str
    task: str
    priority: str = "medium"
    status: str = "pending"


class AddNoteRequest(BaseModel):
    project_path: str
    content: str
    tags: list[str] = []


class UpdateEntryRequest(BaseModel):
    project_path: str
    data: dict
```

**Step 3: Add memory endpoints (before the sync endpoints, around line 1070)**

```python
# ============ Memory Endpoints ============

@app.get("/api/memory")
async def get_memory(project_path: str):
    """Get all memory entries for a project."""
    service = MemoryService(project_path)
    memory = service.load()
    stats = service.get_stats()

    return {
        "entries": {
            "papers": memory.papers,
            "citations": memory.citations,
            "conventions": memory.conventions,
            "todos": memory.todos,
            "notes": memory.notes,
        },
        "stats": stats,
    }


@app.get("/api/memory/stats")
async def get_memory_stats(project_path: str):
    """Get memory token count and warning status."""
    service = MemoryService(project_path)
    return service.get_stats()


@app.post("/api/memory/papers")
async def add_paper(request: AddPaperRequest):
    """Add a paper entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("papers", {
        "title": request.title,
        "authors": request.authors,
        "arxiv_id": request.arxiv_id,
        "summary": request.summary,
        "tags": request.tags,
    })
    return entry


@app.post("/api/memory/citations")
async def add_citation(request: AddCitationRequest):
    """Add a citation entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("citations", {
        "bibtex_key": request.bibtex_key,
        "reason": request.reason,
        "paper_id": request.paper_id,
    })
    return entry


@app.post("/api/memory/conventions")
async def add_convention(request: AddConventionRequest):
    """Add a convention entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("conventions", {
        "rule": request.rule,
        "example": request.example,
    })
    return entry


@app.post("/api/memory/todos")
async def add_todo(request: AddTodoRequest):
    """Add a todo entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("todos", {
        "task": request.task,
        "priority": request.priority,
        "status": request.status,
    })
    return entry


@app.post("/api/memory/notes")
async def add_note(request: AddNoteRequest):
    """Add a note entry."""
    service = MemoryService(request.project_path)
    entry = service.add_entry("notes", {
        "content": request.content,
        "tags": request.tags,
    })
    return entry


@app.put("/api/memory/{entry_type}/{entry_id}")
async def update_memory_entry(
    entry_type: str,
    entry_id: str,
    request: UpdateEntryRequest,
):
    """Update a memory entry."""
    if entry_type not in ["papers", "citations", "conventions", "todos", "notes"]:
        raise HTTPException(status_code=400, detail=f"Invalid entry type: {entry_type}")

    service = MemoryService(request.project_path)
    entry = service.update_entry(entry_type, entry_id, request.data)

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry


@app.delete("/api/memory/{entry_type}/{entry_id}")
async def delete_memory_entry(
    entry_type: str,
    entry_id: str,
    project_path: str,
):
    """Delete a memory entry."""
    if entry_type not in ["papers", "citations", "conventions", "todos", "notes"]:
        raise HTTPException(status_code=400, detail=f"Invalid entry type: {entry_type}")

    service = MemoryService(project_path)
    success = service.delete_entry(entry_type, entry_id)

    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"success": True}
```

**Step 4: Test the endpoints work**

Run: `cd /Users/zhongzhiyi/Aura/backend && python3 -c "from services.memory import MemoryService; print('OK')"`
Expected: OK

**Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat(memory): Add memory API endpoints"
```

---

## Task 3: Inject Memory into System Prompt

**Files:**
- Modify: `backend/agent/prompts.py`

**Step 1: Update the get_system_prompt function to include memory**

Replace the `get_system_prompt` function (lines 139-155) with:

```python
def get_system_prompt(ctx: "RunContext[AuraDeps]") -> str:
    """
    Dynamic system prompt for PydanticAI Agent.

    This function is passed to Agent(system_prompt=...) and receives
    the RunContext with dependencies.

    Args:
        ctx: PydanticAI RunContext containing AuraDeps

    Returns:
        Formatted system prompt string
    """
    from services.memory import MemoryService

    base_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        project_name=ctx.deps.project_name,
        project_path=ctx.deps.project_path,
    )

    # Load and append project memory
    try:
        memory_service = MemoryService(ctx.deps.project_path)
        memory_text = memory_service.format_for_prompt()
        if memory_text:
            base_prompt += "\n\n" + memory_text
    except Exception:
        pass  # If memory loading fails, continue without it

    return base_prompt
```

**Step 2: Also update get_system_prompt_static for consistency**

Replace `get_system_prompt_static` (lines 158-172) with:

```python
def get_system_prompt_static(project_name: str, project_path: str) -> str:
    """
    Static version of system prompt (for testing or non-PydanticAI use).

    Args:
        project_name: Name of the project
        project_path: Path to the project

    Returns:
        Formatted system prompt string
    """
    from services.memory import MemoryService

    base_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        project_name=project_name,
        project_path=project_path,
    )

    # Load and append project memory
    try:
        memory_service = MemoryService(project_path)
        memory_text = memory_service.format_for_prompt()
        if memory_text:
            base_prompt += "\n\n" + memory_text
    except Exception:
        pass

    return base_prompt
```

**Step 3: Test the prompt includes memory**

Run:
```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
from services.memory import MemoryService
import tempfile
import os

# Create temp project
with tempfile.TemporaryDirectory() as tmpdir:
    svc = MemoryService(tmpdir)
    svc.add_entry("notes", {"content": "Test note", "tags": ["test"]})
    prompt = svc.format_for_prompt()
    print("Memory in prompt:", "Test note" in prompt)
EOF
```
Expected: `Memory in prompt: True`

**Step 4: Commit**

```bash
git add backend/agent/prompts.py
git commit -m "feat(memory): Inject project memory into agent system prompt"
```

---

## Task 4: Memory API Client (Frontend)

**Files:**
- Modify: `app/lib/api.ts`

**Step 1: Add memory types after existing types (around line 52)**

```typescript
// =============================================================================
// Memory Types
// =============================================================================

export interface PaperEntry {
  id: string;
  title: string;
  authors: string[];
  arxiv_id: string;
  summary: string;
  tags: string[];
  created_at: string;
}

export interface CitationEntry {
  id: string;
  bibtex_key: string;
  paper_id: string | null;
  reason: string;
  created_at: string;
}

export interface ConventionEntry {
  id: string;
  rule: string;
  example: string;
  created_at: string;
}

export interface TodoEntry {
  id: string;
  task: string;
  priority: 'low' | 'medium' | 'high';
  status: 'pending' | 'in_progress' | 'completed';
  created_at: string;
}

export interface NoteEntry {
  id: string;
  content: string;
  tags: string[];
  created_at: string;
}

export interface MemoryStats {
  token_count: number;
  warning: boolean;
  threshold: number;
}

export interface MemoryData {
  entries: {
    papers: PaperEntry[];
    citations: CitationEntry[];
    conventions: ConventionEntry[];
    todos: TodoEntry[];
    notes: NoteEntry[];
  };
  stats: MemoryStats;
}

export type MemoryEntryType = 'papers' | 'citations' | 'conventions' | 'todos' | 'notes';
```

**Step 2: Add memory methods to ApiClient class (before healthCheck method, around line 475)**

```typescript
  // ===========================================================================
  // Memory Operations
  // ===========================================================================

  /**
   * Get all memory entries for a project
   */
  async getMemory(projectPath: string): Promise<MemoryData> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/memory?project_path=${encodeURIComponent(projectPath)}`;
    console.log('[API] getMemory:', url);

    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get memory stats (token count)
   */
  async getMemoryStats(projectPath: string): Promise<MemoryStats> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/memory/stats?project_path=${encodeURIComponent(projectPath)}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Add a paper entry
   */
  async addPaper(
    projectPath: string,
    paper: { title: string; authors: string[]; arxiv_id?: string; summary?: string; tags?: string[] }
  ): Promise<PaperEntry> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/papers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, ...paper }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Add a citation entry
   */
  async addCitation(
    projectPath: string,
    citation: { bibtex_key: string; reason: string; paper_id?: string }
  ): Promise<CitationEntry> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/citations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, ...citation }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Add a convention entry
   */
  async addConvention(
    projectPath: string,
    convention: { rule: string; example?: string }
  ): Promise<ConventionEntry> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/conventions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, ...convention }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Add a todo entry
   */
  async addTodo(
    projectPath: string,
    todo: { task: string; priority?: string; status?: string }
  ): Promise<TodoEntry> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/todos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, ...todo }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Add a note entry
   */
  async addNote(
    projectPath: string,
    note: { content: string; tags?: string[] }
  ): Promise<NoteEntry> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, ...note }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Update a memory entry
   */
  async updateMemoryEntry(
    projectPath: string,
    entryType: MemoryEntryType,
    entryId: string,
    data: Record<string, unknown>
  ): Promise<unknown> {
    await this.ensureInitialized();

    const response = await fetch(`${this.baseUrl}/api/memory/${entryType}/${entryId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, data }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Delete a memory entry
   */
  async deleteMemoryEntry(
    projectPath: string,
    entryType: MemoryEntryType,
    entryId: string
  ): Promise<void> {
    await this.ensureInitialized();

    const response = await fetch(
      `${this.baseUrl}/api/memory/${entryType}/${entryId}?project_path=${encodeURIComponent(projectPath)}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  }
```

**Step 3: Commit**

```bash
git add app/lib/api.ts
git commit -m "feat(memory): Add memory API client functions"
```

---

## Task 5: Memory Modal Component

**Files:**
- Create: `app/components/MemoryModal.tsx`

**Step 1: Create the MemoryModal component**

```typescript
'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  X,
  Plus,
  Trash2,
  Edit2,
  Book,
  Quote,
  ListChecks,
  FileText,
  AlertTriangle,
  Check,
  BookOpen,
} from 'lucide-react';
import {
  api,
  MemoryData,
  MemoryEntryType,
  PaperEntry,
  CitationEntry,
  ConventionEntry,
  TodoEntry,
  NoteEntry,
} from '@/lib/api';

interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string | null;
}

type TabType = 'papers' | 'citations' | 'conventions' | 'todos' | 'notes';

const TABS: { id: TabType; label: string; icon: React.ReactNode }[] = [
  { id: 'papers', label: 'Papers', icon: <Book size={14} /> },
  { id: 'citations', label: 'Citations', icon: <Quote size={14} /> },
  { id: 'conventions', label: 'Conventions', icon: <BookOpen size={14} /> },
  { id: 'todos', label: 'Todos', icon: <ListChecks size={14} /> },
  { id: 'notes', label: 'Notes', icon: <FileText size={14} /> },
];

export default function MemoryModal({
  isOpen,
  onClose,
  projectPath,
}: MemoryModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('papers');
  const [memory, setMemory] = useState<MemoryData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state for adding/editing
  const [formData, setFormData] = useState<Record<string, string>>({});

  // Load memory on open
  useEffect(() => {
    if (isOpen && projectPath) {
      loadMemory();
    }
  }, [isOpen, projectPath]);

  const loadMemory = async () => {
    if (!projectPath) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getMemory(projectPath);
      setMemory(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load memory');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!projectPath) return;

    try {
      switch (activeTab) {
        case 'papers':
          await api.addPaper(projectPath, {
            title: formData.title || '',
            authors: (formData.authors || '').split(',').map(a => a.trim()).filter(Boolean),
            arxiv_id: formData.arxiv_id || '',
            summary: formData.summary || '',
            tags: (formData.tags || '').split(',').map(t => t.trim()).filter(Boolean),
          });
          break;
        case 'citations':
          await api.addCitation(projectPath, {
            bibtex_key: formData.bibtex_key || '',
            reason: formData.reason || '',
          });
          break;
        case 'conventions':
          await api.addConvention(projectPath, {
            rule: formData.rule || '',
            example: formData.example || '',
          });
          break;
        case 'todos':
          await api.addTodo(projectPath, {
            task: formData.task || '',
            priority: formData.priority || 'medium',
          });
          break;
        case 'notes':
          await api.addNote(projectPath, {
            content: formData.content || '',
            tags: (formData.tags || '').split(',').map(t => t.trim()).filter(Boolean),
          });
          break;
      }

      setFormData({});
      setIsAdding(false);
      loadMemory();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add entry');
    }
  };

  const handleDelete = async (entryType: MemoryEntryType, entryId: string) => {
    if (!projectPath) return;

    try {
      await api.deleteMemoryEntry(projectPath, entryType, entryId);
      loadMemory();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete entry');
    }
  };

  const handleUpdate = async (entryType: MemoryEntryType, entryId: string) => {
    if (!projectPath) return;

    try {
      let data: Record<string, unknown> = {};

      switch (entryType) {
        case 'papers':
          data = {
            title: formData.title || '',
            authors: (formData.authors || '').split(',').map(a => a.trim()).filter(Boolean),
            arxiv_id: formData.arxiv_id || '',
            summary: formData.summary || '',
            tags: (formData.tags || '').split(',').map(t => t.trim()).filter(Boolean),
          };
          break;
        case 'citations':
          data = {
            bibtex_key: formData.bibtex_key || '',
            reason: formData.reason || '',
          };
          break;
        case 'conventions':
          data = {
            rule: formData.rule || '',
            example: formData.example || '',
          };
          break;
        case 'todos':
          data = {
            task: formData.task || '',
            priority: formData.priority || 'medium',
            status: formData.status || 'pending',
          };
          break;
        case 'notes':
          data = {
            content: formData.content || '',
            tags: (formData.tags || '').split(',').map(t => t.trim()).filter(Boolean),
          };
          break;
      }

      await api.updateMemoryEntry(projectPath, entryType, entryId, data);
      setFormData({});
      setEditingId(null);
      loadMemory();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update entry');
    }
  };

  const startEdit = (entry: Record<string, unknown>) => {
    setEditingId(entry.id as string);
    const data: Record<string, string> = {};

    Object.entries(entry).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        data[key] = value.join(', ');
      } else if (typeof value === 'string') {
        data[key] = value;
      }
    });

    setFormData(data);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsAdding(false);
    setFormData({});
  };

  const renderEntryCard = (
    entry: Record<string, unknown>,
    entryType: MemoryEntryType
  ) => {
    const isEditing = editingId === entry.id;

    if (isEditing) {
      return renderForm(entryType, true, entry.id as string);
    }

    return (
      <div
        key={entry.id as string}
        className="p-3 bg-black/3 rounded-yw-lg group"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            {entryType === 'papers' && (
              <>
                <div className="typo-body-strong truncate">{(entry as PaperEntry).title}</div>
                <div className="typo-small text-secondary">
                  {(entry as PaperEntry).authors.join(', ')}
                  {(entry as PaperEntry).arxiv_id && ` • ${(entry as PaperEntry).arxiv_id}`}
                </div>
                {(entry as PaperEntry).summary && (
                  <div className="typo-small text-tertiary mt-1 line-clamp-2">
                    {(entry as PaperEntry).summary}
                  </div>
                )}
                {(entry as PaperEntry).tags.length > 0 && (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {(entry as PaperEntry).tags.map(tag => (
                      <span key={tag} className="px-1.5 py-0.5 bg-green1/10 text-green2 rounded typo-ex-small">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}

            {entryType === 'citations' && (
              <>
                <div className="typo-body-strong font-mono">{(entry as CitationEntry).bibtex_key}</div>
                <div className="typo-small text-secondary mt-1">{(entry as CitationEntry).reason}</div>
              </>
            )}

            {entryType === 'conventions' && (
              <>
                <div className="typo-body">{(entry as ConventionEntry).rule}</div>
                {(entry as ConventionEntry).example && (
                  <div className="typo-small text-tertiary mt-1 font-mono">
                    e.g., {(entry as ConventionEntry).example}
                  </div>
                )}
              </>
            )}

            {entryType === 'todos' && (
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded typo-ex-small ${
                  (entry as TodoEntry).priority === 'high' ? 'bg-error/10 text-error' :
                  (entry as TodoEntry).priority === 'medium' ? 'bg-warn/10 text-warn' :
                  'bg-black/5 text-tertiary'
                }`}>
                  {(entry as TodoEntry).priority.toUpperCase()}
                </span>
                <span className={`typo-body ${(entry as TodoEntry).status === 'completed' ? 'line-through text-tertiary' : ''}`}>
                  {(entry as TodoEntry).task}
                </span>
                <span className="typo-ex-small text-tertiary">({(entry as TodoEntry).status})</span>
              </div>
            )}

            {entryType === 'notes' && (
              <>
                <div className="typo-body">{(entry as NoteEntry).content}</div>
                {(entry as NoteEntry).tags.length > 0 && (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {(entry as NoteEntry).tags.map(tag => (
                      <span key={tag} className="text-green2 typo-small">#{tag}</span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => startEdit(entry)}
              className="p-1 hover:bg-black/5 rounded"
              title="Edit"
            >
              <Edit2 size={14} className="text-secondary" />
            </button>
            <button
              onClick={() => handleDelete(entryType, entry.id as string)}
              className="p-1 hover:bg-error/10 rounded"
              title="Delete"
            >
              <Trash2 size={14} className="text-error" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderForm = (entryType: TabType, isEdit = false, entryId?: string) => {
    return (
      <div className="p-3 bg-black/3 rounded-yw-lg space-y-3">
        {entryType === 'papers' && (
          <>
            <input
              type="text"
              placeholder="Paper title"
              value={formData.title || ''}
              onChange={e => setFormData({ ...formData, title: e.target.value })}
              className="input-field w-full"
            />
            <input
              type="text"
              placeholder="Authors (comma-separated)"
              value={formData.authors || ''}
              onChange={e => setFormData({ ...formData, authors: e.target.value })}
              className="input-field w-full"
            />
            <input
              type="text"
              placeholder="arXiv ID (optional)"
              value={formData.arxiv_id || ''}
              onChange={e => setFormData({ ...formData, arxiv_id: e.target.value })}
              className="input-field w-full"
            />
            <textarea
              placeholder="Summary (optional)"
              value={formData.summary || ''}
              onChange={e => setFormData({ ...formData, summary: e.target.value })}
              className="input-field w-full h-20 resize-none"
            />
            <input
              type="text"
              placeholder="Tags (comma-separated)"
              value={formData.tags || ''}
              onChange={e => setFormData({ ...formData, tags: e.target.value })}
              className="input-field w-full"
            />
          </>
        )}

        {entryType === 'citations' && (
          <>
            <input
              type="text"
              placeholder="BibTeX key (e.g., vaswani2017attention)"
              value={formData.bibtex_key || ''}
              onChange={e => setFormData({ ...formData, bibtex_key: e.target.value })}
              className="input-field w-full font-mono"
            />
            <textarea
              placeholder="Why is this cited?"
              value={formData.reason || ''}
              onChange={e => setFormData({ ...formData, reason: e.target.value })}
              className="input-field w-full h-20 resize-none"
            />
          </>
        )}

        {entryType === 'conventions' && (
          <>
            <input
              type="text"
              placeholder="Rule (e.g., Use \\cref{} instead of \\ref{})"
              value={formData.rule || ''}
              onChange={e => setFormData({ ...formData, rule: e.target.value })}
              className="input-field w-full"
            />
            <input
              type="text"
              placeholder="Example (optional)"
              value={formData.example || ''}
              onChange={e => setFormData({ ...formData, example: e.target.value })}
              className="input-field w-full font-mono"
            />
          </>
        )}

        {entryType === 'todos' && (
          <>
            <input
              type="text"
              placeholder="Task description"
              value={formData.task || ''}
              onChange={e => setFormData({ ...formData, task: e.target.value })}
              className="input-field w-full"
            />
            <div className="flex gap-2">
              <select
                value={formData.priority || 'medium'}
                onChange={e => setFormData({ ...formData, priority: e.target.value })}
                className="input-field"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              {isEdit && (
                <select
                  value={formData.status || 'pending'}
                  onChange={e => setFormData({ ...formData, status: e.target.value })}
                  className="input-field"
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                </select>
              )}
            </div>
          </>
        )}

        {entryType === 'notes' && (
          <>
            <textarea
              placeholder="Note content"
              value={formData.content || ''}
              onChange={e => setFormData({ ...formData, content: e.target.value })}
              className="input-field w-full h-24 resize-none"
            />
            <input
              type="text"
              placeholder="Tags (comma-separated)"
              value={formData.tags || ''}
              onChange={e => setFormData({ ...formData, tags: e.target.value })}
              className="input-field w-full"
            />
          </>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={cancelEdit} className="btn-ghost">
            Cancel
          </button>
          <button
            onClick={() => isEdit && entryId ? handleUpdate(entryType, entryId) : handleAdd()}
            className="btn-primary"
          >
            <Check size={14} />
            {isEdit ? 'Save' : 'Add'}
          </button>
        </div>
      </div>
    );
  };

  if (!isOpen) return null;

  const entries = memory?.entries[activeTab] || [];
  const tokenCount = memory?.stats.token_count || 0;
  const tokenWarning = memory?.stats.warning || false;
  const tokenThreshold = memory?.stats.threshold || 4000;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-2xl max-h-[80vh] bg-white rounded-yw-2xl shadow-xl flex flex-col animate-fadeInUp">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/6">
          <h2 className="typo-h2">Project Memory</h2>
          <button onClick={onClose} className="btn-icon">
            <X size={18} className="text-secondary" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 py-3 border-b border-black/6 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setIsAdding(false);
                setEditingId(null);
                setFormData({});
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full typo-small transition-colors ${
                activeTab === tab.id
                  ? 'bg-green1 text-white'
                  : 'hover:bg-black/5 text-secondary'
              }`}
            >
              {tab.icon}
              {tab.label}
              {memory && (
                <span className={`ml-1 ${activeTab === tab.id ? 'text-white/70' : 'text-tertiary'}`}>
                  ({memory.entries[tab.id].length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-error/10 rounded-yw-lg typo-small text-error">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="text-center py-8 text-tertiary">Loading...</div>
          ) : (
            <div className="space-y-3">
              {entries.map(entry => renderEntryCard(entry, activeTab))}

              {isAdding ? (
                renderForm(activeTab)
              ) : (
                <button
                  onClick={() => setIsAdding(true)}
                  className="w-full p-3 border-2 border-dashed border-black/10 rounded-yw-lg text-secondary hover:border-green1 hover:text-green1 transition-colors flex items-center justify-center gap-2"
                >
                  <Plus size={16} />
                  Add {activeTab.slice(0, -1)}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer with token counter */}
        <div className="px-6 py-3 border-t border-black/6 flex items-center justify-between">
          <div className={`flex items-center gap-2 typo-small ${tokenWarning ? 'text-warn' : 'text-tertiary'}`}>
            {tokenWarning && <AlertTriangle size={14} />}
            Memory size: {tokenCount.toLocaleString()} / {tokenThreshold.toLocaleString()} tokens
          </div>
          <button onClick={onClose} className="btn-ghost">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify the file compiles**

Run: `cd /Users/zhongzhiyi/Aura/app && npx tsc --noEmit components/MemoryModal.tsx 2>&1 | head -20`
Expected: No errors (or only unrelated warnings)

**Step 3: Commit**

```bash
git add app/components/MemoryModal.tsx
git commit -m "feat(memory): Add MemoryModal UI component"
```

---

## Task 6: Add Memory Button to Toolbar

**Files:**
- Modify: `app/components/Toolbar.tsx`

**Step 1: Add Brain icon import (line 4, add to existing import)**

Change the lucide-react import to include `Brain`:

```typescript
import {
  FolderOpen,
  FilePlus,
  Save,
  Play,
  RefreshCw,
  Settings,
  Loader2,
  Check,
  X,
  AlertCircle,
  Cloud,
  CloudOff,
  Brain,
} from 'lucide-react';
```

**Step 2: Add onMemory prop to interface (around line 33)**

Add after `onSettings: () => void;`:

```typescript
  onMemory: () => void;
```

**Step 3: Add onMemory to destructured props (around line 49)**

Add `onMemory` to the destructured props:

```typescript
  onSettings,
  onMemory,
}: ToolbarProps) {
```

**Step 4: Add Memory button before Settings button (around line 175, before the Settings button)**

Add before the Settings button:

```typescript
      {/* Memory */}
      <button
        onClick={onMemory}
        className="btn-icon"
        title="Project Memory"
      >
        <Brain size={16} className="text-secondary" />
      </button>
```

**Step 5: Commit**

```bash
git add app/components/Toolbar.tsx
git commit -m "feat(memory): Add Memory button to toolbar"
```

---

## Task 7: Wire Up Memory Modal in Main Page

**Files:**
- Modify: `app/app/page.tsx`

**Step 1: Add MemoryModal import (near other component imports)**

Add after the SettingsModal import:

```typescript
import MemoryModal from '@/components/MemoryModal';
```

**Step 2: Add memory modal state (near other state declarations)**

Add after `const [showSettings, setShowSettings] = useState(false);`:

```typescript
const [showMemory, setShowMemory] = useState(false);
```

**Step 3: Pass onMemory prop to Toolbar**

Find the Toolbar component and add the `onMemory` prop:

```typescript
onMemory={() => setShowMemory(true)}
```

**Step 4: Add MemoryModal component (near SettingsModal)**

Add after the SettingsModal component:

```typescript
<MemoryModal
  isOpen={showMemory}
  onClose={() => setShowMemory(false)}
  projectPath={projectPath}
/>
```

**Step 5: Commit**

```bash
git add app/app/page.tsx
git commit -m "feat(memory): Wire up MemoryModal in main page"
```

---

## Task 8: End-to-End Test

**Step 1: Start the backend**

Run: `cd /Users/zhongzhiyi/Aura/backend && uvicorn main:app --reload --port 8000 &`

**Step 2: Test memory API endpoints**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
import httpx
import json

base = "http://127.0.0.1:8000"
project = "/tmp/test-memory-project"

# Create test project dir
import os
os.makedirs(f"{project}/.aura", exist_ok=True)

# Test GET (empty)
r = httpx.get(f"{base}/api/memory", params={"project_path": project})
print("GET empty:", r.status_code, len(r.json()["entries"]["notes"]))

# Test POST note
r = httpx.post(f"{base}/api/memory/notes", json={
    "project_path": project,
    "content": "Test note",
    "tags": ["test"]
})
print("POST note:", r.status_code, r.json()["id"][:8])

# Test GET (with note)
r = httpx.get(f"{base}/api/memory", params={"project_path": project})
print("GET with note:", r.status_code, len(r.json()["entries"]["notes"]))

# Test stats
r = httpx.get(f"{base}/api/memory/stats", params={"project_path": project})
print("GET stats:", r.status_code, r.json()["token_count"])

print("All tests passed!")
EOF
```

Expected output:
```
GET empty: 200 0
POST note: 200 <uuid>
GET with note: 200 1
GET stats: 200 <number>
All tests passed!
```

**Step 3: Test prompt injection**

```bash
cd /Users/zhongzhiyi/Aura/backend && python3 << 'EOF'
from services.memory import MemoryService
from agent.prompts import get_system_prompt_static

project = "/tmp/test-memory-project"

# Add some memory
svc = MemoryService(project)
svc.add_entry("conventions", {"rule": "Use booktabs for tables", "example": ""})

# Get prompt
prompt = get_system_prompt_static("test", project)
print("Memory in prompt:", "booktabs" in prompt)
print("Project Memory section:", "## Project Memory" in prompt)
EOF
```

Expected:
```
Memory in prompt: True
Project Memory section: True
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(memory): Complete Phase 6 memory system implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | MemoryService backend | `backend/services/memory.py` |
| 2 | Memory API endpoints | `backend/main.py` |
| 3 | System prompt injection | `backend/agent/prompts.py` |
| 4 | API client functions | `app/lib/api.ts` |
| 5 | MemoryModal component | `app/components/MemoryModal.tsx` |
| 6 | Toolbar Memory button | `app/components/Toolbar.tsx` |
| 7 | Wire up in main page | `app/app/page.tsx` |
| 8 | End-to-end testing | - |

**Total commits**: 8
