import { useState } from 'react'
import { Layout } from './components/Layout'
import { Landing } from './pages/Landing'
import { ContractChat } from './pages/ContractChat'
import { PortfolioDashboard } from './pages/PortfolioDashboard'
import { DailyBrief } from './pages/DailyBrief'
import { ContractDeepDive } from './pages/ContractDeepDive'
import { ClauseAnalytics } from './pages/ClauseAnalytics'
import { ContractSearch } from './pages/ContractSearch'
import { ResourceMap } from './pages/ResourceMap'
import { Architecture } from './pages/Architecture'

export type Page = 'landing' | 'dashboard' | 'brief' | 'chat' | 'deep-dive' | 'analytics' | 'search' | 'resource-map' | 'architecture'

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('landing')

  if (currentPage === 'landing') {
    return <Landing onNavigate={setCurrentPage} />
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return <PortfolioDashboard />
      case 'brief': return <DailyBrief />
      case 'chat': return <ContractChat />
      case 'deep-dive': return <ContractDeepDive />
      case 'analytics': return <ClauseAnalytics />
      case 'search': return <ContractSearch />
      case 'resource-map': return <ResourceMap />
      case 'architecture': return <Architecture />
      default: return <ContractChat />
    }
  }

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      {renderPage()}
    </Layout>
  )
}

export default App
