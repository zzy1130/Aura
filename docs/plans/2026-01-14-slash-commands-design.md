# Slash Commands Design

> **Status**: Approved
> **Date**: 2026-01-14

## Overview

Slash commands make Aura's capabilities discoverable through a familiar `/command` pattern. Users type `/` in the chat input to see available commands.

## Design Decisions

| Aspect | Choice |
|--------|--------|
| Execution Model | Hybrid - agent commands + direct API calls |
| UI Pattern | Inline dropdown below input (Discord/Slack style) |
| Scope | 8 core commands |
| Arguments | Inline after command |

## Commands

| Command | Type | Action |
|---------|------|--------|
| `/research [topic]` | agent | "Search for papers on: {topic}" |
| `/vibe [topic]` | api | Start vibe session, switch to vibe mode |
| `/analyze` | agent | "Analyze the document structure" |
| `/fix` | agent | "Fix the LaTeX compilation errors" |
| `/cite [ref]` | agent | "Add citation for: {ref}" |
| `/compile` | api | Call api.compile(), show result |
| `/sync` | api | Call api.syncProject(), show result |
| `/clean-bib` | agent | "Clean the bibliography" |

## Architecture

### Command Registry

```typescript
// app/lib/commands.ts

interface SlashCommand {
  name: string;
  description: string;
  icon: string;
  category: 'research' | 'writing' | 'project';
  requiresArg: boolean;
  argPlaceholder?: string;
  executionType: 'agent' | 'api';
  toAgentMessage?: (arg: string) => string;
  execute?: (ctx: CommandContext) => Promise<CommandResult>;
}

interface CommandContext {
  projectPath: string;
  argument: string;
  api: ApiClient;
}

interface CommandResult {
  success: boolean;
  message?: string;
  switchMode?: 'chat' | 'vibe';
}
```

### UI Behavior

1. **Trigger**: Dropdown appears when input starts with `/`
2. **Filtering**: As user types `/res`, filter to matching commands
3. **Keyboard nav**: ↑↓ to navigate, Enter to select, Escape to close
4. **Selection**: Inserts command into input (e.g., `/research `)
5. **Execution**: On Enter with complete command, execute it
6. **Empty arg handling**: If command requires arg but none given, prompt user

### Component Structure

```
app/
├── lib/
│   └── commands.ts          # Command registry
└── components/
    ├── CommandPalette.tsx   # Dropdown UI
    └── AgentPanel.tsx       # Integration
```

### Execution Flow

```
User types "/research transformers" + Enter
         │
         ▼
┌─────────────────────────────┐
│ Parse: cmd="research"       │
│        arg="transformers"   │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ cmd.executionType == 'agent'│
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ toAgentMessage(arg)         │
│ = "Search for papers on:    │
│    transformers"            │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ sendMessage(message)        │
│ → /api/chat/stream          │
└─────────────────────────────┘
```

## Implementation Plan

1. Create `app/lib/commands.ts` - command definitions
2. Create `app/components/CommandPalette.tsx` - dropdown UI
3. Modify `app/components/AgentPanel.tsx` - integration

No backend changes required.
