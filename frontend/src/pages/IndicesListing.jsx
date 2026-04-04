import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchIndices, setCurrentPage } from '../store/slices/indicesSlice';
import { motion } from 'framer-motion';

const IndicesListing = () => {
    const dispatch = useDispatch();
    const { items, loading, error, currentPage, pageSize } = useSelector((state) => state.indices);

    useEffect(() => {
        dispatch(fetchIndices({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize 
        }));
    }, [dispatch, currentPage, pageSize]);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Synchronizing Global Benchmarks...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 3xl:flex-row 3xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Systemic Alpha Benchmarking</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Market <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Indices</span>
                    </h1>
                </div>

                <div className="flex gap-8 bg-surface-container-high/40 p-6 rounded-3xl border border-white/5 backdrop-blur-2xl">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500 mb-2">Protocol Status</span>
                        <span className="text-secondary font-black tracking-widest text-lg uppercase flex items-center gap-3">
                            <span className="w-3 h-3 rounded-full bg-secondary animate-pulse shadow-[0_0_10px_rgba(102,221,139,0.5)]"></span>
                            Nominal
                        </span>
                    </div>
                </div>
            </header>

            {error && (
                <div className="p-10 bg-error/10 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-widest text-center shadow-lg">
                    {error}
                </div>
            )}

            {/* Indices List - Ultra Breadth Table */}
            <div className="glass-panel rounded-[4rem] overflow-hidden shadow-[0_64px_128px_rgba(0,0,0,0.6)] border border-white/5 bg-white/[0.01] backdrop-blur-3xl mb-24">
                <div className="w-full overflow-x-auto border-collapse">
                    <table className="w-full text-left min-w-[1400px]">
                        <thead>
                            <tr className="border-b border-white/5 bg-surface-container-low/50">
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Benchmark Identity</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Ticker</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Asset Class</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Level Identity</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha Delta</th>
                                <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Protocol</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((idx, i) => (
                                <tr key={i} className="border-b border-white/5 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair">
                                    <td className="px-16 py-16">
                                        <Link to={`/indices/${idx.benchmark_code}`} className="flex items-center gap-10">
                                            <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center font-black text-2xl text-primary border border-white/5 shadow-2xl group-hover:scale-110 transition-transform tracking-widest">IDX</div>
                                            <div>
                                                <div className="font-extrabold text-4xl text-white mb-3 tracking-tighter truncate max-w-xl group-hover:text-primary transition-colors uppercase">{idx.benchmark_name}</div>
                                                <div className="text-xs text-slate-500 font-black tracking-[0.4em] uppercase opacity-60 italic">{idx.benchmark_type}</div>
                                            </div>
                                        </Link>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <div className="text-2xl font-black text-slate-400 tracking-widest uppercase group-hover:text-white transition-colors">{idx.ticker}</div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <div className="text-sm font-black text-white tracking-[0.3em] uppercase opacity-60">EQUITY / GLOBAL</div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <div className="text-4xl font-extrabold text-white tracking-tighter">{idx.displayMetrics.nav}</div>
                                    </td>
                                    <td className="px-16 py-16 text-right">
                                        <div className={`text-4xl font-black ${idx.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>{idx.displayMetrics.change}</div>
                                    </td>
                                    <td className="px-16 py-16 text-center">
                                        <span className={`px-5 py-2 rounded-xl text-[10px] font-black tracking-widest ${idx.is_active ? 'bg-secondary/10 text-secondary border border-secondary/20' : 'bg-slate-800 text-slate-400 border border-white/5'}`}>
                                            {idx.displayMetrics.status}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center gap-10 mt-10 mb-20">
                <button 
                    disabled={currentPage === 1}
                    onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                    className="px-12 py-5 rounded-3xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 transition-all font-mono"
                >
                    PREV_LEVEL
                </button>
                <div className="text-2xl font-black text-primary font-mono tracking-widest">L-{currentPage}</div>
                <button 
                    onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                    className="px-12 py-5 rounded-3xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 transition-all font-mono"
                >
                    NEXT_LEVEL
                </button>
            </div>

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Benchmark Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

export default IndicesListing;
