import React from 'react';
import { NavLink, Link } from 'react-router-dom';

const TopNavBar = () => (
    <header className="w-full h-20 top-0 sticky bg-[#0f1419]/90 backdrop-blur-2xl border-b border-white/5 shadow-[0_8px_32px_rgba(233,195,73,0.06)] flex justify-between items-center px-6 md:px-12 xl:px-24 2xl:px-32 z-50 transition-all duration-300">
        <div className="flex items-center gap-6 md:gap-12">
            <Link to="/dashboard" className="text-xl md:text-2xl font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-[#e9c349] to-[#9d7e00] hover:scale-[1.02] transition-transform">Nivesh Elite</Link>
            <nav className="hidden lg:flex gap-8 items-center">
                <NavLink to="/portfolio" className={({ isActive }) => `text-sm font-medium transition-all duration-300 ${isActive ? 'text-primary scale-110' : 'text-slate-400 hover:text-white'}`}>Portfolio</NavLink>
                <NavLink to="/indices" className={({ isActive }) => `text-sm font-medium transition-all duration-300 ${isActive ? 'text-primary scale-110' : 'text-slate-400 hover:text-white'}`}>Market Indices</NavLink>
                <NavLink to="/mf" className={({ isActive }) => `text-sm font-medium transition-all duration-300 ${isActive ? 'text-primary scale-110' : 'text-slate-400 hover:text-white'}`}>Wealth Vault</NavLink>
            </nav>
        </div>
        <div className="flex items-center gap-6">
            <div className="relative hidden xl:block">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">search</span>
                <input className="bg-surface-container-highest/50 border-none rounded-lg pl-10 pr-4 py-2.5 text-sm focus:ring-1 focus:ring-primary w-64 xl:w-96 transition-all" placeholder="Search Master Ledger..." type="text"/>
            </div>
            <div className="flex items-center gap-3 md:gap-5 text-slate-400">
                <span className="material-symbols-outlined cursor-pointer hover:text-primary transition-colors text-xl">notifications</span>
                <NavLink to="/admin" className={({ isActive }) => `material-symbols-outlined cursor-pointer hover:text-primary transition-colors text-xl ${isActive ? 'text-primary' : ''}`}>settings</NavLink>
                <div className="h-10 w-10 md:h-11 md:w-11 rounded-full border-[2px] border-primary/50 hover:border-primary transition-colors overflow-hidden cursor-pointer shadow-lg shadow-primary/5">
                    <img alt="Elite Client Profile" className="w-full h-full object-cover" src="https://ui-avatars.com/api/?name=Elite+User&background=e9c349&color=0f1419" />
                </div>
            </div>
        </div>
    </header>
);

const SideNavBar = () => {
    const navItems = [
        { name: 'Homepage', icon: 'home', path: '/dashboard' },
        { name: 'Stocks Listing', icon: 'monitoring', path: '/stocks' },
        { name: 'Mutual Funds', icon: 'account_balance', path: '/mf' },
        { name: 'Portfolio Page', icon: 'account_balance_wallet', path: '/portfolio' },
        { name: 'Admin Panel', icon: 'admin_panel_settings', path: '/admin' },
    ];

    return (
        <aside className="h-screen w-72 left-0 top-20 fixed bg-[#0f1419] border-r border-white/5 flex flex-col pt-4 pb-32 z-40 hidden lg:flex shadow-2xl">
            <nav className="flex-1 space-y-1">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `
                            flex items-center gap-4 py-5 px-8 font-body text-[11px] tracking-[0.2em] uppercase font-bold transition-all duration-300 group
                            ${isActive 
                                ? 'text-[#e9c349] bg-white/5 border-l-4 border-[#e9c349] translate-x-1' 
                                : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'}
                        `}
                    >
                        {({ isActive }) => (
                            <>
                                <span className={`material-symbols-outlined transition-transform duration-300 group-hover:scale-110 ${isActive ? 'scale-110' : ''}`}>{item.icon}</span>
                                <span>{item.name}</span>
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
                </div>
            </div>
        </aside>
    );
};

const Layout = ({ children }) => {
    return (
        <div className="bg-[#0a0f12] text-on-background font-body min-h-screen selection:bg-primary/30 flex flex-col">
            <TopNavBar />
            <div className="flex flex-1">
                <SideNavBar />
                <div className="flex-1 lg:pl-72 flex flex-col transition-all duration-300 w-full">
                    <div className="flex-1 w-full">
                        {children}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Layout;
