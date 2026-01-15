'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import Toolbar from '@/components/Toolbar';
import FileTree from '@/components/FileTree';
import Editor, { PendingEdit, SendToAgentAction } from '@/components/Editor';
import PDFViewer from '@/components/PDFViewer';
import AgentPanel from '@/components/AgentPanel';
import NewProjectModal from '@/components/NewProjectModal';
import SettingsModal from '@/components/SettingsModal';
import MemoryModal from '@/components/MemoryModal';
import DockerGuide from '@/components/DockerGuide';
import ResizeHandle from '@/components/ResizeHandle';
import { api, SyncStatus } from '@/lib/api';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface ProjectState {
  path: string | null;
  name: string;
  currentFile: string | null;
  files: string[];
}

// =============================================================================
// Main Page
// =============================================================================

export default function Home() {
  // Project state
  const [project, setProject] = useState<ProjectState>({
    path: null,
    name: 'No Project Open',
    currentFile: null,
    files: [],
  });

  // Editor state
  const [editorContent, setEditorContent] = useState<string>('');
  const [isDirty, setIsDirty] = useState(false);

  // PDF state
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  // Compilation state
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileStatus, setCompileStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [compileLog, setCompileLog] = useState<string>('');

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [showDockerGuide, setShowDockerGuide] = useState(false);
  const [dockerIsInstalled, setDockerIsInstalled] = useState(false);

  // Sync state
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus['status'] | null>(null);

  // Pending edit state (for HITL approval in Editor)
  const [pendingEdit, setPendingEdit] = useState<PendingEdit | null>(null);

  // Quoted text state (for sending selected text to agent)
  const [quotedText, setQuotedText] = useState<string | null>(null);
  const [quotedAction, setQuotedAction] = useState<SendToAgentAction | null>(null);

  // Panel layout state
  const [fileTreeWidth, setFileTreeWidth] = useState(200);
  const [pdfViewerWidth, setPdfViewerWidth] = useState(400);
  const [agentPanelWidth, setAgentPanelWidth] = useState(350);
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // Panel resize constraints
  const MIN_FILE_TREE = 150;
  const MAX_FILE_TREE = 400;
  const MIN_PDF_VIEWER = 300;
  const MIN_AGENT_PANEL = 280;
  const MAX_AGENT_PANEL = 600;

  // Initialize API client on mount
  useEffect(() => {
    api.init().catch(console.error);
  }, []);

  // Load sync status when project changes
  const loadSyncStatus = useCallback(async () => {
    if (!project.path) {
      setSyncStatus(null);
      return;
    }
    try {
      const status = await api.getSyncStatus(project.path);
      setSyncStatus(status.status);
    } catch (e) {
      console.error('Failed to load sync status:', e);
      setSyncStatus(null);
    }
  }, [project.path]);

  useEffect(() => {
    loadSyncStatus();
  }, [loadSyncStatus]);

  // Compile keyboard shortcut ref (to access handleCompile in useEffect)
  const handleCompileRef = useRef<() => void>(() => {});

  // =============================================================================
  // File List Fetching
  // =============================================================================

  const fetchFileList = useCallback(async (projectPath: string) => {
    try {
      console.log('[Page] Fetching files for path:', projectPath);
      const files = await api.listFiles(projectPath);

      // Extract paths from file objects (backend returns {name, path, type, size})
      const filePaths = files.map((f) => f.path);

      setProject((prev) => ({
        ...prev,
        files: filePaths,
      }));
      setError(null);
    } catch (err) {
      console.error('Failed to fetch file list:', err);
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load files: ${errorMsg}`);
    }
  }, []);

  // =============================================================================
  // Project Operations
  // =============================================================================

  const handleOpenProject = useCallback(async () => {
    if (typeof window !== 'undefined' && window.aura) {
      const projectPath = await window.aura.openProject();
      console.log('[Page] Open project path:', projectPath);

      if (projectPath) {
        // Extract project name - filter out empty strings to handle trailing slashes
        const pathParts = projectPath.split('/').filter((p: string) => p.length > 0);
        const name = pathParts[pathParts.length - 1] || 'Project';
        console.log('[Page] Extracted project name:', name);

        setProject({
          path: projectPath,
          name,
          currentFile: null,
          files: [],
        });
        setEditorContent('');
        setIsDirty(false);
        setPdfUrl(null);
        setCompileStatus('idle');
        setError(null);
        setPendingEdit(null);

        // Fetch file list using full path
        await fetchFileList(projectPath);
      }
    }
  }, [fetchFileList]);

  const handleNewProject = useCallback(() => {
    setIsNewProjectModalOpen(true);
  }, []);

  const handleCreateProject = useCallback(async (name: string) => {
    try {
      // First, open folder picker to choose location
      if (!window.aura) {
        throw new Error('Electron API not available');
      }
      const selectedPath = await window.aura.newProject(name);

      if (!selectedPath) {
        // User cancelled the folder picker
        return;
      }

      // Create project at selected path (empty, no template)
      const newProject = await api.createProject(name, selectedPath);

      // Use the path from the response
      const projectPath = newProject.path;
      if (projectPath) {
        setProject({
          path: projectPath,
          name,
          currentFile: null,
          files: [],
        });
        setEditorContent('');
        setIsDirty(false);
        setPdfUrl(null);
        setCompileStatus('idle');
        setError(null);
        setPendingEdit(null);

        // Fetch file list using full path
        await fetchFileList(projectPath);
      }
    } catch (err) {
      console.error('Failed to create project:', err);
      setError(`Failed to create project: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [fetchFileList]);

  // =============================================================================
  // File Operations
  // =============================================================================

  const handleFileSelect = useCallback(async (filePath: string) => {
    if (!project.path) return;

    setProject((prev) => ({ ...prev, currentFile: filePath }));
    setEditorContent('');

    try {
      const content = await api.readFile(project.path, filePath);
      setEditorContent(content);
      setIsDirty(false);
      setError(null);
    } catch (err) {
      console.error('Failed to read file:', err);
      setEditorContent(`% Error loading ${filePath}\n% ${err instanceof Error ? err.message : 'Unknown error'}`);
      setError(`Failed to load file: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [project.path]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (value !== undefined) {
      setEditorContent(value);
      setIsDirty(true);
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!project.path || !project.currentFile) return;

    try {
      await api.writeFile(project.path, project.currentFile, editorContent);
      setIsDirty(false);
      setError(null);
    } catch (err) {
      console.error('Failed to save file:', err);
      setError(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [project.path, project.currentFile, editorContent]);

  // =============================================================================
  // Compilation
  // =============================================================================

  const handleCompile = useCallback(async () => {
    if (!project.path) return;

    // Determine which file to compile
    let fileToCompile = project.currentFile;

    // If current file is not a .tex file, try to find main.tex or any .tex file
    if (!fileToCompile || !fileToCompile.endsWith('.tex')) {
      const texFiles = project.files.filter(f => f.endsWith('.tex'));
      if (texFiles.includes('main.tex')) {
        fileToCompile = 'main.tex';
      } else if (texFiles.length > 0) {
        fileToCompile = texFiles[0];
      } else {
        setError('No .tex file found to compile');
        return;
      }
    }

    // Save current file first if dirty
    if (isDirty && project.currentFile) {
      await handleSave();
    }

    setIsCompiling(true);
    setCompileStatus('idle');
    setCompileLog('');

    try {
      const result = await api.compile(project.path, fileToCompile);

      setCompileLog(result.log_output || '');

      if (result.success) {
        setCompileStatus('success');
        // Fetch PDF as blob and create object URL
        const pdfName = fileToCompile.replace(/\.tex$/, '.pdf');
        try {
          const pdfBlob = await api.fetchPdfBlob(project.path, pdfName);
          // Revoke old URL to prevent memory leaks
          if (pdfUrl) {
            URL.revokeObjectURL(pdfUrl);
          }
          const newPdfUrl = URL.createObjectURL(pdfBlob);
          setPdfUrl(newPdfUrl);
        } catch (pdfErr) {
          console.error('Failed to load PDF:', pdfErr);
          setError(`Compilation succeeded but failed to load PDF: ${pdfErr instanceof Error ? pdfErr.message : 'Unknown error'}`);
        }
      } else {
        setCompileStatus('error');
        // Check if Docker is not available
        if (result.docker_not_available) {
          // Determine if Docker is installed but not running
          const isInstalled = result.error_summary.includes('not running');
          setDockerIsInstalled(isInstalled);
          setShowDockerGuide(true);
        } else {
          setError(result.error_summary || 'Compilation failed');
        }
      }
    } catch (err) {
      console.error('Compilation error:', err);
      setCompileStatus('error');
      setError(`Compilation error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsCompiling(false);
    }
  }, [project.path, project.currentFile, project.files, isDirty, handleSave, pdfUrl]);

  // Keep handleCompileRef in sync and set up global keyboard shortcut
  useEffect(() => {
    handleCompileRef.current = handleCompile;
  }, [handleCompile]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // ⌘B or Ctrl+B to compile
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        handleCompileRef.current();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // =============================================================================
  // Refresh File List
  // =============================================================================

  const handleRefreshFiles = useCallback(async () => {
    if (project.path) {
      await fetchFileList(project.path);
    }
  }, [project.path, fetchFileList]);

  // =============================================================================
  // Sync Handlers
  // =============================================================================

  const handleSync = useCallback(async () => {
    if (!project.path) return;

    setIsSyncing(true);
    setError(null);

    try {
      // Save any unsaved changes first
      if (isDirty && project.currentFile) {
        await handleSave();
      }

      const result = await api.syncProject(project.path);

      if (result.success) {
        // Refresh file list after sync
        await fetchFileList(project.path);
        // Reload sync status
        await loadSyncStatus();
        // Show success message briefly
        setError(null);
      } else {
        setError(result.message);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed');
    } finally {
      setIsSyncing(false);
    }
  }, [project.path, project.currentFile, isDirty, handleSave, fetchFileList, loadSyncStatus]);

  const handleOpenSettings = useCallback(() => {
    setIsSettingsModalOpen(true);
  }, []);

  const handleCloseSettings = useCallback(() => {
    setIsSettingsModalOpen(false);
  }, []);

  const handleSyncSetup = useCallback(() => {
    // Refresh sync status after setup
    loadSyncStatus();
  }, [loadSyncStatus]);

  // =============================================================================
  // HITL Approval Handlers
  // =============================================================================

  const handleApprovalRequest = useCallback((edit: PendingEdit) => {
    console.log('[Page] Approval request received:', edit);
    console.log('[Page] Setting pendingEdit - old_string length:', edit.old_string?.length);
    console.log('[Page] Setting pendingEdit - new_string length:', edit.new_string?.length);
    setPendingEdit(edit);

    // If the edit is for a different file, switch to it
    if (project.path && edit.filepath) {
      const editFilename = edit.filepath.split('/').pop();
      const currentFilename = project.currentFile?.split('/').pop();

      if (editFilename !== currentFilename) {
        // Load the file being edited
        handleFileSelect(edit.filepath);
      }
    }
  }, [project.path, project.currentFile, handleFileSelect]);

  const handleApproveEdit = useCallback(async (requestId: string) => {
    console.log('[Page] Approving edit:', requestId);

    try {
      let backendUrl = 'http://127.0.0.1:8000';
      if (typeof window !== 'undefined' && window.aura) {
        backendUrl = await window.aura.getBackendUrl();
      }

      await fetch(`${backendUrl}/api/hitl/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId }),
      });

      setPendingEdit(null);

      // Reload the file to show the changes, then auto-compile
      if (project.path && project.currentFile) {
        setTimeout(async () => {
          await handleFileSelect(project.currentFile!);
          // Auto-compile after edit is applied
          setTimeout(() => {
            console.log('[Page] Auto-compiling after edit...');
            handleCompile();
          }, 300);
        }, 500);
      }
    } catch (error) {
      console.error('Failed to approve:', error);
      setError(`Failed to approve edit: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [project.path, project.currentFile, handleFileSelect, handleCompile]);

  const handleRejectEdit = useCallback(async (requestId: string) => {
    console.log('[Page] Rejecting edit:', requestId);

    try {
      let backendUrl = 'http://127.0.0.1:8000';
      if (typeof window !== 'undefined' && window.aura) {
        backendUrl = await window.aura.getBackendUrl();
      }

      await fetch(`${backendUrl}/api/hitl/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: requestId,
          reason: 'User rejected',
        }),
      });

      setPendingEdit(null);
    } catch (error) {
      console.error('Failed to reject:', error);
      setError(`Failed to reject edit: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, []);

  const handleApprovalResolved = useCallback(() => {
    setPendingEdit(null);
  }, []);

  // =============================================================================
  // Send to Agent Handler (from Editor context menu)
  // =============================================================================

  const handleSendToAgent = useCallback((text: string, action: SendToAgentAction) => {
    setQuotedText(text);
    setQuotedAction(action);
    // Open agent panel if closed
    if (!isAgentPanelOpen) {
      setIsAgentPanelOpen(true);
    }
  }, [isAgentPanelOpen]);

  const handleClearQuote = useCallback(() => {
    setQuotedText(null);
    setQuotedAction(null);
  }, []);

  // =============================================================================
  // Panel Resize Handlers
  // =============================================================================

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((prev) => Math.max(MIN_FILE_TREE, Math.min(MAX_FILE_TREE, prev + delta)));
  }, []);

  const handlePdfViewerResize = useCallback((delta: number) => {
    setPdfViewerWidth((prev) => Math.max(MIN_PDF_VIEWER, prev - delta));
  }, []);

  const handleAgentPanelResize = useCallback((delta: number) => {
    setAgentPanelWidth((prev) => Math.max(MIN_AGENT_PANEL, Math.min(MAX_AGENT_PANEL, prev - delta)));
  }, []);

  const toggleAgentPanel = useCallback(() => {
    setIsAgentPanelOpen((prev) => !prev);
  }, []);

  // =============================================================================
  // Render
  // =============================================================================

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-fill-secondary">
      {/* Titlebar drag area for macOS */}
      <div className="h-7 bg-sidebar-bg titlebar-drag border-b border-black/6" />

      {/* Toolbar */}
      <Toolbar
        projectName={project.name}
        projectPath={project.path}
        isDirty={isDirty}
        isCompiling={isCompiling}
        compileStatus={compileStatus}
        isSyncing={isSyncing}
        syncStatus={syncStatus}
        onOpenProject={handleOpenProject}
        onNewProject={handleNewProject}
        onSave={handleSave}
        onCompile={handleCompile}
        onSync={handleSync}
        onSettings={handleOpenSettings}
        onMemory={() => setShowMemory(true)}
      />

      {/* Error Banner */}
      {error && (
        <div className="bg-error/10 border-b border-error/20 px-4 py-2.5 flex items-center justify-between animate-fade-in-down">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-error" />
            <span className="typo-small text-error">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-error/10 transition-colors"
          >
            <span className="text-error text-lg leading-none">×</span>
          </button>
        </div>
      )}

      {/* Main Content - 4 Panel Layout */}
      <div ref={containerRef} className="flex-1 flex overflow-hidden relative">
        {/* File Tree */}
        <div
          style={{ width: fileTreeWidth }}
          className="flex-shrink-0 overflow-hidden bg-sidebar-bg"
        >
          <FileTree
            projectPath={project.path}
            files={project.files}
            currentFile={project.currentFile}
            onFileSelect={handleFileSelect}
            onRefresh={handleRefreshFiles}
          />
        </div>

        {/* Resize Handle: File Tree | Editor */}
        <ResizeHandle onResize={handleFileTreeResize} />

        {/* Editor - Flexible */}
        <div className="flex-1 min-w-[300px] overflow-hidden">
          <Editor
            content={editorContent}
            filePath={project.currentFile}
            onChange={handleEditorChange}
            onSave={handleSave}
            pendingEdit={pendingEdit}
            onApproveEdit={handleApproveEdit}
            onRejectEdit={handleRejectEdit}
            onSendToAgent={handleSendToAgent}
          />
        </div>

        {/* Resize Handle: Editor | PDF Viewer */}
        <ResizeHandle onResize={handlePdfViewerResize} />

        {/* PDF Viewer */}
        <div
          style={{ width: pdfViewerWidth }}
          className="flex-shrink-0 overflow-hidden"
        >
          <PDFViewer
            pdfUrl={pdfUrl}
            isCompiling={isCompiling}
          />
        </div>

        {/* Resize Handle: PDF Viewer | Agent Panel (only if open) */}
        {isAgentPanelOpen && (
          <ResizeHandle onResize={handleAgentPanelResize} />
        )}

        {/* Agent Panel (Collapsible) */}
        <div
          style={{ width: isAgentPanelOpen ? agentPanelWidth : 0 }}
          className={`flex-shrink-0 overflow-hidden transition-all duration-300 ${
            isAgentPanelOpen ? 'opacity-100' : 'opacity-0 w-0'
          }`}
        >
          <AgentPanel
            projectPath={project.path}
            onApprovalRequest={handleApprovalRequest}
            onApprovalResolved={handleApprovalResolved}
            onOpenFile={handleFileSelect}
            quotedText={quotedText}
            quotedAction={quotedAction}
            onClearQuote={handleClearQuote}
          />
        </div>

        {/* Toggle Button for Agent Panel */}
        <button
          onClick={toggleAgentPanel}
          style={{ right: isAgentPanelOpen ? agentPanelWidth + 8 : 8 }}
          className={`absolute z-10 top-14 flex h-8 w-8 items-center justify-center rounded-yw-lg shadow-card transition-all duration-300 ${
            isAgentPanelOpen
              ? 'bg-white border border-black/6 hover:bg-black/3'
              : 'bg-green1 hover:opacity-90'
          }`}
          title={isAgentPanelOpen ? 'Close AI Panel' : 'Open AI Panel'}
        >
          {isAgentPanelOpen ? (
            <PanelRightClose size={16} className="text-secondary" />
          ) : (
            <PanelRightOpen size={16} className="text-white" />
          )}
        </button>
      </div>

      {/* Status Bar */}
      <div className="h-7 bg-white border-t border-black/6 flex items-center px-4 gap-4">
        <span className="flex-1 typo-small text-secondary truncate">
          {project.currentFile || 'No file selected'}
          {isDirty && <span className="text-warn ml-1">•</span>}
        </span>
        {pendingEdit && (
          <span className="badge badge-warning">
            Pending approval
          </span>
        )}
        <span className="typo-small">
          {compileStatus === 'success' && (
            <span className="text-success flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              Compiled
            </span>
          )}
          {compileStatus === 'error' && (
            <span className="text-error flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-error" />
              Error
            </span>
          )}
          {isCompiling && (
            <span className="text-secondary flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
              Compiling...
            </span>
          )}
        </span>
        {compileLog && (
          <button
            onClick={() => console.log(compileLog)}
            className="typo-small text-link hover:underline"
            title="View compilation log"
          >
            View Log
          </button>
        )}
      </div>

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onSubmit={handleCreateProject}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={handleCloseSettings}
        projectPath={project.path}
        onSyncSetup={handleSyncSetup}
      />

      {/* Memory Modal */}
      <MemoryModal
        isOpen={showMemory}
        onClose={() => setShowMemory(false)}
        projectPath={project.path}
      />

      {/* Docker Installation Guide */}
      <DockerGuide
        isOpen={showDockerGuide}
        onClose={() => setShowDockerGuide(false)}
        isInstalled={dockerIsInstalled}
      />
    </div>
  );
}
