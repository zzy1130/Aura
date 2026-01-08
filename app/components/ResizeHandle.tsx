'use client';

import { useCallback, useEffect, useState } from 'react';

interface ResizeHandleProps {
  onResize: (delta: number) => void;
  direction?: 'horizontal' | 'vertical';
  className?: string;
}

export default function ResizeHandle({
  onResize,
  direction = 'horizontal',
  className = ''
}: ResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    setStartPos(direction === 'horizontal' ? e.clientX : e.clientY);
  }, [direction]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY;
      const delta = currentPos - startPos;
      if (Math.abs(delta) > 0) {
        onResize(delta);
        setStartPos(currentPos);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, startPos, direction, onResize]);

  const isHorizontal = direction === 'horizontal';

  return (
    <div
      onMouseDown={handleMouseDown}
      className={`
        ${isHorizontal ? 'w-[3px] cursor-col-resize' : 'h-[3px] cursor-row-resize'}
        bg-transparent hover:bg-green2/30 transition-colors duration-200
        flex-shrink-0 relative group
        ${isDragging ? 'bg-green2/50' : ''}
        ${className}
      `}
    >
      {/* Larger hit area for easier grabbing */}
      <div
        className={`
          absolute
          ${isHorizontal ? 'inset-y-0 -left-1.5 -right-1.5' : 'inset-x-0 -top-1.5 -bottom-1.5'}
        `}
      />
      {/* Subtle visual indicator on hover */}
      <div
        className={`
          absolute opacity-0 group-hover:opacity-100 transition-opacity duration-200
          ${isHorizontal
            ? 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-0.5 h-6 rounded-full bg-green2/60'
            : 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-0.5 w-6 rounded-full bg-green2/60'
          }
        `}
      />
    </div>
  );
}
