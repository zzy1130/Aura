'use client';

import { useState, useCallback } from 'react';
import Toolbar from '@/components/Toolbar';
import FileTree from '@/components/FileTree';
import Editor from '@/components/Editor';
import PDFViewer from '@/components/PDFViewer';
import AgentPanel from '@/components/AgentPanel';

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
  const [pdfUrl, _setPdfUrl] = useState<string | null>(null);

  // Compilation state
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileStatus, setCompileStatus] = useState<'idle' | 'success' | 'error'>('idle');

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
        // TODO: Fetch file list from backend
      }
    }
  }, []);

  const handleNewProject = useCallback(async () => {
    const name = prompt('Project name:');
    if (name && typeof window !== 'undefined' && window.aura) {
      const projectPath = await window.aura.newProject(name);
      if (projectPath) {
        setProject({
          path: projectPath,
          name,
          currentFile: null,
          files: [],
        });
      }
    }
  }, []);

  // =============================================================================
  // File Operations
  // =============================================================================

  const handleFileSelect = useCallback(async (filePath: string) => {
    setProject((prev) => ({ ...prev, currentFile: filePath }));
    // TODO: Fetch file content from backend
    setEditorContent(`% ${filePath}\n% Loading...`);
    setIsDirty(false);
  }, []);

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (value !== undefined) {
      setEditorContent(value);
      setIsDirty(true);
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!project.path || !project.currentFile) return;
    // TODO: Save file via backend
    console.log('Saving file:', project.currentFile);
    setIsDirty(false);
  }, [project.path, project.currentFile]);

  // =============================================================================
  // Compilation
  // =============================================================================

  const handleCompile = useCallback(async () => {
    if (!project.path) return;

    setIsCompiling(true);
    setCompileStatus('idle');

    try {
      // TODO: Call backend compile endpoint
      console.log('Compiling project:', project.path);

      // Simulate compilation
      await new Promise((r) => setTimeout(r, 2000));

      setCompileStatus('success');
      // setPdfUrl(`${backendUrl}/api/projects/${project.path}/output.pdf`);
    } catch (error) {
      console.error('Compilation error:', error);
      setCompileStatus('error');
    } finally {
      setIsCompiling(false);
    }
  }, [project.path]);

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

      {/* Main Content - 4 Panel Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* File Tree - 200px */}
        <div className="w-[200px] flex-shrink-0 border-r border-aura-border overflow-hidden">
          <FileTree
            projectPath={project.path}
            files={project.files}
            currentFile={project.currentFile}
            onFileSelect={handleFileSelect}
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

        {/* PDF Viewer - 40% */}
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
        </span>
        <span>
          {compileStatus === 'success' && '✓ Compiled'}
          {compileStatus === 'error' && '✗ Error'}
        </span>
      </div>
    </div>
  );
}
