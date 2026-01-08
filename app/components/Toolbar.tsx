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
    <div className="h-11 bg-white border-b border-black/6 flex items-center px-3 gap-2 titlebar-no-drag">
      {/* Project name */}
      <div className="flex items-center gap-2 min-w-[140px]">
        <span className="typo-body-strong truncate">
          {projectName}
        </span>
        {isDirty && (
          <span className="w-2 h-2 rounded-full bg-warn" title="Unsaved changes" />
        )}
      </div>

      {/* Separator */}
      <div className="w-px h-5 bg-black/10 mx-1" />

      {/* File operations */}
      <button
        onClick={onOpenProject}
        className="btn-ghost"
        title="Open Project"
      >
        <FolderOpen size={16} className="text-secondary" />
        <span className="hidden sm:inline text-secondary">Open</span>
      </button>

      <button
        onClick={onNewProject}
        className="btn-ghost"
        title="New Project"
      >
        <FilePlus size={16} className="text-secondary" />
        <span className="hidden sm:inline text-secondary">New</span>
      </button>

      <button
        onClick={onSave}
        className={`btn-ghost ${!isDirty ? 'opacity-40 cursor-not-allowed' : ''}`}
        title="Save (⌘S)"
        disabled={!isDirty}
      >
        <Save size={16} className="text-secondary" />
        <span className="hidden sm:inline text-secondary">Save</span>
      </button>

      {/* Separator */}
      <div className="w-px h-5 bg-black/10 mx-1" />

      {/* Compile - Primary action */}
      <button
        onClick={onCompile}
        className={`flex h-7 items-center gap-1.5 rounded-full bg-green1 px-3 text-white typo-small-strong hover:opacity-90 transition-opacity ${isCompiling ? 'opacity-80' : ''}`}
        title="Compile (⌘B)"
        disabled={isCompiling}
      >
        {isCompiling ? (
          <Loader2 size={14} className="animate-spin" />
        ) : compileStatus === 'success' ? (
          <Check size={14} />
        ) : compileStatus === 'error' ? (
          <X size={14} />
        ) : (
          <Play size={14} />
        )}
        <span>Compile</span>
      </button>

      {/* Sync placeholder */}
      <button
        className="btn-ghost opacity-40 cursor-not-allowed"
        title="Sync with Overleaf (Coming soon)"
        disabled
      >
        <RefreshCw size={16} className="text-secondary" />
        <span className="hidden sm:inline text-secondary">Sync</span>
      </button>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Settings */}
      <button
        className="btn-icon"
        title="Settings"
      >
        <Settings size={16} className="text-secondary" />
      </button>
    </div>
  );
}
