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

export interface SyncStatus {
  status: 'not_initialized' | 'clean' | 'local_changes' | 'ahead' | 'behind' | 'diverged' | 'conflict' | 'error';
  is_git_repo: boolean;
  has_remote: boolean;
  remote_url: string | null;
  branch: string;
  commits_ahead: number;
  commits_behind: number;
  uncommitted_files: string[];
  last_sync: string | null;
  error_message: string | null;
}

export interface SyncResult {
  success: boolean;
  operation: 'pull' | 'push' | 'sync' | 'setup' | 'resolve' | 'abort';
  message: string;
  files_changed: string[];
  conflicts: string[];
}

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
   * Get file list for a project by name (only works for ~/aura-projects/)
   * @deprecated Use listFiles() instead for arbitrary paths
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

  /**
   * List files in any directory (works with any path)
   */
  async listFiles(projectPath: string): Promise<ProjectFile[]> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/files/list`;
    console.log('[API] listFiles:', url, { projectPath });

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      console.error('[API] listFiles error:', error);
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
   * Get PDF URL for a project in ~/aura-projects/ (legacy)
   * @deprecated Use getPdfUrlForPath() for projects outside ~/aura-projects/
   */
  getPdfUrl(projectName: string, filename: string = 'main.pdf'): string {
    return `${this.baseUrl}/api/pdf/${encodeURIComponent(projectName)}?filename=${encodeURIComponent(filename)}`;
  }

  /**
   * Get PDF URL for any project path
   * Note: This returns a URL that requires POST, so we need to handle it differently
   */
  async fetchPdfBlob(projectPath: string, filename: string = 'main.pdf'): Promise<Blob> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/pdf/serve`;
    console.log('[API] fetchPdfBlob:', url, { projectPath, filename });

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

    return response.blob();
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
  // Git/Overleaf Sync
  // ===========================================================================

  /**
   * Get sync status for a project
   */
  async getSyncStatus(projectPath: string): Promise<SyncStatus> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/sync/status`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Set up Overleaf sync for a project
   */
  async setupSync(
    projectPath: string,
    overleafUrl: string,
    username?: string,
    password?: string,
  ): Promise<SyncResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/sync/setup`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        overleaf_url: overleafUrl,
        username,
        password,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Sync project with Overleaf (pull then push)
   */
  async syncProject(projectPath: string, commitMessage?: string): Promise<SyncResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/sync`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        commit_message: commitMessage,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Pull changes from Overleaf
   */
  async pullFromOverleaf(projectPath: string): Promise<SyncResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/sync/pull`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Push changes to Overleaf
   */
  async pushToOverleaf(projectPath: string, commitMessage?: string): Promise<SyncResult> {
    await this.ensureInitialized();

    const url = `${this.baseUrl}/api/sync/push`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: projectPath,
        commit_message: commitMessage,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

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
