'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  ZoomIn,
  ZoomOut,
  Loader2,
  RotateCw,
  FileText,
} from 'lucide-react';

// Set up PDF.js worker - use absolute https URL for Electron compatibility
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PDFViewerProps {
  pdfUrl: string | null;
  isCompiling: boolean;
  pdfFile?: string;  // Name of the PDF file (e.g., "main.pdf")
  projectPath?: string | null;  // Path to the project
  onSyncTexClick?: (file: string, line: number) => void;  // Callback for PDF-to-source navigation
}

export default function PDFViewer({
  pdfUrl,
  isCompiling,
  pdfFile,
  projectPath,
  onSyncTexClick,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState<number>(1.0);
  const [_isLoading, setIsLoading] = useState<boolean>(false);
  const [currentVisiblePage, setCurrentVisiblePage] = useState<number>(1);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Handle document load
  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setIsLoading(false);
    setCurrentVisiblePage(1);
  }, []);

  const onDocumentLoadError = useCallback((error: Error) => {
    console.error('PDF load error:', error);
    setIsLoading(false);
  }, []);

  // Zoom controls
  const zoomIn = useCallback(() => {
    setScale((prev) => Math.min(3.0, prev + 0.2));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => Math.max(0.3, prev - 0.2));
  }, []);

  const resetZoom = useCallback(() => {
    setScale(1.0);
  }, []);

  // Mouse wheel zoom (Ctrl/Cmd + scroll)
  const handleWheel = useCallback((e: WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.03 : 0.03;
      setScale((prev) => Math.max(0.3, Math.min(3.0, prev + delta)));
    }
  }, []);

  // Attach wheel listener with passive: false for preventDefault
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [handleWheel]);

  // Track visible page on scroll
  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container || numPages === 0) return;

    const containerRect = container.getBoundingClientRect();
    const containerMiddle = containerRect.top + containerRect.height / 2;

    let closestPage = 1;
    let closestDistance = Infinity;

    pageRefs.current.forEach((pageEl, pageNum) => {
      const rect = pageEl.getBoundingClientRect();
      const pageMiddle = rect.top + rect.height / 2;
      const distance = Math.abs(pageMiddle - containerMiddle);

      if (distance < closestDistance) {
        closestDistance = distance;
        closestPage = pageNum;
      }
    });

    setCurrentVisiblePage(closestPage);
  }, [numPages]);

  // Store page ref
  const setPageRef = useCallback((pageNum: number, el: HTMLDivElement | null) => {
    if (el) {
      pageRefs.current.set(pageNum, el);
    } else {
      pageRefs.current.delete(pageNum);
    }
  }, []);

  // Scroll to specific page
  const scrollToPage = useCallback((pageNum: number) => {
    const pageEl = pageRefs.current.get(pageNum);
    if (pageEl) {
      pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  // Handle double-click on PDF page for SyncTeX navigation
  const handlePageDoubleClick = useCallback(
    async (e: React.MouseEvent, pageNum: number) => {
      if (!projectPath || !pdfFile || !onSyncTexClick) return;

      const pageEl = pageRefs.current.get(pageNum);
      if (!pageEl) return;

      const rect = pageEl.getBoundingClientRect();

      // Convert screen coordinates to PDF coordinates for synctex
      // SyncTeX uses top-left origin, same as screen coordinates
      // Coordinates are in "big points" (72 dpi), so we divide by scale
      const x = (e.clientX - rect.left) / scale;
      const y = (e.clientY - rect.top) / scale;

      try {
        const response = await fetch('http://localhost:8001/api/synctex/view', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_path: projectPath,
            pdf_file: pdfFile,
            page: pageNum,
            x,
            y,
          }),
        });

        const data = await response.json();
        if (data.success && data.file && data.line) {
          onSyncTexClick(data.file, data.line);
        }
      } catch (error) {
        console.error('SyncTeX query failed:', error);
      }
    },
    [projectPath, pdfFile, scale, onSyncTexClick]
  );

  // Generate array of page numbers
  const pageNumbers = Array.from({ length: numPages }, (_, i) => i + 1);

  return (
    <div className="h-full flex flex-col bg-fill-secondary">
      {/* Toolbar */}
      <div className="panel-header">
        {/* Page indicator */}
        <div className="flex items-center gap-2">
          <span className="typo-small text-secondary min-w-[60px]">
            {numPages > 0 ? `${currentVisiblePage} / ${numPages}` : 'No PDF'}
          </span>
          {numPages > 1 && (
            <input
              type="range"
              min={1}
              max={numPages}
              value={currentVisiblePage}
              onChange={(e) => scrollToPage(Number(e.target.value))}
              className="w-16 h-1 bg-black/12 rounded-full appearance-none cursor-pointer accent-green2"
            />
          )}
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={zoomOut}
            className="btn-icon w-7 h-7"
            title="Zoom out"
          >
            <ZoomOut size={14} className="text-secondary" />
          </button>
          <span className="typo-small text-secondary min-w-[40px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={zoomIn}
            className="btn-icon w-7 h-7"
            title="Zoom in"
          >
            <ZoomIn size={14} className="text-secondary" />
          </button>
          <button
            onClick={resetZoom}
            className="btn-icon w-7 h-7 ml-1"
            title="Reset zoom"
          >
            <RotateCw size={14} className="text-secondary" />
          </button>
        </div>
      </div>

      {/* PDF Content - Scrollable */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto bg-[#e8e6e3]"
      >
        {isCompiling ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-16 h-16 rounded-full bg-white/80 flex items-center justify-center mb-3 shadow-card">
              <Loader2 size={28} className="animate-spin text-green2" />
            </div>
            <span className="typo-body text-secondary">Compiling...</span>
          </div>
        ) : pdfUrl ? (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-full">
                <div className="w-16 h-16 rounded-full bg-white/80 flex items-center justify-center shadow-card">
                  <Loader2 size={28} className="animate-spin text-green2" />
                </div>
              </div>
            }
            error={
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-16 h-16 rounded-full bg-error/10 flex items-center justify-center mb-3">
                  <FileText size={28} className="text-error" />
                </div>
                <span className="typo-body text-error mb-1">Failed to load PDF</span>
                <span className="typo-small text-secondary">
                  Check if the file exists and is valid
                </span>
              </div>
            }
            className="py-6 min-w-max"
          >
            {/* Render all pages for continuous scrolling */}
            <div className="flex flex-col items-center">
              {pageNumbers.map((pageNum) => (
                <div
                  key={pageNum}
                  ref={(el) => setPageRef(pageNum, el)}
                  onDoubleClick={(e) => handlePageDoubleClick(e, pageNum)}
                  className="mb-4 last:mb-0 shadow-card rounded-sm overflow-hidden cursor-pointer"
                >
                  <Page
                    pageNumber={pageNum}
                    scale={scale}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                  />
                </div>
              ))}
            </div>
          </Document>
        ) : (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-20 h-20 rounded-full bg-black/3 flex items-center justify-center mb-4">
              <FileText size={36} className="text-tertiary" />
            </div>
            <p className="typo-large text-secondary mb-1">No PDF to display</p>
            <p className="typo-small text-tertiary">
              Compile your LaTeX project to see the output
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
