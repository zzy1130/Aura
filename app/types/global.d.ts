/**
 * Global type declarations for Aura
 */

// Aura API exposed from Electron preload
interface AuraAPI {
  // Backend
  getBackendUrl: () => Promise<string>;

  // Projects
  openProject: () => Promise<string | null>;
  newProject: (name: string) => Promise<string | null>;
  getProjectsDir: () => Promise<string>;

  // Platform info
  platform: NodeJS.Platform;
}

// Extend Window interface
declare global {
  interface Window {
    aura?: AuraAPI;
  }
}

export {};
