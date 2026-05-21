import { useEffect, useState } from 'react'
import { Brain, Activity } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts'

interface AnalyticsData {
  distribution: Array<{ CLAUSE_TYPE: string; CHUNK_COUNT: number; CONTRACT_COUNT: number }>
  top_curtailment: Array<{ CONTRACT_ID: string; CONTRACT_NAME: string; COUNTERPARTY_NAME: string; CURTAILMENT_CHUNKS: number }>
  by_doc_type: Array<{ DOC_TYPE: string; CHUNKS: number; CONTRACTS: number }>
}

const COLORS = ['#f59e0b', '#58a6ff', '#3fb950', '#f85149', '#a371f7', '#ec4899', '#39c5cf', '#84cc16']

export function ClauseAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/clauses/analytics')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-full"><Activity className="animate-spin text-atlas-blue" size={32} /></div>
  if (!data) return <div className="p-8 text-atlas-red">Failed to load analytics</div>

  const radarData = (data.distribution || []).filter(d => d.CLAUSE_TYPE !== 'GENERAL').map(d => ({
    clause: d.CLAUSE_TYPE,
    chunks: d.CHUNK_COUNT,
    contracts: d.CONTRACT_COUNT
  }))

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Brain className="text-atlas-purple" size={28} />
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Clause Analytics</h1>
          <p className="text-sm text-slate-400 mt-1">ML-powered analysis of clause types across 58K+ contract chunks</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="card p-5 col-span-2">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Clause Type Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.distribution || []} margin={{ left: 100 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis type="number" stroke="#30363d" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis dataKey="CLAUSE_TYPE" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={100} stroke="#30363d" />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
              <Bar dataKey="CHUNK_COUNT" fill="#f59e0b" name="Chunks" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Clause Radar (excl. GENERAL)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid stroke="#30363d" />
              <PolarAngleAxis dataKey="clause" tick={{ fontSize: 9, fill: '#94a3b8' }} />
              <PolarRadiusAxis tick={{ fontSize: 9, fill: '#64748b' }} />
              <Radar name="Chunks" dataKey="chunks" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.3} />
              <Radar name="Contracts" dataKey="contracts" stroke="#58a6ff" fill="#58a6ff" fillOpacity={0.2} />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Contracts by Curtailment Clauses</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={(data.top_curtailment || []).slice(0, 10)} margin={{ left: 130 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis type="number" stroke="#30363d" tick={{ fill: '#94a3b8' }} />
              <YAxis dataKey="COUNTERPARTY_NAME" type="category" tick={{ fill: '#94a3b8', fontSize: 10 }} width={130} stroke="#30363d" />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
              <Bar dataKey="CURTAILMENT_CHUNKS" fill="#f85149" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Chunks by Document Type</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={data.by_doc_type || []} dataKey="CHUNKS" nameKey="DOC_TYPE" cx="50%" cy="50%" outerRadius={90} label={({ DOC_TYPE, CHUNKS }) => `${DOC_TYPE} (${CHUNKS})`}>
                {(data.by_doc_type || []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
