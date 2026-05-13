import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { fetchIndexDetail, clearDetail } from '../store/slices/indicesSlice';
import { AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';

const IndexDetail = () => {
    const { benchmarkCode } = useParams();
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { currentDetail: indexData, navHistory, detailLoading: loading, detailError: error } = useSelector((state) => state.indices);
    
    const [activeTab, setActiveTab] = useState("performance");
    const [activeTimeframe, setActiveTimeframe] = useState('1Y');

    const timeframes = [
        { id: '1M', days: 30 },
        { id: '6M', days: 180 },
        { id: '1Y', days: 365 },
        { id: '5Y', days: 1825 },
        { id: 'MAX', days: 10000 }
    ];

    useEffect(() => {
        if (benchmarkCode) {
            dispatch(fetchIndexDetail(benchmarkCode));
        }
        return () => dispatch(clearDetail());
    }, [dispatch, benchmarkCode]);

    if (loading && !indexData) {
        return (
            <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-6">
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
                <Link to="/indices" className="px-12 py-5 bg-primary text-black rounded-2xl font-black uppercase tracking-widest shadow-2xl">
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

    // Filter navHistory based on activeTimeframe
    const tf = timeframes.find(t => t.id === activeTimeframe);
    const filteredHistory = navHistory.slice(-(tf?.days || 365));

    return (
        <div className="min-h-screen bg-surface text-on-surface overflow-hidden relative pb-16">
            {/* Editorial Watermark */}
            <div className="absolute top-40 -right-20 pointer-events-none opacity-[0.02] select-none origin-top-right">
                <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none">{indexData.ticker}</span>
            </div>

            <div className="px-6 md:px-10 lg:px-14 xl:px-16 2xl:px-20 pt-12 relative z-10">
                {/* Compact Sovereign Header */}
                <header className="mb-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 pt-8 border-b border-outline-variant/10 pb-8">
                    <div className="flex items-center gap-6">
                        <button onClick={() => navigate(-1)} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group">
                            <span className="material-symbols-outlined text-sm group-hover:-translate-x-0.5 transition-transform text-white">arrow_back</span>
                        </button>
                        <div className="space-y-1">
                            <h2 className="font-headline text-4xl md:text-5xl tracking-tight text-white uppercase">
                                <span className="font-bold text-primary mr-3">{indexData.benchmark_name}</span>
                                <span className="italic font-light text-white text-3xl">{indexData.ticker}</span>
                            </h2>
                        </div>
                    </div>

                    <div className="flex items-center gap-4 self-end md:self-center">
                        <div className="bg-surface-container-low border border-outline-variant/20 px-4 py-2 rounded-xl flex items-center gap-3">
                            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                            <span className="text-[10px] font-black uppercase tracking-widest text-secondary">Systemic Feed Active</span>
                        </div>
                    </div>
                </header>

                {/* High-Density Metric Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                    {/* Price Card */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Current Level</p>
                            <span className="material-symbols-outlined text-primary text-lg">signal_cellular_alt</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white">{latestVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                            <div className="flex flex-col mb-1">
                                <span className={`text-[10px] font-black ${delta >= 0 ? 'text-secondary' : 'text-error'}`}>
                                    {delta >= 0 ? '+' : ''}{deltaPercent.toFixed(2)}%
                                </span>
                                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Session Delta</span>
                            </div>
                        </div>
                        <div className={`absolute bottom-0 left-0 h-1 transition-all duration-700 ${delta >= 0 ? 'bg-secondary w-full' : 'bg-error w-full'}`}></div>
                    </div>

                    {/* Scale Card */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Asset Type</p>
                            <span className="material-symbols-outlined text-primary text-lg">category</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <p className="font-headline text-3xl font-extrabold text-white uppercase tracking-tighter leading-tight">{indexData.benchmark_type || 'EQUITY / GLOBAL'}</p>
                        </div>
                    </div>

                    {/* Protocol Status Card */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Systemic Weight</p>
                            <span className="material-symbols-outlined text-primary text-lg">balance</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <p className="font-headline text-3xl font-extrabold text-white uppercase tracking-tight">Market Cap weighted</p>
                        </div>
                    </div>

                    {/* Beta/Correlation Card */}
                    <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group border-l-4 border-l-primary">
                        <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Surveillance Tier</p>
                            <span className="material-symbols-outlined text-primary text-lg">security</span>
                        </div>
                        <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white uppercase tracking-tighter leading-none">PRIME</p>
                        </div>
                    </div>
                </div>

                {/* Global Tabs */}
                <div className="flex justify-center gap-8 mb-16 border-b border-outline-variant/20 overflow-x-auto no-scrollbar">
                    {[
                        { id: "performance", label: "Intelligence" },
                        { id: "constituents", label: "Systemic Components" }
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
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
                    {activeTab === "performance" && (
                        <motion.div key="performance" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-16">
                            {/* Full-Width Price Performance Header */}
                            <section className="animate-fadeIn">
                                <div className="flex items-center justify-between mb-8">
                                    <h3 className="font-headline text-3xl font-bold italic tracking-tighter">Index Trajectory</h3>
                                    <div className="flex bg-surface-container-low rounded-xl p-1 shadow-lg border border-outline-variant/5">
                                        {timeframes.map(tf => (
                                            <button
                                                key={tf.id}
                                                onClick={() => setActiveTimeframe(tf.id)}
                                                className={`px-4 py-2 rounded-lg text-xs font-black tracking-widest transition-all ${activeTimeframe === tf.id
                                                    ? 'bg-primary text-on-primary shadow shadow-primary/20'
                                                    : 'text-slate-500 hover:text-white hover:bg-white/5'
                                                    }`}
                                            >
                                                {tf.id}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="glass-panel p-8 rounded-[2rem] border border-outline-variant/10 h-[450px] relative overflow-hidden">
                                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none blur-3xl opacity-30"></div>
                                    {filteredHistory.length > 0 ? (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={filteredHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                                <defs>
                                                    <linearGradient id="colorIndex" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#e9c349" stopOpacity={0.3} />
                                                        <stop offset="95%" stopColor="#e9c349" stopOpacity={0} />
                                                    </linearGradient>
                                                </defs>
                                                <XAxis
                                                    dataKey="date"
                                                    stroke="#64748b"
                                                    fontSize={10}
                                                    tickLine={false}
                                                    axisLine={false}
                                                    tickFormatter={(val) => {
                                                        const d = new Date(val);
                                                        return activeTimeframe === '1M'
                                                            ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
                                                            : d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
                                                    }}
                                                />
                                                <YAxis
                                                    stroke="#64748b"
                                                    fontSize={10}
                                                    tickLine={false}
                                                    axisLine={false}
                                                    domain={['auto', 'auto']}
                                                    tickFormatter={(val) => val.toLocaleString()}
                                                />
                                                <RechartsTooltip
                                                    contentStyle={{ backgroundColor: 'rgba(27, 32, 37, 0.9)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '1rem', color: '#fff', fontSize: '12px' }}
                                                    itemStyle={{ color: '#e9c349', fontWeight: 'bold' }}
                                                    labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                                                />
                                                <Area
                                                    type="monotone"
                                                    dataKey="value"
                                                    stroke="#e9c349"
                                                    strokeWidth={3}
                                                    fillOpacity={1}
                                                    fill="url(#colorIndex)"
                                                    animationDuration={1500}
                                                />
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div className="h-full flex items-center justify-center text-slate-500 font-label text-xs uppercase tracking-widest relative z-10">No Historical Data Recovered</div>
                                    )}
                                </div>
                            </section>

                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
                                <DataCell label="Full Name" value={indexData.benchmark_name} />
                                <DataCell label="Identification" value={indexData.benchmark_code} />
                                <DataCell label="Protocol status" value="NOMINAL" highlight />
                            </div>
                        </motion.div>
                    )}

                    {activeTab === "constituents" && (
                        <motion.div key="constituents" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col items-center justify-center p-20 gap-8">
                             <span className="material-symbols-outlined text-6xl text-slate-800">hub</span>
                             <p className="text-[10px] uppercase font-black tracking-widest text-slate-600">Component mapping currently restricted to prime members</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

function DataCell({ label, value, highlight }) {
    return (
        <div className={`bg-surface-container-low p-8 first:rounded-tl-[2rem] last:rounded-br-[2rem] border-[0.5px] border-outline-variant/10 transition-colors hover:bg-surface-container`}>
            <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.3em] mb-4">{label}</p>
            <p className={`text-2xl font-headline font-bold tracking-tighter ${highlight ? 'text-primary' : 'text-white'}`}>{value}</p>
        </div>
    );
}

export default IndexDetail;

