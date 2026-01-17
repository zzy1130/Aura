# Markdown Preview Feature Design

**Date**: 2026-01-17
**Status**: Implemented

## Overview

Add Markdown file support to Aura with live preview, mirroring the LaTeX editing experience. When a `.md` file is open, the preview panel shows rendered Markdown instead of PDF.

## Architecture

```
When .tex file is open:
[File Tree] | [Monaco Editor] | [PDF Viewer] | [Agent Panel]

When .md file is open:
[File Tree] | [Monaco Editor] | [Markdown Preview] | [Agent Panel]
```

The third panel becomes context-sensitive based on file type.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Preview trigger | Live preview with 300ms debounce |
| Panel behavior | Replace PDF viewer when .md is open |
| Preview theme | Light/paper style (white background) |
| Features | Full suite: Shiki + KaTeX + Mermaid |
| Scroll sync | None (independent scrolling) |

## Components

### New: MarkdownPreview.tsx

```typescript
interface MarkdownPreviewProps {
  content: string;
  className?: string;
}
```

- Wraps Streamdown with full features enabled
- Light theme styling (white background, dark text)
- Typography styles for clean document appearance
- Empty state placeholder when no content

### Modified: page.tsx

- File type detection from `currentFile` extension
- Debounced content state for live preview
- Conditional rendering: MarkdownPreview vs PDFViewer
- Hide Compile button for .md files

### Modified: Editor.tsx

- Monaco has built-in markdown language support (no custom tokenizer needed)

## Dependencies

```bash
npm install streamdown
```

## Styling

- Import Streamdown CSS in globals.css
- Preview container matches PDF viewer layout constraints
- Prose styling for headings, paragraphs, lists, links

## No Backend Changes

Markdown rendering is purely frontend. Existing file read/write APIs work for .md files.

## Implementation Tasks

1. Install streamdown dependency
2. Create MarkdownPreview component
3. Add Streamdown CSS import
4. Modify page.tsx for conditional panel rendering
5. Add debounced content state
6. Hide Compile button for .md files
7. Test with sample .md file
