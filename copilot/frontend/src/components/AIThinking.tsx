import { Brain, Database, Search, Sparkles, Zap, CheckCircle, Loader2 } from 'lucide-react'

interface AIThinkingProps {
  stage?: 'planning' | 'searching' | 'analyzing' | 'generating'
}

export function AIThinking({ stage = 'analyzing' }: AIThinkingProps) {
  const stages = {
    planning: { icon: Brain, text: 'Planning analysis approach...', color: 'purple' },
    searching: { icon: Search, text: 'Searching change orders & documents...', color: 'green' },
    analyzing: { icon: Database, text: 'Analyzing portfolio data...', color: 'blue' },
    generating: { icon: Sparkles, text: 'Generating insights...', color: 'cyan' },
  }

  const current = stages[stage]
  const Icon = current.icon

  const colorClasses = {
    purple: {
      bg: 'bg-purple-500/20',
      text: 'text-purple-400',
      border: 'border-purple-500/30',
      gradient: 'from-purple-500 to-purple-400'
    },
    green: {
      bg: 'bg-green-500/20',
      text: 'text-green-400',
      border: 'border-green-500/30',
      gradient: 'from-green-500 to-green-400'
    },
    blue: {
      bg: 'bg-blue-500/20',
      text: 'text-blue-400',
      border: 'border-blue-500/30',
      gradient: 'from-blue-500 to-blue-400'
    },
    cyan: {
      bg: 'bg-cyan-500/20',
      text: 'text-cyan-400',
      border: 'border-cyan-500/30',
      gradient: 'from-cyan-500 to-cyan-400'
    }
  }

  const colors = colorClasses[current.color as keyof typeof colorClasses]

  return (
    <div className="flex items-center gap-3 p-4">
      {/* Animated icon container */}
      <div className="relative">
        <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center relative overflow-hidden`}>
          {/* Rotating gradient border */}
          <div className="absolute inset-0 rounded-xl animate-spin-slow opacity-50"
               style={{ background: `conic-gradient(from 0deg, transparent, ${current.color === 'purple' ? '#a855f7' : current.color === 'green' ? '#22c55e' : current.color === 'blue' ? '#3b82f6' : '#06b6d4'}, transparent)` }} />
          
          {/* Icon */}
          <Icon size={20} className={`${colors.text} relative z-10`} />
          
          {/* Pulse effect */}
          <div className={`absolute inset-0 ${colors.bg} rounded-xl animate-ping opacity-50`} />
        </div>
        
        {/* Orbiting particles */}
        <div className="absolute inset-0 animate-spin" style={{ animationDuration: '3s' }}>
          <div className={`absolute -top-1 left-1/2 w-1.5 h-1.5 ${colors.bg} rounded-full`} />
        </div>
      </div>

      {/* Text with typing effect */}
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm ${colors.text} font-medium`}>
            {current.text}
          </span>
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 ${colors.bg} rounded-full animate-bounce`}
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="mt-2 h-1 bg-navy-700 rounded-full overflow-hidden">
          <div 
            className={`h-full bg-gradient-to-r ${colors.gradient} rounded-full`}
            style={{
              animation: 'progress-indeterminate 1.5s ease-in-out infinite',
            }}
          />
        </div>
      </div>

      <style>{`
        @keyframes progress-indeterminate {
          0% { width: 0%; margin-left: 0%; }
          50% { width: 60%; margin-left: 20%; }
          100% { width: 0%; margin-left: 100%; }
        }
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 4s linear infinite;
        }
      `}</style>
    </div>
  )
}

interface ThinkingStep {
  id: string
  title: string
  content?: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  sql?: string
}

interface ThinkingStepsProps {
  steps: ThinkingStep[]
  isExpanded: boolean
  onToggle: () => void
}

export function ThinkingSteps({ steps, isExpanded, onToggle }: ThinkingStepsProps) {
  if (steps.length === 0) return null

  return (
    <div className="mt-3 border border-navy-600/50 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 p-3 bg-navy-800/50 hover:bg-navy-700/50 transition-colors text-left"
      >
        <Brain size={14} className="text-atlas-purple" />
        <span className="text-xs text-slate-400 font-medium">
          Thinking steps ({steps.length})
        </span>
        <span className={`ml-auto text-xs transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      
      {isExpanded && (
        <div className="p-3 space-y-2 bg-navy-900/30">
          {steps.map((step) => (
            <div key={step.id} className="flex items-start gap-2">
              {step.status === 'completed' && (
                <CheckCircle size={14} className="text-atlas-green flex-shrink-0 mt-0.5" />
              )}
              {step.status === 'in_progress' && (
                <Loader2 size={14} className="text-atlas-blue animate-spin flex-shrink-0 mt-0.5" />
              )}
              {step.status === 'pending' && (
                <div className="w-3.5 h-3.5 rounded-full border border-slate-600 flex-shrink-0 mt-0.5" />
              )}
              {step.status === 'failed' && (
                <div className="w-3.5 h-3.5 rounded-full bg-atlas-red flex-shrink-0 mt-0.5" />
              )}
              
              <div className="flex-1 min-w-0">
                <p className={`text-xs font-medium ${
                  step.status === 'completed' ? 'text-slate-400' : 'text-slate-300'
                }`}>
                  {step.title}
                </p>
                {step.content && (
                  <p className="text-xs text-slate-500 mt-0.5 truncate">{step.content}</p>
                )}
                {step.sql && (
                  <pre className="mt-1 p-2 bg-navy-900 rounded text-xs text-slate-400 font-mono overflow-x-auto">
                    {step.sql.length > 150 ? step.sql.substring(0, 150) + '...' : step.sql}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface QueryExecutionProps {
  sql?: string
  rowCount?: number
  executionTime?: number
}

export function QueryExecution({ sql, rowCount, executionTime }: QueryExecutionProps) {
  if (!sql) return null

  return (
    <div className="mt-3 p-3 bg-navy-900/50 rounded-lg border border-navy-700">
      <div className="flex items-center gap-2 mb-2">
        <Zap size={12} className="text-cyan-400" />
        <span className="text-xs text-cyan-400 font-medium">SQL Query Executed</span>
        <div className="flex items-center gap-3 ml-auto text-xs text-slate-500">
          {rowCount !== undefined && (
            <span>{rowCount.toLocaleString()} rows</span>
          )}
          {executionTime !== undefined && (
            <span>{executionTime}ms</span>
          )}
        </div>
      </div>
      <pre className="text-xs text-slate-400 font-mono overflow-x-auto whitespace-pre-wrap bg-navy-950 p-2 rounded">
        {sql.trim().length > 300 ? sql.trim().substring(0, 300) + '\n...' : sql.trim()}
      </pre>
    </div>
  )
}

interface DataTablePreviewProps {
  data: Record<string, unknown>[]
  maxRows?: number
}

export function DataTablePreview({ data, maxRows = 5 }: DataTablePreviewProps) {
  if (!data || data.length === 0) return null

  const columns = Object.keys(data[0])
  const rows = data.slice(0, maxRows)

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-navy-700">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-navy-800">
              {columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left text-slate-400 font-medium whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t border-navy-700/50 hover:bg-navy-800/50">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-slate-300 whitespace-nowrap">
                    {String(row[col] ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length > maxRows && (
        <div className="px-3 py-2 bg-navy-800/50 text-xs text-slate-500 text-center">
          Showing {maxRows} of {data.length} rows
        </div>
      )}
    </div>
  )
}
