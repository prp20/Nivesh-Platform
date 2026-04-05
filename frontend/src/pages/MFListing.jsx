import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchFunds, setCategoryFilter, setCurrentPage, setViewMode } from '../store/slices/fundsSlice';
import { motion, AnimatePresence } from 'framer-motion';

const MFListing = () => {
    const dispatch = useDispatch();
    const { items, loading, error, currentPage, pageSize, categoryFilter, viewMode } = useSelector((state) => state.funds);

    useEffect(() => {
        dispatch(fetchFunds({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize, 
            category: categoryFilter === 'All' ? null : categoryFilter 
        }));
    }, [dispatch, currentPage, pageSize, categoryFilter]);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Wealth Archives...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 3xl:flex-row 3xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Institutional Wealth surveillance</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Mutual Fund <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Vault</span>
                    </h1>
                </div>

                <div className="flex flex-wrap gap-8 items-center bg-surface-container-high/40 p-6 rounded-[2.5rem] border border-white/5 backdrop-blur-2xl">
                    {/* Category Filter */}
                    <div className="flex bg-black/40 p-2 rounded-2xl border border-white/5">
                        {['All', 'Equity', 'Debt', 'Hybrid'].map((cat) => (
                            <button 
                                key={cat} 
                                onClick={() => dispatch(setCategoryFilter(cat))}
                                className={`px-8 py-3 text-[10px] font-black tracking-[0.3em] uppercase rounded-xl transition-all ${categoryFilter === cat ? 'bg-primary text-on-primary shadow-2xl shadow-primary/40' : 'text-slate-500 hover:text-white'}`}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>

                    {/* View Toggle */}
                    <div className="h-12 w-px bg-white/10 mx-4 hidden 3xl:block"></div>
                    
                    <div className="flex bg-black/40 p-2 rounded-2xl border border-white/5">
                        <button 
                            onClick={() => dispatch(setViewMode('card'))}
                            className={`p-3 rounded-xl transition-all flex items-center gap-3 ${viewMode === 'card' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Grid Perspective"
                        >
                            <span className="material-symbols-outlined text-xl">grid_view</span>
                        </button>
                        <button 
                            onClick={() => dispatch(setViewMode('table'))}
                            className={`p-3 rounded-xl transition-all flex items-center gap-3 ${viewMode === 'table' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Analytical Ledger"
                        >
                            <span className="material-symbols-outlined text-xl">table_rows</span>
                        </button>
                    </div>
                </div>
            </header>

            {error && (
                <div className="p-10 bg-error/10 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-widest text-center shadow-lg">
                    {error}
                </div>
            )}

            {/* Conditional Rendering: Grid vs Table */}
            <AnimatePresence mode="wait">
                {viewMode === 'card' ? (
                    <motion.div 
                        key="grid"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 1.05 }}
                        transition={{ duration: 0.5, ease: "circOut" }}
                        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5 gap-12 xl:gap-16"
                    >
                        {items.map((fund, idx) => (
                            <motion.div 
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: idx * 0.05 }}
                                key={fund.scheme_code} 
                                className="bg-surface-container p-12 rounded-[3.5rem] border border-white/5 hover:border-primary/40 transition-all duration-700 flex flex-col group relative overflow-hidden shadow-2xl hover:translate-y-[-16px] cursor-crosshair"
                            >
                                <div className="absolute top-0 right-0 p-12 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100">
                                    <span className="material-symbols-outlined text-[150px] text-primary">account_balance</span>
                                </div>
                                
                                <div className="mb-10">
                                    <span className={`text-[11px] font-black tracking-[0.3em] uppercase px-5 py-2 rounded-xl bg-white/5 border border-white/5 transition-all group-hover:border-primary/30 text-secondary`}>
                                        {fund.scheme_category}
                                    </span>
                                </div>

                                <Link to={`/mf/${fund.scheme_code}`} className="text-3xl sm:text-4xl font-headline font-bold text-white mb-4 group-hover:text-primary transition-colors tracking-tight leading-tight uppercase line-clamp-2 min-h-[5rem]">
                                    {fund.scheme_name}
                                </Link>
                                <p className="text-sm text-slate-500 font-black tracking-[0.4em] uppercase mb-12 opacity-60">ID: {fund.scheme_code} • {fund.amc_name}</p>

                                <div className="grid grid-cols-2 gap-10 mb-12 py-8 border-y border-white/5 bg-white/[0.01] backdrop-blur-sm">
                                    <div>
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">AUM Valuation</p>
                                        <p className="font-extrabold text-3xl text-white tracking-tighter truncate">{fund.displayMetrics.aum}</p>
                                    </div>
                                    <div>
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Current Nav</p>
                                        <p className="font-extrabold text-3xl text-white tracking-tighter">₹{fund.displayMetrics.nav}</p>
                                    </div>
                                </div>

                                <div className="flex justify-between items-end mt-auto">
                                    <div>
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Session Alpha</p>
                                        <p className={`text-4xl font-black ${fund.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>
                                            {fund.displayMetrics.change}
                                        </p>
                                    </div>
                                </div>
                                <div className="absolute inset-x-0 bottom-0 h-1 gold-gradient opacity-0 group-hover:opacity-100 transition-opacity"></div>
                            </motion.div>
                        ))}
                    </motion.div>
                ) : (
                    <motion.div 
                        key="table"
                        initial={{ opacity: 0, x: -50 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 50 }}
                        transition={{ duration: 0.5, ease: "circOut" }}
                        className="glass-panel rounded-[4rem] overflow-hidden shadow-[0_64px_128px_rgba(0,0,0,0.6)] border border-white/5 bg-white/[0.01] backdrop-blur-3xl mb-12"
                    >
                         <div className="w-full overflow-x-auto border-collapse">
                            <table className="w-full text-left min-w-[1400px]">
                                <thead>
                                    <tr className="border-b border-white/5 bg-surface-container-low/50">
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Benchmark Identity</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Category</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">AUM Valuation</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Protocol Level (NAV)</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha Delta</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Security Rating</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items.map((fund, i) => (
                                        <tr key={fund.scheme_code} className="border-b border-white/5 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair">
                                            <td className="px-16 py-16">
                                                <Link to={`/mf/${fund.scheme_code}`} className="flex items-center gap-10">
                                                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center font-black text-xl text-primary border border-white/5 shadow-2xl group-hover:scale-110 transition-transform tracking-widest uppercase">{fund.scheme_name.substring(0, 3)}</div>
                                                    <div>
                                                        <div className="font-extrabold text-2xl text-white mb-2 tracking-tighter truncate max-w-xl group-hover:text-primary transition-colors uppercase">{fund.scheme_name}</div>
                                                        <div className="text-xs text-slate-500 font-black tracking-[0.4em] uppercase opacity-60 italic whitespace-nowrap">{fund.scheme_code} • {fund.amc_name}</div>
                                                    </div>
                                                </Link>
                                            </td>
                                            <td className="px-16 py-16 text-center">
                                                <span className="px-5 py-2 rounded-xl text-[10px] font-black tracking-widest bg-white/5 border border-white/5 text-secondary uppercase">
                                                    {fund.scheme_subcategory || fund.scheme_category}
                                                </span>
                                            </td>
                                            <td className="px-16 py-16 text-center">
                                                <div className="text-2xl font-black text-white tracking-widest uppercase">{fund.displayMetrics.aum}</div>
                                            </td>
                                            <td className="px-16 py-16 text-center">
                                                <div className="text-3xl font-extrabold text-white tracking-tighter">₹{fund.displayMetrics.nav}</div>
                                            </td>
                                            <td className="px-16 py-16 text-right">
                                                <div className={`text-4xl font-black ${fund.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>{fund.displayMetrics.change}</div>
                                            </td>
                                            <td className="px-16 py-16 text-center">
                                                <div className="flex justify-center gap-2">
                                                    {[...Array(5)].map((_, starIdx) => (
                                                        <span key={starIdx} className={`material-symbols-outlined text-lg ${starIdx < fund.displayMetrics.rating ? 'text-primary' : 'text-white/10'}`}>
                                                            star
                                                        </span>
                                                    ))}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Pagination */}
            <div className="flex justify-center items-center gap-10 mt-24 mb-20">
                <button 
                    disabled={currentPage === 1}
                    onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                    className="px-12 py-5 rounded-3xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
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

export default MFListing;
