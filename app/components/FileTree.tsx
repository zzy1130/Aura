'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  Image,
  ChevronRight,
  ChevronDown,
  Plus,
  RefreshCw,
} from 'lucide-react';

interface FileTreeProps {
  projectPath: string | null;
  files: string[];
  currentFile: string | null;
  onFileSelect: (filePath: string) => void;
}

interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

// Get icon for file type
function getFileIcon(name: string) {
  if (name.endsWith('.tex')) return <FileCode size={14} className="text-aura-accent" />;
  if (name.endsWith('.bib')) return <FileText size={14} className="text-yellow-400" />;
  if (name.endsWith('.pdf')) return <FileText size={14} className="text-red-400" />;
  if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')) {
    return <Image size={14} className="text-green-400" />;
  }
  if (name.endsWith('.sty') || name.endsWith('.cls')) {
    return <FileCode size={14} className="text-purple-400" />;
  }
  return <FileText size={14} className="text-aura-muted" />;
}

// Tree node component
function TreeNode({
  node,
  depth,
  currentFile,
  onFileSelect,
}: {
  node: FileNode;
  depth: number;
  currentFile: string | null;
  onFileSelect: (path: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(depth < 2);
  const isSelected = currentFile === node.path;

  const handleClick = useCallback(() => {
    if (node.type === 'directory') {
      setIsExpanded(!isExpanded);
    } else {
      onFileSelect(node.path);
    }
  }, [node, isExpanded, onFileSelect]);

  return (
    <div>
      <div
        className={`file-tree-item ${isSelected ? 'selected' : ''}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
      >
        {/* Expand icon for directories */}
        {node.type === 'directory' ? (
          <>
            {isExpanded ? (
              <ChevronDown size={14} className="text-aura-muted" />
            ) : (
              <ChevronRight size={14} className="text-aura-muted" />
            )}
            {isExpanded ? (
              <FolderOpen size={14} className="text-aura-accent" />
            ) : (
              <Folder size={14} className="text-aura-accent" />
            )}
          </>
        ) : (
          <>
            <span className="w-[14px]" /> {/* Spacer */}
            {getFileIcon(node.name)}
          </>
        )}
        <span className="truncate text-sm">{node.name}</span>
      </div>

      {/* Children */}
      {node.type === 'directory' && isExpanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              currentFile={currentFile}
              onFileSelect={onFileSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FileTree({
  projectPath,
  files: _files,
  currentFile,
  onFileSelect,
}: FileTreeProps) {
  const [tree, setTree] = useState<FileNode[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Build tree from file list
  const buildTree = useCallback((filePaths: string[]): FileNode[] => {
    const root: Map<string, FileNode> = new Map();

    for (const filePath of filePaths) {
      const parts = filePath.split('/').filter(Boolean);
      let currentPath = '';

      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        const parentPath = currentPath;
        currentPath = currentPath ? `${currentPath}/${part}` : part;

        if (!root.has(currentPath)) {
          const isFile = i === parts.length - 1;
          const node: FileNode = {
            name: part,
            path: currentPath,
            type: isFile ? 'file' : 'directory',
            children: isFile ? undefined : [],
          };

          root.set(currentPath, node);

          // Add to parent
          if (parentPath) {
            const parent = root.get(parentPath);
            if (parent && parent.children) {
              parent.children.push(node);
            }
          }
        }
      }
    }

    // Get root level nodes
    const rootNodes: FileNode[] = [];
    root.forEach((node, path) => {
      if (!path.includes('/')) {
        rootNodes.push(node);
      }
    });

    // Sort: directories first, then alphabetically
    const sortNodes = (nodes: FileNode[]): FileNode[] => {
      return nodes.sort((a, b) => {
        if (a.type !== b.type) {
          return a.type === 'directory' ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      }).map((node) => ({
        ...node,
        children: node.children ? sortNodes(node.children) : undefined,
      }));
    };

    return sortNodes(rootNodes);
  }, []);

  // Fetch files from backend
  const fetchFiles = useCallback(async () => {
    if (!projectPath) return;

    setIsLoading(true);
    try {
      // TODO: Fetch from backend
      // For now, use mock data
      const mockFiles = [
        'main.tex',
        'refs.bib',
        'sections/introduction.tex',
        'sections/methodology.tex',
        'sections/results.tex',
        'figures/diagram.png',
        '.aura/config.json',
      ];
      setTree(buildTree(mockFiles));
    } catch (error) {
      console.error('Failed to fetch files:', error);
    } finally {
      setIsLoading(false);
    }
  }, [projectPath, buildTree]);

  useEffect(() => {
    if (projectPath) {
      fetchFiles();
    } else {
      setTree([]);
    }
  }, [projectPath, fetchFiles]);

  return (
    <div className="h-full flex flex-col bg-aura-bg">
      {/* Header */}
      <div className="h-8 border-b border-aura-border flex items-center justify-between px-3">
        <span className="text-xs font-medium text-aura-muted uppercase tracking-wider">
          Files
        </span>
        <div className="flex gap-1">
          <button
            className="p-1 hover:bg-aura-surface rounded"
            title="New File"
          >
            <Plus size={14} className="text-aura-muted" />
          </button>
          <button
            className="p-1 hover:bg-aura-surface rounded"
            title="Refresh"
            onClick={fetchFiles}
          >
            <RefreshCw size={14} className={`text-aura-muted ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-auto py-1">
        {projectPath ? (
          tree.length > 0 ? (
            tree.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                depth={0}
                currentFile={currentFile}
                onFileSelect={onFileSelect}
              />
            ))
          ) : (
            <div className="p-4 text-center text-sm text-aura-muted">
              No files found
            </div>
          )
        ) : (
          <div className="p-4 text-center text-sm text-aura-muted">
            Open a project to see files
          </div>
        )}
      </div>
    </div>
  );
}
