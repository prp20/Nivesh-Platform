import React from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import StockListing from './pages/StockListing';
import Screener from './pages/Screener';
import MFListing from './pages/MFListing';
import MFCompare from './pages/MFCompare';
import IndicesListing from './pages/IndicesListing';
import Login from './pages/Login';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import StockDetail from './pages/StockDetail';
import MFDetail from './pages/MFDetail';
import IndexDetail from './pages/IndexDetail';
import Admin from './pages/Admin';
import StockCompare from './pages/StockCompare';

const StockDetailRoute = () => {
  const { symbol } = useParams();
  return <StockDetail symbol={symbol} />;
}

const MFDetailRoute = () => {
  const { schemeCode } = useParams();
  return <MFDetail schemeCode={schemeCode} />;
}

const IndexDetailRoute = () => {
  const { benchmarkCode } = useParams();
  return <IndexDetail benchmarkCode={benchmarkCode} />;
}

const AppContent = () => {
  const { user, loading } = useAuth();
  
  if (loading) return (
      <div className="min-h-screen bg-[#0f1419] flex items-center justify-center">
          <div className="w-12 h-12 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin"></div>
      </div>
  );

  return (
    <Layout>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/login" element={!user ? <Login /> : <Navigate to="/dashboard" replace />} />
        
        {/* Protected Routes */}
        <Route path="/portfolio" element={user ? <Portfolio /> : <Navigate to="/login" replace />} />
        <Route path="/stocks" element={user ? <StockListing /> : <Navigate to="/login" replace />} />
        <Route path="/stocks/:symbol" element={user ? <StockDetailRoute /> : <Navigate to="/login" replace />} />
        <Route path="/stock-compare" element={user ? <StockCompare /> : <Navigate to="/login" replace />} />
        <Route path="/screener" element={user ? <Screener /> : <Navigate to="/login" replace />} />
        <Route path="/mf" element={user ? <MFListing /> : <Navigate to="/login" replace />} />
        <Route path="/mf/:schemeCode" element={user ? <MFDetailRoute /> : <Navigate to="/login" replace />} />
        <Route path="/compare" element={user ? <MFCompare /> : <Navigate to="/login" replace />} />
        <Route path="/indices" element={user ? <IndicesListing /> : <Navigate to="/login" replace />} />
        <Route path="/indices/:benchmarkCode" element={user ? <IndexDetailRoute /> : <Navigate to="/login" replace />} />
        <Route path="/admin" element={user ? <Admin /> : <Navigate to="/login" replace />} />
        
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
};



function App() {
  return (
    <Router>
      <ThemeProvider>
        <AuthProvider>
          <AppContent />
          <Toaster 
            position="top-right"
            toastOptions={{
              style: {
                background: '#1b2025',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '16px',
                fontFamily: 'Manrope, sans-serif',
                fontSize: '14px',
              },
            }}
          />
        </AuthProvider>
      </ThemeProvider>
    </Router>
  );
}

export default App;
