import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchDashboardData } from '../store/slices/dashboardSlice';
import { motion } from 'framer-motion';

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

    // Build conic-gradient string — pure computation, no mutation
    const palette = ['#e9c349', '#66dd8b', '#475569'];
    const conicStops = data.assetAllocation.map((item, i, arr) => {
        const from = arr.slice(0, i).reduce((sum, a) => sum + a.value, 0);
        const to = from + item.value;
        return `${palette[i] || '#888'} ${from}% ${to}%`;
    }).join(', ');

    return (
        <main className="p-6 md:p-12 min-h-screen w-full transition-all duration-500">
            {/* Market Pulse Banner */}
            <motion.section
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-10"
            >
                <div className="bg-surface-container-low rounded-xl p-8 flex flex-col md:flex-row md:items-center justify-between relative overflow-hidden group shadow-2xl shadow-black/40 border border-white/5">
                    <div className="absolute top-0 right-0 w-1/2 h-full gold-gradient opacity-[0.03] skew-x-12 translate-x-32 group-hover:translate-x-24 transition-transform duration-1000"></div>
                    <div className="relative z-10">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="inline-block w-2 h-2 rounded-full bg-secondary animate-pulse shadow-[0_0_15px_rgba(102,221,139,0.5)]"></span>
                            <span className="font-label text-[10px] tracking-[0.2em] uppercase text-secondary font-semibold">Live Market Surveillance Active</span>
                        </div>
                        <h2 className="text-3xl font-headline font-bold text-white mb-2 tracking-tighter">Market Momentum: <span className="text-secondary">{data.momentum}</span></h2>
                        <p className="text-on-surface-variant max-w-xl">
                            Protocol Status: <span className="text-secondary font-bold">+{data.growthPercent}% Alpha Growth</span>, driven by {data.growthDriver}.
                        </p>
                    </div>
                    <div className="mt-6 md:mt-0 relative z-10">
                        <button className="px-6 py-3 rounded-md border border-outline-variant hover:bg-white/5 transition-all flex items-center gap-2 group bg-white/5 backdrop-blur-md">
                            <span className="text-sm font-bold tracking-widest uppercase">Deep Analytics</span>
                            <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
                        </button>
                    </div>
                </div>
            </motion.section>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10">
                <div className="bg-surface-container p-8 rounded-xl border-l-4 border-primary shadow-2xl hover:translate-y-[-4px] transition-all duration-500 group">
                    <div className="font-label text-[10px] tracking-[0.2em] uppercase text-slate-500 mb-4 group-hover:text-primary transition-colors font-black">Consolidated Wealth Assets</div>
                    <div className="text-4xl font-headline font-extrabold text-white mb-3 tracking-tighter">${data.portfolioValue.toLocaleString()}</div>
                    <div className="flex items-center gap-2 text-secondary text-sm font-bold">
                        <span className="material-symbols-outlined text-base">trending_up</span>
                        <span>+{data.growthPercent}% Global Alpha</span>
                    </div>
                </div>
                <div className="bg-surface-container p-8 rounded-xl shadow-2xl hover:translate-y-[-4px] transition-all duration-500">
                    <div className="font-label text-[10px] tracking-[0.2em] uppercase text-slate-500 mb-4 font-black">Absolute Gain (YTD)</div>
                    <div className="text-4xl font-headline font-extrabold text-primary mb-3 tracking-tighter">+${data.absoluteGain.toLocaleString()}</div>
                    <div className="flex items-center gap-2 text-secondary text-sm font-bold">
                        <span className="material-symbols-outlined text-base">insights</span>
                        <span>Institutional Grade</span>
                    </div>
                </div>
                <div className="bg-surface-container p-8 rounded-xl shadow-2xl hover:translate-y-[-4px] transition-all duration-500">
                    <div className="font-label text-[10px] tracking-[0.2em] uppercase text-slate-500 mb-4 font-black">Liquidity Reserve</div>
                    <div className="text-4xl font-headline font-extrabold text-white mb-3 tracking-tighter">${data.liquidityReserve.toLocaleString()}</div>
                    <div className="flex items-center gap-2 text-slate-500 text-sm font-black opacity-60">
                        <span className="material-symbols-outlined text-base text-primary/40">account_balance</span>
                        <span>Tier-1 Global Distribution</span>
                    </div>
                </div>
            </div>

            {/* Performance Chart and Allocation */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
                {/* Performance Chart */}
                <div className="lg:col-span-2 bg-surface-container-low p-8 rounded-xl relative overflow-hidden border border-white/5 shadow-2xl">
                    <div className="flex justify-between items-start mb-2">
                        <div>
                            <h3 className="text-xl font-headline font-bold tracking-tight">Portfolio Performance</h3>
                            <p className="text-slate-500 text-xs font-label mt-1">Historical performance across 24 months</p>
                        </div>
                        <div className="flex gap-2">
                            {['1Y', '3Y', 'MAX'].map((t) => (
                                <button key={t} className="px-3 py-1 rounded text-[10px] font-label font-black uppercase tracking-wider border border-white/10 text-slate-400 hover:text-primary hover:border-primary/30 transition-all">
                                    {t}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="h-64 flex items-end gap-1 mb-4 mt-6">
                        {data.performanceHistory.map((pt, i) => {
                            const maxVal = Math.max(...data.performanceHistory.map(p => p.value));
                            const height = (pt.value / maxVal) * 100;
                            return (
                                <div key={i} className="flex-1 bg-gradient-to-t from-primary/5 to-primary/20 hover:to-primary/70 rounded-t-sm transition-all duration-700 group relative cursor-crosshair" style={{ height: `${height}%` }}>
                                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/80 px-2 py-0.5 rounded text-[10px] font-bold text-primary whitespace-nowrap z-20">
                                        {pt.month}: {pt.value}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    <div className="flex justify-between text-[10px] font-label text-slate-500 tracking-[0.2em] uppercase">
                        <span>Jan 2023</span>
                        <span>May 2023</span>
                        <span>Sep 2023</span>
                        <span>Jan 2024</span>
                        <span>Present</span>
                    </div>
                </div>

                {/* Asset Allocation */}
                <div className="bg-surface-container-low p-8 rounded-xl flex flex-col border border-white/5 shadow-2xl">
                    <h3 className="text-xl font-headline font-bold mb-6 tracking-tight">Asset Allocation</h3>

                    {/* CSS Donut Chart */}
                    <div className="flex items-center justify-center mb-6">
                        <div className="relative" style={{ width: 160, height: 160 }}>
                            <div style={{
                                width: 160,
                                height: 160,
                                borderRadius: '50%',
                                background: `conic-gradient(${conicStops})`,
                            }} />
                            <div style={{
                                position: 'absolute',
                                top: 12,
                                left: 12,
                                width: 136,
                                height: 136,
                                borderRadius: '50%',
                                background: '#171c21',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <span className="text-white font-headline font-bold text-sm">Diverse</span>
                                <span className="text-slate-500 font-label text-[9px] uppercase tracking-wider">Tier 1 Strategy</span>
                            </div>
                        </div>
                    </div>

                    {/* Legend */}
                    <div className="space-y-3">
                        {data.assetAllocation.map((item, i) => (
                            <div key={i} className="flex justify-between items-center">
                                <div className="flex items-center gap-2">
                                    <span className={`w-2.5 h-2.5 rounded-full ${item.color}`} />
                                    <span className="text-slate-300 text-xs font-label font-bold">{item.name}</span>
                                </div>
                                <span className="font-black text-sm text-white">{item.value}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Holdings + Private Activity */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 mb-10">
                {/* Holdings Table */}
                <div className="xl:col-span-2 bg-surface-container p-6 rounded-xl border border-white/5 shadow-2xl">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-base font-headline font-bold tracking-tight uppercase">Elite Equity Holdings</h3>
                        <span className="text-xs font-bold text-primary uppercase tracking-widest cursor-pointer hover:underline">Rebalance</span>
                    </div>
                    <div className="space-y-2">
                        {data.holdings.map((asset, i) => (
                            <div key={i} className="grid grid-cols-4 items-center p-4 hover:bg-white/5 rounded-lg transition-all duration-300 border border-transparent hover:border-white/5 group">
                                <div className="flex items-center gap-4 col-span-2">
                                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center text-[10px] font-bold text-primary border border-white/5 shrink-0">{asset.ticker}</div>
                                    <div className="min-w-0">
                                        <div className="font-bold text-sm text-white mb-0.5 truncate">{asset.name}</div>
                                        <div className="text-[10px] text-slate-500 font-black tracking-[0.2em] uppercase truncate">{asset.allocation}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[10px] text-slate-500 font-black uppercase tracking-[0.2em] mb-1">Valuation</div>
                                    <div className="text-sm font-bold text-white">{asset.value}</div>
                                </div>
                                <div className="text-right">
                                    <div className={`text-sm font-bold mb-1 ${asset.trend === 'up' ? 'text-secondary' : 'text-error'}`}>{asset.return}</div>
                                    <div className="h-1 w-16 bg-surface-container-highest rounded-full ml-auto overflow-hidden">
                                        <div className={`h-full transition-all duration-1000 ${asset.trend === 'up' ? 'bg-secondary' : 'bg-error'}`} style={{ width: '75%' }}></div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Private Activity Timeline */}
                <div className="bg-surface-container p-6 rounded-xl border border-white/5 shadow-2xl flex flex-col">
                    <h3 className="text-base font-headline font-bold uppercase tracking-widest mb-6">Private Activity</h3>
                    <div className="flex-1 border-l border-primary/20 ml-2 pl-5 space-y-6">
                        {data.activities.map((act) => (
                            <div key={act.id} className="relative">
                                <span className="absolute -left-[1.55rem] top-0.5 w-3 h-3 rounded-full bg-primary shadow-[0_0_8px_rgba(233,195,73,0.4)]" />
                                <p className="text-slate-300 text-xs font-body leading-relaxed mb-1">{act.text}</p>
                                <span className="text-[10px] text-slate-500 font-label uppercase tracking-widest">{act.date}</span>
                            </div>
                        ))}
                    </div>
                    <button className="mt-6 w-full py-2.5 rounded-xl border border-white/10 text-[10px] font-label font-black uppercase tracking-widest text-slate-400 hover:text-primary hover:border-primary/30 transition-all">
                        Full Transaction History
                    </button>
                </div>
            </div>

            <footer className="mt-10 py-8 border-t border-white/5 flex flex-col md:flex-row justify-between items-center text-slate-500 text-[10px] tracking-[0.3em] uppercase font-black gap-4 opacity-60">
                <div>© 2024 Nivesh Elite Wealth Intelligence. Autonomous Distributed Ledger Protocol Active.</div>
                <div className="flex gap-8">
                    <span className="hover:text-primary transition-colors cursor-pointer">Legal Disclaimer</span>
                    <span className="hover:text-primary transition-colors cursor-pointer">Privacy Policy</span>
                    <span className="hover:text-primary transition-colors cursor-pointer">Security Standards</span>
                </div>
            </footer>
        </main>
    );
};

export default Dashboard;
