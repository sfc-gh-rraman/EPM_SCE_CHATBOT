import { useEffect, useState } from 'react'
import {
  FileText,
  Users,
  Layers,
  TrendingUp,
  Activity
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from 'recharts'

interface PortfolioData {
  CONTRACT_COUNT: number
  COUNTERPARTY_COUNT: number
  CONTRACTS_WITH_AMENDMENTS: number
  TOTAL_AMENDMENTS: number
  TOTAL_CHUNKS: number
  clause_distribution: Array<{ CLAUSE_TYPE: string; CNT: number }>
  top_counterparties: Array<{ COUNTERPARTY_NAME: string; CONTRACTS: number }>
  amendment_velocity: Array<{ MONTH: string; CNT: number }>
}

const COLORS = ['#f59e0b', '#58a6ff', '#3fb950', '#f85149', '#a371f7', '#ec4899', '#39c5cf', '#84cc16']

export function PortfolioDashboard() {
  const [data, setData] = useState<PortfolioData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/portfolio/summary')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-full"><Activity className="animate-spin text-atlas-blue" size={32} /></div>
  if (!data) return <div className="p-8 text-atlas-red">Failed to load portfolio data</div>

  const kpis = [
    { label: 'Contracts', value: data.CONTRACT_COUNT, icon: FileText, color: 'text-amber-400' },
    { label: 'Counterparties', value: data.COUNTERPARTY_COUNT, icon: Users, color: 'text-atlas-blue' },
    { label: 'Amendments', value: data.TOTAL_AMENDMENTS, icon: Layers, color: 'text-atlas-green' },
    { label: 'Document Chunks', value: data.TOTAL_CHUNKS?.toLocaleString(), icon: TrendingUp, color: 'text-atlas-purple' },
  ]

  const clauseData = (data.clause_distribution || []).filter(d => d.CLAUSE_TYPE !== 'GENERAL')

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Portfolio Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Real-time overview of SCE EPM contract portfolio from 580 CPUC PPAs</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {kpis.map(k => (
          <div key={k.label} className="card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">{k.label}</p>
                <p className="text-2xl font-bold text-slate-100 mt-1">{k.value}</p>
              </div>
              <k.icon className={k.color} size={28} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Counterparties by Contract Count</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.top_counterparties || []} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis type="number" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis dataKey="COUNTERPARTY_NAME" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={120} stroke="#30363d" />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
              <Bar dataKey="CONTRACTS" fill="#f59e0b" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Clause Type Distribution (excl. GENERAL)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={clauseData} dataKey="CNT" nameKey="CLAUSE_TYPE" cx="50%" cy="50%" outerRadius={90} label={({ CLAUSE_TYPE, CNT }) => `${CLAUSE_TYPE} (${CNT})`}>
                {clauseData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Amendment Velocity Over Time</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={(data.amendment_velocity || []).map(d => ({ ...d, MONTH: d.MONTH?.slice(0, 7) }))}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis dataKey="MONTH" tick={{ fill: '#94a3b8', fontSize: 10 }} stroke="#30363d" />
            <YAxis stroke="#30363d" tick={{ fill: '#94a3b8' }} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            <Line type="monotone" dataKey="CNT" stroke="#58a6ff" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
