import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, Link } from 'react-router-dom';
import { fetchFundDetail, clearDetail, syncFundMetrics } from '../store/slices/fundDetailSlice';
import { addToCompare, removeFromCompare } from '../store/slices/compareSlice';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import CompareDock from '../components/Compare/CompareDock';

const MFDetail = () => {
    const { schemeCode } = useParams();
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { fund, navHistory, metrics, loading, error, syncing } = useSelector((state) => state.fundDetail);
    const { compareList } = useSelector((state) => state.compare);
    const [isLedgerExpanded, setIsLedgerExpanded] = useState(false);

    useEffect(() => {
        if (schemeCode) {
            dispatch(fetchFundDetail(schemeCode));
        }
        return () => dispatch(clearDetail());
    }, [dispatch, schemeCode]);

    const handleAddToCompare = () => {
        if (compareList.length >= 4) {
            toast.error('Maximum phase capacity reached (4 assets)');
            return;
        }
        
        if (compareList.length > 0) {
            if (compareList[0].scheme_category !== fund.scheme_category || 
                compareList[0].scheme_subcategory !== fund.scheme_subcategory) {
                toast.error('Strategic Mismatch: Assets must share identical category & subcategory');
                return;
            }
        }

        dispatch(addToCompare(fund));
        toast.success(`${fund.scheme_name.substring(0, 20)}... locked into matrix`);
    };

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
        <div className="p-6 md:p-10 lg:p-12 2xl:p-16 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Compact Asset Header */}
            <header className="mb-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 pt-8 border-b border-outline-variant/10 pb-8">
              <div className="flex items-center gap-6">
                <button onClick={() => navigate(-1)} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group">
                  <span className="material-symbols-outlined text-sm group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
                </button>
                <div className="space-y-1">
                  <p className="font-label text-[10px] font-semibold uppercase tracking-[0.3em] text-primary flex items-center gap-2">
                    {fund.scheme_category} <span className="w-1 h-1 rounded-full bg-primary/50"></span> {fund.scheme_subcategory}
                  </p>
                  <h2 className="font-headline text-4xl md:text-5xl font-light tracking-tight text-white uppercase max-w-4xl">
                    {fund.scheme_name.split(' - ')[0]} <span className="font-extrabold italic text-primary">{fund.scheme_name.split(' - ')[1] || 'Growth'}</span>
                  </h2>
                </div>
              </div>

              <div className="flex items-center gap-4 self-end md:self-center">
                 {(() => {
                   const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);
                   return (
                     <button 
                       onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare()}
                       className={`flex items-center gap-3 px-6 py-2.5 rounded-xl border transition-all font-black text-[10px] uppercase tracking-widest ${isComparing ? 'bg-primary text-on-primary border-primary shadow-[0_0_20px_rgba(233,195,73,0.3)]' : 'bg-white/5 text-slate-400 border-white/10 hover:border-primary/40 hover:text-white'}`}
                     >
                       <span className="material-symbols-outlined text-lg">{isComparing ? 'check_circle' : 'add_circle'}</span>
                       {isComparing ? 'Locked in Matrix' : 'Add to Compare'}
                     </button>
                   );
                 })()}

                 <div className="bg-surface-container-low border border-outline-variant/20 px-4 py-2 rounded-xl flex items-center gap-3">
                   <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                   <span className="text-[10px] font-black uppercase tracking-widest text-secondary italic">Vault Verified</span>
                 </div>
              </div>
            </header>

            {/* Strategic Intelligence Verdict (Compact) */}
            {metrics?.final_verdict && (
                <div className="glass-panel p-6 rounded-2xl border-l-4 border-l-primary bg-white/[0.02]">
                    <div className="flex items-center gap-4 mb-2">
                        <span className="material-symbols-outlined text-xl text-primary animate-pulse">auto_awesome</span>
                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-500">Intelligence Verdict</h4>
                    </div>
                    <p className="text-lg text-white/90 font-medium tracking-tight italic">
                        "{metrics.final_verdict}"
                    </p>
                </div>
            )}

            {/* High-Density Status Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* NAV Card */}
                <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-4">
                    <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Net Asset Value</p>
                    <span className="material-symbols-outlined text-primary text-lg">account_balance</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <p className="font-headline text-4xl font-extrabold text-white">₹{formatValue(metrics?.current_nav)}</p>
                    <div className="flex flex-col mb-1">
                      <span className={`text-[10px] font-black ${metrics?.absolute_return_1y >= 0 ? 'text-secondary' : 'text-error'}`}>
                        {metrics?.absolute_return_1y >= 0 ? '+' : ''}{formatPercent(metrics?.absolute_return_1y)}
                      </span>
                      <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">T-12M Alpha</span>
                    </div>
                  </div>
                  <div className={`absolute bottom-0 left-0 h-1 transition-all duration-700 ${metrics?.absolute_return_1y >= 0 ? 'bg-secondary w-full' : 'bg-error w-full'}`}></div>
                </div>

                {/* AUM Card */}
                <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-4">
                    <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Assets Under Mgmt</p>
                    <span className="material-symbols-outlined text-primary text-lg">inventory_2</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <p className="font-headline text-4xl font-extrabold text-white">₹{metrics?.aum_in_crores ? (metrics.aum_in_crores/1000).toFixed(1) + 'k Cr' : '—'}</p>
                    <div className="flex flex-col mb-1">
                      <span className="text-[10px] text-secondary font-black uppercase tracking-tighter">Tier 1 AUM</span>
                      <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Portfolio Scale</span>
                    </div>
                  </div>
                </div>

                {/* Return Alpha Card */}
                <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-4">
                    <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">3Y CAGR Momentum</p>
                    <span className="material-symbols-outlined text-primary text-lg">trending_up</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <p className="font-headline text-4xl font-extrabold text-white tracking-tighter">{formatPercent(metrics?.cagr_3year)}</p>
                    <div className="flex flex-col mb-1">
                      <span className="text-[10px] text-secondary font-black uppercase">Steady Growth</span>
                      <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Compounded</span>
                    </div>
                  </div>
                </div>

                {/* Asset Identity Card */}
                <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-4">
                    <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Elite Registry ID</p>
                    <span className="material-symbols-outlined text-primary text-lg">fingerprint</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <p className="font-headline text-4xl font-extrabold text-white uppercase tracking-tighter">{fund.scheme_code}</p>
                    <div className="flex flex-col mb-1">
                      <span className="text-[10px] text-secondary font-black uppercase truncate max-w-[100px]">{fund.amc_name?.split(' ')[0]}</span>
                      <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Asset Controller</span>
                    </div>
                  </div>
                </div>
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



            <CompareDock />
        </div>
    );
};

export default MFDetail;
