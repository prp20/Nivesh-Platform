import React from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, Outlet } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Watchlist from './pages/Watchlist';
import AgentChat from './pages/AgentChat';
import StockListing from './pages/StockListing';
import Screener from './pages/Screener';
import MFListing from './pages/MFListing';
import MFCompare from './pages/MFCompare';
import IndicesListing from './pages/IndicesListing';
import Login from './pages/Login';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
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

const LayoutWrapper = () => {
  const outlet = <Outlet />;
  return <Layout>{outlet}</Layout>;
};

function App() {
  return (
    <Router>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />

            {/* Protected Routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<LayoutWrapper />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/stocks" element={<StockListing />} />
                <Route path="/stocks/:symbol" element={<StockDetailRoute />} />
                <Route path="/stock-compare" element={<StockCompare />} />
                <Route path="/screener" element={<Screener />} />
                <Route path="/mf" element={<MFListing />} />
                <Route path="/mf/:schemeCode" element={<MFDetailRoute />} />
                <Route path="/compare" element={<MFCompare />} />
                <Route path="/indices" element={<IndicesListing />} />
                <Route path="/indices/:benchmarkCode" element={<IndexDetailRoute />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/portfolio" element={<Portfolio />} />
                <Route path="/watchlist" element={<Watchlist />} />
                <Route path="/agent" element={<AgentChat />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Route>
          </Routes>
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
