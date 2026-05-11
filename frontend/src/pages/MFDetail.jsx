import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { fetchFundDetail, clearDetail, syncFundMetrics } from '../store/slices/fundDetailSlice';
import { addToCompare, removeFromCompare } from '../store/slices/compareSlice';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import CompareDock from '../components/Compare/CompareDock';
import fundService from '../api/services/fundService';
import agentService from '../api/services/agentService';

const MFDetail = () => {
    const { schemeCode } = useParams();
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { fund, navHistory, metrics, loading, error, syncing } = useSelector((state) => state.fundDetail);
    const { compareList } = useSelector((state) => state.compare);
    const [activeTab, setActiveTab] = useState("intelligence");
    const [agentInsights, setAgentInsights] = useState(null);
    const [loadingInsights, setLoadingInsights] = useState(false);
    const [runningAnalysis, setRunningAnalysis] = useState(false);

    useEffect(() => {
        if (schemeCode) {
            dispatch(fetchFundDetail(schemeCode));
        }
        return () => dispatch(clearDetail());
    }, [dispatch, schemeCode]);

    const fetchAgentInsights = async () => {
        if (agentInsights) return;
        setLoadingInsights(true);
        try {
            const data = await fundService.getFundAgentInsights(schemeCode); // calls GET /agents/fund/{code}/analysis
            setAgentInsights(data);
        } catch (err) {
            if (err?.response?.status !== 404) {
                toast.error("Agentic analysis failed. Ensure Groq API is reachable.");
            }
            // 404 = no analysis yet — UI shows "Run Analysis" button
        } finally {
            setLoadingInsights(false);
        }
    };

    const handleRunFundAnalysis = async (force = false) => {
        setRunningAnalysis(true);
        try {
            await agentService.triggerFundAnalysis(schemeCode, force);
            setAgentInsights(null);
            setLoadingInsights(true);
            try {
                const data = await fundService.getFundAgentInsights(schemeCode);
                setAgentInsights(data);
            } finally {
                setLoadingInsights(false);
            }
            toast.success("Fund analysis complete.");
        } catch (err) {
            toast.error("Fund analysis failed.");
        } finally {
            setRunningAnalysis(false);
        }
    };

    const handleTabChange = (tabId) => {
        setActiveTab(tabId);
        if (tabId === "oracle") {
            fetchAgentInsights();
        }
    };

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
            <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-6">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Alpha Signal...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-20">
                <span className="material-symbols-outlined text-error text-9xl mb-8 font-variation-icon">security_update_warning</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-4 uppercase tracking-widest text-center">Asset Sync Failure</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12 text-center">{error}</p>
                <Link to="/mf" className="px-12 py-5 border border-white/20 rounded-2xl text-white font-black uppercase tracking-widest hover:bg-white/5 transition-all shadow-2xl">
                    Back to Vault
                </Link>
            </div>
        );
    }

    if (!fund) return null;

    const formatPercent = (val) => val != null ? `${(val * 100).toFixed(2)}%` : '—';
    const formatValue = (val) => val != null ? val.toFixed(2) : '—';

    // Detailed Ledger Fields
    const detailedLedger = [
        { label: 'Scheme Core ID', val: metrics?.scheme_code || '—' },
        { label: 'Current NAV', val: `₹${metrics?.current_nav || '—'}` },
        { label: 'Valuation Epoch', val: metrics?.nav_date || '—' },
        { label: 'AUM (Crores)', val: metrics?.aum_in_crores?.toLocaleString() || '0.0' },
        { label: 'Expense Ratio', val: formatPercent(metrics?.expense_ratio) },
        { label: 'Sovereign Rating', val: metrics?.fund_rating || '—' },
        { label: 'Volatility', val: metrics?.volatility || '—' },
        { label: 'CAGR (3Y)', val: formatPercent(metrics?.cagr_3year) },
        { label: 'CAGR (5Y)', val: formatPercent(metrics?.cagr_5year) },
        { label: 'Return (1Y)', val: formatPercent(metrics?.absolute_return_1y) },
        { label: 'Return (3Y)', val: formatPercent(metrics?.absolute_return_3y) },
        { label: 'Return (5Y)', val: formatPercent(metrics?.absolute_return_5y) },
        { label: 'Return (10Y)', val: formatPercent(metrics?.absolute_return_10y) },
        { label: 'Short Term (6M)', val: formatPercent(metrics?.short_term_return_6m) },
        { label: 'Upside Capture', val: metrics?.upside_capture || '—' },
        { label: 'Downside Capture', val: metrics?.downside_capture || '—' },
        { label: 'Sortino Ratio', val: formatValue(metrics?.sortino_ratio) },
        { label: 'Sharpe Ratio', val: formatValue(metrics?.sharpe_ratio) },
        { label: 'Alpha', val: metrics?.alpha || '—' },
        { label: 'Beta Corridor', val: metrics?.beta || '—' },
        { label: 'Std Deviation', val: formatValue(metrics?.standard_deviation) },
        { label: 'Max Drawdown', val: formatPercent(metrics?.maximum_drawdown) },
        { label: 'Tracking Error', val: metrics?.tracking_error || '—' },
        { label: 'Info Ratio', val: metrics?.information_ratio || '—' },
    ];

    const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);

    return (
        <div className="min-h-screen bg-surface text-on-surface overflow-hidden relative pb-16">
            {/* Editorial Watermark */}
            <div className="absolute top-40 -right-20 pointer-events-none opacity-[0.02] select-none origin-top-right">
                <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none">{fund.scheme_code}</span>
            </div>

            <div className="px-6 md:px-10 lg:px-14 xl:px-16 2xl:px-20 pt-12 relative z-10">
                
                {/* Compact Sovereign Header */}
                <header className="mb-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 pt-8 border-b border-outline-variant/10 pb-8">
                    <div className="flex items-center gap-6">
                        <button onClick={() => navigate(-1)} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group">
                            <span className="material-symbols-outlined text-sm group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
                        </button>
                        <div className="space-y-1">
                            <p className="font-label text-[10px] font-semibold uppercase tracking-[0.3em] text-primary flex items-center gap-2">
                                {fund.scheme_category} <span className="w-1 h-1 rounded-full bg-primary/50"></span> {fund.scheme_subcategory}
                            </p>
                            <h2 className="font-headline text-3xl md:text-5xl tracking-tight text-white uppercase max-w-4xl leading-tight">
                                <span className="font-bold text-primary mr-3">{fund.scheme_name.split(' - ')[0]}</span>
                                <span className="italic font-light text-white text-2xl md:text-3xl">{fund.scheme_name.split(' - ')[1] || 'Growth'}</span>
                            </h2>
                        </div>
                    </div>

                    <div className="flex items-center gap-4 self-end md:self-center">
                        <button 
                            onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare()}
                            className={`flex items-center gap-3 px-6 py-2.5 rounded-xl border transition-all font-black text-[10px] uppercase tracking-widest ${isComparing ? 'bg-primary text-on-primary border-primary shadow-[0_0_20px_rgba(233,195,73,0.3)]' : 'bg-white/5 text-slate-400 border-white/10 hover:border-primary/40 hover:text-white'}`}
                        >
                            <span className="material-symbols-outlined text-lg">{isComparing ? 'check_circle' : 'add_circle'}</span>
                            {isComparing ? 'Locked in Matrix' : 'Add to Compare'}
                        </button>
                        <div className="flex bg-surface-container-low border border-outline-variant/20 p-1 rounded-xl">
                            <button
                                onClick={() => dispatch(syncFundMetrics(schemeCode))}
                                disabled={syncing}
                                className="flex items-center gap-2 px-4 py-2.5 hover:bg-white/5 rounded-lg transition-all text-slate-400 hover:text-primary group"
                                title="Refresh Fund Metrics"
                            >
                                <span className={`material-symbols-outlined text-xl ${syncing ? 'animate-spin text-primary' : 'group-hover:rotate-180 transition-transform duration-700'}`}>sync</span>
                                <span className="text-[10px] font-black uppercase tracking-widest hidden md:block">{syncing ? 'Recalculating...' : 'Refresh Artifact'}</span>
                            </button>
                        </div>
                        <div className="bg-surface-container-low border border-outline-variant/20 px-4 py-2 rounded-xl flex items-center gap-3">
                            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                            <span className="text-[10px] font-black uppercase tracking-widest text-secondary">Vault Verified</span>
                        </div>
                    </div>
                </header>

                {/* High-Density Metric Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
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

                    {/* Scale Card (AUM) */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Assets Under Mgmt</p>
                            <span className="material-symbols-outlined text-primary text-lg">inventory_2</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white">₹{metrics?.aum_in_crores ? (metrics.aum_in_crores/1000).toFixed(1) + 'k Cr' : '—'}</p>
                            <div className="flex flex-col mb-1">
                                <span className="text-[10px] text-secondary font-black uppercase">Tier 1 AUM</span>
                                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Portfolio Scale</span>
                            </div>
                        </div>
                    </div>

                    {/* Momentum Card (3Y CAGR) */}
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

                    {/* Identity Card (AMC) */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group border-l-4 border-l-primary">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Asset Controller</p>
                            <span className="material-symbols-outlined text-primary text-lg">domain</span>
                        </div>
                        <div className="flex items-end gap-2 overflow-hidden">
                            <p className="font-headline text-3xl font-extrabold text-white uppercase tracking-tighter leading-tight truncate">{fund.amc_name?.split(' ')[0] || 'AMC'}</p>
                        </div>
                    </div>
                </div>

                {/* Global Tabs */}
                <div className="flex justify-center gap-8 mb-16 border-b border-outline-variant/20 overflow-x-auto no-scrollbar">
                    {[
                        { id: "intelligence", label: "Intelligence" },
                        { id: "oracle", label: "Agent Insights" },
                        { id: "ledger", label: "Ledger Artifacts" }
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className={`pb-4 font-label text-[11px] font-black uppercase tracking-[0.4em] transition-all whitespace-nowrap ${activeTab === tab.id
                                ? "text-primary border-b-2 border-primary"
                                : "text-slate-500 hover:text-white"
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Dynamic Content */}
                <AnimatePresence mode="wait">
                    {activeTab === "intelligence" && (
                        <motion.div key="intelligence" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-16">
                            
                            {/* Growth Trajectory Section */}
                            <section className="animate-fadeIn">
                                <div className="flex items-center justify-between mb-8">
                                    <h3 className="font-headline text-3xl font-bold italic tracking-tighter">Growth Trajectory</h3>
                                    <div className="flex items-center gap-4">
                                        <span className="text-[10px] text-slate-500 font-black uppercase tracking-widest">Absolute Momentum Surveillance</span>
                                        <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                                    </div>
                                </div>

                                <div className="glass-panel p-8 rounded-[2rem] border border-outline-variant/10 h-[450px] relative overflow-hidden">
                                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none blur-3xl opacity-30"></div>
                                    {navHistory.length > 0 ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={navHistory}>
                                                <defs>
                                                    <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#e9c349" stopOpacity={0.3} />
                                                        <stop offset="95%" stopColor="#e9c349" stopOpacity={0} />
                                                    </linearGradient>
                                                </defs>
                                                <XAxis dataKey="date" hide />
                                                <YAxis domain={['auto', 'auto']} hide />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: 'rgba(27, 32, 37, 0.9)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '1rem', color: '#fff', fontSize: '12px' }}
                                                    itemStyle={{ color: '#e9c349', fontWeight: 'bold' }}
                                                    labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                                                />
                                                <Area
                                                    type="monotone"
                                                    dataKey="nav"
                                                    stroke="#e9c349"
                                                    strokeWidth={4}
                                                    fillOpacity={1}
                                                    fill="url(#colorNav)"
                                                    animationDuration={1500}
                                                />
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div className="h-full flex items-center justify-center text-slate-500 font-label text-xs uppercase tracking-widest relative z-10">No Historical Data Recovered</div>
                                    )}
                                </div>
                            </section>

                            <div className="flex flex-col xl:flex-row gap-16">
                                {/* Left Column: Core Metrics & Risk */}
                                <div className="flex-1 flex flex-col gap-12">
                                    
                                    <section>
                                        <h3 className="font-headline text-3xl font-bold italic mb-8 tracking-tighter text-white">Performance Matrix</h3>
                                        <div className="grid grid-cols-2 md:grid-cols-3 gap-1">
                                            <DataCell label="Absolute (6M)" value={formatPercent(metrics?.short_term_return_6m)} />
                                            <DataCell label="Absolute (1Y)" value={formatPercent(metrics?.absolute_return_1y)} />
                                            <DataCell label="Absolute (3Y)" value={formatPercent(metrics?.absolute_return_3year || metrics?.absolute_return_3y)} />
                                            <DataCell label="Absolute (5Y)" value={formatPercent(metrics?.absolute_return_5year || metrics?.absolute_return_5y)} />
                                            <DataCell label="CAGR (3Y)" value={formatPercent(metrics?.cagr_3year)} />
                                            <DataCell label="CAGR (5Y)" value={formatPercent(metrics?.cagr_5year)} highlight />
                                        </div>
                                    </section>

                                    <section>
                                        <h3 className="font-headline text-3xl font-bold italic mb-8 tracking-tighter text-white">Quantitative Risk Surveillance</h3>
                                        <div className="grid grid-cols-2 gap-1">
                                            <DataCell label="Sharpe Ratio" value={formatValue(metrics?.sharpe_ratio)} />
                                            <DataCell label="Sortino Ratio" value={formatValue(metrics?.sortino_ratio)} />
                                            <DataCell label="Alpha" value={metrics?.alpha || '—'} />
                                            <DataCell label="Beta Corridor" value={metrics?.beta || '—'} />
                                            <DataCell label="Std Deviation" value={formatValue(metrics?.standard_deviation)} />
                                            <DataCell label="Max Drawdown" value={formatPercent(metrics?.maximum_drawdown)} />
                                        </div>
                                    </section>
                                </div>

                                {/* Right Column: Sovereign's Oracle */}
                                <div className="xl:w-[450px] shrink-0">
                                    <div className={`sticky top-32 glass-panel rounded-[3rem] p-10 border border-outline-variant/10 shadow-[0_0_40px_rgba(233,195,73,0.1)] relative overflow-hidden`}>
                                        {/* Glass Sheen */}
                                        <div className="absolute inset-x-0 -top-10 h-32 bg-gradient-to-b from-white/5 to-transparent blur-2xl"></div>

                                        <div className="flex items-center gap-4 mb-8 relative z-10">
                                            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center border border-primary/30">
                                                <span className="material-symbols-outlined text-primary font-variation-icon">psychology</span>
                                            </div>
                                            <div>
                                                <h4 className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">The Sovereign's Oracle</h4>
                                                <p className="text-xs text-slate-500 font-label tracking-widest uppercase">Asset Strategic Verdict</p>
                                            </div>
                                        </div>

                                        <div className="space-y-8 relative z-10">
                                            <div>
                                                <h5 className="font-headline text-white font-bold mb-3 italic">Investment Thesis</h5>
                                                <p className="text-sm text-slate-400 font-label leading-relaxed italic">
                                                    {metrics?.final_verdict || `The strategic vector for ${fund.scheme_name} indicates a stable accumulation pattern within the ${fund.scheme_category} space. Sovereign protocols verify the underlying AUM integrity.`}
                                                </p>
                                            </div>

                                            <div className="pt-8 border-t border-white/5">
                                                <div className="flex flex-col items-center text-center group">
                                                    <div className="mb-6">
                                                        <span className="material-symbols-outlined text-6xl text-primary opacity-20 group-hover:opacity-60 transition-all duration-700">shield_with_heart</span>
                                                    </div>
                                                    <h4 className="text-xl font-headline font-black mb-4 uppercase tracking-widest">Institutional Shield</h4>
                                                    <p className="text-[10px] text-slate-500 font-bold leading-relaxed uppercase tracking-[0.2em] italic opacity-60">
                                                        Calculated at: {new Date(metrics?.metrics_calculated_at || Date.now()).toLocaleDateString()} <br/>
                                                        Integrity Verified by Sovereign Protocols.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {activeTab === "oracle" && (
                        <motion.div key="oracle" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                            <AgentInsightsTab
                                data={agentInsights}
                                loading={loadingInsights}
                                runningAnalysis={runningAnalysis}
                                onRunAnalysis={handleRunFundAnalysis}
                                onRefresh={() => {
                                    setAgentInsights(null);
                                    fetchAgentInsights();
                                }}
                            />
                        </motion.div>
                    )}

                    {activeTab === "ledger" && (
                        <motion.div key="ledger" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-12">
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-1">
                                {detailedLedger.map((d, i) => (
                                    <DataCell key={i} label={d.label} value={d.val} />
                                ))}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <CompareDock />
            </div>
        </div>
    );
};

function DataCell({ label, value, highlight }) {
    return (
        <div className={`bg-surface-container-low p-8 first:rounded-tl-[2rem] last:rounded-br-[2rem] border-[0.5px] border-surface transition-colors hover:bg-surface-container`}>
            <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.3em] mb-4">{label}</p>
            <p className={`text-2xl md:text-3xl font-headline font-bold tracking-tighter ${highlight ? 'text-primary' : 'text-white'}`}>{value}</p>
        </div>
    );
}

const AgentInsightsTab = ({ data, loading, runningAnalysis, onRunAnalysis, onRefresh }) => {
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[40vh] space-y-6">
                <div className="relative w-24 h-24">
                    <div className="absolute inset-0 border-4 border-primary/10 rounded-full"></div>
                    <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="material-symbols-outlined text-3xl text-primary animate-pulse">psychology</span>
                    </div>
                </div>
                <div className="text-center">
                    <p className="text-white font-headline text-lg font-black tracking-widest uppercase mb-1">Synthesizing Intelligence</p>
                    <p className="text-slate-500 text-[10px] font-bold uppercase tracking-[0.3em]">Fetching agent analysis...</p>
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="glass-panel p-20 text-center rounded-[3rem] border border-white/5">
                <span className="material-symbols-outlined text-6xl text-slate-700 mb-6 block">psychology</span>
                <p className="text-[10px] uppercase font-black tracking-widest text-slate-500 mb-3">No Analysis Found</p>
                <p className="text-xs text-slate-600 mb-10">Run the AI analysis to score this fund against its peers.</p>
                <button
                    onClick={() => onRunAnalysis(false)}
                    disabled={runningAnalysis}
                    className="px-10 py-4 bg-primary text-black rounded-xl font-black text-[10px] tracking-[0.2em] uppercase hover:brightness-110 active:scale-95 transition-all font-headline disabled:opacity-50 flex items-center gap-3 mx-auto"
                >
                    {runningAnalysis ? (
                        <><span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin"></span>Analysing...</>
                    ) : (
                        <><span className="material-symbols-outlined text-lg">psychology</span>Run Agent Analysis</>
                    )}
                </button>
            </div>
        );
    }

    const compositeScore = data.composite_score || 0;
    const scoreColor = compositeScore >= 70 ? 'text-secondary' : compositeScore >= 45 ? 'text-primary' : 'text-error';

    return (
        <div className="space-y-12 animate-fadeIn pb-20">
            {/* Score + Verdict */}
            <div className="flex flex-col lg:flex-row gap-8">
                {/* Circular Gauge */}
                <div className="lg:w-1/3 glass-panel p-10 rounded-[3rem] border border-white/5 flex flex-col items-center justify-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent pointer-events-none"></div>
                    <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] mb-6 relative z-10">Composite Alpha Score</p>
                    <div className="relative w-48 h-48 flex items-center justify-center z-10">
                        <svg className="w-full h-full transform -rotate-90">
                            <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="2" fill="transparent" className="text-white/5" />
                            <circle
                                cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="10" fill="transparent"
                                strokeDasharray={552.92}
                                strokeDashoffset={552.92 - (552.92 * compositeScore) / 100}
                                className={`${scoreColor} drop-shadow-[0_0_10px_rgba(233,195,73,0.5)]`}
                                strokeLinecap="round"
                            />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-5xl font-headline font-black text-white">{compositeScore.toFixed(1)}</span>
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">/ 100</span>
                        </div>
                    </div>
                    {data.verdict_label && (
                        <div className="mt-8 px-6 py-2 bg-primary/10 border border-primary/20 rounded-full z-10">
                            <span className="text-[10px] font-black text-primary uppercase tracking-widest">{data.verdict_label}</span>
                        </div>
                    )}
                    {/* Peer Rank */}
                    {data.category_rank && (
                        <div className="mt-4 text-center z-10">
                            <span className="text-[10px] text-slate-500 font-black uppercase tracking-widest">
                                Rank #{data.category_rank} of {data.category_size} &nbsp;·&nbsp; {Number(data.peer_percentile || 0).toFixed(0)}th percentile
                            </span>
                        </div>
                    )}
                </div>

                {/* Verdict Text */}
                <div className="lg:flex-1 glass-panel p-10 rounded-[3rem] border border-white/5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-8 opacity-10">
                        <span className="material-symbols-outlined text-8xl text-primary">format_quote</span>
                    </div>
                    <h4 className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500 mb-6">Analyst Verdict</h4>
                    <p className="text-xl md:text-2xl font-headline font-light italic leading-relaxed text-white/90 relative z-10">
                        "{data.verdict_text || 'No verdict available.'}"
                    </p>
                    <div className="mt-12 flex justify-between items-center relative z-10">
                        <div className="flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full bg-secondary animate-pulse"></div>
                            <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                Status: {data.status} &nbsp;·&nbsp; {data.analysed_at ? new Date(data.analysed_at).toLocaleDateString('en-IN') : ''}
                            </span>
                        </div>
                        <button
                            onClick={() => onRunAnalysis(true)}
                            disabled={runningAnalysis}
                            className="flex items-center gap-2 px-6 py-2 rounded-xl border border-white/5 hover:bg-white/5 transition-all group disabled:opacity-50"
                        >
                            <span className={`material-symbols-outlined text-sm text-primary ${runningAnalysis ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`}>sync</span>
                            <span className="text-[9px] font-black text-slate-400 group-hover:text-white uppercase tracking-widest">
                                {runningAnalysis ? 'Running...' : 'Re-run Analysis'}
                            </span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Key Strengths & Risks */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {data.key_strengths?.length > 0 && (
                    <div className="glass-panel p-8 rounded-[2.5rem] border border-white/5">
                        <h5 className="text-[10px] font-black text-secondary uppercase tracking-[0.3em] mb-6">Key Strengths</h5>
                        <ul className="space-y-4">
                            {data.key_strengths.map((s, i) => (
                                <li key={i} className="flex items-start gap-3 text-sm text-slate-300 font-label">
                                    <span className="material-symbols-outlined text-secondary text-base shrink-0 mt-0.5">check_circle</span>
                                    {s}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
                {data.key_risks?.length > 0 && (
                    <div className="glass-panel p-8 rounded-[2.5rem] border border-white/5">
                        <h5 className="text-[10px] font-black text-error uppercase tracking-[0.3em] mb-6">Key Risks</h5>
                        <ul className="space-y-4">
                            {data.key_risks.map((r, i) => (
                                <li key={i} className="flex items-start gap-3 text-sm text-slate-300 font-label">
                                    <span className="material-symbols-outlined text-error text-base shrink-0 mt-0.5">warning</span>
                                    {r}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MFDetail;
