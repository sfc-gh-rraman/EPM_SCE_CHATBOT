import { useEffect, useState } from 'react'
import { ChevronDown, FileText, Layers, Activity } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

interface Contract {
  CONTRACT_ID: string
  CONTRACT_NAME: string
  SUPPLIER: string
  CONTRACT_TYPE: string
  RESOURCE_TYPE: string
  CAPACITY_MW: number
  EXECUTION_DATE: string
  STATUS: string
  AMENDMENT_COUNT: number
  CHUNK_COUNT: number
}

interface DeepDiveData {
  contract: Record<string, any>
  amendments: Array<{ AMENDMENT_ID: string; AMENDMENT_NUMBER: number; EXECUTION_DATE: string; DOC_TYPE: string; FILE_NAME: string }>
  clause_distribution: Array<{ CLAUSE_TYPE: string; CNT: number }>
}

const COLORS = ['#f59e0b', '#58a6ff', '#3fb950', '#f85149', '#a371f7', '#ec4899', '#39c5cf']

export function ContractDeepDive() {
  const [contracts, setContracts] = useState<Contract[]>([])
  const [selected, setSelected] = useState<string>('')
  const [detail, setDetail] = useState<DeepDiveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)

  useEffect(() => {
    fetch('/api/contracts/all')
      .then(r => r.json())
      .then(d => { setContracts(d.rows || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    setDetailLoading(true)
    fetch(`/api/contracts/${selected}/deep-dive`)
      .then(r => r.json())
      .then(d => { setDetail(d); setDetailLoading(false) })
      .catch(() => setDetailLoading(false))
  }, [selected])

  if (loading) return <div className="flex items-center justify-center h-full"><Activity className="animate-spin text-atlas-blue" size={32} /></div>

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Contract Deep Dive</h1>
        <p className="text-sm text-slate-400 mt-1">Select a contract to explore its amendments, clauses, and metadata</p>
      </div>

      <div className="relative">
        <button onClick={() => setShowDropdown(!showDropdown)} className="w-full flex items-center justify-between card px-4 py-3 text-left hover:border-atlas-blue/30 transition">
          <span className="text-sm text-slate-300">{selected ? contracts.find(c => c.CONTRACT_ID === selected)?.CONTRACT_NAME || selected : 'Select a contract...'}</span>
          <ChevronDown size={16} className="text-slate-400" />
        </button>
        {showDropdown && (
          <div className="absolute z-50 mt-1 w-full bg-navy-800 border border-navy-600 rounded-lg shadow-lg max-h-72 overflow-y-auto">
            {contracts.map(c => (
              <button key={c.CONTRACT_ID} onClick={() => { setSelected(c.CONTRACT_ID); setShowDropdown(false) }}
                className="w-full text-left px-4 py-2 text-sm hover:bg-navy-700 text-slate-300 flex justify-between items-center">
                <span className="truncate">{c.CONTRACT_NAME || c.SUPPLIER || c.CONTRACT_ID}</span>
                <span className="text-xs text-slate-500 ml-2">{c.AMENDMENT_COUNT} amd</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {detailLoading && <div className="flex justify-center py-12"><Activity className="animate-spin text-atlas-blue" size={24} /></div>}

      {detail && !detailLoading && (
        <div className="space-y-6">
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Contract Metadata</h3>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div><span className="text-slate-500">Name:</span> <span className="font-medium text-slate-200">{detail.contract.CONTRACT_NAME}</span></div>
              <div><span className="text-slate-500">Counterparty:</span> <span className="font-medium text-slate-200">{detail.contract.SUPPLIER}</span></div>
              <div><span className="text-slate-500">Type:</span> <span className="font-medium text-slate-200">{detail.contract.CONTRACT_TYPE}</span></div>
              <div><span className="text-slate-500">Execution:</span> <span className="font-medium text-slate-200">{detail.contract.EXECUTION_DATE?.slice(0, 10)}</span></div>
              <div><span className="text-slate-500">Resource:</span> <span className="font-medium text-slate-200">{detail.contract.RESOURCE_TYPE}</span></div>
              <div><span className="text-slate-500">Status:</span> <span className="font-medium text-slate-200">{detail.contract.STATUS}</span></div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <Layers size={16} className="text-atlas-blue" />
                <h3 className="text-sm font-semibold text-slate-300">Amendments ({detail.amendments.length})</h3>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {detail.amendments.map(a => (
                  <div key={a.AMENDMENT_ID} className="p-3 bg-navy-700/50 rounded-lg border border-navy-600/50">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-slate-200">#{a.AMENDMENT_NUMBER} — {a.DOC_TYPE}</span>
                      <span className="text-xs text-slate-500">{a.EXECUTION_DATE?.slice(0, 10)}</span>
                    </div>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{a.FILE_NAME}</p>
                  </div>
                ))}
                {detail.amendments.length === 0 && <p className="text-sm text-slate-500">No amendments found</p>}
              </div>
            </div>

            <div className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={16} className="text-atlas-green" />
                <h3 className="text-sm font-semibold text-slate-300">Clause Distribution</h3>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={detail.clause_distribution || []} dataKey="CNT" nameKey="CLAUSE_TYPE" cx="50%" cy="50%" outerRadius={80} label={({ CLAUSE_TYPE }) => CLAUSE_TYPE}>
                    {(detail.clause_distribution || []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, color: '#e2e8f0' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
