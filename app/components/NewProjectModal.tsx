'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { X } from 'lucide-react';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string) => void;
}

export default function NewProjectModal({
  isOpen,
  onClose,
  onSubmit,
}: NewProjectModalProps) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('');
      setError('');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      const trimmedName = name.trim();
      if (!trimmedName) {
        setError('Project name is required');
        return;
      }

      // Validate name (alphanumeric, hyphens, underscores)
      if (!/^[a-zA-Z0-9_-]+$/.test(trimmedName)) {
        setError('Name can only contain letters, numbers, hyphens, and underscores');
        return;
      }

      onSubmit(trimmedName);
      onClose();
    },
    [name, onSubmit, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      <div
        className="bg-aura-surface rounded-lg shadow-xl w-[400px] max-w-[90vw]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-aura-border">
          <h2 className="text-lg font-medium">New Project</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-aura-bg rounded"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4">
          <label className="block text-sm text-aura-muted mb-2">
            Project Name
          </label>
          <input
            ref={inputRef}
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError('');
            }}
            placeholder="my-research-paper"
            className="w-full bg-aura-bg border border-aura-border rounded px-3 py-2 text-sm focus:outline-none focus:border-aura-accent"
          />
          {error && (
            <p className="text-aura-error text-sm mt-2">{error}</p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm hover:bg-aura-bg rounded"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm bg-aura-accent text-aura-bg rounded hover:bg-aura-accent/80"
            >
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
