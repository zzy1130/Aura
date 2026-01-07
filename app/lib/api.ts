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

  /**
   * Initialize the API client with the backend URL
   */
  async init(): Promise<void> {
    if (typeof window !== 'undefined' && window.aura) {
      this.baseUrl = await window.aura.getBackendUrl();
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
    const response = await fetch(`${this.baseUrl}/api/files/read`, {
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
    const response = await fetch(`${this.baseUrl}/api/files/write`, {
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
    const response = await fetch(`${this.baseUrl}/api/projects/${projectName}/files`);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
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
    const response = await fetch(`${this.baseUrl}/api/projects`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Create a new project
   */
  async createProject(name: string, template: string = 'article'): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/api/projects`, {
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
    const response = await fetch(`${this.baseUrl}/api/compile`, {
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
    return `${this.baseUrl}/api/pdf/${projectName}?filename=${encodeURIComponent(filename)}`;
  }

  /**
   * Check LaTeX syntax without full compilation
   */
  async checkSyntax(projectPath: string, filename: string = 'main.tex'): Promise<CompileResult> {
    const response = await fetch(`${this.baseUrl}/api/check-syntax`, {
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

// Initialize on import (async)
if (typeof window !== 'undefined') {
  api.init().catch(console.error);
}
