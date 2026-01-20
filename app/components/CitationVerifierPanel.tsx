'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Check,
} from 'lucide-react';
import { api, VerificationResult } from '../lib/api';

interface CitationVerifierPanelProps {
  projectPath: string;
  onClose: () => void;
}

interface VerifierStats {
  verified: number;
  warnings: number;
  errors: number;
}

export default function CitationVerifierPanel({
  projectPath,
  onClose,
}: CitationVerifierPanelProps) {
  const [results, setResults] = useState<Map<string, VerificationResult>>(new Map());
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [stats, setStats] = useState<VerifierStats>({ verified: 0, warnings: 0, errors: 0 });
  const [isRunning, setIsRunning] = useState(false);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load initial state
  useEffect(() => {
    const loadState = async () => {
      try {
        const state = await api.getVerifierState(projectPath);
        setApproved(new Set(state.approved_citations));
      } catch (e) {
        console.error('Failed to load verifier state:', e);
      }
    };
    loadState();
  }, [projectPath]);

  // Run verification
  const runVerification = useCallback(async () => {
    if (isRunning) return;

    setIsRunning(true);
    setResults(new Map());
    setStats({ verified: 0, warnings: 0, errors: 0 });

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(api.getVerifyReferencesUrl(projectPath), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());

              if (data.cite_key) {
                // This is a verification result
                setResults((prev) => {
                  const next = new Map(prev);
                  next.set(data.cite_key, data as VerificationResult);
                  return next;
                });
              } else if (data.verified !== undefined) {
                // This is the final stats
                setStats(data);
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name !== 'AbortError') {
        console.error('Verification error:', error);
      }
    } finally {
      setIsRunning(false);
      abortControllerRef.current = null;
    }
  }, [projectPath, isRunning]);

  // Auto-run on mount
  useEffect(() => {
    runVerification();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Approve a citation
  const handleApprove = async (citeKey: string) => {
    try {
      await api.approveCitation(projectPath, citeKey);
      setApproved((prev) => new Set([...prev, citeKey]));
      setResults((prev) => {
        const next = new Map(prev);
        const result = next.get(citeKey);
        if (result) {
          next.set(citeKey, { ...result, status: 'verified' });
        }
        return next;
      });
    } catch (e) {
      console.error('Failed to approve:', e);
    }
  };

  // Toggle expansion
  const toggleExpand = (citeKey: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(citeKey)) {
        next.delete(citeKey);
      } else {
        next.add(citeKey);
      }
      return next;
    });
  };

  // Sort results: errors first, then warnings, then verified
  const sortedResults = Array.from(results.values()).sort((a, b) => {
    const order = { error: 0, warning: 1, pending: 2, verified: 3 };
    return order[a.status] - order[b.status];
  });

  return (
    <div className="h-full flex flex-col bg-fill-secondary">
      {/* Header */}
      <div className="panel-header bg-white border-b border-black/6">
        <div className="flex items-center justify-between w-full">
          <h2 className="typo-h4 flex items-center gap-2">
            Reference Verification
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={runVerification}
              disabled={isRunning}
              className="btn-ghost typo-small flex items-center gap-1.5"
            >
              <RefreshCw size={14} className={isRunning ? 'animate-spin' : ''} />
              {isRunning ? 'Verifying...' : 'Run Again'}
            </button>
            <button
              onClick={onClose}
              className="btn-ghost typo-small"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="px-4 py-2 bg-white border-b border-black/6 flex items-center gap-4">
        <span className="typo-small flex items-center gap-1.5 text-success">
          <CheckCircle size={14} />
          {stats.verified} verified
        </span>
        <span className="typo-small flex items-center gap-1.5 text-orange1">
          <AlertTriangle size={14} />
          {stats.warnings} warnings
        </span>
        <span className="typo-small flex items-center gap-1.5 text-error">
          <XCircle size={14} />
          {stats.errors} errors
        </span>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sortedResults.length === 0 && isRunning && (
          <div className="text-center py-8 text-secondary">
            <Loader2 size={24} className="animate-spin mx-auto mb-2" />
            <p className="typo-small">Verifying references...</p>
          </div>
        )}

        {sortedResults.map((result) => (
          <CitationCard
            key={result.cite_key}
            result={result}
            isExpanded={expandedKeys.has(result.cite_key)}
            isApproved={approved.has(result.cite_key)}
            onToggleExpand={() => toggleExpand(result.cite_key)}
            onApprove={() => handleApprove(result.cite_key)}
          />
        ))}
      </div>
    </div>
  );
}

// Individual citation card
function CitationCard({
  result,
  isExpanded,
  isApproved,
  onToggleExpand,
  onApprove,
}: {
  result: VerificationResult;
  isExpanded: boolean;
  isApproved: boolean;
  onToggleExpand: () => void;
  onApprove: () => void;
}) {
  const statusIcon = {
    verified: <CheckCircle size={16} className="text-success" />,
    warning: <AlertTriangle size={16} className="text-orange1" />,
    error: <XCircle size={16} className="text-error" />,
    pending: <Loader2 size={16} className="text-tertiary animate-spin" />,
  }[result.status];

  const statusClass = {
    verified: 'border-success/20 bg-success/5',
    warning: 'border-orange1/20 bg-orange1/5',
    error: 'border-error/20 bg-error/5',
    pending: 'border-black/6 bg-white',
  }[result.status];

  return (
    <div className={`rounded-yw-lg border p-3 ${statusClass}`}>
      {/* Header row */}
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={onToggleExpand}
      >
        {isExpanded ? (
          <ChevronDown size={14} className="text-tertiary" />
        ) : (
          <ChevronRight size={14} className="text-tertiary" />
        )}
        {statusIcon}
        <span className="typo-small-strong flex-1 font-mono">{result.cite_key}</span>

        {/* Actions */}
        {result.status !== 'verified' && !isApproved && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onApprove();
            }}
            className="btn-ghost typo-ex-small flex items-center gap-1 text-success"
          >
            <Check size={12} />
            Approve
          </button>
        )}
      </div>

      {/* Title */}
      {result.matched_paper && (
        <div className="mt-1 ml-6 typo-small text-secondary">
          &quot;{result.matched_paper.title}&quot; ({result.matched_paper.year || 'n.d.'})
        </div>
      )}

      {/* Issues */}
      {result.metadata_issues.length > 0 && (
        <div className="mt-1 ml-6 typo-ex-small text-orange1">
          {result.metadata_issues.join(', ')}
        </div>
      )}

      {/* Context score */}
      {result.checked_via !== 'skipped' && (
        <div className="mt-1 ml-6 typo-ex-small text-tertiary">
          {result.usages.length} usage{result.usages.length !== 1 ? 's' : ''} ·
          Context: {result.context_explanation || `${(result.context_score * 100).toFixed(0)}% confidence`}
        </div>
      )}

      {/* Expanded details */}
      {isExpanded && (
        <div className="mt-3 ml-6 space-y-2">
          {/* Paper link */}
          {result.matched_paper?.url && (
            <a
              href={result.matched_paper.url}
              target="_blank"
              rel="noopener noreferrer"
              className="typo-small text-green1 flex items-center gap-1 hover:underline"
            >
              <ExternalLink size={12} />
              View on Semantic Scholar
            </a>
          )}

          {/* Usages */}
          {result.usages.length > 0 && (
            <div>
              <div className="typo-ex-small text-tertiary mb-1">Usages in document:</div>
              {result.usages.map((usage, i) => (
                <div key={i} className="typo-ex-small bg-white rounded p-2 mb-1 border border-black/6">
                  <div className="text-tertiary">Line {usage.line_number}</div>
                  <div className="text-primary italic">&quot;{usage.claim}&quot;</div>
                </div>
              ))}
            </div>
          )}

          {/* BibTeX info */}
          {result.bib_entry && (
            <div>
              <div className="typo-ex-small text-tertiary mb-1">BibTeX fields:</div>
              <pre className="typo-ex-small bg-white rounded p-2 border border-black/6 overflow-x-auto font-mono">
                {JSON.stringify(result.bib_entry.fields, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
