import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, Link } from 'react-router-dom';
import { fetchFundDetail, clearDetail, syncFundMetrics } from '../store/slices/fundDetailSlice';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';

const MFDetail = () => {
    const { schemeCode } = useParams();
    const dispatch = useDispatch();
    const { fund, navHistory, metrics, loading, error, syncing } = useSelector((state) => state.fundDetail);
    const [isLedgerExpanded, setIsLedgerExpanded] = useState(false);

    useEffect(() => {
        if (schemeCode) {
            dispatch(fetchFundDetail(schemeCode));
        }
        return () => dispatch(clearDetail());
    }, [dispatch, schemeCode]);

    if (loading && !fund) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Alpha Signal...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-20">
                <span className="material-symbols-outlined text-error text-9xl mb-8">security_update_warning</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-4 uppercase tracking-widest">Asset Sync Failure</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12">{error}</p>
                <Link to="/mf" className="px-12 py-5 border border-white/20 rounded-2xl text-white font-black uppercase tracking-widest hover:bg-white/5 transition-all shadow-2xl">
                    Back to Vault
                </Link>
            </div>
        );
    }

    if (!fund) return null;

    const formatPercent = (val) => val != null ? `${(val * 100).toFixed(2)}%` : 'N/A';
    const formatValue = (val) => val != null ? val.toFixed(2) : 'N/A';

    const displayMetrics = [
        { label: 'Vault Wealth (AUM)', val: metrics?.aum_in_crores ? `₹${metrics.aum_in_crores.toLocaleString()} Cr` : 'N/A', sub: 'Institutional Grade', icon: 'account_balance' },
        { label: 'Expense Artifact', val: metrics?.expense_ratio ? formatPercent(metrics.expense_ratio) : 'N/A', sub: 'Optimized Ratio', icon: 'settings_pro_active' },
        { label: 'CAGR (3-Year)', val: formatPercent(metrics?.cagr_3year), sub: 'Historical Alpha', icon: 'trending_up' },
        { label: 'Risk Quadrant', val: fund.scheme_subcategory || 'AGGRESSIVE', sub: 'Elite Strategy', icon: 'bolt' },
    ];

    const performanceMatrix = [
        { label: 'Absolute (6M)', val: formatPercent(metrics?.short_term_return_6m) },
        { label: 'Absolute (1Y)', val: formatPercent(metrics?.absolute_return_1y) },
        { label: 'Absolute (3Y)', val: formatPercent(metrics?.absolute_return_3y) },
        { label: 'Absolute (5Y)', val: formatPercent(metrics?.absolute_return_5y) },
    ];

    // Detailed Ledger Fields
    const detailedLedger = [
        { label: 'Scheme Core ID', val: metrics?.scheme_code || 'N/A' },
        { label: 'Current Valuation (NAV)', val: `₹${metrics?.current_nav || 'N/A'}` },
        { label: 'Valuation Epoch', val: metrics?.nav_date || 'N/A' },
        { label: 'Wealth (AUM Crores)', val: metrics?.aum_in_crores || '0.0' },
        { label: 'Expense Artifact', val: formatPercent(metrics?.expense_ratio) },
        { label: 'Sovereign Rating', val: metrics?.fund_rating || 'N/A' },
        { label: 'Volatility Deviation', val: metrics?.volatility || 'N/A' },
        { label: 'CAGR (3-Year)', val: formatPercent(metrics?.cagr_3year) },
        { label: 'CAGR (5-Year)', val: formatPercent(metrics?.cagr_5year) },
        { label: 'Absolute (1Y)', val: formatPercent(metrics?.absolute_return_1y) },
        { label: 'Absolute (3Y)', val: formatPercent(metrics?.absolute_return_3y) },
        { label: 'Absolute (5Y)', val: formatPercent(metrics?.absolute_return_5y) },
        { label: 'Absolute (10Y)', val: formatPercent(metrics?.absolute_return_10y) },
        { label: 'Short Term (6M)', val: formatPercent(metrics?.short_term_return_6m) },
        { label: 'Upside Capture', val: metrics?.upside_capture || 'N/A' },
        { label: 'Downside Capture', val: metrics?.downside_capture || 'N/A' },
        { label: 'Sortino Ratio', val: formatValue(metrics?.sortino_ratio) },
        { label: 'Sharpe Ratio', val: formatValue(metrics?.sharpe_ratio) },
        { label: 'Alpha Alpha', val: metrics?.alpha || 'N/A' },
        { label: 'Beta Corridor', val: metrics?.beta || 'N/A' },
        { label: 'Standard Deviation', val: formatValue(metrics?.standard_deviation) },
        { label: 'Maximum Drawdown', val: formatPercent(metrics?.maximum_drawdown) },
        { label: 'Tracking Error', val: metrics?.tracking_error || 'N/A' },
        { label: 'Information Ratio', val: metrics?.information_ratio || 'N/A' },
    ];

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Breadcrumbs */}
            <nav className="flex items-center gap-6 text-xs sm:text-sm font-black uppercase tracking-[0.5em] opacity-40">
                <Link to="/mf" className="hover:text-primary transition-all hover:scale-105">Resource Vault</Link>
                <span className="material-symbols-outlined text-sm">chevron_right</span>
                <span className="text-white">Quantitative Intelligence</span>
            </nav>

            {/* Hero Section */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-16 mb-8">
                <div className="flex-1">
                    <div className="flex items-center gap-6 mb-10">
                        <span className="bg-primary/10 text-primary border border-primary/20 px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-[0.4em] leading-none"> {fund.scheme_category} </span>
                        {metrics?.hash_sufficient_data && (
                            <span className="text-secondary text-sm font-black uppercase tracking-[0.4em] flex items-center gap-3">
                                <span className="material-symbols-outlined text-2xl animate-pulse">verified</span>
                                Elite Certified ({formatPercent(metrics.data_completeness_percentage/100)} COMP)
                            </span>
                        )}
                    </div>
                    <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[12rem] font-headline font-bold text-white tracking-tighter leading-none mb-10 group">
                        {fund.scheme_name.split(' - ')[0]} <span className="text-primary/10 group-hover:text-primary transition-all duration-1000">{fund.scheme_name.split(' - ')[1] || 'Growth'}</span>
                    </h1>
                    <p className="text-xl md:text-2xl text-slate-500 font-black max-w-6xl leading-tight italic uppercase tracking-[0.2em] opacity-60"> 
                        Identifier: {fund.scheme_code} • ISIN: {fund.isin || 'ARTIFACT-X'} • Inception: {fund.inception_date || 'N/A'}
                    </p>
                    <p className="text-sm font-black text-primary uppercase tracking-[0.4em] mt-8 opacity-40 italic"> {fund.amc_name} • Benchmark: {fund.benchmark_index_code} </p>
                </div>

                <div className="flex flex-col items-end gap-4 bg-surface-container-high/60 p-12 md:p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] backdrop-blur-3xl min-w-[400px]">
                    <span className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] leading-none mb-2 opacity-60">Global Nav Valuation</span>
                    <div className="text-7xl sm:text-8xl md:text-9xl font-headline font-black text-white tracking-tighter leading-none mt-2">₹{formatValue(metrics?.current_nav)}</div>
                    <div className={`flex items-center gap-4 text-3xl font-black uppercase tracking-[0.3em] mt-8 px-10 py-5 rounded-[2.5rem] border shadow-2xl ${metrics?.absolute_return_1y > 0 ? 'text-secondary bg-secondary/10 border-secondary/20' : 'text-error bg-error/10 border-error/20'}`}>
                        <span className="material-symbols-outlined text-4xl">{metrics?.absolute_return_1y > 0 ? 'trending_up' : 'trending_down'}</span>
                        {formatPercent(metrics?.absolute_return_1y)} T-12M
                    </div>
                </div>
            </header>

            {/* Strategic Intelligence Verdict */}
            {metrics?.final_verdict && (
                <div className="glass-panel p-16 rounded-[4rem] border-l-8 border border-white/5 border-l-primary shadow-2xl bg-white/[0.02] backdrop-blur-3xl">
                    <div className="flex items-center gap-8 mb-8">
                        <span className="material-symbols-outlined text-4xl text-primary animate-bounce">auto_awesome</span>
                        <h4 className="text-3xl font-headline font-black uppercase tracking-widest leading-none">Strategic Intelligence Verdict</h4>
                    </div>
                    <p className="text-3xl sm:text-4xl text-white/80 font-bold leading-tight uppercase tracking-tight italic opacity-90">
                        "{metrics.final_verdict}"
                    </p>
                </div>
            )}

            {/* Top Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-4 gap-12 xl:gap-16">
                {displayMetrics.map((m, idx) => (
                    <div key={idx} className="glass-panel p-12 rounded-[2.5rem] border border-white/5 shadow-2xl hover:translate-y-[-10px] transition-all duration-500 bg-white/[0.01] relative overflow-hidden group">
                        <span className="material-symbols-outlined absolute -right-6 -bottom-6 text-[120px] text-primary opacity-[0.03] group-hover:scale-125 transition-transform duration-1000">{m.icon}</span>
                        <p className="text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black mb-8 leading-none">{m.label}</p>
                        <p className="text-4xl sm:text-5xl xl:text-6xl font-headline font-black text-white tracking-tighter mb-4 leading-none">{m.val}</p>
                        <p className="text-[11px] text-primary font-black uppercase tracking-[0.4em] opacity-40 italic tracking-widest">{m.sub}</p>
                    </div>
                ))}
            </div>

            {/* Detailed Ledger Toggle */}
            <section className="flex flex-col gap-8">
                <button 
                    onClick={() => setIsLedgerExpanded(!isLedgerExpanded)}
                    className="flex items-center gap-6 group hover:translate-x-4 transition-all duration-500 border border-white/10 rounded-3xl p-8 bg-surface-container-high/20 w-fit"
                >
                    <div className="bg-primary/10 p-4 rounded-2xl border border-primary/20 group-hover:bg-primary group-hover:text-on-primary transition-all">
                        <motion.span 
                            animate={{ rotate: isLedgerExpanded ? 180 : 0 }}
                            className="material-symbols-outlined text-3xl block"
                        >
                            expand_more
                        </motion.span>
                    </div>
                    <div>
                        <h4 className="text-2xl font-headline font-black uppercase tracking-widest leading-none mb-2">Detailed Wealth Ledger</h4>
                        <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] opacity-40"> Access Full Quantitative Artifacts </p>
                    </div>
                </button>

                <AnimatePresence>
                    {isLedgerExpanded && (
                        <motion.div 
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="glass-panel p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] bg-white/[0.01] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-12 font-mono">
                                {detailedLedger.map((d, i) => (
                                    <div key={i} className="p-8 border border-white/5 rounded-3xl hover:bg-white/[0.03] transition-all group flex flex-col justify-between">
                                        <p className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em] mb-4 group-hover:text-primary transition-colors">{d.label}</p>
                                        <p className="text-3xl font-black text-white tracking-tighter truncate">{d.val}</p>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </section>

            {/* Performance Correlation Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 xl:gap-16 bg-surface-container-high/20 p-12 rounded-[4rem] border border-white/5">
                {performanceMatrix.map((p, idx) => (
                    <div key={idx} className="flex flex-col items-center text-center p-6 border-x border-white/5 first:border-l-0 last:border-r-0">
                        <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] mb-4 opacity-60">{p.label}</p>
                        <p className={`text-5xl font-headline font-black tracking-tighter ${p.val.startsWith('-') ? 'text-error' : 'text-secondary'}`}>{p.val}</p>
                    </div>
                ))}
            </div>

            {/* Performance Chart */}
            <section className="glass-panel p-12 md:p-16 2xl:p-24 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.7)] relative overflow-hidden backdrop-blur-3xl min-h-[650px] bg-white/[0.01]">
                <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-12 mb-20 relative z-10">
                    <div>
                        <h3 className="text-4xl font-headline font-bold tracking-tight mb-4 uppercase tracking-[0.2em] leading-none">Growth Trajectory</h3>
                        <p className="text-base text-slate-500 font-black tracking-[0.3em] flex items-center gap-4 uppercase opacity-60"> Absolute Performance Momentum Surveillance <span className="inline-block w-3 h-3 rounded-full bg-secondary animate-pulse shadow-[0_0_15px_rgba(102,221,139,0.5)]"></span> </p>
                    </div>
                    <button 
                        disabled={syncing}
                        onClick={() => dispatch(syncFundMetrics(schemeCode))}
                        className={`px-12 py-5 rounded-3xl border border-white/10 text-white font-black text-xs uppercase tracking-[0.4em] transition-all flex items-center gap-4 shadow-2xl ${syncing ? 'opacity-50' : 'hover:bg-white/5'}`}
                    >
                        <span className={`material-symbols-outlined text-2xl ${syncing ? 'animate-spin' : ''}`}>sync</span>
                        {syncing ? 'Recalculating...' : 'Refresh Artifact'}
                    </button>
                </div>
                
                <div className="w-full h-[500px] 2xl:h-[600px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={navHistory}>
                            <defs>
                                <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#e9c349" stopOpacity={0.6}/>
                                    <stop offset="95%" stopColor="#e9c349" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                            <XAxis dataKey="date" hide />
                            <YAxis domain={['auto', 'auto']} hide />
                            <RechartsTooltip contentStyle={{ backgroundColor: '#1b2025', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '24px', backdropFilter: 'blur(16px)', padding: '24px', boxShadow: '0 32px 64px rgba(0,0,0,0.5)' }} itemStyle={{ fontSize: '18px', fontWeight: 'black', color: '#e9c349' }} />
                            <Area type="monotone" dataKey="nav" stroke="#e9c349" strokeWidth={6} fillOpacity={1} fill="url(#colorNav)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </section>

            {/* Risk Artifacts */}
            <div className="grid grid-cols-1 3xl:grid-cols-3 gap-16 mb-24 font-headline">
                <div className="col-span-1 3xl:col-span-2 glass-panel p-16 rounded-[4rem] border border-white/5 shadow-2xl bg-white/[0.02] backdrop-blur-2xl">
                    <h3 className="text-4xl font-headline font-bold mb-16 tracking-tight uppercase tracking-[0.2em] leading-none">Quantitative Risk Surveillance</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
                        {[
                            { label: 'Volatility Deviation', val: formatValue(metrics?.standard_deviation), sub: 'STD DEV' },
                            { label: 'Worst-Case Decimation', val: formatPercent(metrics?.maximum_drawdown), sub: 'MAX DRAWDOWN' },
                            { label: 'Alpha Excess Efficiency', val: metrics?.sharpe_ratio ? formatValue(metrics.sharpe_ratio) : 'N/A', sub: 'SHARPE RATIO' },
                            { label: 'Sortino Tail Protection', val: metrics?.sortino_ratio ? formatValue(metrics.sortino_ratio) : 'N/A', sub: 'SORTINO' },
                        ].map((q, idx) => (
                            <div key={idx} className="flex justify-between items-center border-b border-white/5 pb-10 hover:translate-x-4 transition-all cursor-crosshair group">
                                <div className="flex flex-col gap-2">
                                    <p className="text-xs text-slate-500 font-black uppercase tracking-[0.4em] opacity-40 group-hover:opacity-100 transition-opacity">{q.label}</p>
                                    <p className="text-sm text-primary font-black uppercase tracking-[0.3em] italic">{q.sub}</p>
                                </div>
                                <div className={`text-5xl font-black tracking-tighter group-hover:scale-110 transition-transform duration-500 ${q.val.toString().startsWith('-') ? 'text-primary' : 'text-white'}`}>{q.val}</div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="bg-surface-container p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] relative overflow-hidden flex flex-col justify-center items-center text-center group">
                    <div className="mb-10 relative z-10">
                        <span className="material-symbols-outlined text-[120px] text-primary opacity-20 group-hover:opacity-50 transition-all duration-1000 group-hover:rotate-12">shield_with_heart</span>
                    </div>
                    <h4 className="text-3xl font-headline font-black mb-8 tracking-tight uppercase tracking-widest relative z-10">Institutional Shield</h4>
                    <p className="text-base text-slate-500 font-bold leading-relaxed uppercase tracking-[0.2em] italic opacity-60 mb-12 relative z-10 max-w-sm">
                        Calculated at: {new Date(metrics?.metrics_calculated_at || Date.now()).toLocaleString()} <br/>
                        Integrity Verified by Sovereign Protocols.
                    </p>
                    <button className="w-full gold-gradient py-8 rounded-3xl text-on-primary font-black text-sm uppercase tracking-[0.5em] shadow-2xl hover:brightness-110 active:scale-95 transition-all relative z-10">
                        Expert Concierge
                    </button>
                    <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[120px] rounded-full translate-x-32 -translate-y-32"></div>
                </div>
            </div>

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Autonomous Decentralized Feed: Sync Interval T-1s • Ledger Identification Artifacts Verified <br/>
                Sovereign Protocol Core-ID: {fund.isin || fund.scheme_code}
            </footer>
        </div>
    );
};

export default MFDetail;
