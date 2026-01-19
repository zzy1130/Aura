# SyncTeX: PDF to Source Navigation

## Overview

Enable double-click on PDF to jump to corresponding line in LaTeX source editor.

## User Flow

1. User compiles document → `.synctex.gz` file generated alongside PDF
2. User double-clicks on text in PDF viewer
3. Editor jumps to the corresponding line in the source file

## Technical Design

### 1. Compilation Changes

Add `-synctex=1` flag to pdflatex commands:

**Files:**
- `backend/services/docker.py` - Docker compilation
- `backend/services/local_latex.py` - Local TeX compilation

**Change:**
```python
# Before
pdflatex -interaction=nonstopmode {filename}

# After
pdflatex -synctex=1 -interaction=nonstopmode {filename}
```

### 2. Backend SyncTeX Service

**New file:** `backend/services/synctex.py`

```python
async def query_synctex(project_path: str, pdf_file: str, page: int, x: float, y: float) -> dict:
    """Query synctex to find source location for PDF coordinates."""
    # Run: synctex view -i "page:x:y:pdf_file" -d project_path
    # Parse output for Input:/Line:/Column:
    # Return {success, file, line, column}
```

**New endpoint:** `POST /api/synctex/view`

Request:
```json
{
  "project_path": "/path/to/project",
  "pdf_file": "main.pdf",
  "page": 3,
  "x": 150.5,
  "y": 400.2
}
```

Response:
```json
{
  "success": true,
  "file": "chapter1.tex",
  "line": 42,
  "column": 0
}
```

### 3. PDF Viewer Changes

**File:** `app/components/PDFViewer.tsx`

New props:
```tsx
interface PDFViewerProps {
  pdfUrl: string | null;
  isCompiling: boolean;
  pdfFile?: string;
  projectPath?: string | null;
  onSyncTexClick?: (file: string, line: number) => void;
}
```

Double-click handler:
- Get click position relative to page element
- Convert screen coordinates to PDF coordinates (account for scale)
- PDF coord system: origin bottom-left, y increases upward
- Call `/api/synctex/view` endpoint
- Invoke `onSyncTexClick` callback with result

### 4. Editor Integration

**File:** `app/components/Editor.tsx`

Expose method via ref:
```tsx
// Allow parent to scroll editor to specific line
editorRef.current?.revealLineInCenter(line);
```

**File:** `app/app/page.tsx`

Handle SyncTeX callback:
```tsx
const handleSyncTexClick = (file: string, line: number) => {
  // Switch file if needed
  // Scroll editor to line
  // Optionally highlight line briefly
};
```

## Limitations

- Only works with Local TeX or Docker backends (Tectonic lacks synctex support)
- Requires successful compilation first (synctex file must exist)
- Accuracy depends on document complexity

## Files to Modify

1. `backend/services/docker.py` - Add synctex flag
2. `backend/services/local_latex.py` - Add synctex flag
3. `backend/services/synctex.py` - New service (create)
4. `backend/main.py` - Add endpoint
5. `app/components/PDFViewer.tsx` - Double-click handler
6. `app/components/Editor.tsx` - Expose scroll method
7. `app/app/page.tsx` - Wire components together
