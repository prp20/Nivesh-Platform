import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, Link } from 'react-router-dom';
import { fetchIndexDetail, clearDetail } from '../store/slices/indicesSlice';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';

const IndexDetail = () => {
    const { benchmarkCode } = useParams();
    const dispatch = useDispatch();
    const { currentDetail: indexData, navHistory, detailLoading: loading, detailError: error } = useSelector((state) => state.indices);

    useEffect(() => {
        if (benchmarkCode) {
            dispatch(fetchIndexDetail(benchmarkCode));
        }
        return () => dispatch(clearDetail());
    }, [dispatch, benchmarkCode]);

    if (loading && !indexData) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Synchronizing Global Datum...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-20">
                <span className="material-symbols-outlined text-error text-9xl mb-8">security_update_warning</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-4 uppercase tracking-widest">Protocol Breach</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12">{error}</p>
                <Link to="/indices" className="px-12 py-5 gold-gradient rounded-2xl text-on-primary font-black uppercase tracking-widest shadow-2xl">
                    Back to Indices
                </Link>
            </div>
        );
    }

    if (!indexData) return null;

    const latestVal = navHistory.length > 0 ? navHistory[navHistory.length - 1].value : 0;
    const prevVal = navHistory.length > 1 ? navHistory[navHistory.length - 2].value : latestVal;
    const delta = latestVal - prevVal;
    const deltaPercent = prevVal !== 0 ? (delta / prevVal) * 100 : 0;

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Breadcrumbs */}
            <nav className="flex items-center gap-6 text-xs sm:text-sm font-black uppercase tracking-[0.5em] opacity-40">
                <Link to="/indices" className="hover:text-primary transition-all hover:scale-105">Market Indices</Link>
                <span className="material-symbols-outlined text-sm">chevron_right</span>
                <span className="text-white">Systemic Surveillance</span>
            </nav>

            {/* Header - Ultra Scale */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-12 mb-8">
                <div className="flex-1">
                    <div className="flex items-center gap-6 mb-10">
                        <span className="bg-primary/20 text-primary border border-primary/30 px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-[0.4em] leading-none"> {indexData.benchmark_type || 'GLOBAL EQUITY'} </span>
                        <span className="text-secondary text-sm font-black uppercase tracking-[0.4em] flex items-center gap-3">
                            <span className="material-symbols-outlined text-2xl animate-pulse">verified</span>
                            Protocol Status: Nominal
                        </span>
                    </div>
                    <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[12rem] font-headline font-bold text-white tracking-tighter leading-none mb-10 group uppercase">
                        {indexData.benchmark_name} <span className="text-primary/10 group-hover:text-primary transition-all duration-1000">INDEX</span>
                    </h1>
                    <p className="text-xl md:text-2xl text-slate-500 font-black max-w-6xl leading-tight italic uppercase tracking-[0.3em] opacity-60"> Ticker: {indexData.ticker} • Protocol Identification: {indexData.benchmark_code} </p>
                </div>

                <div className="flex flex-col items-end gap-4 bg-surface-container-high/60 p-12 md:p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] backdrop-blur-3xl min-w-[400px]">
                    <span className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] leading-none mb-2 opacity-60">Global Index Valuation</span>
                    <div className="text-7xl sm:text-8xl md:text-9xl font-headline font-black text-white tracking-tighter leading-none mt-2">
                        {latestVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className={`flex items-center gap-4 text-3xl font-black uppercase tracking-[0.3em] mt-8 px-10 py-5 rounded-[2.5rem] border shadow-2xl ${delta >= 0 ? 'text-secondary bg-secondary/10 border-secondary/20' : 'text-error bg-error/10 border-error/20'}`}>
                        <span className="material-symbols-outlined text-4xl">{delta >= 0 ? 'trending_up' : 'trending_down'}</span>
                        {delta >= 0 ? '+' : ''}{deltaPercent.toFixed(2)}% T-SESSION
                    </div>
                </div>
            </header>

            {/* Performance Chart Section */}
            <section className="glass-panel p-12 md:p-16 2xl:p-24 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.7)] relative overflow-hidden backdrop-blur-3xl min-h-[600px] bg-white/[0.01]">
                <div className="mb-20 relative z-10">
                    <h3 className="text-4xl font-headline font-bold tracking-tight mb-4 uppercase tracking-[0.2em] leading-none">Global Trajectory Matrix</h3>
                    <p className="text-base text-slate-500 font-black tracking-[0.3em] flex items-center gap-4 uppercase opacity-60"> Continuous surveillance of systemic benchmark momentum <span className="inline-block w-3 h-3 rounded-full bg-secondary animate-pulse shadow-[0_0_15px_rgba(102,221,139,0.5)]"></span> </p>
                </div>
                
                <div className="w-full h-[500px] 2xl:h-[600px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={navHistory}>
                            <defs>
                                <linearGradient id="colorIndex" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#e9c349" stopOpacity={0.6}/>
                                    <stop offset="95%" stopColor="#e9c349" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                            <XAxis dataKey="date" hide />
                            <YAxis domain={['auto', 'auto']} hide />
                            <RechartsTooltip contentStyle={{ backgroundColor: '#1b2025', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '24px', backdropFilter: 'blur(16px)', padding: '24px', boxShadow: '0 32px 64px rgba(0,0,0,0.5)' }} itemStyle={{ fontSize: '18px', fontWeight: 'black', color: '#e9c349' }} />
                            <Area type="monotone" dataKey="value" stroke="#e9c349" strokeWidth={6} fillOpacity={1} fill="url(#colorIndex)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </section>

            {/* Strategic Information Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-12 xl:gap-16 mb-24">
                {[
                    { label: 'Systemic Weight', val: 'Market Cap Weighted', sub: 'Standard Methodology', icon: 'scale' },
                    { label: 'Protocol Coverage', val: indexData.benchmark_type || 'Equity', sub: 'Asset Class Filter', icon: 'dataset' },
                    { label: 'Alpha Correlation', val: '0.98', sub: 'Beta Aligned to Global Markets', icon: 'hub' },
                ].map((m, idx) => (
                    <div key={idx} className="glass-panel p-12 rounded-[2.5rem] border border-white/5 shadow-2xl hover:translate-y-[-10px] transition-all duration-500 bg-white/[0.01] relative overflow-hidden group">
                        <span className="material-symbols-outlined absolute -right-6 -bottom-6 text-[100px] text-primary opacity-[0.03] group-hover:scale-125 transition-transform duration-1000">{m.icon}</span>
                        <p className="text-[10px] uppercase tracking-[0.5em] text-slate-500 font-black mb-8 leading-none">{m.label}</p>
                        <p className="text-3xl xl:text-4xl font-headline font-black text-white tracking-tighter mb-4 leading-none uppercase">{m.val}</p>
                        <p className="text-[10px] text-primary font-black uppercase tracking-[0.4em] opacity-40 italic tracking-widest">{m.sub}</p>
                    </div>
                ))}
            </div>

             {/* Footer */}
             <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Benchmark Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

export default IndexDetail;
