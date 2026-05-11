import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Sparkles, Database, AlertTriangle, CheckCircle, Loader2, Code, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { VegaChart } from './VegaChart'

interface ThinkingStep {
  id: string
  title: string
  content: string
  status: 'pending' | 'in_progress' | 'completed'
  sql?: string
}

interface ChartSpec {
  $schema?: string
  data?: unknown
  mark?: unknown
  encoding?: unknown
  [key: string]: unknown
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  intent?: string
  visualization?: string
  alert_level?: string
  timestamp: Date
  thinkingSteps?: ThinkingStep[]
  isStreaming?: boolean
  chartSpec?: ChartSpec
  context?: Record<string, unknown>
}

interface ChatProps {
  projectId?: string
  onVisualizationRequest?: (type: string, data?: Record<string, unknown>) => void
}

const SUGGESTED_QUESTIONS = [
  "How many amendments does CTR-001 have, and what does each one cover?",
  "What changed in the most recent amendment to CTR-005?",
  "Show me contracts with economic curtailment terms",
  "Show me contracts with capacity > 10 MW",
  "How do our contracts handle failure to deliver Resource Adequacy?",
  "Which contracts are paid by SCE meter but have a separate ISO meter?",
]

export function Chat({ projectId, onVisualizationRequest }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `👋 Hello! I'm the **SCE EPM Contract Assistant**, here to help you navigate Power Purchase, Resource Adequacy, and Tolling agreements.

I can answer questions across structured contract metadata and the actual PDF clause text. Ask me about:

- 📑 **Amendments** — counts, dates, what changed
- ⚡ **Curtailment** terms (economic / reliability / unlimited operational)
- 🔋 **Capacity** thresholds and supplier filters
- 📊 **EANEP / degradation** factors and product-deficiency remedies
- 🔌 **Metering** edge cases (paid by SCE meter but with ISO meter)

Try one of the suggestions below or ask your own question.`,
      sources: [],
      timestamp: new Date()
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showThinking, setShowThinking] = useState<Record<string, boolean>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessageWithStream = async (content: string) => {
    if (!content.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    const assistantId = (Date.now() + 1).toString()
    
    // Initialize assistant message with thinking steps
    const initialAssistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      thinkingSteps: [],
      isStreaming: true,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, initialAssistantMessage])
    setShowThinking(prev => ({ ...prev, [assistantId]: true }))

    try {
      // Try streaming endpoint first
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content.trim(),
          contract_id: projectId
        })
      })

      if (!response.ok || !response.body) {
        throw new Error('Streaming not available')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''
      const thinkingSteps: ThinkingStep[] = []
      let sources: string[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        
        // Process complete events
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const eventStr of events) {
          if (!eventStr.trim() || !eventStr.startsWith('data:')) continue
          
          const dataStr = eventStr.replace('data:', '').trim()
          if (dataStr === '[DONE]') continue

          try {
            const event = JSON.parse(dataStr)
            
            // Handle different event types from Cortex Agent
            if (event.type === 'text') {
              // ACTUAL OUTPUT TEXT - this is what we show to the user
              fullContent += event.content || ''
              setMessages(prev => prev.map(msg => 
                msg.id === assistantId 
                  ? { ...msg, content: fullContent }
                  : msg
              ))
            } else if (event.type === 'thinking') {
              // Agent's internal reasoning - accumulate but don't show as main content
              const thinkingText = event.content || ''
              // Only add substantial thinking steps
              if (thinkingText.length > 20) {
                const step: ThinkingStep = {
                  id: `step-${Date.now()}`,
                  title: event.title || 'Reasoning',
                  content: thinkingText.slice(0, 200) + (thinkingText.length > 200 ? '...' : ''),
                  status: 'in_progress',
                  sql: event.sql
                }
                // Limit to last 5 thinking steps to avoid clutter
                if (thinkingSteps.length >= 5) {
                  thinkingSteps.shift()
                }
                thinkingSteps.push(step)
                thinkingSteps.slice(0, -1).forEach(s => s.status = 'completed')
                
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantId 
                    ? { ...msg, thinkingSteps: [...thinkingSteps] }
                    : msg
                ))
              }
            } else if (event.type === 'status' || event.type === 'tool_status') {
              // Status updates - add as thinking steps
              const step: ThinkingStep = {
                id: `status-${Date.now()}`,
                title: event.title || event.status || 'Processing',
                content: '',
                status: 'in_progress'
              }
              thinkingSteps.push(step)
              thinkingSteps.slice(0, -1).forEach(s => s.status = 'completed')
              
              setMessages(prev => prev.map(msg => 
                msg.id === assistantId 
                  ? { ...msg, thinkingSteps: [...thinkingSteps] }
                  : msg
              ))
            } else if (event.type === 'tool_result') {
              // Tool execution result - may contain SQL and data
              if (event.sql) {
                const sqlStep: ThinkingStep = {
                  id: `sql-${Date.now()}`,
                  title: 'SQL Executed',
                  content: event.error || 'Query completed',
                  status: event.error ? 'pending' : 'completed',
                  sql: event.sql
                }
                thinkingSteps.push(sqlStep)
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantId 
                    ? { ...msg, thinkingSteps: [...thinkingSteps] }
                    : msg
                ))
              }
            } else if (event.type === 'sources') {
              sources = event.sources || []
            } else if (event.type === 'citations') {
              // Citations attached to the final answer (CHK-... doc IDs from Cortex Search)
              sources = (event.citations || [])
                .map((c: { doc_id?: string; doc_title?: string }) =>
                  c.doc_title ? `${c.doc_id}: ${c.doc_title}` : (c.doc_id || ''))
                .filter(Boolean)
              setMessages(prev => prev.map(msg =>
                msg.id === assistantId ? { ...msg, sources: [...sources] } : msg
              ))
            } else if (event.type === 'suggested_queries') {
              // Follow-up question suggestions from the agent
              setMessages(prev => prev.map(msg =>
                msg.id === assistantId
                  ? { ...msg, context: { ...(msg.context || {}), suggestedQueries: event.queries } }
                  : msg
              ))
            } else if (event.type === 'tool_use') {
              // Which tool the agent picked (analyst / search / custom proc)
              const step: ThinkingStep = {
                id: `tool-${Date.now()}`,
                title: `Using ${event.name || 'tool'}`,
                content: '',
                status: 'in_progress',
              }
              thinkingSteps.push(step)
              thinkingSteps.slice(0, -1).forEach(s => s.status = 'completed')
              setMessages(prev => prev.map(msg =>
                msg.id === assistantId ? { ...msg, thinkingSteps: [...thinkingSteps] } : msg
              ))
            } else if (event.type === 'chart') {
              // Chart/visualization from the agent
              const chartSpec = event.chart_spec
              if (chartSpec) {
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantId 
                    ? { ...msg, chartSpec }
                    : msg
                ))
              }
            } else if (event.type === 'error') {
              fullContent += `\n\n⚠️ ${event.content || 'An error occurred'}`
              setMessages(prev => prev.map(msg => 
                msg.id === assistantId 
                  ? { ...msg, content: fullContent }
                  : msg
              ))
            } else if (event.type === 'done') {
              // Stream complete
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }

      // Mark all thinking steps as completed
      thinkingSteps.forEach(s => s.status = 'completed')
      
      // Final update
      setMessages(prev => prev.map(msg => 
        msg.id === assistantId 
          ? { 
              ...msg, 
              content: fullContent || 'I processed your request.',
              thinkingSteps: [...thinkingSteps],
              sources,
              isStreaming: false 
            }
          : msg
      ))

      // Collapse thinking after streaming completes
      setTimeout(() => {
        setShowThinking(prev => ({ ...prev, [assistantId]: false }))
      }, 2000)

    } catch (error) {
      console.log('Streaming failed, falling back to local:', error)
      
      // Fallback to local endpoint
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: content.trim(),
            contract_id: projectId
          })
        })

        if (!response.ok) throw new Error('Failed to get response')

        const data = await response.json()
        
        setMessages(prev => prev.map(msg => 
          msg.id === assistantId 
            ? { 
                ...msg, 
                content: data.response,
                sources: data.sources,
                intent: data.intent,
                visualization: data.visualization,
                alert_level: data.alert_level,
                isStreaming: false,
                thinkingSteps: [
                  { id: 'step-1', title: 'Query Processing', content: 'Analyzed your question', status: 'completed' as const },
                  { id: 'step-2', title: 'Data Retrieval', content: 'Retrieved data from Snowflake', status: 'completed' as const },
                ]
              }
            : msg
        ))

        if (data.visualization && onVisualizationRequest) {
          onVisualizationRequest(data.visualization, data.context)
        }
      } catch (fallbackError) {
        console.error('Chat error:', fallbackError)
        setMessages(prev => prev.map(msg => 
          msg.id === assistantId 
            ? { 
                ...msg, 
                content: 'I encountered an error. Please try rephrasing your question.',
                isStreaming: false 
              }
            : msg
        ))
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessageWithStream(input)
  }

  const toggleThinking = (messageId: string) => {
    setShowThinking(prev => ({ ...prev, [messageId]: !prev[messageId] }))
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div 
            key={message.id}
            className={`flex gap-3 chat-message ${
              message.role === 'user' ? 'justify-end' : ''
            }`}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-atlas-blue to-atlas-purple flex items-center justify-center">
                <Bot size={16} className="text-white" />
              </div>
            )}
            
            <div className={`max-w-[85%] ${message.role === 'user' ? 'order-first' : ''}`}>
              {/* Thinking Steps Panel */}
              {message.role === 'assistant' && message.thinkingSteps && message.thinkingSteps.length > 0 && (
                <div className="mb-2">
                  <button
                    onClick={() => toggleThinking(message.id)}
                    className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300 transition-colors mb-1"
                  >
                    <span className="flex items-center gap-1">
                      {message.isStreaming ? (
                        <Loader2 size={12} className="animate-spin text-atlas-blue" />
                      ) : (
                        <CheckCircle size={12} className="text-atlas-green" />
                      )}
                      <span>Thinking steps ({message.thinkingSteps.length})</span>
                    </span>
                    {showThinking[message.id] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                  
                  {showThinking[message.id] && (
                    <div className="bg-navy-900/50 border border-navy-700/50 rounded-lg p-3 space-y-2">
                      {message.thinkingSteps.map((step) => (
                        <div key={step.id} className="flex items-start gap-2">
                          {step.status === 'completed' ? (
                            <CheckCircle size={14} className="text-atlas-green mt-0.5 flex-shrink-0" />
                          ) : step.status === 'in_progress' ? (
                            <Loader2 size={14} className="animate-spin text-atlas-blue mt-0.5 flex-shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-slate-600 mt-0.5 flex-shrink-0" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-slate-300">{step.title}</div>
                            <div className="text-xs text-slate-500">{step.content}</div>
                            {step.sql && (
                              <div className="mt-1 p-2 bg-navy-800 rounded text-xs font-mono text-slate-400 overflow-x-auto">
                                <div className="flex items-center gap-1 text-atlas-blue mb-1">
                                  <Code size={10} />
                                  <span>SQL</span>
                                </div>
                                <pre className="whitespace-pre-wrap break-all">{step.sql.slice(0, 200)}...</pre>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Message Content */}
              <div 
                className={`rounded-lg p-4 ${
                  message.role === 'user' 
                    ? 'bg-atlas-blue text-white' 
                    : 'bg-navy-800 border border-navy-600/50'
                }`}
              >
                {message.role === 'assistant' ? (
                  <div className="markdown-content">
                    {message.isStreaming && !message.content ? (
                      <div className="flex items-center gap-2 text-slate-400">
                        <Loader2 size={14} className="animate-spin" />
                        <span>Processing...</span>
                      </div>
                    ) : (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    )}
                    
                    {/* Chart visualization */}
                    {message.chartSpec && (
                      <div className="mt-4">
                        <div className="flex items-center gap-2 mb-2 text-xs text-atlas-blue">
                          <BarChart3 size={14} />
                          <span>Generated Visualization</span>
                        </div>
                        <VegaChart spec={message.chartSpec} className="w-full" />
                      </div>
                    )}
                  </div>
                ) : (
                  <p>{message.content}</p>
                )}
              </div>
              
              {/* Sources and metadata */}
              {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <Database size={12} />
                  <span>Sources:</span>
                  {message.sources.map((source, i) => (
                    <span key={i} className="px-2 py-0.5 bg-navy-700 rounded text-slate-400">
                      {source}
                    </span>
                  ))}
                </div>
              )}

              {message.alert_level === 'high' && (
                <div className="mt-2 flex items-center gap-2 text-xs text-atlas-yellow">
                  <AlertTriangle size={12} />
                  <span>High-priority insight detected</span>
                </div>
              )}
            </div>

            {message.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-navy-600 flex items-center justify-center">
                <User size={16} className="text-slate-300" />
              </div>
            )}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {messages.length <= 2 && (
        <div className="px-4 pb-2">
          <div className="flex items-center gap-2 mb-2 text-xs text-slate-500">
            <Sparkles size={12} />
            <span>Suggested questions</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.slice(0, 4).map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessageWithStream(q)}
                className="px-3 py-1.5 bg-navy-700/50 hover:bg-navy-600/50 rounded-full text-xs text-slate-300 hover:text-white transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-navy-700/50">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask ATLAS anything..."
            className="input flex-1"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={18} />
          </button>
        </div>
      </form>
    </div>
  )
}
