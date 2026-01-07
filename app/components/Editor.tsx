'use client';

import { useCallback, useRef } from 'react';
import MonacoEditor, { OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';

interface EditorProps {
  content: string;
  filePath: string | null;
  onChange: (value: string | undefined) => void;
  onSave: () => void;
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

export default function Editor({
  content,
  filePath,
  onChange,
  onSave,
}: EditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  // Handle editor mount
  const handleEditorMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;

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

      // Focus editor
      editor.focus();
    },
    [onSave]
  );

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

  return (
    <div className="h-full flex flex-col bg-aura-surface">
      {/* File tab */}
      {filePath && (
        <div className="h-8 border-b border-aura-border flex items-center px-3">
          <span className="text-sm text-aura-text truncate">
            {filePath.split('/').pop()}
          </span>
        </div>
      )}

      {/* Editor */}
      <div className="flex-1">
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
            }}
            theme="aura-dark"
          />
        ) : (
          <div className="h-full flex items-center justify-center text-aura-muted">
            <div className="text-center">
              <p className="text-lg mb-2">No file selected</p>
              <p className="text-sm">Open a project to start editing</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
