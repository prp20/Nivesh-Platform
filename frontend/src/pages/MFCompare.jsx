import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import fundService from '../api/services/fundService';
import { clearCompare } from '../store/slices/compareSlice';
import { motion, AnimatePresence } from 'framer-motion';

const MFCompare = () => {
    const { compareList } = useSelector((state) => state.compare);
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const [comparisonData, setComparisonData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchComparison = async () => {
            if (compareList.length < 2) return;
            setLoading(true);
            try {
                const codes = compareList.map(f => f.scheme_code);
                const data = await fundService.compareFunds(codes);
                setComparisonData(data);
            } catch (err) {
                setError(err.message || 'Comparison Matrix Failed to initialize.');
            } finally {
                setLoading(false);
            }
        };

        fetchComparison();
    }, [compareList]);

    if (compareList.length < 2) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12] p-20 text-center">
                <span className="material-symbols-outlined text-primary text-[120px] mb-8 opacity-20">compare_arrows</span>
                <h2 className="text-4xl font-headline font-bold text-white mb-6 uppercase tracking-widest">Insufficient Assets</h2>
                <p className="text-slate-500 text-xl font-bold tracking-tight mb-12 max-w-2xl uppercase leading-relaxed opacity-60">
                    A minimum of two identified asset artifacts are required to initialize the differential comparison matrix.
                </p>
                <Link to="/mf" className="px-12 py-5 gold-gradient rounded-2xl text-on-primary font-black uppercase tracking-widest shadow-2xl transition-all active:scale-95">
                    Return to Resource Vault
                </Link>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Aligning Differential Vectors...</p>
            </div>
        );
    }

    const funds = comparisonData?.aligned_navs ? compareList : [];

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 3xl:flex-row 3xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Asymmetric Intelligence Matrix</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Vault <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Fingerprint</span> <span className="text-slate-500 opacity-20 block 3xl:inline">Comparison</span>
                    </h1>
                </div>

                <div className="flex gap-8">
                    <button 
                        onClick={() => dispatch(clearCompare())}
                        className="px-10 py-5 rounded-[2rem] border border-white/10 text-white font-black text-xs uppercase tracking-[0.3em] hover:bg-error hover:border-error transition-all flex items-center gap-4 shadow-xl group"
                    >
                        <span className="material-symbols-outlined text-2xl group-hover:rotate-180 transition-transform">delete_sweep</span>
                        Purge Matrix
                    </button>
                </div>
            </header>

            {/* Comparison Grid - Ultra Breadth */}
            <div className="glass-panel rounded-[4rem] overflow-hidden shadow-[0_64px_128px_rgba(0,0,0,0.6)] border border-white/5 bg-white/[0.01] backdrop-blur-3xl">
                <div className="w-full overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[1200px]">
                        <thead>
                            <tr className="border-b border-white/5 bg-surface-container-low/50">
                                <th className="px-16 py-10 text-[11px] uppercase tracking-[0.4em] text-slate-500 font-black">Comparison Attribute</th>
                                {compareList.map((f, i) => (
                                    <th key={i} className="px-16 py-10 text-[11px] uppercase tracking-[0.4em] text-primary font-black text-center border-l border-white/5">
                                        Vault Identity: {f.scheme_name.substring(0, 15)}...
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {[
                                { attr: 'Strategy Category', key: 'scheme_category', label: 'Asset Quadrant' },
                                { attr: 'Absolute Return (1Y)', key: 'absolute_return_1y', label: 'Benchmark Alpha', percent: true },
                                { attr: 'Risk Efficiency', key: 'sharpe_ratio', label: 'Sharpe Ratio' },
                                { attr: 'Exit Penalty', key: 'exit_load', label: 'Liquidity Lock', default: '1.0% < 1Y' },
                                { attr: 'Asset Management', key: 'amc_name', label: 'Sovereign Institutional' }
                            ].map((row, idx) => (
                                <tr key={idx} className="border-b border-white/5 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair">
                                    <td className="px-16 py-12">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[10px] text-slate-500 font-black uppercase tracking-[0.3em] opacity-40">{row.label}</span>
                                            <span className="text-2xl font-black text-white tracking-tight uppercase tracking-widest group-hover:text-primary transition-colors">{row.attr}</span>
                                        </div>
                                    </td>
                                    {compareList.map((f, i) => {
                                        const val = f[row.key] || row.default || 'N/A';
                                        return (
                                            <td key={i} className="px-16 py-12 text-center border-l border-white/5">
                                                <span className={`text-3xl font-black ${val.toString().startsWith('+') || parseFloat(val) > 10 ? 'text-secondary' : 'text-white'} tracking-tighter`}>
                                                    {row.percent && val !== 'N/A' ? `${val}%` : val}
                                                </span>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Footer */}
            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                 Matrix Identification: COMP-ELITE-X9 • Differential Analytics Protocol Active • Aligned NAV points: {comparisonData?.aligned_navs?.length || 0}
            </footer>
        </div>
    );
};

export default MFCompare;
