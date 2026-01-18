# Multi-Provider Model Support Design

**Date:** 2026-01-18
**Status:** Approved

## Overview

Add support for alternative model providers beyond Colorist, specifically DashScope (阿里云百炼) for users in China who need access to Chinese models with Alipay payment.

## Requirements

1. **Provider Selection in Settings**: Users can switch between Colorist (default) and DashScope
2. **API Key Management**: DashScope requires user-provided API key
3. **Model Selection**: When DashScope is active, show model selector dropdown in Agent Panel
4. **Backward Compatible**: Colorist remains default, no changes for existing users

## Provider Details

### Colorist (Default)
- **Use case**: Default for non-China users
- **API**: Anthropic-compatible via gateway
- **Model**: Fixed (`claude-4-5-sonnet-by-all`)
- **No model selector UI**

### DashScope (阿里云百炼)
- **Use case**: China users with Alipay payment
- **Base URL**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **API Style**: OpenAI-compatible
- **Payment**: Alipay via Aliyun account

## DashScope Models

| Model ID | Display Name | Provider |
|----------|--------------|----------|
| `deepseek-v3.2` | DeepSeek V3.2 | DeepSeek |
| `qwen-max-latest` | Qwen Max | Alibaba |
| `kimi-k2-thinking` | Kimi K2 | Moonshot |
| `glm-4.7` | GLM-4.7 | Zhipu |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        App Settings                              │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ Provider:  ○ Colorist (default)    ● DashScope              ││
│  │                                                              ││
│  │ [DashScope only]                                             ││
│  │ API Key: [sk-xxxxxxxxxxxxx]                                  ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Agent Panel Header                           │
│                                                                  │
│  Colorist mode:                                                  │
│  ┌─────────────────┐                                            │
│  │ Chat │ Vibe     │   (no model selector)                      │
│  └─────────────────┘                                            │
│                                                                  │
│  DashScope mode:                                                 │
│  ┌─────────────────┐  ┌───────────────────────┐                 │
│  │ Chat │ Vibe     │  │ DeepSeek V3.2 ▼      │                 │
│  └─────────────────┘  └───────────────────────┘                 │
│                        ├─ DeepSeek V3.2    ✓ │                  │
│                        ├─ Qwen Max           │                  │
│                        ├─ Kimi K2            │                  │
│                        ├─ GLM-4.7            │                  │
│                        └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Model

### Frontend Settings (Electron Store)

```typescript
interface ProviderSettings {
  provider: 'colorist' | 'dashscope';
  dashscope?: {
    apiKey: string;
    selectedModel: string;  // e.g., "deepseek-v3.2"
  };
}
```

### Registered DashScope Models

```typescript
const DASHSCOPE_MODELS = [
  { id: 'deepseek-v3.2', name: 'DeepSeek V3.2' },
  { id: 'qwen-max-latest', name: 'Qwen Max' },
  { id: 'kimi-k2-thinking', name: 'Kimi K2' },
  { id: 'glm-4.7', name: 'GLM-4.7' },
];
```

## Backend Changes

### New File: `backend/agent/providers/dashscope.py`

```python
"""DashScope Provider for PydanticAI (阿里云百炼)"""

from pydantic_ai.providers.openai import OpenAIProvider

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

def dashscope_provider(api_key: str) -> OpenAIProvider:
    """Create DashScope provider using OpenAI-compatible API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DASHSCOPE_BASE_URL,
    )
    return OpenAIProvider(openai_client=client)
```

### Modified: `backend/agent/providers/colorist.py`

Add unified model getter:

```python
def get_model(
    provider: str = "colorist",
    model_id: str | None = None,
    api_key: str | None = None,
) -> Model:
    """Get model based on provider selection."""
    if provider == "colorist":
        return infer_model()  # existing behavior
    elif provider == "dashscope":
        from agent.providers.dashscope import dashscope_provider
        provider_instance = dashscope_provider(api_key)
        return infer_model(f"openai:{model_id}", lambda _: provider_instance)
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

## API Changes

### Modified Request: `/api/chat/stream`

```typescript
// Request body
{
  message: string;
  project_path: string;
  session_id?: string;
  history: Message[];
  provider?: {
    name: 'colorist' | 'dashscope';
    model?: string;      // e.g., "deepseek-v3.2"
    api_key?: string;    // DashScope API key
  };
}
```

Backward compatible: if `provider` is missing, defaults to Colorist.

## Frontend Changes

### 1. Settings Modal (`SettingsModal.tsx`)

Add provider selection section with:
- Radio buttons: Colorist / DashScope
- Conditional API key input for DashScope
- Persist to Electron store

### 2. New Component: `ModelSelector.tsx`

Dropdown component for model selection:
- Shows current model name
- Dropdown list of available models
- Checkmark on selected model
- Only rendered when DashScope is active

### 3. Agent Panel Header (`AgentPanel.tsx`)

Add model selector to header:
- Positioned after mode toggle, aligned right
- Only visible when `provider === 'dashscope'`

### 4. Provider Context

Create React context to share provider settings across components:
- Load from Electron store on mount
- Provide to AgentPanel and Settings
- Persist changes back to store

## File Changes Summary

| File | Change |
|------|--------|
| `backend/agent/providers/dashscope.py` | New - DashScope provider |
| `backend/agent/providers/colorist.py` | Add `get_model()` unified function |
| `backend/main.py` | Update `/api/chat/stream` to accept provider config |
| `app/components/ModelSelector.tsx` | New - Model dropdown component |
| `app/components/SettingsModal.tsx` | Add provider selection section |
| `app/components/AgentPanel.tsx` | Add model selector to header |
| `app/lib/providerSettings.ts` | New - Provider settings types and storage |
| `app/contexts/ProviderContext.tsx` | New - React context for provider state |

## Implementation Order

1. Backend: Create `dashscope.py` provider
2. Backend: Add `get_model()` to `colorist.py`
3. Backend: Update `/api/chat/stream` endpoint
4. Frontend: Create provider settings types and storage
5. Frontend: Add provider section to Settings modal
6. Frontend: Create ModelSelector component
7. Frontend: Integrate into AgentPanel header
8. Testing: Verify both providers work end-to-end
