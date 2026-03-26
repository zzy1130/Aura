# Capability Discovery & Expression Design

> **Goal**: Make Aura's powerful features discoverable, accessible, and delightful to use.

## The Problem

We've built sophisticated capabilities:
- **Vibe Research**: Deep autonomous literature exploration
- **Writing Intelligence** (Phase 8): LaTeX-aware editing, citations, figures
- **Memory System**: Persistent project context
- **Overleaf Sync**: Git-based collaboration
- **Compilation**: Docker-based LaTeX with error fixing

But users may not know:
1. What Aura can do
2. How to trigger these capabilities
3. When to use which feature
4. What the agent is capable of vs. what requires manual action

## Design Principles

1. **Progressive Disclosure**: Show basics first, reveal depth as needed
2. **Context-Aware**: Suggest relevant actions based on current state
3. **Low Friction**: One keystroke to discover, one more to execute
4. **Visual Hierarchy**: Primary actions visible, secondary discoverable
5. **Learn by Doing**: Interactive tutorials, not walls of text

---

## Proposed Solutions

### 1. Slash Command System (Priority: High)

**The Idea**: Users type "/" in the chat input to see available commands.

**Why**:
- Familiar pattern (Discord, Slack, Notion)
- Discoverable without being intrusive
- Self-documenting

**Implementation**:

```
User types: /
Dropdown appears:
┌─────────────────────────────────────────────────┐
│ 🔍 Commands                                     │
├─────────────────────────────────────────────────┤
│ 📚 /research [topic]                            │
│    Quick research on a topic                    │
│                                                 │
│ 🔬 /vibe-research [topic]                       │
│    Start deep autonomous research session       │
│                                                 │
│ 📄 /analyze                                     │
│    Analyze document structure                   │
│                                                 │
│ 🔧 /fix-errors                                  │
│    Fix LaTeX compilation errors                 │
│                                                 │
│ 📖 /add-citation [arxiv:id or query]            │
│    Add a citation to the document               │
│                                                 │
│ ✨ /improve [section]                           │
│    Improve writing in a section                 │
│                                                 │
│ 🧹 /clean-bibliography                          │
│    Remove unused citations                      │
│                                                 │
│ 📊 /create-figure [description]                 │
│    Generate a TikZ/pgfplots figure              │
│                                                 │
│ 📋 /create-table [description]                  │
│    Generate a booktabs table                    │
└─────────────────────────────────────────────────┘
```

**Command Categories**:

| Category | Commands |
|----------|----------|
| Research | `/research`, `/vibe-research`, `/find-papers`, `/add-citation` |
| Writing | `/improve`, `/expand`, `/summarize`, `/check-consistency` |
| Structure | `/analyze`, `/outline`, `/add-section`, `/refactor` |
| LaTeX | `/fix-errors`, `/create-figure`, `/create-table`, `/format` |
| Bibliography | `/add-citation`, `/clean-bibliography`, `/suggest-citations` |
| Project | `/memory`, `/settings`, `/compile`, `/sync` |

**Technical Design**:

```typescript
// app/lib/commands.ts

interface SlashCommand {
  name: string;
  aliases?: string[];
  description: string;
  icon: React.ComponentType;
  category: 'research' | 'writing' | 'structure' | 'latex' | 'bibliography' | 'project';
  args?: {
    name: string;
    description: string;
    required: boolean;
    placeholder?: string;
  }[];
  execute: (args: Record<string, string>, context: CommandContext) => Promise<void>;
}

const commands: SlashCommand[] = [
  {
    name: 'vibe-research',
    description: 'Start deep autonomous research session',
    icon: Microscope,
    category: 'research',
    args: [{ name: 'topic', description: 'Research topic', required: true, placeholder: 'e.g., efficient attention mechanisms' }],
    execute: async (args, ctx) => {
      // Switch to vibe mode and start session
      ctx.setMode('vibe');
      await ctx.api.startVibeResearch(ctx.projectPath, args.topic);
    },
  },
  // ... more commands
];
```

**UI Component**:

```typescript
// app/components/CommandPalette.tsx

// Triggered when user types "/" in chat input
// - Fuzzy search through commands
// - Keyboard navigation (↑↓ Enter)
// - Shows argument hints after command selected
// - Executes on Enter or click
```

---

### 2. Welcome Message & Capability Showcase (Priority: High)

**The Idea**: When a project is opened, show a contextual welcome that introduces capabilities.

**Empty Project Welcome**:
```
┌─────────────────────────────────────────────────────┐
│  ✨ Welcome to Aura                                 │
│                                                     │
│  I'm your AI research assistant. Here's what I     │
│  can help you with:                                │
│                                                     │
│  📚 Research Papers                                 │
│     "Find papers on [topic]" or /vibe-research     │
│                                                     │
│  ✍️  Write & Edit LaTeX                            │
│     "Write an introduction about..." or /improve   │
│                                                     │
│  🔧 Fix Errors                                      │
│     "Fix the compilation errors" or /fix-errors    │
│                                                     │
│  📖 Manage Citations                                │
│     "Add citation for arxiv:2301.07041"            │
│                                                     │
│  Type / for more commands, or just ask me anything!│
│                                                     │
│  ┌──────────────────┐ ┌───────────────────┐        │
│  │ 🔬 Vibe Research │ │ ❓ What Can I Do? │        │
│  └──────────────────┘ └───────────────────┘        │
└─────────────────────────────────────────────────────┘
```

**Returning User Welcome** (if session has history):
```
┌─────────────────────────────────────────────────────┐
│  Welcome back! Last session:                        │
│  - Worked on: Introduction section                  │
│  - Vibe Research: "efficient attention" (70% done)  │
│                                                     │
│  ┌────────────────┐ ┌─────────────────────┐        │
│  │ ▶ Continue     │ │ 🆕 Start Fresh      │        │
│  └────────────────┘ └─────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

---

### 3. Contextual Action Buttons (Priority: Medium)

**The Idea**: Show relevant action buttons based on current context.

**After Compilation Error**:
```
┌─────────────────────────────────────────────────────┐
│  ❌ Compilation failed with 3 errors                │
│                                                     │
│  ┌────────────────┐ ┌────────────────┐              │
│  │ 🔧 Fix Errors  │ │ 📋 Show Log    │              │
│  └────────────────┘ └────────────────┘              │
└─────────────────────────────────────────────────────┘
```

**When Viewing a Section**:
```
┌─────────────────────────────────────────────────────┐
│  Currently editing: \section{Introduction}          │
│                                                     │
│  ┌──────────┐ ┌────────┐ ┌───────────┐ ┌────────┐  │
│  │ ✨Improve│ │ 📝Expand│ │ 📖Add Cite│ │ 🔍Check│  │
│  └──────────┘ └────────┘ └───────────┘ └────────┘  │
└─────────────────────────────────────────────────────┘
```

**When Paper URL is Detected in Chat**:
```
User: Check out this paper https://arxiv.org/abs/2301.07041
┌─────────────────────────────────────────────────────┐
│  I found a paper reference. Would you like me to:   │
│                                                     │
│  ┌────────────────┐ ┌────────────────┐              │
│  │ 📚 Read Paper  │ │ 📖 Add Citation│              │
│  └────────────────┘ └────────────────┘              │
└─────────────────────────────────────────────────────┘
```

---

### 4. Agent Proactive Suggestions (Priority: Medium)

**The Idea**: Agent notices things and offers help without being asked.

**Examples**:

| Trigger | Suggestion |
|---------|------------|
| Unused citations detected | "I noticed 5 unused citations in your bibliography. /clean-bibliography to remove them." |
| Missing citations in claims | "This paragraph makes claims that might need citations. /suggest-citations to find relevant papers." |
| Long section without structure | "Your Methods section is 2000+ words. Would you like me to suggest subsections?" |
| Inconsistent notation | "I noticed you use both 'Transformer' and 'transformer'. /check-consistency to standardize." |
| After vibe research completes | "Your research session found 3 promising gaps. Would you like to incorporate findings into your paper?" |

**Implementation**: Add a "suggestions" system that runs lightweight analysis when files change.

---

### 5. Capability Modal / Help System (Priority: Low)

**The Idea**: Accessible from toolbar or "?" button, shows all capabilities with examples.

```
┌─────────────────────────────────────────────────────────────┐
│  What Can Aura Do?                                      [×] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐   │
│  │Research │ │  Writing  │ │  LaTeX   │ │ Bibliography  │   │
│  └─────────┘ └───────────┘ └──────────┘ └───────────────┘   │
│                                                             │
│  ══ Research ══                                             │
│                                                             │
│  🔍 Quick Search                                            │
│  "Find papers on transformer attention mechanisms"          │
│  ──────────────────────────────────────────────────         │
│                                                             │
│  🔬 Vibe Research (Deep Exploration)                        │
│  Start an autonomous research session that:                 │
│  • Searches 100+ papers across arXiv & Semantic Scholar     │
│  • Follows citation trails to find seminal work             │
│  • Identifies themes and gaps in the literature             │
│  • Generates novel research hypotheses                      │
│                                                             │
│  Try: /vibe-research "efficient attention for long context" │
│  ──────────────────────────────────────────────────         │
│                                                             │
│  📖 Read & Summarize Papers                                 │
│  "Read arxiv:2301.07041 and summarize the key contributions"│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 6. Toolbar Enhancement (Priority: Medium)

**Current Toolbar**:
```
[Open] [New] [Save] | [▶ Compile] [Sync] | [🧠 Memory] [⚙ Settings]
```

**Proposed Toolbar**:
```
[Open] [New] [Save] | [▶ Compile] [Sync] | [🔬 Research ▾] [🧠 Memory] [⚙ Settings] [?]
```

The **Research** dropdown would show:
```
┌────────────────────────────┐
│ 🔍 Quick Research          │
│ 🔬 Vibe Research           │
│ ─────────────────────────  │
│ 📊 Active Sessions (2)     │
│   • efficient attention    │
│   • multimodal learning    │
└────────────────────────────┘
```

---

### 7. Status Bar Enhancements (Priority: Low)

Add a status bar at the bottom showing:
```
┌────────────────────────────────────────────────────────────────────────┐
│ Ln 42, Col 15 │ LaTeX │ 💡 Tip: Type / for commands │ 🔬 Research: 70% │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Priority

| Phase | Feature | Effort | Impact |
|-------|---------|--------|--------|
| 1 | Slash Command System | Medium | High |
| 1 | Welcome Message | Low | High |
| 2 | Contextual Action Buttons | Medium | Medium |
| 2 | Toolbar Research Dropdown | Low | Medium |
| 3 | Proactive Suggestions | High | High |
| 3 | Capability Modal | Low | Low |
| 4 | Status Bar | Low | Low |

---

## Phase 1 Implementation Plan

### Task 1: Command Registry

Create `app/lib/commands.ts` with:
- Command interface definition
- All slash commands registered
- Command execution logic

### Task 2: Command Palette Component

Create `app/components/CommandPalette.tsx` with:
- Trigger on "/" keystroke in chat input
- Fuzzy search through commands
- Keyboard navigation
- Argument prompts for commands that need them

### Task 3: Integrate with AgentPanel

Modify `app/components/AgentPanel.tsx`:
- Detect "/" input and show CommandPalette
- Handle command execution
- Show welcome message on first open

### Task 4: Backend Command Endpoints

Add endpoints to support commands that need backend interaction:
- `/api/analyze-document` - Document structure analysis
- `/api/suggest-citations` - Find claims needing citations
- `/api/check-consistency` - Terminology/notation check

---

## Mockups

### Slash Command Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ AGENT PANEL                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ [Previous messages...]                                                      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ /vibe█                                                                  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 🔬 /vibe-research [topic]                                               │ │
│ │    Start deep autonomous research session                               │ │
│ │                                                                         │ │
│ │ 📚 /vibe-report [session_id]                                            │ │
│ │    View report from a vibe research session                             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Welcome Message

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ AGENT PANEL                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ ✨ Welcome to your-project                                            │  │
│  │                                                                       │  │
│  │ I'm Aura, your AI research assistant. I can help you:                │  │
│  │                                                                       │  │
│  │ • 📚 Find and summarize academic papers                              │  │
│  │ • 🔬 Run deep literature reviews with Vibe Research                  │  │
│  │ • ✍️  Write, edit, and improve your LaTeX                            │  │
│  │ • 🔧 Fix compilation errors automatically                            │  │
│  │ • 📖 Manage citations and bibliography                               │  │
│  │                                                                       │  │
│  │ Type / for commands, or just describe what you need.                 │  │
│  │                                                                       │  │
│  │ ┌─────────────────┐ ┌──────────────────┐ ┌────────────────┐          │  │
│  │ │ 🔬 Start Vibe   │ │ 📄 Analyze Doc   │ │ ❓ More Help   │          │  │
│  │ │    Research     │ │                  │ │                │          │  │
│  │ └─────────────────┘ └──────────────────┘ └────────────────┘          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Ask me anything...                                                      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Users who discover slash commands | >50% in first session |
| Vibe Research usage | >30% of active users try it |
| Command completion rate | >80% (user follows through after starting) |
| Feature discovery time | <2 minutes to find key features |

---

## Next Steps

1. **Review this design** - Get feedback on priorities and approach
2. **Implement Phase 1** - Slash commands + welcome message
3. **User testing** - Watch real users interact, iterate
4. **Phase 2** - Contextual buttons based on learnings
