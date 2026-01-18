/**
 * Provider Settings
 *
 * Manages model provider configuration (Colorist vs DashScope).
 * Settings are persisted in localStorage.
 */

// =============================================================================
// Types
// =============================================================================

export type ProviderName = 'colorist' | 'dashscope';

export interface DashScopeModel {
  id: string;
  name: string;
}

export interface ProviderSettings {
  provider: ProviderName;
  dashscope?: {
    apiKey: string;
    selectedModel: string;
  };
}

// =============================================================================
// Constants
// =============================================================================

const STORAGE_KEY = 'aura_provider_settings';

export const DASHSCOPE_MODELS: DashScopeModel[] = [
  { id: 'deepseek-v3.2', name: 'DeepSeek V3.2' },
  { id: 'qwen-max-latest', name: 'Qwen Max' },
  { id: 'kimi-k2-thinking', name: 'Kimi K2' },
  { id: 'glm-4.7', name: 'GLM-4.7' },
];

export const DEFAULT_DASHSCOPE_MODEL = 'deepseek-v3.2';

// =============================================================================
// Storage Functions
// =============================================================================

export function getProviderSettings(): ProviderSettings {
  if (typeof window === 'undefined') {
    return { provider: 'colorist' };
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored) as ProviderSettings;
    }
  } catch (e) {
    console.error('Failed to load provider settings:', e);
  }

  return { provider: 'colorist' };
}

export function saveProviderSettings(settings: ProviderSettings): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    // Dispatch custom event for same-tab listeners
    window.dispatchEvent(new CustomEvent('aura-provider-changed'));
  } catch (e) {
    console.error('Failed to save provider settings:', e);
  }
}

// =============================================================================
// Helper Functions
// =============================================================================

export function isDashScopeConfigured(settings: ProviderSettings): boolean {
  return (
    settings.provider === 'dashscope' &&
    !!settings.dashscope?.apiKey &&
    !!settings.dashscope?.selectedModel
  );
}

export function getSelectedModelName(settings: ProviderSettings): string | null {
  if (settings.provider !== 'dashscope' || !settings.dashscope?.selectedModel) {
    return null;
  }

  const model = DASHSCOPE_MODELS.find(m => m.id === settings.dashscope?.selectedModel);
  return model?.name || settings.dashscope.selectedModel;
}

export function getProviderConfigForRequest(settings: ProviderSettings): {
  name: ProviderName;
  model?: string;
  api_key?: string;
} | undefined {
  if (settings.provider === 'colorist') {
    return undefined; // Use default
  }

  if (settings.provider === 'dashscope' && settings.dashscope) {
    return {
      name: 'dashscope',
      model: settings.dashscope.selectedModel,
      api_key: settings.dashscope.apiKey,
    };
  }

  return undefined;
}
