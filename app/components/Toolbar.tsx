'use client';

import {
  FolderOpen,
  FilePlus,
  Save,
  Play,
  RefreshCw,
  Settings,
  Loader2,
  Check,
  X,
} from 'lucide-react';

interface ToolbarProps {
  projectName: string;
  isDirty: boolean;
  isCompiling: boolean;
  compileStatus: 'idle' | 'success' | 'error';
  onOpenProject: () => void;
  onNewProject: () => void;
  onSave: () => void;
  onCompile: () => void;
}

export default function Toolbar({
  projectName,
  isDirty,
  isCompiling,
  compileStatus,
  onOpenProject,
  onNewProject,
  onSave,
  onCompile,
}: ToolbarProps) {
  return (
    <div className="h-10 bg-aura-surface border-b border-aura-border flex items-center px-2 gap-1 titlebar-no-drag">
      {/* Project name */}
      <div className="flex items-center gap-2 px-2 min-w-[150px]">
        <span className="text-sm font-medium text-aura-text truncate">
          {projectName}
        </span>
        {isDirty && <span className="text-aura-warning">●</span>}
      </div>

      {/* Separator */}
      <div className="w-px h-5 bg-aura-border mx-1" />

      {/* File operations */}
      <button
        onClick={onOpenProject}
        className="toolbar-btn"
        title="Open Project"
      >
        <FolderOpen size={16} />
        <span className="hidden sm:inline">Open</span>
      </button>

      <button
        onClick={onNewProject}
        className="toolbar-btn"
        title="New Project"
      >
        <FilePlus size={16} />
        <span className="hidden sm:inline">New</span>
      </button>

      <button
        onClick={onSave}
        className="toolbar-btn"
        title="Save (⌘S)"
        disabled={!isDirty}
      >
        <Save size={16} />
        <span className="hidden sm:inline">Save</span>
      </button>

      {/* Separator */}
      <div className="w-px h-5 bg-aura-border mx-1" />

      {/* Compile */}
      <button
        onClick={onCompile}
        className="toolbar-btn toolbar-btn-primary"
        title="Compile (⌘B)"
        disabled={isCompiling}
      >
        {isCompiling ? (
          <Loader2 size={16} className="animate-spin" />
        ) : compileStatus === 'success' ? (
          <Check size={16} />
        ) : compileStatus === 'error' ? (
          <X size={16} />
        ) : (
          <Play size={16} />
        )}
        <span>Compile</span>
      </button>

      {/* Sync placeholder */}
      <button
        className="toolbar-btn"
        title="Sync with Overleaf"
        disabled
      >
        <RefreshCw size={16} />
        <span className="hidden sm:inline">Sync</span>
      </button>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Settings */}
      <button
        className="toolbar-btn"
        title="Settings"
      >
        <Settings size={16} />
      </button>
    </div>
  );
}
