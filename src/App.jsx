import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import StockListing from './pages/StockListing';
import StockDetail from './pages/StockDetail';
import MFListing from './pages/MFListing';
import MFDetail from './pages/MFDetail';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Layout';
import './App.css';

function App() {
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
        return <MFDetail name={activeParams} />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <ThemeProvider>
      <Layout>
        {renderContent()}
      </Layout>
    </ThemeProvider>
  );
}

export default App;
