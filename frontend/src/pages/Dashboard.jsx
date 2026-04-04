import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchDashboardData } from '../store/slices/dashboardSlice';
import { motion, AnimatePresence } from 'framer-motion';

const Dashboard = () => {
    const dispatch = useDispatch();
    const { data, loading, error } = useSelector((state) => state.dashboard);

    useEffect(() => {
        dispatch(fetchDashboardData());
    }, [dispatch]);

    if (loading) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Synchronizing Wealth Pulse...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-20">
                <span className="material-symbols-outlined text-error text-9xl mb-8">security_update_warning</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-4 uppercase tracking-widest">Protocol Breach</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12">{error}</p>
                <button 
                    onClick={() => dispatch(fetchDashboardData())}
                    className="px-12 py-5 gold-gradient rounded-2xl text-on-primary font-black uppercase tracking-widest shadow-2xl"
                >
                    Re-initialize Core
                </button>
            </div>
        );
    }

    if (!data) return null;

    return (
        <main className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 min-h-screen w-full transition-all duration-500">
            {/* Market Pulse Banner */}
            <motion.section 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-16 xl:mb-24"
            >
                <div className="bg-surface-container-low rounded-3xl p-10 md:p-16 lg:p-20 xl:p-28 flex flex-col 2xl:flex-row 2xl:items-center justify-between relative overflow-hidden group shadow-2xl shadow-black/40 border border-white/5">
                    <div className="absolute top-0 right-0 w-1/2 h-full gold-gradient opacity-[0.03] skew-x-12 translate-x-32 group-hover:translate-x-24 transition-transform duration-1000"></div>
                    <div className="relative z-10">
                        <div className="flex items-center gap-4 mb-8">
                            <span className="inline-block w-4 h-4 rounded-full bg-secondary animate-pulse shadow-[0_0_15px_rgba(102,221,139,0.5)]"></span>
                            <span className="font-label text-sm tracking-[0.4em] uppercase text-secondary font-black">Live Market Surveillance Active</span>
                        </div>
                        <h2 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl 2xl:text-9xl font-headline font-bold text-white mb-8 tracking-tighter leading-none">Market Momentum: <span className="text-secondary">{data.momentum}</span></h2>
                        <p className="text-on-surface-variant text-lg sm:text-xl md:text-2xl 2xl:text-3xl max-w-5xl leading-tight opacity-70 mb-2 lowercase">
                            Protocol Status: <span className="text-secondary font-black">+{data.growthPercent}% Alpha Growth</span>, driven by {data.growthDriver}.
                        </p>
                    </div>
                    <div className="mt-12 2xl:mt-0 relative z-10">
                        <button className="px-10 py-5 rounded-2xl border border-white/10 hover:bg-white/10 transition-all flex items-center justify-center gap-4 group bg-white/5 backdrop-blur-md shadow-2xl shadow-black/40">
                            <span className="text-base font-black tracking-[0.3em] uppercase">Deep Intelligence</span>
                            <span className="material-symbols-outlined text-2xl group-hover:translate-x-3 transition-transform">arrow_forward</span>
                        </button>
                    </div>
                </div>
            </motion.section>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-3 gap-12 xl:gap-16 mb-16 xl:mb-24">
                <div className="bg-surface-container p-12 rounded-[2.5rem] border-l-[8px] border-primary shadow-2xl hover:translate-y-[-8px] transition-all duration-500 group">
                    <div className="font-label text-xs tracking-[0.3em] uppercase text-slate-500 mb-8 group-hover:text-primary transition-colors font-black">Consolidated Wealth Assets</div>
                    <div className="text-6xl sm:text-7xl xl:text-8xl 2xl:text-9xl font-headline font-extrabold text-white mb-6 tracking-tighter leading-none">${data.portfolioValue.toLocaleString()}</div>
                    <div className="flex items-center gap-3 text-secondary text-lg font-black uppercase tracking-widest">
                        <span className="material-symbols-outlined text-2xl">trending_up</span>
                        <span>+{data.growthPercent}% Global Alpha</span>
                    </div>
                </div>
                <div className="bg-surface-container p-12 rounded-[2.5rem] border-l-2 border-white/5 shadow-2xl hover:translate-y-[-8px] transition-all duration-500">
                    <div className="font-label text-xs tracking-[0.3em] uppercase text-slate-500 mb-8 font-black">Absolute Gain (YTD)</div>
                    <div className="text-6xl sm:text-7xl xl:text-8xl 2xl:text-9xl font-headline font-extrabold text-primary mb-6 tracking-tighter leading-none">+${data.absoluteGain.toLocaleString()}</div>
                    <div className="flex items-center gap-3 text-secondary text-lg font-black uppercase tracking-widest">
                        <span className="material-symbols-outlined text-2xl">insights</span>
                        <span>Institutional Grade</span>
                    </div>
                </div>
                <div className="bg-surface-container p-12 rounded-[2.5rem] border-l-2 border-white/5 shadow-2xl hover:translate-y-[-8px] transition-all duration-500">
                    <div className="font-label text-xs tracking-[0.3em] uppercase text-slate-500 mb-8 font-black">Liquidity Reserve</div>
                    <div className="text-6xl sm:text-7xl xl:text-8xl 2xl:text-9xl font-headline font-extrabold text-white mb-6 tracking-tighter leading-none">${data.liquidityReserve.toLocaleString()}</div>
                    <div className="flex items-center gap-3 text-slate-500 text-sm font-black uppercase tracking-[0.2em] opacity-60">
                        <span className="material-symbols-outlined text-2xl text-primary/40">account_balance</span>
                        <span>Tier-1 Global Distribution</span>
                    </div>
                </div>
            </div>

            {/* Performance Chart and Allocation */}
            <div className="grid grid-cols-1 3xl:grid-cols-3 gap-12 xl:gap-16 mb-16 xl:mb-24">
                <div className="3xl:col-span-2 bg-surface-container-low p-12 md:p-16 rounded-[3rem] relative overflow-hidden border border-white/5 shadow-2xl">
                    <h3 className="text-4xl font-headline font-bold mb-16 tracking-tight uppercase tracking-widest">Growth Trajectory Analyzer</h3>
                    <div className="h-[500px] flex items-end gap-3 mb-10">
                        {data.performanceHistory.map((pt, i) => {
                            const maxVal = Math.max(...data.performanceHistory.map(p => p.value));
                            const height = (pt.value / maxVal) * 100;
                            return (
                                <div key={i} className="flex-1 bg-gradient-to-t from-primary/5 to-primary/20 hover:to-primary/70 rounded-t-2xl transition-all duration-700 group relative cursor-crosshair" style={{ height: `${height}%` }}>
                                    <div className="absolute -top-12 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/80 px-3 py-1 rounded text-[10px] text-white whitespace-nowrap z-20">
                                        {pt.month}: {pt.value}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="bg-surface-container-low p-12 md:p-16 rounded-[3rem] flex flex-col border border-white/5 shadow-2xl">
                    <h3 className="text-3xl font-headline font-bold mb-12 tracking-tight uppercase tracking-widest">Asset Dispersion</h3>
                    <div className="space-y-6">
                        {data.assetAllocation.map((item, i) => (
                            <div key={i} className="flex justify-between items-center p-5 hover:bg-white/5 rounded-2xl transition-all duration-300 group">
                                <div className="flex items-center gap-5">
                                    <span className={`w-4 h-4 rounded-full ${item.color} shadow-2xl`}></span>
                                    <span className="text-slate-200 text-lg font-bold tracking-tight uppercase tracking-[0.1em]">{item.name}</span>
                                </div>
                                <span className="font-black text-2xl text-white group-hover:text-primary transition-colors">{item.value}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Holdings Table */}
            <div className="bg-surface-container p-12 md:p-16 rounded-[3.5rem] border border-white/5 shadow-2xl mb-16 xl:mb-24">
                <h3 className="text-4xl font-headline font-bold tracking-tight uppercase tracking-widest mb-16">Institutional Holding Ledger</h3>
                <div className="space-y-8">
                    {data.holdings.map((asset, i) => (
                        <div key={i} className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-5 items-center p-10 hover:bg-white/5 rounded-[2.5rem] transition-all duration-500 border border-transparent hover:border-white/10 group">
                            <div className="flex items-center gap-10 col-span-2">
                                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center font-black text-lg text-primary border border-white/5 shadow-2xl">{asset.ticker}</div>
                                <div>
                                    <div className="font-extrabold text-3xl text-white mb-2 tracking-tighter truncate max-w-md">{asset.name}</div>
                                    <div className="text-xs text-slate-500 font-black tracking-[0.3em] uppercase opacity-60 truncate">{asset.allocation}</div>
                                </div>
                            </div>
                            <div className="hidden xl:block text-center">
                                <div className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] mb-2">AUM Weight</div>
                                <div className="text-2xl font-black text-white tracking-tight">{asset.cap}</div>
                            </div>
                            <div className="text-right">
                                <div className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] mb-2">Valuation</div>
                                <div className="text-3xl font-extrabold text-white tracking-tighter">{asset.value}</div>
                            </div>
                            <div className="text-right">
                                <div className={`text-2xl font-black mb-3 ${asset.trend === 'up' ? 'text-secondary' : 'text-error'}`}>{asset.return}</div>
                                <div className="h-2 w-32 bg-surface-container-highest rounded-full ml-auto overflow-hidden shadow-inner border border-white/5">
                                    <div className={`h-full shadow-[0_0_15px_rgba(102,221,139,0.6)] transition-all duration-1000 ${asset.trend === 'up' ? 'bg-secondary' : 'bg-error'}`} style={{ width: '75%' }}></div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <footer className="mt-24 py-16 border-t border-white/5 flex flex-col xl:flex-row justify-between items-center text-slate-500 text-xs tracking-[0.4em] uppercase font-black gap-12 opacity-60 italic">
                <div className="text-center xl:text-left leading-relaxed">
                    © 2024 Nivesh Elite Wealth Intelligence. <br/>
                    Autonomous Distributed Ledger Protocol Active.
                </div>
            </footer>
        </main>
    );
};

export default Dashboard;
