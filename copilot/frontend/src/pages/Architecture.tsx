import { useState } from 'react'
import {
  Database, Brain, MessageSquare, Zap, Server, Search, X, Activity, FileText, Layers
} from 'lucide-react'

interface ComponentInfo {
  id: string
  name: string
  shortName: string
  description: string
  tech: string[]
  stats?: string
  color: string
}

const components: Record<string, ComponentInfo> = {
  frontend: {
    id: 'frontend',
    name: 'React Frontend',
    shortName: 'UI',
    description: 'Dark-themed React SPA with 8 pages: Dashboard, Daily Brief, Chat, Deep Dive, Search, Analytics, Resource Map, Architecture. SSE streaming for real-time agent responses.',
    tech: ['React 18', 'TypeScript', 'Tailwind CSS', 'Vite', 'Recharts'],
    stats: '8 pages, SSE streaming',
    color: 'cyan',
  },
  backend: {
    id: 'backend',
    name: 'FastAPI Backend',
    shortName: 'API',
    description: 'Python middleware handling REST endpoints and SSE agent proxy. Connects to Snowflake via CLI locally or Snowpark Session in SPCS. Serves portfolio, contract, and clause analytics data.',
    tech: ['Python 3.11', 'FastAPI', 'Uvicorn', 'httpx'],
    stats: '12 endpoints',
    color: 'blue',
  },
  agent: {
    id: 'agent',
    name: 'Cortex Agent',
    shortName: 'Agent',
    description: 'SCE_EPM_CONTRACT_AGENT — a 7-tool Snowflake Cortex Agent that orchestrates Analyst, Search, and custom tools to answer contract questions with grounded citations.',
    tech: ['Cortex Agents', '7 Tools', 'Multi-turn', 'Streaming'],
    stats: '7 tools orchestrated',
    color: 'purple',
  },
  analyst: {
    id: 'analyst',
    name: 'Cortex Analyst',
    shortName: 'SQL',
    description: 'Text-to-SQL over the semantic model. Handles structured queries about contract counts, capacity, amendments, and counterparties.',
    tech: ['Semantic Model YAML', 'Verified Queries', 'Natural Language → SQL'],
    stats: '122 contracts queryable',
    color: 'yellow',
  },
  search: {
    id: 'search',
    name: 'Cortex Search',
    shortName: 'Search',
    description: 'Two search services: CONTRACT_CLAUSE_SEARCH (58K chunks) and AMENDMENT_FILE_SEARCH (360 amendments). Retrieves relevant contract text with sub-second latency.',
    tech: ['Cortex Search', '58K chunks', 'Hybrid retrieval', 'Attribute filters'],
    stats: '58,088 indexed chunks',
    color: 'green',
  },
  tools: {
    id: 'tools',
    name: 'Custom Tools',
    shortName: 'Tools',
    description: 'Three custom SQL tools: PARSE_AMENDMENT_FILENAME (UDF), GET_CONTRACT_360 (proc), COMPARE_CLAUSE_ACROSS_CONTRACTS (proc). Registered as generic agent tools.',
    tech: ['SQL UDF', 'Stored Procedures', 'Generic tool type'],
    stats: '3 custom tools',
    color: 'red',
  },
  snowflake: {
    id: 'snowflake',
    name: 'Snowflake Data Cloud',
    shortName: 'Data',
    description: 'SCE_EPM_DB with schemas: RAW (580 PDFs), ATOMIC (contracts, amendments, chunks), DOCS (search tables), CORTEX (agent, model, tools), SPCS (container service).',
    tech: ['SCE_EPM_DB', '5 Schemas', 'PARSE_DOCUMENT', 'SPLIT_TEXT'],
    stats: '580 PDFs, 106M chars',
    color: 'blue',
  },
  spcs: {
    id: 'spcs',
    name: 'SPCS Container',
    shortName: 'Deploy',
    description: 'Snowpark Container Services deployment: nginx → React SPA + FastAPI backend. OAuth-authenticated public endpoint. CPU_X64_XS compute pool with auto-suspend.',
    tech: ['Docker', 'nginx', 'SPCS', 'OAuth'],
    stats: 'Production endpoint live',
    color: 'cyan',
  },
}

export function Architecture() {
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null)
  const [hoveredFlow, setHoveredFlow] = useState<string | null>(null)

  const selectedInfo = selectedComponent ? components[selectedComponent] : null

  const getColorClasses = (color: string, isActive: boolean) => {
    const colors: Record<string, { bg: string; border: string }> = {
      cyan: { bg: isActive ? 'bg-cyan-500/20' : 'bg-cyan-500/10', border: isActive ? 'border-cyan-400' : 'border-cyan-500/30' },
      blue: { bg: isActive ? 'bg-blue-500/20' : 'bg-blue-500/10', border: isActive ? 'border-blue-400' : 'border-blue-500/30' },
      purple: { bg: isActive ? 'bg-purple-500/20' : 'bg-purple-500/10', border: isActive ? 'border-purple-400' : 'border-purple-500/30' },
      green: { bg: isActive ? 'bg-emerald-500/20' : 'bg-emerald-500/10', border: isActive ? 'border-emerald-400' : 'border-emerald-500/30' },
      yellow: { bg: isActive ? 'bg-amber-500/20' : 'bg-amber-500/10', border: isActive ? 'border-amber-400' : 'border-amber-500/30' },
      red: { bg: isActive ? 'bg-red-500/20' : 'bg-red-500/10', border: isActive ? 'border-red-400' : 'border-red-500/30' },
    }
    return colors[color] || colors.blue
  }

  const ComponentNode = ({ id, x, y }: { id: string; x: number; y: number }) => {
    const comp = components[id]
    const isActive = selectedComponent === id
    const colors = getColorClasses(comp.color, isActive)
    const icons: Record<string, any> = { frontend: MessageSquare, backend: Server, agent: Brain, analyst: Layers, search: Search, tools: FileText, snowflake: Database, spcs: Zap }
    const Icon = icons[id] || Activity

    return (
      <g transform={`translate(${x}, ${y})`} onClick={() => setSelectedComponent(isActive ? null : id)} className="cursor-pointer">
        <rect x="0" y="0" width="80" height="80" rx="12" className={`${colors.bg} ${colors.border} border-2 transition-all duration-300`} />
        <foreignObject x="20" y="15" width="40" height="40">
          <div className="flex items-center justify-center w-full h-full">
            <Icon size={28} className={`text-${comp.color === 'yellow' ? 'amber' : comp.color === 'green' ? 'emerald' : comp.color}-400`} />
          </div>
        </foreignObject>
        <text x="40" y="68" textAnchor="middle" className="text-xs font-medium fill-slate-300">{comp.shortName}</text>
        <circle cx="70" cy="10" r="5" className="fill-emerald-400" style={{ filter: 'drop-shadow(0 0 4px #10b981)' }}>
          <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite" />
        </circle>
      </g>
    )
  }

  const FlowLine = ({ from, to, label }: { from: { x: number; y: number }; to: { x: number; y: number }; label?: string }) => {
    const isActive = hoveredFlow === label
    const path = `M ${from.x} ${from.y} L ${to.x} ${to.y}`
    return (
      <g onMouseEnter={() => setHoveredFlow(label || null)} onMouseLeave={() => setHoveredFlow(null)}>
        <path d={path} fill="none" stroke="#58a6ff" strokeWidth={isActive ? 4 : 2} strokeOpacity={isActive ? 0.5 : 0.2} style={{ filter: isActive ? 'blur(4px)' : 'none' }} />
        <path d={path} fill="none" stroke="#58a6ff" strokeWidth="2" strokeDasharray="8 4" strokeOpacity={isActive ? 1 : 0.6}>
          <animate attributeName="stroke-dashoffset" values="0;-12" dur="1s" repeatCount="indefinite" />
        </path>
        <circle cx={to.x} cy={to.y} r="4" fill="#58a6ff"><animate attributeName="r" values="3;5;3" dur="1.5s" repeatCount="indefinite" /></circle>
        {label && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8} textAnchor="middle" className={`text-[10px] ${isActive ? 'fill-blue-300' : 'fill-slate-500'}`}>{label}</text>}
      </g>
    )
  }

  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-200 flex items-center gap-3">
            <div className="relative"><Zap className="text-atlas-blue" /><div className="absolute inset-0 text-atlas-blue animate-ping opacity-30"><Zap /></div></div>
            System Architecture
          </h1>
          <p className="text-slate-400 mt-2">Interactive blueprint of the SCE EPM Contract Intelligence platform. Click any component to learn more.</p>
        </div>

        <div className="grid grid-cols-5 gap-4 mb-8">
          {[
            { label: 'Agent Tools', value: '7', color: 'purple' },
            { label: 'PDF Documents', value: '580', color: 'green' },
            { label: 'Contract Chunks', value: '58K', color: 'blue' },
            { label: 'Counterparties', value: '315', color: 'cyan' },
            { label: 'API Endpoints', value: '12', color: 'yellow' },
          ].map((stat, i) => (
            <div key={i} className="card-glow text-center py-4">
              <p className="text-2xl font-mono font-bold text-atlas-blue">{stat.value}</p>
              <p className="text-xs text-slate-500 mt-1">{stat.label}</p>
            </div>
          ))}
        </div>

        <div className="card p-8 relative overflow-hidden">
          <div className="absolute inset-0 scan-line pointer-events-none" />
          <svg viewBox="0 0 1000 400" className="w-full h-auto" style={{ minHeight: '350px' }}>
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(88, 166, 255, 0.05)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            <text x="50" y="30" className="text-xs fill-slate-500 uppercase tracking-wider">Presentation</text>
            <text x="250" y="30" className="text-xs fill-slate-500 uppercase tracking-wider">API Layer</text>
            <text x="420" y="30" className="text-xs fill-slate-500 uppercase tracking-wider">Intelligence</text>
            <text x="700" y="30" className="text-xs fill-slate-500 uppercase tracking-wider">Data & AI</text>

            <FlowLine from={{ x: 120, y: 200 }} to={{ x: 220, y: 200 }} label="HTTP/SSE" />
            <FlowLine from={{ x: 320, y: 200 }} to={{ x: 420, y: 200 }} label="Agent API" />
            <FlowLine from={{ x: 500, y: 160 }} to={{ x: 620, y: 120 }} label="text→SQL" />
            <FlowLine from={{ x: 500, y: 200 }} to={{ x: 620, y: 200 }} label="Retrieve" />
            <FlowLine from={{ x: 500, y: 240 }} to={{ x: 620, y: 280 }} label="Invoke" />
            <FlowLine from={{ x: 700, y: 120 }} to={{ x: 820, y: 200 }} label="Query" />
            <FlowLine from={{ x: 700, y: 200 }} to={{ x: 820, y: 200 }} />
            <FlowLine from={{ x: 700, y: 280 }} to={{ x: 820, y: 200 }} />

            <ComponentNode id="frontend" x={40} y={160} />
            <ComponentNode id="backend" x={220} y={160} />
            <ComponentNode id="agent" x={420} y={160} />
            <ComponentNode id="analyst" x={620} y={80} />
            <ComponentNode id="search" x={620} y={160} />
            <ComponentNode id="tools" x={620} y={240} />
            <ComponentNode id="snowflake" x={820} y={160} />
            <ComponentNode id="spcs" x={40} y={280} />

            {[...Array(5)].map((_, i) => (
              <circle key={i} r="2" fill="#58a6ff">
                <animateMotion dur={`${3 + i * 0.5}s`} repeatCount="indefinite" path="M 120 200 L 320 200 L 460 200 L 700 200 L 860 200" />
                <animate attributeName="opacity" values="0;1;1;0" dur={`${3 + i * 0.5}s`} repeatCount="indefinite" />
              </circle>
            ))}
          </svg>

          <div className="flex items-center justify-center gap-6 mt-4 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #58a6ff 0, #58a6ff 8px, transparent 8px, transparent 12px)' }} />
              <span>Data Flow</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-emerald-400 rounded-full" style={{ boxShadow: '0 0 8px #10b981' }} />
              <span>Active</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-atlas-blue/30 rounded" />
              <span>Click for details</span>
            </div>
          </div>
        </div>

        {selectedInfo && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setSelectedComponent(null)}>
            <div className="card max-w-lg w-full relative animate-scale-in" onClick={e => e.stopPropagation()}>
              <button onClick={() => setSelectedComponent(null)} className="absolute top-4 right-4 p-2 rounded-lg hover:bg-navy-700 transition-colors">
                <X size={20} className="text-slate-400" />
              </button>
              <div className="flex items-start gap-4 mb-6 p-6 pb-0">
                <div className="w-14 h-14 rounded-xl bg-navy-700 flex items-center justify-center">
                  {selectedInfo.id === 'frontend' && <MessageSquare className="text-cyan-400" size={28} />}
                  {selectedInfo.id === 'backend' && <Server className="text-blue-400" size={28} />}
                  {selectedInfo.id === 'agent' && <Brain className="text-purple-400" size={28} />}
                  {selectedInfo.id === 'analyst' && <Layers className="text-amber-400" size={28} />}
                  {selectedInfo.id === 'search' && <Search className="text-emerald-400" size={28} />}
                  {selectedInfo.id === 'tools' && <FileText className="text-red-400" size={28} />}
                  {selectedInfo.id === 'snowflake' && <Database className="text-blue-400" size={28} />}
                  {selectedInfo.id === 'spcs' && <Zap className="text-cyan-400" size={28} />}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-200">{selectedInfo.name}</h3>
                  {selectedInfo.stats && <p className="text-sm text-atlas-blue font-mono">{selectedInfo.stats}</p>}
                </div>
              </div>
              <div className="px-6">
                <p className="text-slate-300 mb-6">{selectedInfo.description}</p>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Technologies</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedInfo.tech.map((tech, i) => (
                      <span key={i} className="text-xs px-3 py-1.5 bg-atlas-blue/10 text-atlas-blue rounded-full border border-atlas-blue/20">{tech}</span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-6 mx-6 mb-6 pt-4 border-t border-navy-700 flex items-center justify-between">
                <span className="text-xs text-slate-500">Component ID: {selectedInfo.id}</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                  <span className="text-xs text-emerald-400">Online</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
