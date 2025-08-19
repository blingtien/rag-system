import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import DocumentManager from './pages/DocumentManager'
import QueryInterface from './pages/QueryInterface'
import SystemStatus from './pages/SystemStatus'
import Configuration from './pages/Configuration'

const { Content } = Layout

const App: React.FC = () => {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Sidebar />
        <Layout>
          <Content style={{ padding: '24px', background: '#f5f5f5' }}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/overview" element={<Overview />} />
              <Route path="/documents" element={<DocumentManager />} />
              <Route path="/query" element={<QueryInterface />} />
              <Route path="/status" element={<SystemStatus />} />
              <Route path="/config" element={<Configuration />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Router>
  )
}

export default App