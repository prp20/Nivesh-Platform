import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useSelector } from 'react-redux';
import fundService from '../api/services/fundService';
import { useAuth } from '../context/AuthContext';

// ─── Error Boundary ───────────────────────────────────────────────────────────

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }
    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }
    componentDidCatch(error, info) {
        console.error('[ErrorBoundary]', error, info);
    }
    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-16 text-center">
                    <span className="material-symbols-outlined text-error text-6xl mb-6">error</span>
                    <h2 className="text-2xl font-headline font-bold text-white mb-3 uppercase tracking-widest">Something went wrong</h2>
                    <p className="text-slate-500 text-sm mb-8">{this.state.error?.message}</p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="px-8 py-3 gold-gradient rounded-xl text-on-primary font-black uppercase tracking-widest text-sm"
                    >
                        Retry
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

// ─── Top Nav Bar ──────────────────────────────────────────────────────────────

const TopNavBar = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [results, setResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const navigate = useNavigate();
    const dropdownRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        const timer = setTimeout(async () => {
            const trimmedQuery = searchQuery.trim();
            if (trimmedQuery.length > 2) {
                setIsSearching(true);
                try {
                    const data = await fundService.getFunds(0, 20, null, null, null, null, 'scheme_name', trimmedQuery);
                    setResults(data.items || []);
                    setShowDropdown(true);
                } catch (error) {
                    console.error("[Matrix Search] Malfunction:", error);
                } finally {
                    setIsSearching(false);
                }
            } else {
                setResults([]);
                setShowDropdown(false);
            }
        }, 400);

        return () => clearTimeout(timer);
    }, [searchQuery]);

    const handleSelect = (schemeCode) => {
        navigate(`/mf/${schemeCode}`);
        setSearchQuery('');
        setShowDropdown(false);
    };

    return (
        <header className="w-full h-20 top-0 sticky bg-[#0f1419]/80 backdrop-blur-xl border-b border-white/5 shadow-[0_8px_32px_rgba(233,195,73,0.06)] flex justify-between items-center px-6 md:px-12 xl:px-24 2xl:px-32 z-50 transition-all duration-300">
            <div className="flex items-center gap-6 md:gap-12">
                <Link to="/dashboard" className="text-xl md:text-2xl font-headline font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-[#e9c349] to-[#9d7e00] hover:scale-[1.02] transition-transform">Nivesh Elite</Link>
                <nav className="hidden lg:flex gap-8 items-center font-label">
                    <NavLink to="/portfolio" className={({ isActive }) => `text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300 ${isActive ? 'text-primary' : 'text-slate-500 hover:text-white'}`}>Portfolio</NavLink>
                    <NavLink to="/indices" className={({ isActive }) => `text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300 ${isActive ? 'text-primary' : 'text-slate-500 hover:text-white'}`}>Market Indices</NavLink>
                    <NavLink to="/mf" className={({ isActive }) => `text-[10px] font-black uppercase tracking-[0.2em] transition-all duration-300 ${isActive ? 'text-primary' : 'text-slate-500 hover:text-white'}`}>Wealth Vault</NavLink>
                </nav>
            </div>

            <div className="flex items-center gap-6 flex-1 justify-end">
                <div className="relative hidden xl:block w-full max-w-md" ref={dropdownRef}>
                    <div className="relative group">
                        <span className={`material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-sm transition-colors ${isSearching ? 'text-primary animate-spin' : 'text-slate-600 group-focus-within:text-primary'}`}>
                            {isSearching ? 'sync' : 'search'}
                        </span>
                        <input
                            className="w-full bg-surface-container-lowest/40 border border-[#45464c]/10 rounded-xl pl-12 pr-4 py-2.5 text-[11px] font-label font-bold text-white placeholder:text-slate-700 focus:outline-none focus:border-primary/30 focus:ring-4 focus:ring-primary/5 transition-all uppercase tracking-widest italic"
                            placeholder="SEARCH MASTER LEDGER..."
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onFocus={() => searchQuery.length > 2 && setShowDropdown(true)}
                        />
                    </div>

                    <AnimatePresence>
                        {showDropdown && (
                            <motion.div
                                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 10, scale: 0.98 }}
                                className="absolute top-full mt-4 left-0 right-0 glass-panel rounded-2xl shadow-[0_32px_64px_rgba(0,0,0,0.8)] border border-[#45464c]/20 overflow-hidden z-[100] max-h-[400px] overflow-y-auto no-scrollbar"
                            >
                                {results.length > 0 ? (
                                    <div className="p-2">
                                        {results.map((fund) => (
                                            <button
                                                key={fund.scheme_code}
                                                onClick={() => handleSelect(fund.scheme_code)}
                                                className="w-full text-left p-4 hover:bg-white/[0.03] rounded-xl transition-all group flex items-center justify-between border border-transparent hover:border-white/5"
                                            >
                                                <div className="flex flex-col gap-1">
                                                    <div className="text-[11px] font-headline font-bold text-white group-hover:text-primary transition-colors uppercase italic tracking-tight">{fund.scheme_name}</div>
                                                    <div className="flex items-center gap-3">
                                                        <span className="text-[9px] text-slate-500 font-black tracking-widest uppercase font-label">{fund.scheme_code}</span>
                                                        <span className="text-[8px] px-2 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded font-black uppercase tracking-tighter">{fund.scheme_category}</span>
                                                    </div>
                                                </div>
                                                <span className="material-symbols-outlined text-slate-700 text-sm opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-1">chevron_right</span>
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="p-12 text-center flex flex-col items-center gap-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-800 font-thin">search_off</span>
                                        <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.4em] italic font-label">No Cryptographic Matches</p>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <div className="flex items-center gap-3 md:gap-5 text-slate-500">
                    <span className="material-symbols-outlined cursor-pointer hover:text-primary transition-colors text-xl font-thin">notifications</span>
                    <NavLink to="/admin" className={({ isActive }) => `material-symbols-outlined cursor-pointer hover:text-primary transition-colors text-xl font-thin ${isActive ? 'text-primary' : ''}`}>settings</NavLink>
                    <div className="h-10 w-10 md:h-11 md:w-11 rounded-full border-[2px] border-primary/30 hover:border-primary transition-all overflow-hidden cursor-pointer shadow-lg shadow-primary/5 active:scale-95">
                        <img alt="Elite Client Profile" className="w-full h-full object-cover grayscale hover:grayscale-0 transition-all" src="https://ui-avatars.com/api/?name=Elite+User&background=e9c349&color=0f1419" />
                    </div>
                </div>
            </div>
        </header>
    );
};

// ─── Side Nav Bar ─────────────────────────────────────────────────────────────

const SideNavBar = () => {
    const { compareList } = useSelector((state) => state.compare);
    const { logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    // Determine default open states based on current URL
    const searchParams = new URLSearchParams(location.search);
    const tab = searchParams.get('tab');
    const isAdminActive = location.pathname.startsWith('/admin') && (!tab || tab === 'dashboard' || tab === 'assets' || tab === 'logs');
    const isSystemActive = location.pathname.startsWith('/admin') && (tab === 'health' || tab === 'pipeline');

    const [isAdminOpen, setIsAdminOpen] = useState(isAdminActive);
    const [isSystemOpen, setIsSystemOpen] = useState(isSystemActive);

    const isActive = (path) => location.pathname === path;

    const navItemBaseClass = "flex items-center justify-between px-8 py-4 text-slate-500 hover:text-slate-200 hover:bg-[#45464c]/10 transition-all duration-200 group";
    const navItemActiveClass = "flex items-center justify-between px-8 py-4 text-[#e9c349] border-r-2 border-[#e9c349] bg-gradient-to-r from-[#e9c349]/10 to-transparent group";
    
    return (
        <aside className="h-screen w-72 left-0 top-0 fixed bg-[#0f1419] border-r border-[#45464c]/15 flex flex-col py-8 z-40 hidden lg:flex shadow-2xl overflow-y-auto no-scrollbar pt-24">
            {/* Branding block */}
            <div className="px-8 mb-10 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full border-2 border-primary overflow-hidden flex items-center justify-center bg-primary/10">
                    <span className="material-symbols-outlined text-primary text-xl">security</span>
                </div>
                <div>
                    <h2 className="text-lg font-black text-[#e9c349] tracking-tight whitespace-nowrap">The Sovereign</h2>
                    <p className="text-[10px] font-label uppercase tracking-[0.2em] text-slate-500">Private Wealth Tier</p>
                </div>
            </div>

            <nav className="flex-1 flex flex-col gap-1">
                {/* Portfolio */}
                <div>
                    <NavLink to="/portfolio" className={({ isActive }) => isActive ? navItemActiveClass : navItemBaseClass}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">account_balance_wallet</span>
                            <span className="font-medium text-sm">Portfolio</span>
                        </div>
                    </NavLink>
                </div>
                {/* Markets -> Stocks */}
                <div>
                    <NavLink to="/stocks" className={({ isActive }) => isActive ? navItemActiveClass : navItemBaseClass}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">insights</span>
                            <span className="font-medium text-sm">Stocks</span>
                        </div>
                    </NavLink>
                </div>
                {/* Mutual Funds */}
                <div>
                    <NavLink to="/mf" className={({ isActive }) => isActive ? navItemActiveClass : navItemBaseClass}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">lock</span>
                            <span className="font-medium text-sm">Mutual Funds</span>
                        </div>
                    </NavLink>
                </div>
                {/* Intelligence Matrix - Stock Comparison */}
                <div>
                    <NavLink to="/stock-compare" className={({ isActive }) => isActive ? navItemActiveClass : navItemBaseClass}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">query_stats</span>
                            <span className="font-medium text-sm">Stock Comparison</span>
                        </div>
                    </NavLink>
                </div>
                {/* Intelligence Matrix - Fund Comparison */}
                <div>
                    <NavLink to="/compare" className={({ isActive }) => isActive ? navItemActiveClass : navItemBaseClass}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">compare_arrows</span>
                            <span className="font-medium text-sm flex items-center justify-between gap-4">Fund Comparison {compareList?.length > 0 && <span className="bg-primary text-black rounded-full px-1.5 text-[8px] font-bold leading-tight">{compareList.length}</span>}</span>
                        </div>
                    </NavLink>
                </div>
                {/* System */}
                <div className="mb-1">
                    <button onClick={() => setIsSystemOpen(!isSystemOpen)} className={isSystemActive ? navItemActiveClass : navItemBaseClass + " w-full"}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">dns</span>
                            <span className="font-medium text-sm">System</span>
                        </div>
                        <span className={`material-symbols-outlined text-sm transition-transform ${isSystemOpen ? 'rotate-180' : ''}`}>expand_more</span>
                    </button>
                    <AnimatePresence>
                        {isSystemOpen && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="flex flex-col mt-1 mb-2 bg-[#1b2025]/30 overflow-hidden">
                                <Link to="/admin?tab=health" className={`flex items-center gap-4 pl-16 py-3 transition-colors border-l-2 ${tab === 'health' ? 'text-[#e9c349] font-bold border-[#e9c349]' : 'text-slate-400 hover:text-primary border-transparent hover:border-primary/30'}`}>
                                    <span className="font-medium text-xs">Health Dashboard</span>
                                </Link>
                                <Link to="/admin?tab=pipeline" className={`flex items-center gap-4 pl-16 py-3 transition-colors border-l-2 ${tab === 'pipeline' ? 'text-[#e9c349] font-bold border-[#e9c349]' : 'text-slate-400 hover:text-primary border-transparent hover:border-primary/30'}`}>
                                    <span className="font-medium text-xs">Node Manager</span>
                                </Link>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                {/* Admin */}
                <div className="mb-1">
                    <button onClick={() => setIsAdminOpen(!isAdminOpen)} className={isAdminActive ? navItemActiveClass : navItemBaseClass + " w-full"}>
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">admin_panel_settings</span>
                            <span className="font-medium text-sm">Admin</span>
                        </div>
                        <span className={`material-symbols-outlined text-sm transition-transform ${isAdminOpen ? 'rotate-180' : ''}`}>expand_more</span>
                    </button>
                    <AnimatePresence>
                        {isAdminOpen && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="flex flex-col mt-1 mb-2 bg-[#1b2025]/30 overflow-hidden">
                                <Link to="/admin?tab=dashboard" className={`flex items-center gap-4 pl-16 py-3 transition-colors border-l-2 ${tab === 'dashboard' || (!tab && location.pathname === '/admin') ? 'text-[#e9c349] font-bold border-[#e9c349]' : 'text-slate-400 hover:text-primary border-transparent hover:border-primary/30'}`}>
                                    <span className="font-medium text-xs">Command Center</span>
                                </Link>
                                <Link to="/admin?tab=assets" className={`flex items-center gap-4 pl-16 py-3 transition-colors border-l-2 ${tab === 'assets' ? 'text-[#e9c349] font-bold border-[#e9c349]' : 'text-slate-400 hover:text-primary border-transparent hover:border-primary/30'}`}>
                                    <span className="font-medium text-xs">Asset Management</span>
                                </Link>
                                <Link to="/admin?tab=logs" className={`flex items-center gap-4 pl-16 py-3 transition-colors border-l-2 ${tab === 'logs' ? 'text-[#e9c349] font-bold border-[#e9c349]' : 'text-slate-400 hover:text-primary border-transparent hover:border-primary/30'}`}>
                                    <span className="font-medium text-xs">Audit Logs</span>
                                </Link>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </nav>

            <div className="px-8 mt-auto flex flex-col gap-2 pt-6">
                <div className="flex flex-col gap-1">
                    <button className="flex items-center justify-between py-3 text-slate-500 hover:text-slate-200 transition-colors w-full group">
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined text-xl">settings</span>
                            <span className="font-medium text-sm">Preferences</span>
                        </div>
                    </button>
                    {/* 
                    <button onClick={() => { logout(); navigate('/login'); }} className="flex items-center justify-between py-3 text-slate-500 hover:text-error transition-colors w-full group">
                        <div className="flex items-center gap-4">
                            <span className="material-symbols-outlined text-xl group-hover:translate-x-1 transition-transform">logout</span>
                            <span className="font-medium text-sm">Terminal Exit</span>
                        </div>
                    </button>
                    */}
                </div>
            </div>
        </aside>
    );
};

// ─── Layout ───────────────────────────────────────────────────────────────────

const Layout = ({ children }) => {
    return (
        <div className="bg-[#0a0f12] text-on-background font-body min-h-screen selection:bg-primary/30 flex flex-col">
            <TopNavBar />
            <div className="flex flex-1">
                <SideNavBar />
                <div className="flex-1 lg:pl-72 flex flex-col transition-all duration-300 w-full">
                    <div className="flex-1 w-full">
                        <ErrorBoundary>{children}</ErrorBoundary>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Layout;
