# Memory System Design

## Overview

Project memory system that persists knowledge across sessions. Users explicitly manage memories through a dedicated UI panel. All memories are injected into the agent's system prompt at session start.

**Key principles**:
- Sessions are independent conversations (like Claude Code)
- Memory is user-controlled, not automatic
- All memories loaded at session start (no semantic search needed)
- Simple JSON storage (git-friendly, human-readable)

---

## Data Model

**Storage**: `.aura/memory.json`

```json
{
  "version": 1,
  "created_at": "2026-01-10T...",
  "updated_at": "2026-01-12T...",
  "entries": {
    "papers": [
      {
        "id": "uuid",
        "title": "Attention Is All You Need",
        "authors": ["Vaswani et al."],
        "arxiv_id": "1706.03762",
        "summary": "Introduces transformer architecture...",
        "tags": ["transformers", "attention"],
        "created_at": "..."
      }
    ],
    "citations": [
      {
        "id": "uuid",
        "bibtex_key": "vaswani2017attention",
        "paper_id": "uuid-ref-to-paper",
        "reason": "Foundational architecture for our method",
        "created_at": "..."
      }
    ],
    "conventions": [
      {
        "id": "uuid",
        "rule": "Use \\cref{} instead of \\ref{}",
        "example": "As shown in \\cref{fig:architecture}...",
        "created_at": "..."
      }
    ],
    "todos": [
      {
        "id": "uuid",
        "task": "Add ablation study for attention heads",
        "priority": "high",
        "status": "pending",
        "created_at": "..."
      }
    ],
    "notes": [
      {
        "id": "uuid",
        "content": "Main theorem proof relies on Lemma 3.2",
        "tags": ["theorem", "proof"],
        "created_at": "..."
      }
    ]
  }
}
```

### Entry Types

| Type | Fields | Purpose |
|------|--------|---------|
| Paper | title, authors, arxiv_id, summary, tags | Track papers you've read |
| Citation | bibtex_key, paper_id, reason | Remember why you cited something |
| Convention | rule, example | Project-specific writing rules |
| Todo | task, priority, status | Research tasks to remember |
| Note | content, tags | Free-form notes |

---

## Agent Injection

At session start, memories are formatted and appended to the system prompt.

**Format**:

```
## Project Memory

### Papers (3 entries)
- **Attention Is All You Need** (Vaswani et al.) [1706.03762]
  Summary: Introduces transformer architecture...
  Tags: transformers, attention

- **BERT: Pre-training of Deep Bidirectional Transformers** (Devlin et al.) [1810.04805]
  Summary: Masked language modeling for pre-training...
  Tags: transformers, pretraining

### Citations (2 entries)
- `vaswani2017attention` → Foundational architecture for our method
- `devlin2018bert` → Comparison baseline in experiments

### Conventions (2 entries)
- Use \cref{} instead of \ref{} (e.g., "As shown in \cref{fig:architecture}...")
- Always use booktabs for tables

### Todos (1 entry)
- [HIGH] Add ablation study for attention heads (pending)

### Notes (2 entries)
- Main theorem proof relies on Lemma 3.2 #theorem #proof
- Reviewer 2 prefers passive voice in methods section
```

**Size limit**: Soft warning at ~4000 tokens. Users can exceed if desired.

---

## UI Design

### Toolbar

New "Memory" button (brain icon) next to Settings gear.

### Memory Modal

```
┌─────────────────────────────────────────────────────────────────────┐
│  Project Memory                                              ✕ Close │
├─────────────────────────────────────────────────────────────────────┤
│  [Papers] [Citations] [Conventions] [Todos] [Notes]    ← Tab buttons │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Attention Is All You Need                              [Edit]│   │
│  │ Vaswani et al. • 1706.03762                           [Del] │   │
│  │ Introduces transformer architecture with self-attention...  │   │
│  │ #transformers #attention                                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ BERT: Pre-training of Deep Bidirectional...           [Edit]│   │
│  │ Devlin et al. • 1810.04805                            [Del] │   │
│  │ Masked language modeling approach for pre-training...       │   │
│  │ #transformers #pretraining                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                                            [+ Add Paper]            │
├─────────────────────────────────────────────────────────────────────┤
│  ⚠ Memory size: 3,200 / 4,000 tokens                               │
└─────────────────────────────────────────────────────────────────────┘
```

**Interactions**:
- Tabs switch between entry types
- Each entry card has Edit/Delete buttons
- "+ Add" button opens inline form for that type
- Token counter at bottom: yellow > 3000, red > 4000

---

## Backend API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/memory` | GET | Load all memory entries for project |
| `/api/memory` | PUT | Save entire memory (full replace) |
| `/api/memory/{type}` | POST | Add entry (papers, citations, etc.) |
| `/api/memory/{type}/{id}` | PUT | Update specific entry |
| `/api/memory/{type}/{id}` | DELETE | Delete specific entry |
| `/api/memory/stats` | GET | Get token count and size warning |

### Examples

```python
# GET /api/memory?project_path=/path/to/project
{
  "entries": { "papers": [...], "citations": [...], ... },
  "stats": { "token_count": 3200, "warning": false }
}

# POST /api/memory/papers?project_path=/path/to/project
{
  "title": "GPT-3",
  "authors": ["Brown et al."],
  "arxiv_id": "2005.14165",
  "summary": "Large language models are few-shot learners",
  "tags": ["llm", "few-shot"]
}
# Returns: { "id": "uuid", "created_at": "..." }
```

---

## Implementation

### New Files

```
backend/
└── services/
    └── memory.py          # MemoryService - CRUD + token counting

app/
└── components/
    └── MemoryModal.tsx    # Memory modal UI with tabs
```

### Modified Files

```
backend/
├── main.py                # Add /api/memory endpoints
└── agent/
    └── pydantic_agent.py  # Inject memory into system prompt

app/
├── components/
│   └── Toolbar.tsx        # Add Memory button
└── lib/
    └── api.ts             # Add memory API functions
```

### Dependencies

None new - uses standard JSON operations and existing token estimation logic.

---

## Implementation Order

1. **MemoryService** (`backend/services/memory.py`)
   - JSON read/write
   - CRUD operations for each entry type
   - Token counting and warning logic

2. **API Endpoints** (`backend/main.py`)
   - All `/api/memory/*` routes

3. **Agent Integration** (`backend/agent/pydantic_agent.py`)
   - Load memory at session start
   - Format and inject into system prompt

4. **Memory Modal** (`app/components/MemoryModal.tsx`)
   - Tabbed interface
   - Entry cards with edit/delete
   - Add forms for each type
   - Token counter with warnings

5. **Toolbar Integration** (`app/components/Toolbar.tsx`)
   - Add Memory button with brain icon

6. **API Client** (`app/lib/api.ts`)
   - Memory API functions

---

## Success Criteria

- Users can add/edit/delete all 5 entry types
- Memory persists across app restarts
- Agent sees formatted memory in every session
- Token warning appears when approaching limit
- Memory file is valid JSON and git-diffable
