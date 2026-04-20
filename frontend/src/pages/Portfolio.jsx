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

    // Stabilize portfolio data using useMemo to prevent re-randomization on every render
    const { portfolioHoldings, totalPortfolioValue } = React.useMemo(() => {
        const holdings = items.slice(0, 5).map(fund => ({
            ticker: fund.isin?.substring(0, 4) || 'ELTE',
            name: fund.scheme_name,
            allocation: fund.scheme_category,
            valueNum: Math.random() * 500000 + 100000,
            weight: Math.floor(Math.random() * 20 + 5),
            return: fund.displayMetrics.change,
            trend: fund.displayMetrics.change.startsWith('+') ? 'up' : 'down'
        }));

        const total = holdings.reduce((acc, curr) => acc + curr.valueNum, 0);

        return {
            portfolioHoldings: holdings.map(h => ({
                ...h,
                value: `₹${h.valueNum.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            })),
            totalPortfolioValue: total
        };
    }, [items]);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Asset Ledger...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-10 lg:p-12 2xl:p-16 max-w-screen-2xl mx-auto w-full animate-fadeIn flex flex-col gap-12 transition-all duration-500">
            {/* Compact Header */}
            <header className="flex flex-col xl:flex-row items-start xl:items-center justify-between gap-8 pt-8">
                <div className="space-y-1">
                    <p className="font-label text-xs font-semibold uppercase tracking-[0.3em] text-primary">Sovereign Asset Surveillance</p>
                    <h2 className="font-headline text-5xl font-light tracking-tight text-white uppercase">
                        Master <span className="font-extrabold italic text-primary">Portfolio</span>
                    </h2>
                </div>
                
                <div className="flex gap-4">
                    <button className="px-6 py-3 rounded-xl border border-outline-variant/30 text-[10px] font-black uppercase tracking-widest hover:bg-white/5 transition-all flex items-center gap-3">
                        <span className="material-symbols-outlined text-lg">download</span>
                        Export Statement
                    </button>
                    <button className="px-6 py-3 rounded-xl bg-primary text-on-primary text-[10px] font-black uppercase tracking-widest hover:brightness-110 transition-all flex items-center gap-3 shadow-2xl">
                        <span className="material-symbols-outlined text-lg">sync</span>
                        Rebalance Matrix
                    </button>
                </div>
            </header>

            {/* High-Density Status Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {[
                    { label: 'Consolidated Net Worth', val: `₹${totalPortfolioValue.toLocaleString()}`, trend: '+12.4%', icon: 'account_balance_wallet' },
                    { label: 'Unrealized Alpha', val: '₹12,45,000', trend: '+14%', icon: 'insights' },
                    { label: 'Realized Gains', val: '₹4,50,000', trend: '+5.2%', icon: 'payments' },
                    { label: 'Dividend Stream', val: '₹84,000', trend: 'Monthly', icon: 'currency_exchange' },
                    { label: 'System Health', val: '98.5%', trend: 'Tier-1', icon: 'shield_moon' },
                ].map((stat, i) => (
                    <div key={i} className="bg-surface-container-low/40 backdrop-blur-xl p-6 rounded-2xl border border-outline-variant/10 shadow-xl group hover:border-primary/30 transition-all">
                        <div className="flex items-start justify-between mb-4">
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{stat.label}</span>
                            <span className="material-symbols-outlined text-primary/40 group-hover:text-primary transition-colors text-xl">{stat.icon}</span>
                        </div>
                        <div className="text-2xl font-black text-white tracking-widest mb-1">{stat.val}</div>
                        <div className="text-[10px] font-black text-secondary tracking-widest opacity-80 uppercase">{stat.trend}</div>
                    </div>
                ))}
            </div>

            {/* High-Density Ledger Table */}
            <div className="bg-surface-container-low/20 backdrop-blur-3xl rounded-3xl border border-outline-variant/10 overflow-hidden shadow-2xl mb-12">
                <div className="w-full overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-outline-variant/10 bg-white/[0.02]">
                                <th className="px-8 py-5 text-[10px] uppercase tracking-widest text-slate-500 font-black">Asset Identity</th>
                                <th className="px-8 py-5 text-[10px] uppercase tracking-widest text-slate-500 font-black text-center">Weight</th>
                                <th className="px-8 py-5 text-[10px] uppercase tracking-widest text-slate-500 font-black text-center">Liquidity Value</th>
                                <th className="px-8 py-5 text-[10px] uppercase tracking-widest text-slate-500 font-black text-right">Alpha (1Y)</th>
                                <th className="px-8 py-5 text-[10px] uppercase tracking-widest text-slate-500 font-black text-center">Protocol Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {portfolioHoldings.map((asset, i) => (
                                <tr key={i} className="border-b border-outline-variant/5 hover:bg-white/[0.03] transition-all group">
                                    <td className="px-8 py-6">
                                        <div className="flex items-center gap-6">
                                            <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center font-black text-sm text-primary group-hover:scale-110 transition-transform">
                                                {asset.ticker}
                                            </div>
                                            <div>
                                                <div className="font-bold text-lg text-white group-hover:text-primary transition-colors tracking-tight">
                                                    {asset.name}
                                                </div>
                                                <div className="text-[10px] text-slate-500 font-black tracking-widest uppercase opacity-60">
                                                    {asset.allocation}
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-center">
                                        <div className="text-lg font-black text-white tracking-widest">
                                            {asset.weight}%
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-center">
                                        <div className="text-xl font-bold text-white tracking-tight">
                                            {asset.value}
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-right">
                                        <div className={`text-xl font-black ${asset.trend === 'up' ? 'text-secondary' : 'text-error'} tracking-tighter`}>
                                            {asset.return}
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-center">
                                        <div className="flex items-center justify-center gap-2">
                                            <span className="material-symbols-outlined text-2xl text-secondary animate-pulse">verified</span>
                                            <span className="text-[9px] font-black text-secondary tracking-widest uppercase">Verified</span>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>


            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Ledger Verification Hash: ELITE-P-4402X • Sovereign Protocol Active • Wealth Distribution Consensus Reached
            </footer>
        </div>
    );
};

export default Portfolio;
