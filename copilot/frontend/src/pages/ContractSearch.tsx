import { useState } from 'react'
import { Search, Filter, FileText, Activity } from 'lucide-react'

interface SearchResult {
  CHUNK_ID: string
  CONTRACT_ID: string
  CONTRACT_NAME: string
  COUNTERPARTY_NAME: string
  CLAUSE_TYPE: string
  DOC_TYPE: string
  SNIPPET: string
}

const CLAUSE_TYPES = ['ALL', 'CURTAILMENT', 'RA_REMEDY', 'METERING', 'DELIVERY_FAILURE', 'TERMINATION', 'PRICING', 'TERM', 'EANEP', 'DEGRADATION']

export function ContractSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [clauseFilter, setClauseFilter] = useState('ALL')
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)

  const doSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await fetch('/api/contracts/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 30, clause_type: clauseFilter === 'ALL' ? null : clauseFilter })
      })
      const data = await res.json()
      setResults(data.results || [])
    } catch { setResults([]) }
    setLoading(false)
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Contract Search</h1>
        <p className="text-sm text-slate-400 mt-1">Semantic search across 58,088 contract document chunks</p>
      </div>

      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doSearch()}
            placeholder="Search contract clauses... (e.g. curtailment notice, delivery failure remedy)"
            className="input pl-10"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-slate-500" />
          <select value={clauseFilter} onChange={e => setClauseFilter(e.target.value)}
            className="bg-navy-800 border border-navy-600 rounded-md px-3 py-2 text-sm text-slate-300 focus:border-atlas-blue focus:outline-none">
            {CLAUSE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button onClick={doSearch} className="btn-primary">Search</button>
      </div>

      {loading && <div className="flex justify-center py-8"><Activity className="animate-spin text-atlas-blue" size={24} /></div>}

      {!loading && results.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 space-y-3">
            {results.map(r => (
              <button key={r.CHUNK_ID} onClick={() => setSelectedResult(r)}
                className={`w-full text-left p-4 border rounded-lg transition ${selectedResult?.CHUNK_ID === r.CHUNK_ID ? 'border-atlas-blue bg-atlas-blue/5' : 'border-navy-600 bg-navy-800/80 hover:border-atlas-blue/30'}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-slate-200">{r.CONTRACT_NAME || r.COUNTERPARTY_NAME || r.CONTRACT_ID}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-400 border border-navy-600">{r.CLAUSE_TYPE}</span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-2">{r.SNIPPET}</p>
              </button>
            ))}
          </div>
          <div className="sticky top-0">
            {selectedResult && (
              <div className="card p-5">
                <div className="flex items-center gap-2 mb-3">
                  <FileText size={16} className="text-amber-400" />
                  <h3 className="text-sm font-semibold text-slate-300">Chunk Detail</h3>
                </div>
                <div className="space-y-2 text-xs">
                  <p><span className="text-slate-500">Contract:</span> <span className="font-medium text-slate-200">{selectedResult.CONTRACT_NAME || selectedResult.CONTRACT_ID}</span></p>
                  <p><span className="text-slate-500">Counterparty:</span> <span className="font-medium text-slate-200">{selectedResult.COUNTERPARTY_NAME}</span></p>
                  <p><span className="text-slate-500">Clause Type:</span> <span className="font-medium text-atlas-blue">{selectedResult.CLAUSE_TYPE}</span></p>
                  <p><span className="text-slate-500">Doc Type:</span> <span className="font-medium text-slate-200">{selectedResult.DOC_TYPE}</span></p>
                  <hr className="my-2 border-navy-600" />
                  <p className="text-slate-300 whitespace-pre-wrap leading-relaxed">{selectedResult.SNIPPET}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {!loading && results.length === 0 && query && <p className="text-center text-slate-500 py-8">No results found. Try different keywords.</p>}
    </div>
  )
}
