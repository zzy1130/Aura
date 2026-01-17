'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Streamdown } from 'streamdown';
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  FileText,
} from 'lucide-react';

interface MarkdownPreviewProps {
  content: string;
  className?: string;
}

export default function MarkdownPreview({ content, className }: MarkdownPreviewProps) {
  const [scale, setScale] = useState<number>(1.0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Zoom controls
  const zoomIn = useCallback(() => {
    setScale((prev) => Math.min(2.0, prev + 0.1));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => Math.max(0.5, prev - 0.1));
  }, []);

  const resetZoom = useCallback(() => {
    setScale(1.0);
  }, []);

  // Mouse wheel zoom (Ctrl/Cmd + scroll)
  const handleWheel = useCallback((e: WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.05 : 0.05;
      setScale((prev) => Math.max(0.5, Math.min(2.0, prev + delta)));
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

  const isEmpty = !content || content.trim() === '';

  return (
    <div className={`h-full flex flex-col bg-fill-secondary ${className || ''}`}>
      {/* Toolbar */}
      <div className="panel-header">
        <span className="typo-small-strong text-secondary">Preview</span>

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

      {/* Markdown Content - Scrollable */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-white"
      >
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-20 h-20 rounded-full bg-black/3 flex items-center justify-center mb-4">
              <FileText size={36} className="text-tertiary" />
            </div>
            <p className="typo-large text-secondary mb-1">No content to preview</p>
            <p className="typo-small text-tertiary">
              Start typing to see the rendered Markdown
            </p>
          </div>
        ) : (
          <div
            className="p-8 max-w-4xl mx-auto"
            style={{
              transform: `scale(${scale})`,
              transformOrigin: 'top center',
              minHeight: scale > 1 ? `${100 / scale}%` : '100%',
            }}
          >
            <article className="markdown-preview-content prose prose-slate max-w-none">
              <Streamdown
                mode="static"
                shikiTheme={['github-light', 'github-light']}
                controls={{
                  code: true,
                  table: true,
                  mermaid: {
                    download: true,
                    copy: true,
                    fullscreen: true,
                    panZoom: true,
                  },
                }}
              >
                {content}
              </Streamdown>
            </article>
          </div>
        )}
      </div>
    </div>
  );
}
