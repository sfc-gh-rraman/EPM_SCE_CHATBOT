import { Sparkles, FileText, Zap, BarChart3, ArrowRight } from 'lucide-react'
import type { Page } from '../App'

interface LandingProps {
  onNavigate: (page: Page) => void
}

const SAMPLE_QUESTIONS = [
  "How many amendments does CTR-001 have, and what does each one cover?",
  "What changed in the most recent amendment to CTR-005?",
  "Show me contracts with economic curtailment terms",
  "Show me contracts with capacity > 10 MW",
  "How do our contracts handle failure to deliver Resource Adequacy?",
  "Which contracts are paid by SCE meter but have a separate ISO meter?",
]

const FEATURES = [
  {
    icon: FileText,
    title: 'Amendment Intelligence',
    desc: 'Parses contract amendments from filenames and extracts clause-level changes via Cortex Search.',
  },
  {
    icon: Zap,
    title: 'Curtailment & Capacity',
    desc: 'Filter the active book by curtailment type, capacity threshold, supplier, or POI substation.',
  },
  {
    icon: BarChart3,
    title: 'Concept Extraction',
    desc: 'Cross-contract retrieval — group distinct legal approaches to RA delivery, product deficiency, EANEP, and metering.',
  },
]

export function Landing({ onNavigate }: LandingProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white">
      <div className="max-w-6xl mx-auto px-8 py-16">
        <div className="flex items-center gap-3 mb-8">
          <Sparkles className="w-8 h-8 text-amber-400" />
          <span className="text-lg tracking-widest text-amber-300/80 uppercase">
            SCE EPM Contract Intelligence
          </span>
        </div>

        <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
          Ask anything about your<br/>
          <span className="bg-gradient-to-r from-amber-300 to-orange-400 bg-clip-text text-transparent">
            PPA, RA, and Tolling contracts.
          </span>
        </h1>

        <p className="text-xl text-slate-300 max-w-3xl mb-10">
          A Snowflake-native chatbot that combines structured contract metadata with
          PDF clause-level retrieval, so portfolio teams can answer questions in seconds
          instead of digging through SharePoint.
        </p>

        <div className="flex gap-4">
          <button
            onClick={() => onNavigate('dashboard')}
            className="inline-flex items-center gap-2 px-8 py-4 bg-amber-400 hover:bg-amber-300 text-slate-900 font-semibold rounded-lg transition-all shadow-lg shadow-amber-500/30"
          >
            Open Dashboard <ArrowRight className="w-5 h-5" />
          </button>
          <button
            onClick={() => onNavigate('chat')}
            className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-lg transition-all border border-white/20"
          >
            Contract Chat <ArrowRight className="w-5 h-5" />
          </button>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mt-20">
          {FEATURES.map((f) => {
            const Icon = f.icon
            return (
              <div key={f.title} className="bg-white/5 backdrop-blur border border-white/10 rounded-xl p-6">
                <Icon className="w-8 h-8 text-amber-300 mb-4" />
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-slate-300 text-sm">{f.desc}</p>
              </div>
            )
          })}
        </div>

        <div className="mt-16">
          <h2 className="text-2xl font-semibold mb-4">Try one of these questions</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => onNavigate('chat')}
                className="text-left px-5 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-200 transition"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
