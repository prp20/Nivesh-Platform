import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchFunds, setCategoryFilter, setCurrentPage } from '../store/slices/fundsSlice';
import { motion } from 'framer-motion';

const MFListing = () => {
    const dispatch = useDispatch();
    const { items, loading, error, currentPage, pageSize, categoryFilter } = useSelector((state) => state.funds);

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
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Wealth Archives...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Market surveillance Protocol</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl font-headline font-bold tracking-tighter leading-none group uppercase">
                        Mutual Fund <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Vault</span>
                    </h1>
                </div>

                <div className="flex flex-wrap gap-8 items-center">
                    <div className="flex bg-surface-container-high/40 p-2 rounded-2xl border border-white/10 backdrop-blur-xl">
                        {['All', 'Equity', 'Debt', 'Hybrid'].map((cat) => (
                            <button 
                                key={cat} 
                                onClick={() => dispatch(setCategoryFilter(cat))}
                                className={`px-10 py-3 text-xs font-black tracking-[0.3em] uppercase rounded-xl transition-all ${categoryFilter === cat ? 'bg-primary text-on-primary shadow-2xl shadow-primary/40' : 'text-slate-500 hover:text-white'}`}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {error && (
                <div className="p-10 bg-error/10 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-widest text-center">
                    {error}
                </div>
            )}

            {/* Fund Grid - Ultra Scaling */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5 gap-12 xl:gap-16">
                {items.map((fund, idx) => (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        key={fund.scheme_code} 
                        className="bg-surface-container p-12 rounded-[3rem] border border-white/5 hover:border-primary/40 transition-all duration-700 flex flex-col group relative overflow-hidden shadow-2xl hover:translate-y-[-16px] cursor-crosshair"
                    >
                        <div className="absolute top-0 right-0 p-12 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100">
                            <span className="material-symbols-outlined text-[150px] text-primary">account_balance</span>
                        </div>
                        
                        <div className="mb-10">
                            <span className={`text-[11px] font-black tracking-[0.3em] uppercase px-5 py-2 rounded-xl bg-white/5 border border-white/5 transition-all group-hover:border-primary/30 text-secondary`}>
                                {fund.scheme_category}
                            </span>
                        </div>

                        <Link to={`/mf/${fund.scheme_code}`} className="text-3xl sm:text-4xl font-headline font-bold text-white mb-4 group-hover:text-primary transition-colors tracking-tight leading-tight truncate">
                            {fund.scheme_name}
                        </Link>
                        <p className="text-sm text-slate-500 font-black tracking-[0.4em] uppercase mb-12 opacity-60">ID: {fund.scheme_code} / AMC: {fund.amc_name}</p>

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
                                <p className={`text-4xl font-black ${fund.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'}`}>
                                    {fund.displayMetrics.change}
                                </p>
                            </div>
                        </div>
                        <div className="absolute inset-x-0 bottom-0 h-1 gold-gradient opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    </motion.div>
                ))}
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center gap-10 mt-24 mb-20">
                <button 
                    disabled={currentPage === 1}
                    onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                    className="px-10 py-5 rounded-2xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                >
                    PREV_BLOCK
                </button>
                <span className="text-primary font-black text-xl tracking-widest font-mono">0{currentPage}</span>
                <button 
                    onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                    className="px-10 py-5 rounded-2xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 transition-all font-mono"
                >
                    NEXT_BLOCK
                </button>
            </div>
        </div>
    );
};

export default MFListing;
