'use client';

import { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Loader2,
} from 'lucide-react';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PDFViewerProps {
  pdfUrl: string | null;
  isCompiling: boolean;
}

export default function PDFViewer({ pdfUrl, isCompiling }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [_isLoading, setIsLoading] = useState<boolean>(false);

  // Handle document load
  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setCurrentPage(1);
    setIsLoading(false);
  }, []);

  const onDocumentLoadError = useCallback((error: Error) => {
    console.error('PDF load error:', error);
    setIsLoading(false);
  }, []);

  // Navigation
  const goToPrevPage = useCallback(() => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  }, []);

  const goToNextPage = useCallback(() => {
    setCurrentPage((prev) => Math.min(numPages, prev + 1));
  }, [numPages]);

  // Zoom
  const zoomIn = useCallback(() => {
    setScale((prev) => Math.min(2.0, prev + 0.1));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => Math.max(0.5, prev - 0.1));
  }, []);

  const fitToWidth = useCallback(() => {
    setScale(1.0);
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#525659]">
      {/* Toolbar */}
      <div className="h-10 bg-aura-surface border-b border-aura-border flex items-center justify-between px-2">
        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <button
            onClick={goToPrevPage}
            disabled={currentPage <= 1}
            className="p-1.5 hover:bg-aura-bg rounded disabled:opacity-30"
            title="Previous page"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm min-w-[80px] text-center">
            {numPages > 0 ? `${currentPage} / ${numPages}` : '—'}
          </span>
          <button
            onClick={goToNextPage}
            disabled={currentPage >= numPages}
            className="p-1.5 hover:bg-aura-bg rounded disabled:opacity-30"
            title="Next page"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={zoomOut}
            className="p-1.5 hover:bg-aura-bg rounded"
            title="Zoom out"
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-sm min-w-[50px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={zoomIn}
            className="p-1.5 hover:bg-aura-bg rounded"
            title="Zoom in"
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={fitToWidth}
            className="p-1.5 hover:bg-aura-bg rounded ml-1"
            title="Fit to width"
          >
            <Maximize2 size={16} />
          </button>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-auto flex items-start justify-center p-4">
        {isCompiling ? (
          <div className="flex flex-col items-center justify-center h-full text-aura-text">
            <Loader2 size={32} className="animate-spin mb-2" />
            <span className="text-sm">Compiling...</span>
          </div>
        ) : pdfUrl ? (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-full">
                <Loader2 size={32} className="animate-spin text-aura-text" />
              </div>
            }
            error={
              <div className="flex flex-col items-center justify-center h-full text-aura-error">
                <span className="text-lg mb-2">Failed to load PDF</span>
                <span className="text-sm text-aura-muted">
                  Check if the file exists and is valid
                </span>
              </div>
            }
          >
            <Page
              pageNumber={currentPage}
              scale={scale}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="shadow-lg"
            />
          </Document>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-aura-muted">
            <div className="text-center">
              <div className="text-6xl mb-4 opacity-20">📄</div>
              <p className="text-lg mb-2">No PDF to display</p>
              <p className="text-sm">
                Compile your LaTeX project to see the output
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
