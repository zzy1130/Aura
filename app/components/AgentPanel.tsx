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
  Zap,
} from 'lucide-react';
import { PendingEdit } from './Editor';

interface AgentPanelProps {
  projectPath: string | null;
  onApprovalRequest?: (edit: PendingEdit) => void;
  onApprovalResolved?: () => void;
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
}: AgentPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message to agent
  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming || !projectPath) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      parts: [{ type: 'text', content: input.trim() }],
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

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
          message: userMessage.parts[0]?.content || '',
          project_path: projectPath,
          history: messages.map((m) => ({
            role: m.role,
            content: m.parts
              .filter((p) => p.type === 'text')
              .map((p) => p.content)
              .join('\n'),
          })),
        }),
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
    }
  }, [input, isStreaming, projectPath, messages, onApprovalRequest, onApprovalResolved]);

  // Send steering message to redirect agent while it's running
  const sendSteering = useCallback(async () => {
    if (!input.trim() || !projectPath) return;

    const steeringContent = input.trim();
    setInput('');

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    try {
      const response = await fetch('http://localhost:8000/api/steering/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: steeringContent,
          priority: 1, // High priority
          session_id: 'default',
        }),
      });

      if (response.ok) {
        // Add a visual indicator that steering was sent
        const steeringMessage: Message = {
          id: crypto.randomUUID(),
          role: 'user',
          parts: [{ type: 'text', content: `⚡ Steering: ${steeringContent}` }],
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, steeringMessage]);
      }
    } catch (error) {
      console.error('Failed to send steering:', error);
    }
  }, [input, projectPath]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (isStreaming) {
          sendSteering();
        } else {
          sendMessage();
        }
      }
    },
    [sendMessage, sendSteering, isStreaming]
  );

  return (
    <div className="h-full flex flex-col bg-fill-secondary">
      {/* Header */}
      <div className="panel-header bg-white">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-green3 flex items-center justify-center">
            <Sparkles size={12} className="text-green1" />
          </div>
          <span className="typo-body-strong">AI Assistant</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {messages.length === 0 ? (
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
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-black/6 p-3 bg-white">
        {/* Steering mode indicator */}
        {isStreaming && (
          <div className="flex items-center gap-1.5 mb-2 text-orange1">
            <Zap size={12} />
            <span className="typo-ex-small">Steering mode - redirect the agent</span>
          </div>
        )}
        <div className="relative">
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
                ? "Send steering instruction..."
                : "Ask the assistant..."
            }
            disabled={!projectPath}
            className={`w-full min-h-[44px] max-h-[200px] rounded-yw-lg border bg-white pl-3 pr-12 py-2.5 typo-body placeholder:text-tertiary focus:outline-none focus:ring-1 transition-colors resize-none overflow-y-auto ${
              isStreaming
                ? 'border-orange1/30 focus:border-orange1 focus:ring-orange1/20'
                : 'border-black/12 focus:border-green2 focus:ring-green2/20'
            }`}
            rows={1}
          />
          <button
            onClick={isStreaming ? sendSteering : sendMessage}
            disabled={!input.trim() || !projectPath}
            className={`absolute right-2 bottom-2 flex h-7 w-7 items-center justify-center rounded-yw-md transition-all ${
              !input.trim() || !projectPath
                ? 'bg-black/6 text-tertiary cursor-not-allowed'
                : isStreaming
                ? 'bg-orange1 text-white hover:opacity-90'
                : 'bg-green1 text-white hover:opacity-90'
            }`}
          >
            {isStreaming ? (
              <Zap size={14} />
            ) : (
              <Send size={14} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
