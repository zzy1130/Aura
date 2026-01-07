/**
 * Aura Backend API Client
 *
 * Utilities for interacting with the FastAPI backend.
 */

// =============================================================================
// Types
// =============================================================================

export interface CompileResult {
  success: boolean;
  pdf_path: string | null;
  error_summary: string;
  log_output: string;
}

export interface ProjectFile {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  modified?: string;
}

export interface Project {
  name: string;
  path: string;
  has_overleaf: boolean;
  last_modified: string;
}

// =============================================================================
// API Client
// =============================================================================

class ApiClient {
  private baseUrl: string = 'http://127.0.0.1:8000';
  private initialized: boolean = false;
  private initPromise: Promise<void> | null = null;

  /**
   * Initialize the API client with the backend URL
   */
  async init(): Promise<void> {
    if (this.initialized) return;

    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = (async () => {
      if (typeof window !== 'undefined' && window.aura) {
        try {
          this.baseUrl = await window.aura.getBackendUrl();
          console.log('[API] Initialized with URL:', this.baseUrl);
        } catch (e) {
          console.error('[API] Failed to get backend URL:', e);
        }
      } else {
        console.log('[API] Using default URL:', this.baseUrl);
      }
      this.initialized = true;
    })();

    return this.initPromise;
  }

  /**
   * Ensure API is initialized before making a request
   */
  private async ensureInitialized(): Promise<void> {
    if (!this.initialized) {
      await this.init();
    }
  }

  /**
   * Get the current backend URL
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  // ===========================================================================
  // File Operations
  // ===========================================================================

  /**
   * Read a file from a project
   */
  async readFile(projectPath: string, filename: string): Promise<string> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/files/read`;
    console.log('[API] readFile:', url, { projectPath, filename });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        filename: filename,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.content;
  }

  /**
   * Write a file to a project
   */
  async writeFile(projectPath: string, filename: string, content: string): Promise<void> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/files/write`;
    console.log('[API] writeFile:', url, { projectPath, filename });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        filename: filename,
        content: content,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  }

  /**
   * Get file list for a project
   */
  async getProjectFiles(projectName: string): Promise<ProjectFile[]> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/projects/${encodeURIComponent(projectName)}/files`;
    console.log('[API] getProjectFiles:', url, { projectName });

    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      console.error('[API] getProjectFiles error:', error);
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ===========================================================================
  // Project Operations
  // ===========================================================================

  /**
   * List all projects
   */
  async listProjects(): Promise<Project[]> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/projects`;
    console.log('[API] listProjects:', url);

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Create a new project
   */
  async createProject(name: string, template: string = 'article'): Promise<Project> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/projects`;
    console.log('[API] createProject:', url, { name, template });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, template }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ===========================================================================
  // Compilation
  // ===========================================================================

  /**
   * Compile a LaTeX project
   */
  async compile(projectPath: string, filename: string = 'main.tex'): Promise<CompileResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/compile`;
    console.log('[API] compile:', url, { projectPath, filename });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        filename: filename,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get PDF URL for a project
   */
  getPdfUrl(projectName: string, filename: string = 'main.pdf'): string {
    return `${this.baseUrl}/api/pdf/${encodeURIComponent(projectName)}?filename=${encodeURIComponent(filename)}`;
  }

  /**
   * Check LaTeX syntax without full compilation
   */
  async checkSyntax(projectPath: string, filename: string = 'main.tex'): Promise<CompileResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/check-syntax`;
    console.log('[API] checkSyntax:', url, { projectPath, filename });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        filename: filename,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ===========================================================================
  // Health Check
  // ===========================================================================

  /**
   * Check if the backend is healthy
   */
  async healthCheck(): Promise<boolean> {
    await this.ensureInitialized();

    try {
      const response = await fetch(`${this.baseUrl}/api/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}

// Singleton instance
export const api = new ApiClient();

// Initialize on import (async) - but callers should await ensureInitialized
if (typeof window !== 'undefined') {
  api.init().catch(console.error);
}
