import { MessageSquare, Activity } from 'lucide-react'
import type { Page } from '../App'

interface LayoutProps {
  children: React.ReactNode
  currentPage: Page
  onNavigate: (page: Page) => void
}

const navItems = [
  { id: 'chat' as Page, label: 'Contract Chat', icon: MessageSquare },
]

export function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  return (
    <div className="h-screen flex overflow-hidden bg-slate-50">
      <aside className="w-64 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="h-16 flex items-center px-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
              <span className="text-slate-900 font-bold text-sm">S</span>
            </div>
            <div>
              <span className="font-bold text-lg text-white">SCE EPM</span>
              <span className="text-xs text-slate-400 block -mt-1">Contract Assistant</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = currentPage === item.id
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
                  ${isActive ? 'bg-amber-400/10 text-amber-300' : 'text-slate-400 hover:text-white hover:bg-slate-800'}`}
              >
                <item.icon size={20} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 text-xs">
          <div className="flex items-center justify-between text-slate-400">
            <span>Status</span>
            <span className="flex items-center gap-1 text-emerald-400">
              <Activity size={12} /> Online
            </span>
          </div>
          <p className="text-slate-500 mt-2">Snowflake Cortex Agents</p>
        </div>
      </aside>

      <main className="flex-1 overflow-hidden flex flex-col bg-white">
        {children}
      </main>
    </div>
  )
}
