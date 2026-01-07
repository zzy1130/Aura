'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  Loader2,
  Code,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface AgentPanelProps {
  projectPath: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
}

interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'success' | 'error';
}

// Tool call display component
function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusIcon = {
    pending: <Loader2 size={14} className="text-aura-muted" />,
    running: <Loader2 size={14} className="text-aura-accent animate-spin" />,
    success: <CheckCircle size={14} className="text-aura-success" />,
    error: <XCircle size={14} className="text-aura-error" />,
  }[toolCall.status];

  return (
    <div className="agent-tool-call">
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Code size={14} className="text-aura-accent" />
        <span className="text-aura-accent">{toolCall.name}</span>
        <span className="flex-1" />
        {statusIcon}
      </div>

      {isExpanded && (
        <div className="mt-2 text-xs">
          <div className="text-aura-muted mb-1">Arguments:</div>
          <pre className="bg-aura-bg p-2 rounded overflow-x-auto">
            {JSON.stringify(toolCall.args, null, 2)}
          </pre>

          {toolCall.result && (
            <>
              <div className="text-aura-muted mt-2 mb-1">Result:</div>
              <pre className="bg-aura-bg p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">
                {toolCall.result}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Message display component
function MessageDisplay({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`agent-message ${isUser ? 'agent-message-user' : 'agent-message-assistant'}`}>
      <div className="flex items-start gap-2">
        <div className={`p-1 rounded ${isUser ? 'bg-aura-accent/20' : 'bg-aura-surface'}`}>
          {isUser ? (
            <User size={14} className="text-aura-accent" />
          ) : (
            <Bot size={14} className="text-aura-success" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </div>

          {/* Tool calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-2 space-y-1">
              {message.toolCalls.map((tc) => (
                <ToolCallDisplay key={tc.id} toolCall={tc} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgentPanel({ projectPath }: AgentPanelProps) {
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
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    // Create assistant message placeholder
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      toolCalls: [],
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      // Get backend URL
      let backendUrl = 'http://127.0.0.1:8000';
      if (typeof window !== 'undefined' && window.aura) {
        backendUrl = await window.aura.getBackendUrl();
      }

      // Start SSE stream
      const response = await fetch(`${backendUrl}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.content,
          project_path: projectPath,
          history: messages.map((m) => ({
            role: m.role,
            content: m.content,
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

      // Process SSE stream
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            // Event type is part of SSE protocol, we handle data separately
            continue;
          }

          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              console.log('[Agent] SSE event:', data);

              // Handle different event types (matching backend format)
              if (data.type === 'text_delta' && data.content) {
                // Text streaming from model
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === 'assistant') {
                    last.content += data.content;
                  }
                  return updated;
                });
              } else if (data.type === 'tool_call') {
                // Tool is being called - backend sends {tool_name, args}
                const toolCall: ToolCall = {
                  id: crypto.randomUUID(),
                  name: data.tool_name,
                  args: data.args || {},
                  status: 'running',
                };
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === 'assistant') {
                    last.toolCalls = [...(last.toolCalls || []), toolCall];
                  }
                  return updated;
                });
              } else if (data.type === 'tool_result') {
                // Tool execution result - backend sends {tool_name, result}
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === 'assistant' && last.toolCalls) {
                    // Find the most recent tool call with matching name that hasn't been resolved
                    const tc = last.toolCalls.find((t) => t.name === data.tool_name && t.status === 'running');
                    if (tc) {
                      tc.result = data.result;
                      tc.status = 'success';
                    }
                  }
                  return updated;
                });
              } else if (data.type === 'done') {
                // Stream complete - backend sends {output, usage}
                console.log('[Agent] Stream done:', data);
              } else if (data.type === 'error') {
                // Error occurred - backend sends {message}
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === 'assistant') {
                    last.content += `\n\nError: ${data.message || 'Unknown error'}`;
                  }
                  return updated;
                });
              } else if (data.type === 'compression') {
                // History was compressed - informational
                console.log('[Agent] History compressed:', data);
              }
            } catch (e) {
              console.error('[Agent] JSON parse error:', e, 'Line:', line);
            }
          }
        }
      }
    } catch (error) {
      console.error('Agent stream error:', error);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === 'assistant') {
          last.content = `Error: ${error instanceof Error ? error.message : 'Unknown error'}`;
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, projectPath, messages]);

  // Handle key press
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage]
  );

  return (
    <div className="h-full flex flex-col bg-aura-bg">
      {/* Header */}
      <div className="h-10 border-b border-aura-border flex items-center px-3">
        <Bot size={16} className="text-aura-accent mr-2" />
        <span className="text-sm font-medium">Agent</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-aura-muted">
            <div className="text-center">
              <Bot size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Ask the agent anything about your paper</p>
              <p className="text-xs mt-1 opacity-70">
                Research, write, fix errors, and more
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
      <div className="border-t border-aura-border p-3">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={projectPath ? "Ask the agent..." : "Open a project first"}
            disabled={!projectPath || isStreaming}
            className="flex-1 bg-aura-surface border border-aura-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-aura-accent disabled:opacity-50"
            rows={2}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || !projectPath || isStreaming}
            className="px-3 py-2 bg-aura-accent text-aura-bg rounded hover:bg-aura-accent/80 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isStreaming ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
