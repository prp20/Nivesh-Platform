import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import fundService from '../api/services/fundService';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';

const IndexDetail = () => {
    const { indexCode } = useParams();
    const [indexData, setIndexData] = useState(null);
    const [navHistory, setNavHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchIndexData = async () => {
            setLoading(true);
            try {
                const [detail, history] = await Promise.all([
                    fundService.getBenchmarkDetail(indexCode),
                    fundService.getBenchmarkNavHistory(indexCode, 2000)
                ]);
                setIndexData(detail);
                setNavHistory(history.map(pt => ({
                    date: pt.nav_date,
                    value: parseFloat(pt.index_value)
                })).reverse());
            } catch (err) {
                setError(err.message || 'Benchmark synchronization failed.');
            } finally {
                setLoading(false);
            }
        };

        if (indexCode) {
            fetchIndexData();
        }
    }, [indexCode]);

    if (loading) {
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

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-12 mb-8">
                <div className="flex-1">
                    <div className="flex items-center gap-6 mb-10">
                        <span className="bg-primary/10 text-primary border border-primary/20 px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-[0.4em] leading-none"> {indexData.asset_class || 'Global Equity'} </span>
                        <span className="text-secondary text-sm font-black uppercase tracking-[0.4em] flex items-center gap-3">
                            <span className="material-symbols-outlined text-2xl">verified</span>
                            Systemic Alpha Calibrated
                        </span>
                    </div>
                    <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[12rem] font-headline font-bold text-white tracking-tighter leading-none mb-10 group uppercase">
                        {indexData.benchmark_name} <span className="text-primary/10 group-hover:text-primary transition-all duration-1000">INDEX</span>
                    </h1>
                    <p className="text-xl md:text-2xl text-slate-500 font-black max-w-6xl leading-tight italic uppercase tracking-[0.3em] opacity-60"> Ticker: {indexData.ticker} • Benchmark Protocol Active </p>
                </div>

                <div className="flex flex-col items-end gap-4 bg-surface-container-high/60 p-12 md:p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] backdrop-blur-3xl min-w-[400px]">
                    <span className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] leading-none mb-2 opacity-60">Global Index Valuation</span>
                    <div className="text-7xl sm:text-8xl md:text-9xl font-headline font-black text-white tracking-tighter leading-none mt-2">{navHistory[0]?.value?.toLocaleString()}</div>
                    <div className="flex items-center gap-4 text-secondary text-3xl font-black uppercase tracking-[0.3em] mt-8 px-10 py-5 bg-secondary/10 rounded-[2.5rem] border border-secondary/20 shadow-2xl shadow-secondary/10">
                        <span className="material-symbols-outlined text-4xl">trending_up</span>
                        +1.45% T-SESSION
                    </div>
                </div>
            </header>

            {/* Performance Chart Section */}
            <section className="glass-panel p-12 md:p-16 2xl:p-24 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.7)] relative overflow-hidden backdrop-blur-3xl min-h-[600px] bg-white/[0.01]">
                <div className="mb-20 relative z-10">
                    <h3 className="text-4xl font-headline font-bold tracking-tight mb-4 uppercase tracking-[0.2em] leading-none">Global Trajectory Matrix</h3>
                    <p className="text-base text-slate-500 font-black tracking-[0.3em] flex items-center gap-4 uppercase opacity-60"> Continuous surveillance of systemic benchmark momentum <span className="inline-block w-3 h-3 rounded-full bg-secondary animate-pulse"></span> </p>
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
                            <Tooltip contentStyle={{ backgroundColor: '#1b2025', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '24px', backdropFilter: 'blur(16px)', padding: '24px' }} itemStyle={{ fontSize: '18px', fontWeight: 'black', color: '#e9c349' }} />
                            <Area type="monotone" dataKey="value" stroke="#e9c349" strokeWidth={6} fillOpacity={1} fill="url(#colorIndex)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </section>

             {/* Footer */}
             <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Benchmark Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

export default IndexDetail;
