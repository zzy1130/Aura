/**
 * Electron Preload Script
 *
 * Exposes safe IPC methods to the renderer process.
 * This is the bridge between Node.js and the browser context.
 */

import { contextBridge, ipcRenderer } from 'electron';

// =============================================================================
// Type Definitions
// =============================================================================

export interface AuraAPI {
  // Backend
  getBackendUrl: () => Promise<string>;

  // Projects
  openProject: () => Promise<string | null>;
  newProject: (name: string) => Promise<string | null>;
  getProjectsDir: () => Promise<string>;

  // File operations
  revealInFinder: (path: string) => Promise<void>;

  // Platform info
  platform: NodeJS.Platform;
}

// =============================================================================
// API Implementation
// =============================================================================

const auraAPI: AuraAPI = {
  // Backend URL
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),

  // Project operations
  openProject: () => ipcRenderer.invoke('open-project'),
  newProject: (name: string) => ipcRenderer.invoke('new-project', name),
  getProjectsDir: () => ipcRenderer.invoke('get-projects-dir'),

  // File operations
  revealInFinder: (path: string) => ipcRenderer.invoke('reveal-in-finder', path),

  // Platform
  platform: process.platform,
};

// =============================================================================
// Expose to Renderer
// =============================================================================

contextBridge.exposeInMainWorld('aura', auraAPI);

// Type augmentation for window.aura
declare global {
  interface Window {
    aura: AuraAPI;
  }
}
