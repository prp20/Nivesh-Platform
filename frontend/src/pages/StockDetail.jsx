import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import fundService from '../api/services/fundService';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';

const StockDetail = () => {
    const { stockCode } = useParams();
    const [stockData, setStockData] = useState(null);
    const [navHistory, setNavHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStockData = async () => {
            setLoading(true);
            try {
                // If the backend has a specific stock detail, use it. 
                // For now, many stocks are mapped to 'funds' in the Nivesh schema.
                const [detail, history] = await Promise.all([
                    fundService.getFundDetail(stockCode).catch(() => fundService.getBenchmarkDetail(stockCode)),
                    fundService.getFundNavHistory(stockCode, 2000).catch(() => fundService.getBenchmarkNavHistory(stockCode, 2000))
                ]);
                setStockData(detail);
                setNavHistory(history.map(pt => ({
                    date: pt.nav_date,
                    nav: parseFloat(pt.nav_value || pt.index_value)
                })).reverse());
            } catch (err) {
                setError(err.message || 'Equity synchronization failed.');
            } finally {
                setLoading(false);
            }
        };

        if (stockCode) {
            fetchStockData();
        }
    }, [stockCode]);

    if (loading) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Equity Artifact...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-20">
                <span className="material-symbols-outlined text-error text-9xl mb-8">security_update_warning</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-4 uppercase tracking-widest">Protocol Breach</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12">{error}</p>
                <Link to="/stocks" className="px-12 py-5 gold-gradient rounded-2xl text-on-primary font-black uppercase tracking-widest shadow-2xl transition-all active:scale-95">
                    Return to Navigator
                </Link>
            </div>
        );
    }

    if (!stockData) return null;

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
             {/* Header - Ultra Scale */}
             <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-16 mb-8">
                <div className="flex-1">
                    <div className="flex items-center gap-6 mb-10">
                        <span className="bg-primary/10 text-primary border border-primary/20 px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-[0.4em] leading-none"> {stockData.scheme_category || 'Elite Equity'} </span>
                        <span className="text-secondary text-sm font-black uppercase tracking-[0.4em] flex items-center gap-3">
                            <span className="material-symbols-outlined text-2xl animate-pulse">verified</span>
                            SECURED ARTIFACT
                        </span>
                    </div>
                    <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[13rem] font-headline font-bold text-white tracking-tighter leading-none mb-10 group uppercase">
                        {stockData.scheme_name || stockData.benchmark_name}
                    </h1>
                    <p className="text-xl md:text-2xl text-slate-500 font-black max-w-6xl leading-tight uppercase tracking-[0.2em] opacity-60"> ISIN: {stockData.isin || 'NIV-X'} • SECTOR: TECHNOLOGY </p>
                </div>

                <div className="flex flex-col items-end gap-4 bg-surface-container-high/60 p-12 md:p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] backdrop-blur-3xl min-w-[400px]">
                    <span className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] leading-none mb-2 opacity-60">Market Identity Price</span>
                    <div className="text-7xl sm:text-8xl md:text-9xl font-headline font-black text-white tracking-tighter leading-none mt-2">₹{navHistory[0]?.nav?.toFixed(2) || 'N/A'}</div>
                    <div className="flex items-center gap-4 text-secondary text-3xl font-black uppercase tracking-[0.3em] mt-8 px-10 py-5 bg-secondary/10 rounded-[2.5rem] border border-secondary/20 shadow-2xl">
                        <span className="material-symbols-outlined text-4xl">trending_up</span>
                        +2.45% T-1
                    </div>
                </div>
            </header>

            {/* Performance Chart */}
            <section className="glass-panel p-12 md:p-16 2xl:p-24 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.7)] relative overflow-hidden backdrop-blur-3xl min-h-[600px] bg-white/[0.01]">
                <div className="mb-20 relative z-10">
                    <h3 className="text-4xl font-headline font-bold tracking-tight mb-4 uppercase tracking-[0.2em] leading-none">Price Action Matrix</h3>
                    <p className="text-base text-slate-500 font-black tracking-[0.3em] flex items-center gap-4 uppercase opacity-60"> Continuous surveillance of equity momentum <span className="inline-block w-3 h-3 rounded-full bg-secondary animate-pulse"></span> </p>
                </div>
                
                <div className="w-full h-[500px] 2xl:h-[600px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={navHistory}>
                            <defs>
                                <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#e9c349" stopOpacity={0.6}/>
                                    <stop offset="95%" stopColor="#e9c349" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                            <XAxis dataKey="date" hide />
                            <YAxis domain={['auto', 'auto']} hide />
                            <Tooltip contentStyle={{ backgroundColor: '#1b2025', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '24px', backdropFilter: 'blur(16px)', padding: '24px' }} itemStyle={{ fontSize: '18px', fontWeight: 'black', color: '#e9c349' }} />
                            <Area type="monotone" dataKey="nav" stroke="#e9c349" strokeWidth={6} fillOpacity={1} fill="url(#colorStock)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </section>

             {/* Footer */}
             <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Equity Consumption Protocol Active • Decentralized Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

export default StockDetail;
