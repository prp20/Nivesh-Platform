import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchFunds } from '../store/slices/fundsSlice';
import { motion } from 'framer-motion';

const Portfolio = () => {
    const dispatch = useDispatch();
    const { items, loading } = useSelector((state) => state.funds);

    useEffect(() => {
        if (items.length === 0) {
            dispatch(fetchFunds({ skip: 0, limit: 10 }));
        }
    }, [dispatch, items.length]);

    // Simulate portfolio data from existing funds
    const portfolioHoldings = items.slice(0, 5).map(fund => ({
        ticker: fund.isin?.substring(0, 4) || 'ELTE',
        name: fund.scheme_name,
        allocation: fund.scheme_category,
        value: `₹${(Math.random() * 500000 + 100000).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
        return: fund.displayMetrics.change,
        trend: fund.displayMetrics.change.startsWith('+') ? 'up' : 'down'
    }));

    const totalPortfolioValue = portfolioHoldings.reduce((acc, curr) => {
        const val = parseFloat(curr.value.replace(/[₹,]/g, ''));
        return acc + val;
    }, 0);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Asset Ledger...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Sovereign Asset Ledger</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Master <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Portfolio</span>
                    </h1>
                </div>

                <div className="flex flex-col items-end gap-4 bg-surface-container-high/60 p-12 md:p-16 rounded-[4rem] border border-white/5 shadow-[0_64px_128px_rgba(0,0,0,0.6)] backdrop-blur-3xl min-w-[450px]">
                    <span className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] mb-2 opacity-60">Consolidated Net Worth</span>
                    <div className="text-7xl sm:text-8xl md:text-9xl font-headline font-black text-white tracking-tighter leading-none">₹{totalPortfolioValue.toLocaleString()}</div>
                    <div className="flex items-center gap-4 text-secondary text-3xl font-black uppercase tracking-[0.3em] mt-8 px-10 py-5 bg-secondary/10 rounded-[2.5rem] border border-secondary/20 shadow-2xl">
                        <span className="material-symbols-outlined text-4xl">trending_up</span>
                        +12.4% ALL-TIME
                    </div>
                </div>
            </header>

            {/* Portfolio Table - Ultra Breadth */}
            <div className="glass-panel rounded-[4rem] overflow-hidden shadow-[0_64px_128px_rgba(0,0,0,0.6)] border border-white/5 bg-white/[0.01] backdrop-blur-3xl mb-24">
                <div className="w-full overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[1400px]">
                        <thead>
                            <tr className="border-b border-white/5 bg-surface-container-low/50">
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Asset Identity</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Weight</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Liquidity Value</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha (1Y)</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Verification</th>
                            </tr>
                        </thead>
                        <tbody>
                            {portfolioHoldings.map((asset, i) => (
                                <tr key={i} className="border-b border-white/5 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair">
                                    <td className="px-16 py-16">
                                        <div className="flex items-center gap-10">
                                            <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center font-black text-2xl text-primary border border-white/5 shadow-2xl group-hover:scale-110 transition-transform">{asset.ticker}</div>
                                            <div>
                                                <div className="font-extrabold text-4xl text-white mb-3 tracking-tighter truncate max-w-xl group-hover:text-primary transition-colors">{asset.name}</div>
                                                <div className="text-xs text-slate-500 font-black tracking-[0.4em] uppercase opacity-60 italic">{asset.allocation}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <div className="text-3xl font-black text-white tracking-widest">{Math.floor(Math.random() * 20 + 5)}%</div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <div className="text-4xl font-extrabold text-white tracking-tighter shadow-primary/20">{asset.value}</div>
                                    </td>
                                    <td className="px-16 py-16 text-right">
                                        <div className={`text-4xl font-black ${asset.trend === 'up' ? 'text-secondary' : 'text-error'} tracking-tighter`}>{asset.return}</div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <span className="material-symbols-outlined text-[48px] text-secondary opacity-40 group-hover:opacity-100 transition-all duration-700 animate-pulse">verified</span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Performance Summary Footer */}
            <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-4 gap-12 xl:gap-16 mb-24">
                {[
                    { label: 'Unrealized Alpha', val: '₹12,45,000', trend: '+14%', icon: 'insights' },
                    { label: 'Realized Gains', val: '₹4,50,000', trend: '+5.2%', icon: 'payments' },
                    { label: 'Dividend Stream', val: '₹84,000', trend: 'Monthly', icon: 'currency_exchange' },
                    { label: 'System Health', val: '98.5%', trend: 'Tier-1', icon: 'shield_moon' },
                ].map((stat, i) => (
                    <div key={i} className="glass-panel p-16 rounded-[4rem] border border-white/5 shadow-2xl hover:translate-y-[-12px] transition-all duration-500 relative overflow-hidden group bg-white/[0.01]">
                         <span className="material-symbols-outlined absolute -right-10 -bottom-10 text-[180px] text-primary opacity-[0.02] group-hover:opacity-[0.06] transition-all duration-1000">{stat.icon}</span>
                        <p className="text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black mb-10 leading-none">{stat.label}</p>
                        <p className="text-5xl 2xl:text-6xl font-headline font-black text-white tracking-tighter mb-4 leading-none">{stat.val}</p>
                        <p className="text-sm text-secondary font-black uppercase tracking-[0.5em] opacity-80">{stat.trend}</p>
                    </div>
                ))}
            </div>

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Ledger Verification Hash: ELITE-P-4402X • Sovereign Protocol Active • Wealth Distribution Consensus Reached
            </footer>
        </div>
    );
};

export default Portfolio;
