'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import MonacoEditor, { OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { Check, X, AlertCircle, FileCode } from 'lucide-react';

export interface PendingEdit {
  request_id: string;
  filepath: string;
  old_string: string;
  new_string: string;
}

export type SendToAgentAction = 'polish' | 'ask' | 'file';

interface EditorProps {
  content: string;
  filePath: string | null;
  onChange: (value: string | undefined) => void;
  onSave: () => void;
  pendingEdit?: PendingEdit | null;
  onApproveEdit?: (requestId: string) => void;
  onRejectEdit?: (requestId: string) => void;
  onSendToAgent?: (text: string, action: SendToAgentAction) => void;
}

// LaTeX language configuration
const latexLanguageConfig = {
  comments: {
    lineComment: '%',
  },
  brackets: [
    ['{', '}'],
    ['[', ']'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '$', close: '$' },
    { open: '`', close: "'" },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '$', close: '$' },
  ],
};

// LaTeX syntax highlighting tokens
const latexTokenProvider = {
  tokenizer: {
    root: [
      // Comments
      [/%.*$/, 'comment'],

      // Commands
      [/\\[a-zA-Z@]+/, 'keyword'],

      // Math mode
      [/\$\$/, { token: 'string', next: '@mathDisplay' }],
      [/\$/, { token: 'string', next: '@mathInline' }],

      // Environments
      [/\\begin\{[^}]+\}/, 'type'],
      [/\\end\{[^}]+\}/, 'type'],

      // Arguments
      [/\{/, 'delimiter.bracket'],
      [/\}/, 'delimiter.bracket'],
      [/\[/, 'delimiter.square'],
      [/\]/, 'delimiter.square'],

      // Special characters
      [/[&~^_]/, 'operator'],
    ],

    mathInline: [
      [/[^\$]+/, 'string'],
      [/\$/, { token: 'string', next: '@pop' }],
    ],

    mathDisplay: [
      [/[^\$]+/, 'string'],
      [/\$\$/, { token: 'string', next: '@pop' }],
    ],
  },
};

// Aura dark theme for Monaco
const auraTheme: editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6c7086', fontStyle: 'italic' },
    { token: 'keyword', foreground: '89b4fa' },
    { token: 'string', foreground: 'a6e3a1' },
    { token: 'type', foreground: 'f9e2af' },
    { token: 'operator', foreground: 'f38ba8' },
    { token: 'delimiter', foreground: 'cdd6f4' },
  ],
  colors: {
    'editor.background': '#282838',
    'editor.foreground': '#cdd6f4',
    'editor.lineHighlightBackground': '#313244',
    'editor.selectionBackground': '#45475a',
    'editorCursor.foreground': '#89b4fa',
    'editorLineNumber.foreground': '#6c7086',
    'editorLineNumber.activeForeground': '#cdd6f4',
  },
};

// Find line numbers where a string appears in content
function findStringLocation(content: string, searchStr: string): { startLine: number; endLine: number } | null {
  if (!searchStr || !content.includes(searchStr)) return null;

  const index = content.indexOf(searchStr);
  const beforeMatch = content.substring(0, index);
  const startLine = beforeMatch.split('\n').length;
  const matchLines = searchStr.split('\n').length;
  const endLine = startLine + matchLines - 1;

  return { startLine, endLine };
}

export default function Editor({
  content,
  filePath,
  onChange,
  onSave,
  pendingEdit,
  onApproveEdit,
  onRejectEdit,
  onSendToAgent,
}: EditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import('monaco-editor') | null>(null);
  const decorationsRef = useRef<string[]>([]);
  const viewZoneIdRef = useRef<string | null>(null);
  const [editLocation, setEditLocation] = useState<{ startLine: number; endLine: number } | null>(null);
  const layoutListenerRef = useRef<{ dispose: () => void } | null>(null);
  const onSendToAgentRef = useRef(onSendToAgent);

  // Keep ref in sync with prop
  useEffect(() => {
    onSendToAgentRef.current = onSendToAgent;
  }, [onSendToAgent]);

  // Function to calculate view zone height based on current editor width
  const calculateViewZoneHeight = useCallback((
    editorInstance: editor.IStandaloneCodeEditor,
    newString: string
  ): number => {
    const newLines = newString.split('\n');
    const editorWidth = editorInstance.getLayoutInfo().contentWidth;
    const charWidth = 7.5; // Approximate character width for monospace

    let totalVisualLines = 0;
    newLines.forEach(line => {
      if (line.length === 0) {
        totalVisualLines += 1;
      } else {
        // Account for "+ " prefix and padding
        const availableWidth = Math.max(editorWidth - 80, 100);
        const charsPerLine = Math.max(10, Math.floor(availableWidth / charWidth));
        const wrappedLines = Math.max(1, Math.ceil(line.length / charsPerLine));
        totalVisualLines += wrappedLines;
      }
    });

    // Buffer for padding
    return totalVisualLines + 2;
  }, []);

  // Function to create or update the view zone
  const updateViewZone = useCallback((
    editorInstance: editor.IStandaloneCodeEditor,
    monacoInstance: typeof import('monaco-editor'),
    newString: string,
    afterLine: number
  ) => {
    // Clear existing view zone
    if (viewZoneIdRef.current) {
      editorInstance.changeViewZones((accessor) => {
        if (viewZoneIdRef.current) {
          accessor.removeZone(viewZoneIdRef.current);
          viewZoneIdRef.current = null;
        }
      });
    }

    if (!newString) return;

    const newLines = newString.split('\n');
    const lineHeight = editorInstance.getOption(monacoInstance.editor.EditorOption.lineHeight);
    const finalHeight = calculateViewZoneHeight(editorInstance, newString);

    editorInstance.changeViewZones((accessor) => {
      const domNode = document.createElement('div');
      domNode.className = 'pending-edit-add-zone';
      domNode.style.backgroundColor = 'rgba(166, 227, 161, 0.15)';
      domNode.style.borderLeft = '4px solid #a6e3a1';
      domNode.style.paddingLeft = '8px';
      domNode.style.paddingRight = '8px';
      domNode.style.paddingTop = '4px';
      domNode.style.paddingBottom = '4px';
      domNode.style.fontFamily = "'JetBrains Mono', 'Fira Code', monospace";
      domNode.style.fontSize = '14px';
      domNode.style.lineHeight = `${lineHeight}px`;
      domNode.style.color = '#a6e3a1';
      domNode.style.whiteSpace = 'pre-wrap';
      domNode.style.wordBreak = 'break-word';
      domNode.style.overflowWrap = 'break-word';
      domNode.style.boxSizing = 'border-box';
      domNode.style.overflow = 'hidden';

      newLines.forEach((line) => {
        const lineDiv = document.createElement('div');
        lineDiv.style.display = 'flex';
        lineDiv.style.alignItems = 'flex-start';
        const plusSpan = document.createElement('span');
        plusSpan.textContent = '+ ';
        plusSpan.style.color = '#40a02b';
        plusSpan.style.marginRight = '4px';
        plusSpan.style.userSelect = 'none';
        plusSpan.style.flexShrink = '0';
        const textSpan = document.createElement('span');
        textSpan.textContent = line || ' ';
        textSpan.style.flex = '1';
        lineDiv.appendChild(plusSpan);
        lineDiv.appendChild(textSpan);
        domNode.appendChild(lineDiv);
      });

      const zoneId = accessor.addZone({
        afterLineNumber: afterLine,
        heightInLines: finalHeight,
        domNode: domNode,
        suppressMouseDown: true,
      });

      viewZoneIdRef.current = zoneId;
    });
  }, [calculateViewZoneHeight]);

  // Handle editor mount
  const handleEditorMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Register LaTeX language
      monaco.languages.register({ id: 'latex' });
      monaco.languages.setLanguageConfiguration('latex', latexLanguageConfig as any);
      monaco.languages.setMonarchTokensProvider('latex', latexTokenProvider as any);

      // Register theme
      monaco.editor.defineTheme('aura-dark', auraTheme);
      monaco.editor.setTheme('aura-dark');

      // Add save keybinding
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        onSave();
      });

      // Add context menu actions for AI (use 'z_aura' group to put at bottom with separator)
      editor.addAction({
        id: 'aura-polish',
        label: '✨ Polish with AI',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyP],
        contextMenuGroupId: 'z_aura',
        contextMenuOrder: 1,
        run: (ed) => {
          const selection = ed.getSelection();
          if (selection && !selection.isEmpty()) {
            const selectedText = ed.getModel()?.getValueInRange(selection);
            if (selectedText && selectedText.trim() && onSendToAgentRef.current) {
              onSendToAgentRef.current(selectedText, 'polish');
            }
          }
        },
      });

      editor.addAction({
        id: 'aura-ask-ai',
        label: '💬 Ask AI',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyA],
        contextMenuGroupId: 'z_aura',
        contextMenuOrder: 2,
        run: (ed) => {
          const selection = ed.getSelection();
          if (selection && !selection.isEmpty()) {
            const selectedText = ed.getModel()?.getValueInRange(selection);
            if (selectedText && selectedText.trim() && onSendToAgentRef.current) {
              onSendToAgentRef.current(selectedText, 'ask');
            }
          }
        },
      });

      // Focus editor
      editor.focus();
    },
    [onSave]
  );

  // Apply decorations when pendingEdit changes
  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;

    console.log('[Editor] useEffect triggered - pendingEdit:', pendingEdit?.request_id);
    console.log('[Editor] filePath:', filePath);

    if (!editor || !monaco) {
      console.log('[Editor] Editor or Monaco not ready');
      return;
    }

    // Clear existing decorations
    if (decorationsRef.current.length > 0) {
      editor.deltaDecorations(decorationsRef.current, []);
      decorationsRef.current = [];
    }

    // Clear existing view zones
    if (viewZoneIdRef.current) {
      editor.changeViewZones((accessor) => {
        if (viewZoneIdRef.current) {
          accessor.removeZone(viewZoneIdRef.current);
          viewZoneIdRef.current = null;
        }
      });
    }

    // Check if this edit is for the current file
    if (!pendingEdit || !filePath) {
      console.log('[Editor] No pendingEdit or filePath, clearing');
      setEditLocation(null);
      return;
    }

    // Check if the pending edit is for this file
    const editFilename = pendingEdit.filepath.split('/').pop();
    const currentFilename = filePath.split('/').pop();
    console.log('[Editor] Checking file match:', editFilename, 'vs', currentFilename);
    if (editFilename !== currentFilename && pendingEdit.filepath !== filePath) {
      console.log('[Editor] File mismatch, clearing');
      setEditLocation(null);
      return;
    }

    // Find where the old string is in the content
    const location = findStringLocation(content, pendingEdit.old_string);
    console.log('[Editor] Found location:', location);
    if (!location) {
      console.log('[Editor] Could not find old_string in content');
      console.log('[Editor] old_string:', pendingEdit.old_string?.substring(0, 100));
      console.log('[Editor] content length:', content?.length);
      setEditLocation(null);
      return;
    }

    console.log('[Editor] Setting editLocation and creating decorations');
    setEditLocation(location);

    // Create decorations for the lines being changed
    const decorations: editor.IModelDeltaDecoration[] = [];

    // Highlight the lines that will be removed (red background)
    decorations.push({
      range: new monaco.Range(location.startLine, 1, location.endLine, 1),
      options: {
        isWholeLine: true,
        className: 'pending-edit-remove-line',
        glyphMarginClassName: 'pending-edit-remove-glyph',
        overviewRuler: {
          color: '#f38ba8',
          position: monaco.editor.OverviewRulerLane.Full,
        },
      },
    });

    // Add inline decoration to show the text being removed
    decorations.push({
      range: new monaco.Range(
        location.startLine,
        1,
        location.endLine,
        editor.getModel()?.getLineMaxColumn(location.endLine) || 1
      ),
      options: {
        inlineClassName: 'pending-edit-remove-text',
      },
    });

    decorationsRef.current = editor.deltaDecorations([], decorations);

    // Add view zone to show new content in green after the removed lines
    if (pendingEdit.new_string) {
      updateViewZone(editor, monaco, pendingEdit.new_string, location.endLine);

      // Set up layout listener to recalculate view zone on resize
      if (layoutListenerRef.current) {
        layoutListenerRef.current.dispose();
      }
      layoutListenerRef.current = editor.onDidLayoutChange(() => {
        if (pendingEdit?.new_string && viewZoneIdRef.current) {
          updateViewZone(editor, monaco, pendingEdit.new_string, location.endLine);
        }
      });
    }

    // Scroll to the edit location
    editor.revealLineInCenter(location.startLine);

    // Cleanup layout listener when effect is re-run or unmounted
    return () => {
      if (layoutListenerRef.current) {
        layoutListenerRef.current.dispose();
        layoutListenerRef.current = null;
      }
    };
  }, [pendingEdit, content, filePath, updateViewZone]);

  // Determine language from file extension
  const getLanguage = (path: string | null): string => {
    if (!path) return 'latex';
    if (path.endsWith('.tex')) return 'latex';
    if (path.endsWith('.bib')) return 'bibtex';
    if (path.endsWith('.sty')) return 'latex';
    if (path.endsWith('.cls')) return 'latex';
    if (path.endsWith('.json')) return 'json';
    if (path.endsWith('.md')) return 'markdown';
    return 'plaintext';
  };

  // Check if the pending edit applies to current file
  const isEditForCurrentFile = pendingEdit && filePath && (
    pendingEdit.filepath === filePath ||
    pendingEdit.filepath.split('/').pop() === filePath.split('/').pop()
  );

  return (
    <div className="h-full flex flex-col bg-editor-surface">
      {/* File tab */}
      {filePath && (
        <div className="h-9 bg-editor-bg border-b border-editor-border flex items-center px-3">
          <span className="typo-small text-editor-text truncate">
            {filePath.split('/').pop()}
          </span>
        </div>
      )}

      {/* Pending Edit Banner */}
      {isEditForCurrentFile && editLocation && (
        <div className="bg-orange2/20 border-b border-orange1/30 px-4 py-2.5 flex items-center gap-3">
          <AlertCircle size={16} className="text-orange1 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="typo-small-strong text-orange1">Pending Edit</div>
            <div className="typo-ex-small text-orange1/70">
              Lines {editLocation.startLine}-{editLocation.endLine} will be modified
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => onRejectEdit?.(pendingEdit!.request_id)}
              className="flex items-center gap-1.5 px-3 py-1.5 typo-small-strong bg-error/10 text-error rounded-yw-lg hover:bg-error/20 transition-colors"
            >
              <X size={12} />
              Reject
            </button>
            <button
              onClick={() => onApproveEdit?.(pendingEdit!.request_id)}
              className="flex items-center gap-1.5 px-3 py-1.5 typo-small-strong bg-success/10 text-success rounded-yw-lg hover:bg-success/20 transition-colors"
            >
              <Check size={12} />
              Accept
            </button>
          </div>
        </div>
      )}

      {/* Editor */}
      <div className="flex-1 dark-scrollbar">
        {filePath ? (
          <MonacoEditor
            height="100%"
            language={getLanguage(filePath)}
            value={content}
            onChange={onChange}
            onMount={handleEditorMount}
            options={{
              fontSize: 14,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontLigatures: true,
              minimap: { enabled: false },
              lineNumbers: 'on',
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              renderWhitespace: 'selection',
              tabSize: 2,
              automaticLayout: true,
              padding: { top: 10 },
              readOnly: !!pendingEdit,
            }}
            theme="aura-dark"
          />
        ) : (
          <div className="h-full flex items-center justify-center bg-editor-bg">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-editor-surface flex items-center justify-center">
                <FileCode size={32} className="text-editor-muted" />
              </div>
              <p className="typo-large text-editor-text mb-1">No file selected</p>
              <p className="typo-small text-editor-muted">Open a project to start editing</p>
            </div>
          </div>
        )}
      </div>

      {/* CSS for decorations */}
      <style jsx global>{`
        .pending-edit-remove-line {
          background-color: rgba(243, 139, 168, 0.15) !important;
        }
        .pending-edit-remove-glyph {
          background-color: #f38ba8;
          width: 4px !important;
          margin-left: 3px;
        }
        .pending-edit-remove-text {
          text-decoration: line-through;
          opacity: 0.7;
        }
      `}</style>
    </div>
  );
}
