'use client';

import { useState, useCallback, useEffect } from 'react';
import Toolbar from '@/components/Toolbar';
import FileTree from '@/components/FileTree';
import Editor from '@/components/Editor';
import PDFViewer from '@/components/PDFViewer';
import AgentPanel from '@/components/AgentPanel';
import { api } from '@/lib/api';

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

  // Initialize API client on mount
  useEffect(() => {
    api.init().catch(console.error);
  }, []);

  // =============================================================================
  // File List Fetching
  // =============================================================================

  const fetchFileList = useCallback(async (projectPath: string) => {
    try {
      const projectName = projectPath.split('/').pop() || '';
      const files = await api.getProjectFiles(projectName);

      // Extract paths from file objects (backend returns {name, path, type, size})
      const filePaths = files.map((f) => f.path);

      setProject((prev) => ({
        ...prev,
        files: filePaths,
      }));
    } catch (err) {
      console.error('Failed to fetch file list:', err);
      setError(`Failed to load files: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, []);

  // =============================================================================
  // Project Operations
  // =============================================================================

  const handleOpenProject = useCallback(async () => {
    if (typeof window !== 'undefined' && window.aura) {
      const projectPath = await window.aura.openProject();
      if (projectPath) {
        const name = projectPath.split('/').pop() || 'Project';
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

        // Fetch file list from backend
        await fetchFileList(projectPath);
      }
    }
  }, [fetchFileList]);

  const handleNewProject = useCallback(async () => {
    const name = prompt('Project name:');
    if (name && typeof window !== 'undefined' && window.aura) {
      try {
        // Create project via backend API
        const newProject = await api.createProject(name);

        // Use the IPC path or construct from response
        const projectPath = newProject.path || await window.aura.newProject(name);
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

          // Fetch file list
          await fetchFileList(projectPath);
        }
      } catch (err) {
        console.error('Failed to create project:', err);
        setError(`Failed to create project: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
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

    // Save current file first if dirty
    if (isDirty && project.currentFile) {
      await handleSave();
    }

    setIsCompiling(true);
    setCompileStatus('idle');
    setCompileLog('');

    try {
      const result = await api.compile(project.path, 'main.tex');

      setCompileLog(result.log_output || '');

      if (result.success) {
        setCompileStatus('success');
        // Update PDF URL
        const projectName = project.path.split('/').pop() || '';
        setPdfUrl(api.getPdfUrl(projectName, 'main.pdf'));
      } else {
        setCompileStatus('error');
        setError(result.error_summary || 'Compilation failed');
      }
    } catch (err) {
      console.error('Compilation error:', err);
      setCompileStatus('error');
      setError(`Compilation error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsCompiling(false);
    }
  }, [project.path, project.currentFile, isDirty, handleSave]);

  // =============================================================================
  // Refresh File List
  // =============================================================================

  const handleRefreshFiles = useCallback(async () => {
    if (project.path) {
      await fetchFileList(project.path);
    }
  }, [project.path, fetchFileList]);

  // =============================================================================
  // Render
  // =============================================================================

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Titlebar drag area for macOS */}
      <div className="h-7 bg-aura-bg titlebar-drag" />

      {/* Toolbar */}
      <Toolbar
        projectName={project.name}
        isDirty={isDirty}
        isCompiling={isCompiling}
        compileStatus={compileStatus}
        onOpenProject={handleOpenProject}
        onNewProject={handleNewProject}
        onSave={handleSave}
        onCompile={handleCompile}
      />

      {/* Error Banner */}
      {error && (
        <div className="bg-aura-error/20 border-b border-aura-error px-4 py-2 text-sm text-aura-error flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-aura-error hover:text-aura-text"
          >
            ×
          </button>
        </div>
      )}

      {/* Main Content - 4 Panel Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* File Tree - 200px */}
        <div className="w-[200px] flex-shrink-0 border-r border-aura-border overflow-hidden">
          <FileTree
            projectPath={project.path}
            files={project.files}
            currentFile={project.currentFile}
            onFileSelect={handleFileSelect}
            onRefresh={handleRefreshFiles}
          />
        </div>

        {/* Editor - Flexible */}
        <div className="flex-1 min-w-[300px] border-r border-aura-border overflow-hidden">
          <Editor
            content={editorContent}
            filePath={project.currentFile}
            onChange={handleEditorChange}
            onSave={handleSave}
          />
        </div>

        {/* PDF Viewer - 35% */}
        <div className="w-[35%] min-w-[300px] border-r border-aura-border overflow-hidden">
          <PDFViewer
            pdfUrl={pdfUrl}
            isCompiling={isCompiling}
          />
        </div>

        {/* Agent Panel - 350px */}
        <div className="w-[350px] flex-shrink-0 overflow-hidden">
          <AgentPanel
            projectPath={project.path}
          />
        </div>
      </div>

      {/* Status Bar */}
      <div className="h-6 bg-aura-surface border-t border-aura-border flex items-center px-4 text-xs text-aura-muted">
        <span className="flex-1">
          {project.currentFile || 'No file selected'}
          {isDirty && ' •'}
        </span>
        <span className="mr-4">
          {compileStatus === 'success' && '✓ Compiled'}
          {compileStatus === 'error' && '✗ Error'}
          {isCompiling && '⟳ Compiling...'}
        </span>
        {compileLog && (
          <button
            onClick={() => console.log(compileLog)}
            className="hover:text-aura-text"
            title="View compilation log"
          >
            Log
          </button>
        )}
      </div>
    </div>
  );
}
