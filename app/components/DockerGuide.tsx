'use client';

import { X, Download, ExternalLink, Box, CheckCircle } from 'lucide-react';

interface DockerGuideProps {
  isOpen: boolean;
  onClose: () => void;
  isInstalled?: boolean; // True if Docker is installed but not running
}

export default function DockerGuide({ isOpen, onClose, isInstalled = false }: DockerGuideProps) {
  if (!isOpen) return null;

  const downloadUrl = 'https://desktop.docker.com/mac/main/arm64/Docker.dmg';
  const infoUrl = 'https://www.docker.com/products/docker-desktop/';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-panel border border-border rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Box size={24} className="text-blue-500" />
            </div>
            <div>
              <h2 className="typo-heading text-primary">
                {isInstalled ? 'Start Docker Desktop' : 'Install Docker Desktop'}
              </h2>
              <p className="typo-small text-secondary">Required for LaTeX compilation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <X size={20} className="text-secondary" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Explanation */}
          <div className="bg-surface rounded-lg p-4">
            <p className="typo-body text-secondary">
              Aura uses Docker to compile LaTeX documents in a safe, isolated environment.
              This ensures consistent results and protects your system.
            </p>
          </div>

          {isInstalled ? (
            /* Docker installed but not running */
            <div className="space-y-4">
              <h3 className="typo-label text-primary">Start Docker Desktop</h3>

              <ol className="space-y-3">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">1</span>
                  <span className="typo-body text-secondary">Open <strong className="text-primary">Docker</strong> from your Applications folder</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">2</span>
                  <span className="typo-body text-secondary">Wait for the whale icon to appear in the menu bar</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">3</span>
                  <span className="typo-body text-secondary">Once it shows &quot;Docker Desktop is running&quot;, try compiling again!</span>
                </li>
              </ol>

              <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                <p className="typo-small text-yellow-600 dark:text-yellow-400">
                  <strong>Tip:</strong> You can set Docker to start automatically on login in Docker Desktop preferences.
                </p>
              </div>
            </div>
          ) : (
            /* Docker not installed */
            <div className="space-y-4">
              <h3 className="typo-label text-primary">Installation Steps</h3>

              <ol className="space-y-3">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">1</span>
                  <span className="typo-body text-secondary">Download Docker Desktop for Mac</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">2</span>
                  <span className="typo-body text-secondary">Open the downloaded .dmg file</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">3</span>
                  <span className="typo-body text-secondary">Drag Docker to your Applications folder</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">4</span>
                  <span className="typo-body text-secondary">Launch Docker from Applications</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">5</span>
                  <span className="typo-body text-secondary">Wait for Docker to start (whale icon in menu bar)</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center typo-small font-medium">6</span>
                  <span className="typo-body text-secondary">Return to Aura and compile!</span>
                </li>
              </ol>

              {/* Download Button */}
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-3 px-4 bg-accent hover:bg-accent/90 text-white rounded-lg transition-colors typo-body font-medium"
              >
                <Download size={20} />
                Download Docker Desktop
              </a>

              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 flex items-start gap-2">
                <CheckCircle size={18} className="text-green-500 flex-shrink-0 mt-0.5" />
                <p className="typo-small text-green-600 dark:text-green-400">
                  Docker Desktop is <strong>free</strong> for personal use and educational purposes.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border flex justify-between items-center">
          <a
            href={infoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 typo-small text-secondary hover:text-primary transition-colors"
          >
            Learn more about Docker
            <ExternalLink size={14} />
          </a>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface hover:bg-hover rounded-lg transition-colors typo-body"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
