import { useEffect, useState } from 'react'
import { Sun, AlertTriangle, Clock, FileText, Activity } from 'lucide-react'

interface BriefData {
  stats: {
    TOTAL_CONTRACTS: number
    TOTAL_AMENDMENTS: number
    COUNTERPARTIES: number
    CURTAILMENT_CLAUSES: number
    DELIVERY_FAILURE_CLAUSES: number
  }
  recent_amendments: Array<{
    AMENDMENT_ID: string
    CONTRACT_ID: string
    CONTRACT_NAME: string
    COUNTERPARTY_NAME: string
    DOC_TYPE: string
    EXECUTION_DATE: string
    FILE_NAME: string
  }>
  high_amendment_contracts: Array<{
    CONTRACT_ID: string
    CONTRACT_NAME: string
    COUNTERPARTY_NAME: string
    AMD_COUNT: number
  }>
}

export function DailyBrief() {
  const [data, setData] = useState<BriefData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/daily-brief')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-full"><Activity className="animate-spin text-atlas-blue" size={32} /></div>
  if (!data) return <div className="p-8 text-atlas-red">Failed to load brief</div>

  const { stats, recent_amendments, high_amendment_contracts } = data

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Sun className="text-amber-400" size={28} />
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Daily Brief</h1>
          <p className="text-sm text-slate-400">{new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
      </div>

      <div className="card-glow p-6">
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Portfolio Snapshot</h2>
        <div className="grid grid-cols-5 gap-4 text-center">
          <div><p className="text-2xl font-bold text-slate-100">{stats?.TOTAL_CONTRACTS}</p><p className="text-xs text-slate-500">Contracts</p></div>
          <div><p className="text-2xl font-bold text-slate-100">{stats?.TOTAL_AMENDMENTS}</p><p className="text-xs text-slate-500">Amendments</p></div>
          <div><p className="text-2xl font-bold text-slate-100">{stats?.COUNTERPARTIES}</p><p className="text-xs text-slate-500">Counterparties</p></div>
          <div><p className="text-2xl font-bold text-amber-400">{stats?.CURTAILMENT_CLAUSES}</p><p className="text-xs text-slate-500">Curtailment Clauses</p></div>
          <div><p className="text-2xl font-bold text-atlas-red">{stats?.DELIVERY_FAILURE_CLAUSES}</p><p className="text-xs text-slate-500">Delivery Failure</p></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="text-amber-400" size={18} />
            <h3 className="text-sm font-semibold text-slate-300">High Amendment Velocity Contracts</h3>
          </div>
          <div className="space-y-2">
            {(high_amendment_contracts || []).map(c => (
              <div key={c.CONTRACT_ID} className="flex items-center justify-between p-3 bg-navy-700/50 rounded-lg border border-navy-600/50">
                <div>
                  <p className="text-sm font-medium text-slate-200">{c.CONTRACT_NAME || c.COUNTERPARTY_NAME}</p>
                  <p className="text-xs text-slate-500">{c.COUNTERPARTY_NAME}</p>
                </div>
                <span className="text-sm font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">{c.AMD_COUNT} amd</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="text-atlas-blue" size={18} />
            <h3 className="text-sm font-semibold text-slate-300">Most Recent Amendments</h3>
          </div>
          <div className="space-y-2">
            {(recent_amendments || []).map(a => (
              <div key={a.AMENDMENT_ID} className="flex items-center justify-between p-3 bg-navy-700/50 rounded-lg border border-navy-600/50">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{a.CONTRACT_NAME || a.COUNTERPARTY_NAME}</p>
                  <p className="text-xs text-slate-500 flex items-center gap-1"><FileText size={10} /> {a.DOC_TYPE}</p>
                </div>
                <span className="text-xs text-slate-400 whitespace-nowrap ml-2">{a.EXECUTION_DATE?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
