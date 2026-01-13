'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Send,
  User,
  Loader2,
  Code,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Sparkles,
  Square,
  MessageSquare,
  Microscope,
  Plus,
} from 'lucide-react';
import { PendingEdit } from './Editor';
import PlanDisplay, { Plan, PlanStep } from './PlanDisplay';
import VibeResearchView from './VibeResearchView';
import { api, VibeSessionSummary } from '../lib/api';

// Mode types
type AgentMode = 'chat' | 'vibe';

interface AgentPanelProps {
  projectPath: string | null;
  onApprovalRequest?: (edit: PendingEdit) => void;
  onApprovalResolved?: () => void;
  onOpenFile?: (filePath: string) => void;
}

interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'success' | 'error' | 'waiting_approval';
}

interface MessagePart {
  type: 'text' | 'tool';
  content?: string;
  toolCall?: ToolCall;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  parts: MessagePart[];
  timestamp: Date;
}

// Tool call display component
function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusIcon = {
    pending: <Loader2 size={14} className="text-tertiary" />,
    running: <Loader2 size={14} className="text-green2 animate-spin" />,
    waiting_approval: <AlertCircle size={14} className="text-orange1" />,
    success: <CheckCircle size={14} className="text-success" />,
    error: <XCircle size={14} className="text-error" />,
  }[toolCall.status];

  const statusLabel = {
    pending: '',
    running: '',
    waiting_approval: 'awaiting approval',
    success: '',
    error: '',
  }[toolCall.status];

  return (
    <div className="bg-fill-secondary rounded-yw-lg p-2.5 my-2 border border-black/6">
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {isExpanded ? (
          <ChevronDown size={14} className="text-tertiary" />
        ) : (
          <ChevronRight size={14} className="text-tertiary" />
        )}
        <Code size={14} className="text-green2" />
        <span className="typo-small-strong text-green1">{toolCall.name}</span>
        {statusLabel && (
          <span className="badge badge-warning typo-ex-small">{statusLabel}</span>
        )}
        <span className="flex-1" />
        {statusIcon}
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-2">
          <div>
            <div className="typo-ex-small text-tertiary mb-1">Arguments</div>
            <pre className="bg-white p-2.5 rounded-yw-md text-xs overflow-x-auto border border-black/6 font-mono">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>

          {toolCall.result && (
            <div>
              <div className="typo-ex-small text-tertiary mb-1">Result</div>
              <pre className="bg-white p-2.5 rounded-yw-md text-xs overflow-x-auto max-h-32 overflow-y-auto border border-black/6 font-mono">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Text part display
function TextPartDisplay({ content }: { content: string }) {
  if (!content.trim()) return null;

  return (
    <div className="typo-body prose prose-sm max-w-none prose-headings:text-primary prose-p:text-primary prose-strong:text-primary prose-code:text-green1 prose-code:bg-green3/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-fill-secondary prose-pre:border prose-pre:border-black/6 prose-ul:text-primary prose-ol:text-primary prose-li:text-primary my-1">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

// Message display component
function MessageDisplay({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`
        rounded-yw-xl p-3 animate-fade-in-up
        ${isUser
          ? 'bg-green3/50 border border-green2/20 ml-8'
          : 'bg-white border border-black/6'
        }
      `}
    >
      <div className="flex items-start gap-2.5">
        <div
          className={`
            w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0
            ${isUser ? 'bg-green2' : 'bg-green3'}
          `}
        >
          {isUser ? (
            <User size={14} className="text-white" />
          ) : (
            <Sparkles size={14} className="text-green1" />
          )}
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          {isUser ? (
            <div className="typo-body whitespace-pre-wrap break-words">
              {message.parts[0]?.content || ''}
            </div>
          ) : (
            <div className="space-y-1">
              {message.parts.map((part, index) => (
                part.type === 'text' ? (
                  <TextPartDisplay key={index} content={part.content || ''} />
                ) : part.toolCall ? (
                  <ToolCallDisplay key={index} toolCall={part.toolCall} />
                ) : null
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgentPanel({
  projectPath,
  onApprovalRequest,
  onApprovalResolved,
  onOpenFile,
}: AgentPanelProps) {
  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const pendingMessageRef = useRef<string | null>(null);

  // Mode state
  const [mode, setMode] = useState<AgentMode>('chat');
  const [vibeSessions, setVibeSessions] = useState<VibeSessionSummary[]>([]);
  const [selectedVibeSession, setSelectedVibeSession] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [showNewResearchInput, setShowNewResearchInput] = useState(false);
  const [newResearchTopic, setNewResearchTopic] = useState('');
  const [isStartingResearch, setIsStartingResearch] = useState(false);

  const loadVibeSessions = useCallback(async () => {
    if (!projectPath) return;
    setIsLoadingSessions(true);
    try {
      const result = await api.listVibeSessions(projectPath);
      setVibeSessions(result.sessions);
      // Auto-select first incomplete session if none selected
      if (result.sessions.length > 0) {
        const incomplete = result.sessions.find(s => !s.is_complete);
        if (incomplete) {
          setSelectedVibeSession(incomplete.session_id);
        }
      }
    } catch (e) {
      console.error('Failed to load vibe sessions:', e);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [projectPath]);

  // Load vibe sessions when mode changes or project changes
  useEffect(() => {
    if (mode === 'vibe' && projectPath) {
      loadVibeSessions();
    }
  }, [mode, projectPath, loadVibeSessions]);

  const startNewResearch = async () => {
    if (!projectPath || !newResearchTopic.trim()) return;
    setIsStartingResearch(true);
    try {
      const session = await api.startVibeResearch(projectPath, newResearchTopic.trim());
      setSelectedVibeSession(session.session_id);
      setShowNewResearchInput(false);
      setNewResearchTopic('');
      await loadVibeSessions();
    } catch (e) {
      console.error('Failed to start research:', e);
    } finally {
      setIsStartingResearch(false);
    }
  };

  // Keep ref in sync with state for use in callbacks
  useEffect(() => {
    pendingMessageRef.current = pendingMessage;
  }, [pendingMessage]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-scroll to pending message when it changes
  useEffect(() => {
    if (pendingMessage) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [pendingMessage]);

  // Reference to sendMessage for use in effect
  const sendMessageRef = useRef<(content?: string) => Promise<void>>();

  // Track previous streaming state to detect when it ends
  const wasStreamingRef = useRef(false);
  useEffect(() => {
    // When streaming ends and there's a pending message, send it
    if (wasStreamingRef.current && !isStreaming && pendingMessageRef.current) {
      const pending = pendingMessageRef.current;
      setPendingMessage(null);
      // Use setTimeout to ensure state updates have propagated
      setTimeout(() => {
        sendMessageRef.current?.(pending);
      }, 100);
    }
    wasStreamingRef.current = isStreaming;
  }, [isStreaming]);

  // Send message to agent
  const sendMessage = useCallback(async (messageContent?: string) => {
    const content = messageContent || input.trim();
    if (!content || isStreaming || !projectPath) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      parts: [{ type: 'text', content }],
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!messageContent) {
      setInput('');
    }
    setIsStreaming(true);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      parts: [],
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      let backendUrl = 'http://127.0.0.1:8000';
      if (typeof window !== 'undefined' && window.aura) {
        backendUrl = await window.aura.getBackendUrl();
      }

      const response = await fetch(`${backendUrl}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          project_path: projectPath,
          history: messages.map((m) => ({
            role: m.role,
            content: m.parts
              .filter((p) => p.type === 'text')
              .map((p) => p.content)
              .join('\n'),
          })),
        }),
        signal: abortControllerRef.current?.signal,
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
          if (line.startsWith('event:')) continue;

          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());

              if (data.type === 'text_delta' && data.content) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIndex = updated.length - 1;
                  const last = updated[lastIndex];
                  if (last.role === 'assistant') {
                    const parts = [...last.parts];
                    const lastPart = parts[parts.length - 1];

                    if (lastPart && lastPart.type === 'text') {
                      parts[parts.length - 1] = {
                        ...lastPart,
                        content: (lastPart.content || '') + data.content,
                      };
                    } else {
                      parts.push({ type: 'text', content: data.content });
                    }

                    updated[lastIndex] = { ...last, parts };
                  }
                  return updated;
                });
              } else if (data.type === 'tool_call') {
                const toolCall: ToolCall = {
                  id: data.tool_call_id || crypto.randomUUID(),
                  name: data.tool_name,
                  args: data.args || {},
                  status: 'running',
                };
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIndex = updated.length - 1;
                  const last = updated[lastIndex];
                  if (last.role === 'assistant') {
                    const parts = [...last.parts, { type: 'tool' as const, toolCall }];
                    updated[lastIndex] = { ...last, parts };
                  }
                  return updated;
                });
              } else if (data.type === 'tool_result') {
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIndex = updated.length - 1;
                  const last = updated[lastIndex];
                  if (last.role === 'assistant') {
                    const parts = [...last.parts];
                    let matched = false;

                    // First try to match by tool_call_id (exact match)
                    if (data.tool_call_id) {
                      for (let i = 0; i < parts.length; i++) {
                        const part = parts[i];
                        if (part.type === 'tool' && part.toolCall &&
                            part.toolCall.id === data.tool_call_id) {
                          parts[i] = {
                            ...part,
                            toolCall: { ...part.toolCall, result: data.result, status: 'success' },
                          };
                          matched = true;
                          break;
                        }
                      }
                    }

                    // If no ID match, match by name (iterate forwards to match in order)
                    if (!matched) {
                      for (let i = 0; i < parts.length; i++) {
                        const part = parts[i];
                        if (part.type === 'tool' && part.toolCall) {
                          const tc = part.toolCall;
                          if (tc.name === data.tool_name &&
                              (tc.status === 'running' || tc.status === 'waiting_approval')) {
                            parts[i] = {
                              ...part,
                              toolCall: { ...tc, result: data.result, status: 'success' },
                            };
                            break;
                          }
                        }
                      }
                    }

                    updated[lastIndex] = { ...last, parts };
                  }
                  return updated;
                });
              } else if (data.type === 'error') {
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIndex = updated.length - 1;
                  const last = updated[lastIndex];
                  if (last.role === 'assistant') {
                    const parts = [...last.parts];
                    parts.push({
                      type: 'text',
                      content: `\n\n**Error:** ${data.message || 'Unknown error'}`
                    });
                    updated[lastIndex] = { ...last, parts };
                  }
                  return updated;
                });
              } else if (data.type === 'approval_required') {
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIndex = updated.length - 1;
                  const last = updated[lastIndex];
                  if (last.role === 'assistant') {
                    const parts = [...last.parts];
                    for (let i = parts.length - 1; i >= 0; i--) {
                      const part = parts[i];
                      if (part.type === 'tool' && part.toolCall &&
                          part.toolCall.name === data.tool_name &&
                          part.toolCall.status === 'running') {
                        parts[i] = {
                          ...part,
                          toolCall: { ...part.toolCall, status: 'waiting_approval' },
                        };
                        break;
                      }
                    }
                    updated[lastIndex] = { ...last, parts };
                  }
                  return updated;
                });

                if (onApprovalRequest && data.tool_name === 'edit_file') {
                  onApprovalRequest({
                    request_id: data.request_id,
                    filepath: data.tool_args?.filepath || '',
                    old_string: data.tool_args?.old_string || '',
                    new_string: data.tool_args?.new_string || '',
                  });
                } else if (onApprovalRequest && data.tool_name === 'write_file') {
                  onApprovalRequest({
                    request_id: data.request_id,
                    filepath: data.tool_args?.filepath || '',
                    old_string: '',
                    new_string: data.tool_args?.content || '',
                  });
                }
              } else if (data.type === 'approval_resolved') {
                onApprovalResolved?.();
              } else if (data.type === 'plan_created') {
                // A new plan was created
                console.log('[Agent] Plan created event:', data);
                setCurrentPlan({
                  plan_id: data.plan_id,
                  goal: data.goal,
                  complexity: data.complexity,
                  steps: (data.steps || []).map((s: { step_number: number; title: string; description?: string; status?: string; files?: string[] }) => ({
                    step_number: s.step_number,
                    title: s.title,
                    description: s.description || '',
                    status: (s.status || 'pending') as PlanStep['status'],
                    files: s.files || [],
                  })),
                });
              } else if (data.type === 'plan_step') {
                // A plan step status changed
                console.log('[Agent] Plan step event:', data);
                setCurrentPlan((prev) => {
                  if (!prev || prev.plan_id !== data.plan_id) return prev;
                  return {
                    ...prev,
                    steps: prev.steps.map((step) =>
                      step.step_number === data.step_number
                        ? { ...step, status: data.status as PlanStep['status'] }
                        : step
                    ),
                  };
                });
              } else if (data.type === 'plan_completed') {
                // Plan finished - mark all steps as their final status
                // Keep the plan visible so user can see completion
              }
            } catch (e) {
              console.error('[Agent] JSON parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Agent stream error:', error);
      setMessages((prev) => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        const last = updated[lastIndex];
        if (last.role === 'assistant') {
          const parts = [...last.parts];
          parts.push({
            type: 'text',
            content: `**Error:** ${error instanceof Error ? error.message : 'Unknown error'}`
          });
          updated[lastIndex] = { ...last, parts };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [input, isStreaming, projectPath, messages, onApprovalRequest, onApprovalResolved]);

  // Keep sendMessageRef in sync
  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  // Stop the current generation
  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);

    // Add a note that generation was stopped
    setMessages((prev) => {
      const updated = [...prev];
      const lastIndex = updated.length - 1;
      const last = updated[lastIndex];
      if (last.role === 'assistant') {
        const parts = [...last.parts];
        parts.push({ type: 'text', content: '\n\n*[Generation stopped]*' });
        updated[lastIndex] = { ...last, parts };
      }
      return updated;
    });
  }, []);

  // Queue a message to be sent after current generation
  const queuePendingMessage = useCallback(() => {
    if (!input.trim()) return;
    setPendingMessage(input.trim());
    setInput('');
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
  }, [input]);

  // Clear pending message
  const clearPendingMessage = useCallback(() => {
    setPendingMessage(null);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (isStreaming) {
          queuePendingMessage();
        } else {
          sendMessage();
        }
      }
    },
    [sendMessage, queuePendingMessage, isStreaming]
  );

  return (
    <div className="h-full flex flex-col bg-fill-secondary">
      {/* Header with Mode Toggle */}
      <div className="panel-header bg-white">
        <div className="flex items-center gap-2 w-full">
          {/* Mode toggle buttons */}
          <div className="flex items-center bg-fill-secondary rounded-yw-lg p-0.5">
            <button
              onClick={() => setMode('chat')}
              disabled={isStreaming}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-yw-md typo-small transition-all ${
                mode === 'chat'
                  ? 'bg-white text-green1 shadow-sm'
                  : 'text-secondary hover:text-primary'
              } ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <MessageSquare size={14} />
              Chat
            </button>
            <button
              onClick={() => setMode('vibe')}
              disabled={isStreaming}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-yw-md typo-small transition-all ${
                mode === 'vibe'
                  ? 'bg-white text-green1 shadow-sm'
                  : 'text-secondary hover:text-primary'
              } ${isStreaming ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Microscope size={14} />
              Vibe Research
            </button>
          </div>
        </div>
      </div>

      {/* Content based on mode */}
      {mode === 'chat' ? (
        <>
          {/* Chat Messages */}
          <div className="flex-1 overflow-auto p-3 space-y-3">
        {messages.length === 0 && !currentPlan ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center px-6">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green3 flex items-center justify-center">
                <Sparkles size={28} className="text-green1" />
              </div>
              <h3 className="typo-h3 mb-2">Ask the AI Assistant</h3>
              <p className="typo-small text-secondary">
                Research papers, write LaTeX, fix errors, and more
              </p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageDisplay key={msg.id} message={msg} />
            ))}
            {/* Pending message box */}
            {pendingMessage && (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-yw-lg bg-orange2/30 border border-orange1/30 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Loader2 size={12} className="text-orange1 animate-spin" />
                    <span className="typo-ex-small text-orange1">Pending - will send when current generation ends</span>
                  </div>
                  <div className="typo-body text-primary">{pendingMessage}</div>
                  <button
                    onClick={clearPendingMessage}
                    className="mt-2 typo-ex-small text-tertiary hover:text-error transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {/* Active Plan Display - appears inline after messages */}
            {currentPlan && (
              <PlanDisplay
                plan={currentPlan}
                onClear={() => setCurrentPlan(null)}
              />
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

          {/* Chat Input */}
          <div className="border-t border-black/6 p-3 bg-white">
            <div className="relative flex gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  // Auto-resize textarea
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                }}
                onKeyDown={handleKeyDown}
                placeholder={
                  !projectPath
                    ? "Open a project first"
                    : isStreaming
                    ? "Queue next message..."
                    : "Ask the assistant..."
                }
                disabled={!projectPath || !!pendingMessage}
                className={`flex-1 min-h-[44px] max-h-[200px] rounded-yw-lg border bg-white pl-3 pr-3 py-2.5 typo-body placeholder:text-tertiary focus:outline-none focus:ring-1 transition-colors resize-none overflow-y-auto ${
                  isStreaming
                    ? 'border-orange1/20 focus:border-orange1 focus:ring-orange1/20'
                    : 'border-black/12 focus:border-green2 focus:ring-green2/20'
                }`}
                rows={1}
              />
              {isStreaming ? (
                <>
                  {/* Queue button - only show when there's input and no pending message */}
                  {input.trim() && !pendingMessage && (
                    <button
                      onClick={queuePendingMessage}
                      className="flex h-[44px] w-[44px] items-center justify-center rounded-yw-lg bg-orange1 text-white hover:opacity-90 transition-all flex-shrink-0"
                      title="Queue message"
                    >
                      <Send size={14} />
                    </button>
                  )}
                  {/* Stop button */}
                  <button
                    onClick={stopGeneration}
                    className="flex h-[44px] w-[44px] items-center justify-center rounded-yw-lg bg-error text-white hover:opacity-90 transition-all flex-shrink-0"
                    title="Stop generation"
                  >
                    <Square size={14} fill="currentColor" />
                  </button>
                </>
              ) : (
                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || !projectPath}
                  className={`flex h-[44px] w-[44px] items-center justify-center rounded-yw-lg transition-all flex-shrink-0 ${
                    !input.trim() || !projectPath
                      ? 'bg-black/6 text-tertiary cursor-not-allowed'
                      : 'bg-green1 text-white hover:opacity-90'
                  }`}
                >
                  <Send size={14} />
                </button>
              )}
            </div>
          </div>
        </>
      ) : (
        /* Vibe Research Mode */
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Session selector */}
          <div className="p-3 border-b border-black/6 bg-white">
            <div className="flex items-center gap-2">
              <select
                value={selectedVibeSession || ''}
                onChange={(e) => setSelectedVibeSession(e.target.value || null)}
                className="flex-1 rounded-yw-md border border-black/12 bg-white px-3 py-2 typo-small focus:outline-none focus:ring-1 focus:ring-green2/20"
                disabled={isLoadingSessions}
              >
                <option value="">Select a research session...</option>
                {vibeSessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.topic.slice(0, 40)}{session.topic.length > 40 ? '...' : ''}
                    ({session.current_phase}{session.is_complete ? ' - Complete' : ''})
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowNewResearchInput(true)}
                className="flex h-[36px] w-[36px] items-center justify-center rounded-yw-md bg-green1 text-white hover:opacity-90 transition-all flex-shrink-0"
                title="New research"
              >
                <Plus size={14} />
              </button>
            </div>

            {/* New research input */}
            {showNewResearchInput && (
              <div className="mt-3 p-3 bg-fill-secondary rounded-yw-lg">
                <div className="typo-small-strong mb-2">Start New Research</div>
                <textarea
                  value={newResearchTopic}
                  onChange={(e) => setNewResearchTopic(e.target.value)}
                  placeholder="Enter your research topic or question..."
                  className="w-full rounded-yw-md border border-black/12 bg-white px-3 py-2 typo-small focus:outline-none focus:ring-1 focus:ring-green2/20 resize-none"
                  rows={2}
                />
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={startNewResearch}
                    disabled={!newResearchTopic.trim() || isStartingResearch}
                    className="btn-primary typo-small flex items-center gap-1"
                  >
                    {isStartingResearch ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Microscope size={12} />
                    )}
                    Start Research
                  </button>
                  <button
                    onClick={() => {
                      setShowNewResearchInput(false);
                      setNewResearchTopic('');
                    }}
                    className="btn-ghost typo-small"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Vibe Research View */}
          {selectedVibeSession && projectPath ? (
            <VibeResearchView
              projectPath={projectPath}
              sessionId={selectedVibeSession}
              onComplete={loadVibeSessions}
              onDelete={() => {
                setSelectedVibeSession(null);
                loadVibeSessions();
              }}
              onOpenFile={onOpenFile}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center px-6">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-100 flex items-center justify-center">
                  <Microscope size={28} className="text-purple-600" />
                </div>
                <h3 className="typo-h3 mb-2">Vibe Research</h3>
                <p className="typo-small text-secondary mb-4">
                  AI-led autonomous research that discovers papers, identifies gaps, and generates novel hypotheses
                </p>
                <button
                  onClick={() => setShowNewResearchInput(true)}
                  className="btn-primary flex items-center gap-2 mx-auto"
                >
                  <Plus size={14} />
                  Start New Research
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
