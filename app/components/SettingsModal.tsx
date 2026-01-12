'use client';

import { useState, useCallback, useEffect } from 'react';
import { X, Link, Eye, EyeOff, Loader2, Check, AlertCircle } from 'lucide-react';
import { api, SyncStatus } from '@/lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string | null;
  onSyncSetup?: () => void;
}

export default function SettingsModal({
  isOpen,
  onClose,
  projectPath,
  onSyncSetup,
}: SettingsModalProps) {
  // Overleaf settings
  const [overleafUrl, setOverleafUrl] = useState('');
  const [token, setToken] = useState('');
  const [showToken, setShowToken] = useState(false);

  // Status
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

  // Load current sync status on mount
  useEffect(() => {
    if (isOpen && projectPath) {
      loadSyncStatus();
    }
  }, [isOpen, projectPath]);

  const loadSyncStatus = async () => {
    if (!projectPath) return;

    try {
      const status = await api.getSyncStatus(projectPath);
      setSyncStatus(status);
      if (status.remote_url) {
        // Extract clean URL (without credentials)
        const cleanUrl = status.remote_url.replace(/https:\/\/[^@]+@/, 'https://');
        setOverleafUrl(cleanUrl);
      }
    } catch (e) {
      console.error('Failed to load sync status:', e);
    }
  };

  const handleSetup = useCallback(async () => {
    console.log('[SettingsModal] handleSetup called', { projectPath, overleafUrl, token: token ? '***' : 'empty' });

    if (!projectPath) {
      setError('No project open');
      return;
    }

    if (!overleafUrl) {
      setError('Please enter an Overleaf URL');
      return;
    }

    // Clean URL - remove any embedded credentials (e.g., git@ or user:pass@)
    const cleanUrl = overleafUrl.replace(/https:\/\/[^@]+@/, 'https://');

    // Validate URL format
    if (!cleanUrl.startsWith('https://git.overleaf.com/')) {
      setError('Invalid URL. Should be: https://git.overleaf.com/<project_id>');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await api.setupSync(
        projectPath,
        overleafUrl,  // Send original URL, backend will clean it
        undefined,
        token || undefined,
      );

      if (result.success) {
        setSuccess(result.message);
        await loadSyncStatus();
        onSyncSetup?.();
      } else {
        setError(result.message);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Setup failed');
    } finally {
      setIsLoading(false);
    }
  }, [projectPath, overleafUrl, token, onSyncSetup]);

  const handleTest = useCallback(async () => {
    if (!projectPath) return;

    setIsTesting(true);
    setError(null);
    setSuccess(null);

    try {
      const status = await api.getSyncStatus(projectPath);
      setSyncStatus(status);

      if (status.status === 'not_initialized') {
        setError('Not connected to Overleaf. Please set up sync first.');
      } else if (status.status === 'error') {
        setError(status.error_message || 'Connection error');
      } else {
        setSuccess(`Connected! Status: ${status.status}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test failed');
    } finally {
      setIsTesting(false);
    }
  }, [projectPath]);

  if (!isOpen) return null;

  console.log('[SettingsModal] Rendering with projectPath:', projectPath);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 z-0"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg bg-white rounded-yw-2xl shadow-xl animate-fadeInUp">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/6">
          <h2 className="typo-h2">Settings</h2>
          <button
            onClick={onClose}
            className="btn-icon"
          >
            <X size={18} className="text-secondary" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Overleaf Sync Section */}
          <div>
            <h3 className="typo-body-strong mb-3 flex items-center gap-2">
              <Link size={16} className="text-green2" />
              Overleaf Sync
            </h3>

            {/* Current Status */}
            {syncStatus && (
              <div className={`mb-4 p-3 rounded-yw-lg ${
                syncStatus.status === 'clean' ? 'bg-success/10' :
                syncStatus.status === 'not_initialized' ? 'bg-black/5' :
                'bg-warn/10'
              }`}>
                <div className="flex items-center gap-2">
                  {syncStatus.status === 'clean' ? (
                    <Check size={14} className="text-success" />
                  ) : syncStatus.status === 'not_initialized' ? (
                    <AlertCircle size={14} className="text-tertiary" />
                  ) : (
                    <AlertCircle size={14} className="text-warn" />
                  )}
                  <span className="typo-small">
                    {syncStatus.status === 'not_initialized' ? 'Not connected' :
                     syncStatus.status === 'clean' ? 'Synced with Overleaf' :
                     syncStatus.status === 'local_changes' ? 'Local changes pending' :
                     syncStatus.status === 'ahead' ? `${syncStatus.commits_ahead} commits to push` :
                     syncStatus.status === 'behind' ? `${syncStatus.commits_behind} commits to pull` :
                     syncStatus.status === 'diverged' ? 'Local and remote have diverged' :
                     syncStatus.status}
                  </span>
                </div>
                {syncStatus.last_sync && (
                  <span className="typo-ex-small text-tertiary block mt-1">
                    Last sync: {new Date(syncStatus.last_sync).toLocaleString()}
                  </span>
                )}
              </div>
            )}

            {/* Overleaf URL Input */}
            <div className="space-y-3">
              <div>
                <label className="typo-small text-secondary block mb-1.5">
                  Overleaf Git URL
                </label>
                <input
                  type="url"
                  value={overleafUrl}
                  onChange={(e) => setOverleafUrl(e.target.value)}
                  placeholder="https://git.overleaf.com/..."
                  className="input-field w-full"
                />
                <p className="typo-ex-small text-tertiary mt-1">
                  Find this in Overleaf: Menu &rarr; Git &rarr; Clone URL
                </p>
              </div>

              <div>
                <label className="typo-small text-secondary block mb-1.5">
                  Git Token
                </label>
                <div className="relative">
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="olp_xxxxxxxxxxxx"
                    className="input-field w-full pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-secondary"
                  >
                    {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <p className="typo-ex-small text-tertiary mt-1">
                  Create token in Overleaf: Account &rarr; Settings &rarr; Git Integration
                </p>
              </div>
            </div>

            {/* Error/Success Messages */}
            {error && (
              <div className="mt-3 p-3 bg-error/10 rounded-yw-lg">
                <span className="typo-small text-error">{error}</span>
              </div>
            )}
            {success && (
              <div className="mt-3 p-3 bg-success/10 rounded-yw-lg">
                <span className="typo-small text-success">{success}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 mt-4">
              {!projectPath && (
                <p className="typo-small text-warn mb-2 w-full">Open a project first to connect to Overleaf</p>
              )}
              <button
                onClick={() => {
                  console.log('[SettingsModal] Connect button clicked');
                  handleSetup();
                }}
                disabled={isLoading || !projectPath}
                className={`btn-primary flex-1 ${!projectPath ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={14} className="animate-spin mr-2" />
                    Connecting...
                  </>
                ) : (
                  'Connect to Overleaf'
                )}
              </button>
              <button
                onClick={handleTest}
                disabled={isTesting || !projectPath || !syncStatus?.has_remote}
                className="btn-secondary"
              >
                {isTesting ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  'Test'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-black/6 flex justify-end">
          <button
            onClick={onClose}
            className="btn-ghost"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
