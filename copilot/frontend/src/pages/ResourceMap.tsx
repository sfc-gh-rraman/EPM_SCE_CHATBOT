import { useEffect, useState } from 'react'
import { Map, Activity } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts'

interface ResourceData {
  by_counterparty: Array<{ COUNTERPARTY_NAME: string; CONTRACT_TYPE: string; RESOURCE_TYPE: string; CONTRACT_COUNT: number }>
  by_doc_type: Array<{ DOC_TYPE: string; DOC_COUNT: number }>
}

const COLORS = ['#f59e0b', '#58a6ff', '#3fb950', '#f85149', '#a371f7', '#ec4899', '#39c5cf', '#84cc16', '#f97316', '#14b8a6']

export function ResourceMap() {
  const [data, setData] = useState<ResourceData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/resource-map')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-full"><Activity className="animate-spin text-atlas-blue" size={32} /></div>
  if (!data) return <div className="p-8 text-atlas-red">Failed to load resource data</div>

  const counterpartyAgg: Record<string, number> = {}
  ;(data.by_counterparty || []).forEach(r => {
    counterpartyAgg[r.COUNTERPARTY_NAME] = (counterpartyAgg[r.COUNTERPARTY_NAME] || 0) + r.CONTRACT_COUNT
  })
  const treemapData = Object.entries(counterpartyAgg)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([name, size]) => ({ name, size }))

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Map className="text-atlas-green" size={28} />
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Resource Map</h1>
          <p className="text-sm text-slate-400 mt-1">Contract distribution by counterparty, resource type, and document type</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Top 20 Counterparties</h3>
          <div className="grid grid-cols-4 gap-2">
            {treemapData.map((item, i) => (
              <div key={item.name} className="p-2 rounded-lg text-center border border-navy-600/50" style={{ backgroundColor: COLORS[i % COLORS.length] + '15' }}>
                <p className="text-xs font-medium text-slate-300 truncate">{item.name}</p>
                <p className="text-sm font-bold text-slate-100">{item.size}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Amendment Document Types</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={data.by_doc_type || []} dataKey="DOC_COUNT" nameKey="DOC_TYPE" cx="50%" cy="50%" outerRadius={100}
                label={({ DOC_TYPE, DOC_COUNT }) => `${DOC_TYPE} (${DOC_COUNT})`}>
                {(data.by_doc_type || []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Counterparties by Contract Count</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={treemapData.slice(0, 15)} margin={{ bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9 }} angle={-45} textAnchor="end" height={80} stroke="#30363d" />
            <YAxis stroke="#30363d" tick={{ fill: '#94a3b8' }} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
            <Bar dataKey="size" fill="#58a6ff" radius={[4, 4, 0, 0]} name="Contracts" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
