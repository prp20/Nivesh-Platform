import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useSelector } from 'react-redux';
import fundService from '../api/services/fundService';
import stockService from '../api/services/stockService';
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

// ─── Dropdown Menu ─────────────────────────────────────────────────────────────

const NavDropdown = ({ label, icon, children, isAnyActive }) => {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen((v) => !v)}
                className={`flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.18em] transition-all duration-200 px-1 py-1 rounded-lg group
                    ${isAnyActive ? 'text-primary' : 'text-slate-400 hover:text-white'}`}
            >
                {icon && <span className="material-symbols-outlined text-[15px] font-thin">{icon}</span>}
                {label}
                <span className={`material-symbols-outlined text-[13px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>
                    expand_more
                </span>
            </button>

            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 6, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className="absolute top-full left-0 mt-2 min-w-[180px] bg-[#161c22] border border-white/8 rounded-xl shadow-[0_16px_40px_rgba(0,0,0,0.7)] z-[200] overflow-hidden"
                    >
                        {children({ close: () => setOpen(false) })}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const DropdownItem = ({ to, icon, label, badge, close, matchSearch }) => {
    const location = useLocation();
    const isActive = matchSearch
        ? location.pathname === to.split('?')[0] && location.search.includes(matchSearch)
        : location.pathname === to || (to.includes('?') && location.pathname === to.split('?')[0] && location.search === '?' + to.split('?')[1]);

    return (
        <NavLink
            to={to}
            onClick={close}
            className={`flex items-center gap-3 px-4 py-3 text-[11px] font-semibold transition-all group border-l-2
                ${isActive
                    ? 'text-primary bg-primary/8 border-primary'
                    : 'text-slate-400 hover:text-white hover:bg-white/4 border-transparent'
                }`}
        >
            {icon && <span className="material-symbols-outlined text-[16px] font-thin">{icon}</span>}
            <span className="flex-1">{label}</span>
            {badge !== undefined && badge > 0 && (
                <span className="bg-primary text-black rounded-full px-1.5 text-[8px] font-bold leading-tight">{badge}</span>
            )}
        </NavLink>
    );
};

// ─── Top Nav Bar ──────────────────────────────────────────────────────────────

const TopNavBar = ({ onMobileMenuClick, isMobileMenuOpen }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [results, setResults] = useState({ stocks: [], funds: [] });
    const [isSearching, setIsSearching] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const dropdownRef = useRef(null);
    const settingsRef = useRef(null);
    const { logout } = useAuth();
    const { compareList } = useSelector((state) => state.compare);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowDropdown(false);
            }
            if (settingsRef.current && !settingsRef.current.contains(event.target)) {
                setSettingsOpen(false);
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
                    const [fundRes, stockRes] = await Promise.all([
                        fundService.getFunds(0, 10, null, null, null, null, 'scheme_name', trimmedQuery),
                        stockService.searchStocks(trimmedQuery)
                    ]);
                    setResults({
                        funds: fundRes.items || [],
                        stocks: stockRes.results || []
                    });
                    setShowDropdown(true);
                } catch (error) {
                    console.error("[Search] Error:", error);
                } finally {
                    setIsSearching(false);
                }
            } else {
                setResults({ stocks: [], funds: [] });
                setShowDropdown(false);
            }
        }, 400);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const handleSelect = (path) => {
        navigate(path);
        setSearchQuery('');
        setShowDropdown(false);
    };

    const hasResults = results.stocks.length > 0 || results.funds.length > 0;

    // Active state helpers
    const isStocksActive = ['/stocks', '/indices', '/stock-compare'].some(p => location.pathname.startsWith(p));
    const isMFActive = ['/mf', '/compare'].some(p => location.pathname.startsWith(p));
    const isPortfolioActive = location.pathname.startsWith('/portfolio');
    const isSettingsActive = location.pathname.startsWith('/admin');

    const searchParams = new URLSearchParams(location.search);
    const tab = searchParams.get('tab');

    return (
        <header className="w-full h-[64px] top-0 sticky bg-[#0f1419]/95 backdrop-blur-xl border-b border-white/5 shadow-[0_4px_24px_rgba(0,0,0,0.4)] flex items-center px-4 md:px-8 lg:px-12 z-[150] gap-4">
            {/* Brand */}
            <Link
                to="/dashboard"
                className="text-xl font-headline font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-[#e9c349] to-[#b8942e] hover:opacity-90 transition-opacity shrink-0"
            >
                Nivesh Platform
            </Link>

            {/* Desktop Nav */}
            <nav className="hidden lg:flex items-center gap-1 ml-6">
                {/* Stocks Group */}
                <NavDropdown label="Stocks" icon="show_chart" isAnyActive={isStocksActive}>
                    {({ close }) => (
                        <>
                            <DropdownItem to="/stocks" icon="insights" label="Stocks" close={close} />
                            <DropdownItem to="/indices" icon="bar_chart" label="Indices" close={close} />
                            <DropdownItem to="/stock-compare" icon="query_stats" label="Compare Stocks" close={close} />
                        </>
                    )}
                </NavDropdown>

                {/* Mutual Funds Group */}
                <NavDropdown label="Mutual Funds" icon="account_balance" isAnyActive={isMFActive}>
                    {({ close }) => (
                        <>
                            <DropdownItem to="/mf" icon="lock" label="Mutual Funds" close={close} />
                            <DropdownItem
                                to="/compare"
                                icon="compare_arrows"
                                label="Compare Funds"
                                badge={compareList?.length}
                                close={close}
                            />
                        </>
                    )}
                </NavDropdown>

                {/* Portfolio — direct link */}
                <NavLink
                    to="/portfolio"
                    className={({ isActive }) =>
                        `flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.18em] transition-all duration-200 px-1 py-1 rounded-lg
                        ${isActive ? 'text-primary' : 'text-slate-400 hover:text-white'}`
                    }
                >
                    <span className="material-symbols-outlined text-[15px] font-thin">account_balance_wallet</span>
                    Portfolio
                </NavLink>
            </nav>

            {/* Search */}
            <div className="flex-1 flex justify-center">
                <div className="relative w-full max-w-xs sm:max-w-sm md:max-w-md hidden sm:block" ref={dropdownRef}>
                    <div className="relative group">
                        <span className={`material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-[16px] transition-colors ${isSearching ? 'text-primary animate-spin' : 'text-slate-600 group-focus-within:text-primary'}`}>
                            {isSearching ? 'sync' : 'search'}
                        </span>
                        <input
                            className="w-full bg-white/4 border border-white/6 rounded-xl pl-10 pr-4 py-2 text-[11px] font-semibold text-white placeholder:text-slate-600 focus:outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/10 transition-all uppercase tracking-widest"
                            placeholder="Search stocks & funds..."
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onFocus={() => searchQuery.length > 2 && setShowDropdown(true)}
                        />
                    </div>

                    <AnimatePresence>
                        {showDropdown && (
                            <motion.div
                                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 8, scale: 0.98 }}
                                className="absolute top-full mt-3 left-0 right-0 bg-[#161c22] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.8)] border border-white/8 overflow-hidden z-[260] max-h-[480px] overflow-y-auto no-scrollbar"
                            >
                                {hasResults ? (
                                    <div className="p-2 flex flex-col gap-1">
                                        {results.stocks.length > 0 && (
                                            <div>
                                                <div className="px-4 py-2 text-[8px] font-black text-slate-500 uppercase tracking-[0.3em] bg-white/4 rounded-lg mb-1">Stocks</div>
                                                {results.stocks.map((stock) => (
                                                    <button
                                                        key={stock.symbol}
                                                        onClick={() => handleSelect(`/stocks/${stock.symbol}`)}
                                                        className="w-full text-left p-3 hover:bg-white/4 rounded-xl transition-all group flex items-center justify-between"
                                                    >
                                                        <div className="flex flex-col gap-0.5">
                                                            <div className="text-[11px] font-bold text-white group-hover:text-primary transition-colors">{stock.name}</div>
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-[9px] text-slate-400 font-bold tracking-widest uppercase">{stock.symbol}</span>
                                                                <span className="text-[8px] px-1.5 py-0.5 bg-secondary/10 text-secondary border border-secondary/20 rounded font-bold uppercase">{stock.sector}</span>
                                                            </div>
                                                        </div>
                                                        <span className="material-symbols-outlined text-slate-700 text-sm opacity-0 group-hover:opacity-100 transition-all">trending_up</span>
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                        {results.funds.length > 0 && (
                                            <div>
                                                <div className="px-4 py-2 text-[8px] font-black text-slate-500 uppercase tracking-[0.3em] bg-white/4 rounded-lg mb-1">Mutual Funds</div>
                                                {results.funds.map((fund) => (
                                                    <button
                                                        key={fund.scheme_code}
                                                        onClick={() => handleSelect(`/mf/${fund.scheme_code}`)}
                                                        className="w-full text-left p-3 hover:bg-white/4 rounded-xl transition-all group flex items-center justify-between"
                                                    >
                                                        <div className="flex flex-col gap-0.5">
                                                            <div className="text-[11px] font-bold text-white group-hover:text-primary transition-colors">{fund.scheme_name}</div>
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-[9px] text-slate-500 font-bold tracking-widest uppercase">{fund.scheme_code}</span>
                                                                <span className="text-[8px] px-1.5 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded font-bold uppercase">{fund.scheme_category}</span>
                                                            </div>
                                                        </div>
                                                        <span className="material-symbols-outlined text-slate-700 text-sm opacity-0 group-hover:opacity-100 transition-all">chevron_right</span>
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="p-10 text-center flex flex-col items-center gap-3">
                                        <span className="material-symbols-outlined text-4xl text-slate-800 font-thin">search_off</span>
                                        <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em]">No results found</p>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Right: Notifications, Settings, Avatar */}
            <div className="flex items-center gap-3 shrink-0">
                {/* Notifications */}
                <button className="p-2 text-slate-500 hover:text-primary transition-colors rounded-lg hover:bg-white/4 hidden sm:flex">
                    <span className="material-symbols-outlined text-[20px] font-thin">notifications</span>
                </button>

                {/* Settings Dropdown (Admin + System) */}
                <div className="relative" ref={settingsRef}>
                    <button
                        onClick={() => setSettingsOpen((v) => !v)}
                        className={`p-2 transition-colors rounded-lg hover:bg-white/4 ${isSettingsActive ? 'text-primary' : 'text-slate-500 hover:text-primary'}`}
                        title="Settings"
                    >
                        <span className="material-symbols-outlined text-[20px] font-thin">settings</span>
                    </button>
                    <AnimatePresence>
                        {settingsOpen && (
                            <motion.div
                                initial={{ opacity: 0, y: 6, scale: 0.97 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 6, scale: 0.97 }}
                                transition={{ duration: 0.15 }}
                                className="absolute top-full right-0 mt-2 min-w-[200px] bg-[#161c22] border border-white/8 rounded-xl shadow-[0_16px_40px_rgba(0,0,0,0.7)] z-[200] overflow-hidden"
                            >
                                <div className="px-4 pt-3 pb-1">
                                    <p className="text-[8px] font-black text-slate-600 uppercase tracking-[0.3em]">Admin</p>
                                </div>
                                <Link
                                    to="/admin?tab=dashboard"
                                    onClick={() => setSettingsOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-2.5 text-[11px] font-semibold transition-all hover:bg-white/4 border-l-2
                                        ${tab === 'dashboard' || (!tab && location.pathname === '/admin') ? 'text-primary border-primary' : 'text-slate-400 hover:text-white border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined text-[15px]">admin_panel_settings</span>
                                    Command Center
                                </Link>
                                <Link
                                    to="/admin?tab=assets"
                                    onClick={() => setSettingsOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-2.5 text-[11px] font-semibold transition-all hover:bg-white/4 border-l-2
                                        ${tab === 'assets' ? 'text-primary border-primary' : 'text-slate-400 hover:text-white border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined text-[15px]">inventory</span>
                                    Asset Management
                                </Link>
                                <Link
                                    to="/admin?tab=logs"
                                    onClick={() => setSettingsOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-2.5 text-[11px] font-semibold transition-all hover:bg-white/4 border-l-2
                                        ${tab === 'logs' ? 'text-primary border-primary' : 'text-slate-400 hover:text-white border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined text-[15px]">receipt_long</span>
                                    Audit Logs
                                </Link>

                                <div className="px-4 pt-3 pb-1 mt-1 border-t border-white/5">
                                    <p className="text-[8px] font-black text-slate-600 uppercase tracking-[0.3em]">System</p>
                                </div>
                                <Link
                                    to="/admin?tab=health"
                                    onClick={() => setSettingsOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-2.5 text-[11px] font-semibold transition-all hover:bg-white/4 border-l-2
                                        ${tab === 'health' ? 'text-primary border-primary' : 'text-slate-400 hover:text-white border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined text-[15px]">dns</span>
                                    Health Dashboard
                                </Link>
                                <Link
                                    to="/admin?tab=pipeline"
                                    onClick={() => setSettingsOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-2.5 text-[11px] font-semibold transition-all hover:bg-white/4 border-l-2
                                        ${tab === 'pipeline' ? 'text-primary border-primary' : 'text-slate-400 hover:text-white border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined text-[15px]">account_tree</span>
                                    Node Manager
                                </Link>

                                <div className="p-2 mt-1 border-t border-white/5">
                                    <button
                                        onClick={() => { setSettingsOpen(false); logout(); }}
                                        className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-red-400 hover:bg-red-500/8 transition-all"
                                    >
                                        <span className="material-symbols-outlined text-[15px]">logout</span>
                                        Sign Out
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Avatar */}
                <div className="h-9 w-9 rounded-full border-[2px] border-primary/30 hover:border-primary/70 transition-all overflow-hidden cursor-pointer shadow-lg shadow-primary/5 active:scale-95">
                    <img
                        alt="User Profile"
                        className="w-full h-full object-cover"
                        src="https://ui-avatars.com/api/?name=User&background=e9c349&color=0f1419"
                    />
                </div>

                {/* Mobile menu button */}
                <button
                    onClick={onMobileMenuClick}
                    className="lg:hidden p-2 text-slate-400 hover:text-primary transition-colors rounded-lg hover:bg-white/4"
                >
                    <span className="material-symbols-outlined text-[22px]">
                        {isMobileMenuOpen ? 'close' : 'menu'}
                    </span>
                </button>
            </div>
        </header>
    );
};

// ─── Mobile Menu ──────────────────────────────────────────────────────────────

const MobileMenu = ({ onClose }) => {
    const location = useLocation();
    const { logout } = useAuth();
    const navigate = useNavigate();
    const { compareList } = useSelector((state) => state.compare);

    const navGroups = [
        {
            label: 'Stocks',
            items: [
                { to: '/stocks', icon: 'insights', label: 'Stocks' },
                { to: '/indices', icon: 'bar_chart', label: 'Indices' },
                { to: '/stock-compare', icon: 'query_stats', label: 'Compare Stocks' },
            ],
        },
        {
            label: 'Mutual Funds',
            items: [
                { to: '/mf', icon: 'lock', label: 'Mutual Funds' },
                { to: '/compare', icon: 'compare_arrows', label: 'Compare Funds', badge: compareList?.length },
            ],
        },
        {
            label: 'Portfolio',
            items: [
                { to: '/portfolio', icon: 'account_balance_wallet', label: 'Portfolio' },
            ],
        },
        {
            label: 'Settings',
            items: [
                { to: '/admin?tab=dashboard', icon: 'admin_panel_settings', label: 'Command Center' },
                { to: '/admin?tab=assets', icon: 'inventory', label: 'Asset Management' },
                { to: '/admin?tab=logs', icon: 'receipt_long', label: 'Audit Logs' },
                { to: '/admin?tab=health', icon: 'dns', label: 'Health Dashboard' },
                { to: '/admin?tab=pipeline', icon: 'account_tree', label: 'Node Manager' },
            ],
        },
    ];

    return (
        <div className="flex flex-col overflow-y-auto h-full py-4">
            {navGroups.map((group) => (
                <div key={group.label} className="mb-2">
                    <p className="px-5 py-2 text-[9px] font-black text-slate-600 uppercase tracking-[0.3em]">{group.label}</p>
                    {group.items.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            onClick={onClose}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-5 py-3 text-sm font-medium transition-all
                                ${isActive ? 'text-primary bg-primary/6 border-r-2 border-primary' : 'text-slate-400 hover:text-white hover:bg-white/4'}`
                            }
                        >
                            <span className="material-symbols-outlined text-[18px] font-thin">{item.icon}</span>
                            <span className="flex-1">{item.label}</span>
                            {item.badge > 0 && (
                                <span className="bg-primary text-black rounded-full px-1.5 text-[8px] font-bold">{item.badge}</span>
                            )}
                        </NavLink>
                    ))}
                </div>
            ))}
            <div className="mt-auto px-5 py-4 border-t border-white/5">
                <button
                    onClick={() => { logout(); navigate('/login'); onClose(); }}
                    className="flex items-center gap-3 w-full text-sm font-medium text-slate-500 hover:text-red-400 transition-colors py-2"
                >
                    <span className="material-symbols-outlined text-[18px]">logout</span>
                    Sign Out
                </button>
            </div>
        </div>
    );
};

// ─── Footer ───────────────────────────────────────────────────────────────────

const Footer = () => (
    <footer className="w-full border-t border-white/5 py-4 flex items-center justify-center bg-[#0a0f12]">
        <p className="text-[10px] font-black uppercase tracking-[0.25em] text-slate-600">
            NIVESH PLATFORM &copy; 2026
        </p>
    </footer>
);

// ─── Layout ───────────────────────────────────────────────────────────────────

const Layout = ({ children }) => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    return (
        <div className="bg-[#0a0f12] text-on-background font-body min-h-screen selection:bg-primary/30 flex flex-col">
            <TopNavBar
                onMobileMenuClick={() => setIsMobileMenuOpen((v) => !v)}
                isMobileMenuOpen={isMobileMenuOpen}
            />

            {/* Mobile Drawer */}
            <AnimatePresence>
                {isMobileMenuOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsMobileMenuOpen(false)}
                            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[360] lg:hidden"
                        />
                        <motion.aside
                            initial={{ x: '-100%' }}
                            animate={{ x: 0 }}
                            exit={{ x: '-100%' }}
                            transition={{ type: 'spring', damping: 28, stiffness: 240 }}
                            className="fixed inset-y-0 left-0 w-72 bg-[#0f1419] z-[370] lg:hidden shadow-2xl border-r border-white/5"
                        >
                            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
                                <Link
                                    to="/dashboard"
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className="text-base font-headline font-bold text-transparent bg-clip-text bg-gradient-to-r from-[#e9c349] to-[#b8942e]"
                                >
                                    Nivesh Platform
                                </Link>
                                <button
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className="text-slate-500 hover:text-white transition-colors"
                                >
                                    <span className="material-symbols-outlined">close</span>
                                </button>
                            </div>
                            <MobileMenu onClose={() => setIsMobileMenuOpen(false)} />
                        </motion.aside>
                    </>
                )}
            </AnimatePresence>

            {/* Main content */}
            <main className="flex-1 w-full flex flex-col">
                <div className="flex-1 w-full">
                    <ErrorBoundary>{children}</ErrorBoundary>
                </div>
                <Footer />
            </main>
        </div>
    );
};

export default Layout;
