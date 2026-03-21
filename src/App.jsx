import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import StockListing from './pages/StockListing';
import StockDetail from './pages/StockDetail';
import MFListing from './pages/MFListing';
import MFDetail from './pages/MFDetail';
import IndicesListing from './pages/IndicesListing';
import Login from './pages/Login';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import './App.css';

const AppContent = () => {
  const { user, loading } = useAuth();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [activeParams, setActiveParams] = useState('');

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') || 'dashboard';
      if (hash.startsWith('stock-detail-')) {
        setActiveTab('stock-detail');
        setActiveParams(hash.replace('stock-detail-', ''));
      } else if (hash.startsWith('mf-detail-')) {
        setActiveTab('mf-detail');
        setActiveParams(hash.replace('mf-detail-', ''));
      } else {
        setActiveTab(hash);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  if (loading) return <div className="loading-screen">Loading Nivesh...</div>;
  if (!user) return <Login />;

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'portfolio':
        return <Portfolio />;
      case 'stocks':
        return <StockListing />;
      case 'stock-detail':
        return <StockDetail symbol={activeParams} />;
      case 'mf':
        return <MFListing />;
      case 'mf-detail':
        return <MFDetail schemeCode={activeParams} />;
      case 'indices':
        return <IndicesListing />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <Layout>
      {renderContent()}
    </Layout>
  );
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
