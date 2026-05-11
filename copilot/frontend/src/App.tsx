import { useState } from 'react'
import { Layout } from './components/Layout'
import { Landing } from './pages/Landing'
import { ContractChat } from './pages/ContractChat'

export type Page = 'landing' | 'chat'

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('landing')

  if (currentPage === 'landing') {
    return <Landing onNavigate={setCurrentPage} />
  }

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      <ContractChat />
    </Layout>
  )
}

export default App
