import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
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

    const navItems = [
        { name: 'Homepage', icon: 'home', path: '/dashboard' },
        { name: 'Stocks Listing', icon: 'monitoring', path: '/stocks' },
        { name: 'Mutual Funds', icon: 'account_balance', path: '/mf' },
        { name: 'Compare Funds', icon: 'compare_arrows', path: '/compare', badge: compareList.length },
        { name: 'Portfolio Page', icon: 'account_balance_wallet', path: '/portfolio' },
        { name: 'Admin Panel', icon: 'admin_panel_settings', path: '/admin' },
    ];

    return (
        <aside className="h-screen w-72 left-0 top-0 fixed bg-[#0f1419] border-r border-white/5 flex flex-col py-10 z-40 hidden lg:flex shadow-2xl">
            {/* Branding block */}
            <div className="px-8 mb-10">
                <div className="text-[11px] font-label font-black uppercase tracking-[0.25em] text-primary mb-1">The Sovereign Ledger</div>
                <div className="text-[9px] font-label font-black uppercase tracking-[0.3em] text-slate-500">Private Tier</div>
            </div>

            <nav className="flex-1 space-y-1">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `
                            flex items-center justify-between py-5 font-body text-[11px] tracking-[0.2em] uppercase font-bold transition-all duration-300 group
                            ${isActive
                                ? 'text-[#e9c349] bg-primary/10 rounded-r-full px-8'
                                : 'text-slate-500 hover:bg-white/5 hover:text-slate-200 px-8'}
                        `}
                    >
                        {({ isActive }) => (
                            <>
                                <div className="flex items-center gap-4">
                                    <span className={`material-symbols-outlined transition-transform duration-300 group-hover:scale-110 ${isActive ? 'scale-110' : ''}`}>{item.icon}</span>
                                    <span>{item.name}</span>
                                </div>
                                {item.badge > 0 && (
                                    <span className="bg-primary text-on-primary text-[10px] px-2 py-0.5 rounded-full font-black animate-pulse shadow-lg shadow-primary/20">
                                        {item.badge}
                                    </span>
                                )}
                            </>
                        )}
                    </NavLink>
                ))}
            </nav>

            <div className="px-8 mt-auto space-y-6">
                <button className="w-full gold-gradient text-on-primary py-4 rounded-xl font-bold text-[10px] tracking-widest uppercase shadow-xl shadow-primary/10 transition-all hover:brightness-110 active:scale-95">
                    Expert Concierge
                </button>
                <div className="pt-6 border-t border-white/5 flex flex-col gap-5">
                    <div className="flex items-center gap-4 text-slate-500 hover:text-white cursor-pointer transition-colors text-xs font-bold tracking-widest uppercase">
                        <span className="material-symbols-outlined text-lg">help_center</span>
                        <span>Support</span>
                    </div>
                    <div
                        className="flex items-center gap-4 text-slate-500 hover:text-error cursor-pointer transition-colors text-xs font-bold tracking-widest uppercase"
                        onClick={() => { logout(); navigate('/login'); }}
                    >
                        <span className="material-symbols-outlined text-lg">logout</span>
                        <span>Logout</span>
                    </div>
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
