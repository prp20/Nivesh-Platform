import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import { fetchFunds, setCategoryFilter, setCurrentPage, setViewMode } from '../store/slices/fundsSlice';
import { addToCompare, removeFromCompare, clearCompare } from '../store/slices/compareSlice';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

const MFListing = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { items, loading, error, currentPage, pageSize, categoryFilter, viewMode } = useSelector((state) => state.funds);
    const { compareList, selectedCategory, selectedSubcategory } = useSelector((state) => state.compare);

    useEffect(() => {
        dispatch(fetchFunds({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize, 
            category: categoryFilter === 'All' ? null : categoryFilter 
        }));
    }, [dispatch, currentPage, pageSize, categoryFilter]);

    const handleDetailNavigation = (e, schemeCode) => {
        if (compareList.length > 0) {
            e.preventDefault();
            toast.error('Clear comparisons to view mutual fund details', {
                icon: 'lock',
                duration: 4000,
            });
        }
    };

    const handleAddToCompare = (fund) => {
        if (compareList.length >= 4) {
            toast.error('Maximum phase capacity reached (4 assets)');
            return;
        }
        
        if (compareList.length > 0) {
            if (compareList[0].scheme_category !== fund.scheme_category || 
                compareList[0].scheme_subcategory !== fund.scheme_subcategory) {
                toast.error('Strategic Mismatch: Assets must share identical category & subcategory');
                return;
            }
        }

        dispatch(addToCompare(fund));
        toast.success(`${fund.scheme_name.substring(0, 20)}... locked into matrix`);
    };

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Wealth Archives...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500 relative pb-64">
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
                        {items.map((fund, idx) => {
                            const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);
                            const isLocked = compareList.length > 0 && 
                                (compareList[0].scheme_category !== fund.scheme_category || 
                                 compareList[0].scheme_subcategory !== fund.scheme_subcategory);

                            return (
                                <motion.div 
                                    initial={{ opacity: 0, y: 30 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: idx * 0.05 }}
                                    key={fund.scheme_code} 
                                    className={`bg-surface-container p-12 rounded-[3.5rem] border ${isComparing ? 'border-primary/60 shadow-[0_0_40px_rgba(233,195,73,0.1)]' : 'border-white/5'} hover:border-primary/40 transition-all duration-700 flex flex-col group relative overflow-hidden shadow-2xl hover:translate-y-[-16px] cursor-crosshair`}
                                >
                                    <div className="absolute top-0 right-0 p-12 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100">
                                        <span className="material-symbols-outlined text-[150px] text-primary">account_balance</span>
                                    </div>
                                    
                                    <div className="mb-10 flex justify-between items-start relative z-10">
                                        <span className={`text-[11px] font-black tracking-[0.3em] uppercase px-5 py-2 rounded-xl bg-white/5 border border-white/5 transition-all group-hover:border-primary/30 text-secondary`}>
                                            {fund.scheme_category}
                                        </span>
                                        
                                        <button 
                                            onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare(fund)}
                                            className={`p-3 rounded-full transition-all ${isComparing ? 'bg-primary text-on-primary ring-4 ring-primary/20' : 'bg-white/5 text-slate-500 hover:text-white hover:bg-white/10'} ${isLocked && !isComparing ? 'opacity-20 cursor-not-allowed' : ''}`}
                                            title={isComparing ? "Remove from Matrix" : "Inject into Matrix"}
                                        >
                                            <span className="material-symbols-outlined text-2xl">{isComparing ? 'check_circle' : 'add_circle'}</span>
                                        </button>
                                    </div>

                                    <Link 
                                        to={`/mf/${fund.scheme_code}`} 
                                        onClick={(e) => handleDetailNavigation(e, fund.scheme_code)}
                                        className="text-3xl sm:text-4xl font-headline font-bold text-white mb-4 group-hover:text-primary transition-colors tracking-tight leading-tight uppercase line-clamp-2 min-h-[5rem] relative z-10"
                                    >
                                        {fund.scheme_name}
                                    </Link>
                                    <p className="text-sm text-slate-500 font-black tracking-[0.4em] uppercase mb-12 opacity-60 relative z-10">ID: {fund.scheme_code} • {fund.amc_name}</p>

                                    <div className="grid grid-cols-2 gap-10 mb-12 py-8 border-y border-white/5 bg-white/[0.01] backdrop-blur-sm relative z-10">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">AUM Valuation</p>
                                            <p className="font-extrabold text-3xl text-white tracking-tighter truncate">{fund.displayMetrics.aum}</p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Current Nav</p>
                                            <p className="font-extrabold text-3xl text-white tracking-tighter">₹{fund.displayMetrics.nav}</p>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-end mt-auto relative z-10">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Session Alpha</p>
                                            <p className={`text-4xl font-black ${fund.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>
                                                {fund.displayMetrics.change}
                                            </p>
                                        </div>
                                    </div>
                                    <div className={`absolute inset-x-0 bottom-0 h-1 gold-gradient transition-opacity ${isComparing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
                                </motion.div>
                            );
                        })}
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
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black w-24 text-center">Matrix</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Benchmark Identity</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Category</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">AUM Valuation</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Protocol Level (NAV)</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha Delta</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Security Rating</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items.map((fund, i) => {
                                        const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);
                                        const isLocked = compareList.length > 0 && 
                                            (compareList[0].scheme_category !== fund.scheme_category || 
                                             compareList[0].scheme_subcategory !== fund.scheme_subcategory);

                                        return (
                                            <tr key={fund.scheme_code} className={`border-b border-white/5 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair ${isComparing ? 'bg-primary/[0.03]' : ''}`}>
                                                <td className="px-10 py-16 text-center">
                                                    <button 
                                                        onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare(fund)}
                                                        className={`p-3 rounded-full transition-all ${isComparing ? 'bg-primary text-on-primary shadow-[0_0_20px_rgba(233,195,73,0.3)]' : 'bg-white/5 text-slate-500 hover:text-white'} ${isLocked && !isComparing ? 'opacity-20 cursor-not-allowed' : ''}`}
                                                    >
                                                        <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                                    </button>
                                                </td>
                                                <td className="px-16 py-16">
                                                    <Link 
                                                        to={`/mf/${fund.scheme_code}`} 
                                                        onClick={(e) => handleDetailNavigation(e, fund.scheme_code)}
                                                        className="flex items-center gap-10"
                                                    >
                                                        <div className={`w-20 h-20 rounded-2xl flex items-center justify-center font-black text-xl border shadow-2xl group-hover:scale-110 transition-transform tracking-widest uppercase ${isComparing ? 'bg-primary text-on-primary border-primary' : 'bg-gradient-to-br from-white/10 to-white/5 text-primary border-white/5'}`}>{fund.scheme_name.substring(0, 3)}</div>
                                                        <div>
                                                            <div className={`font-extrabold text-2xl mb-2 tracking-tighter truncate max-w-xl transition-colors uppercase ${isComparing ? 'text-primary' : 'text-white group-hover:text-primary'}`}>{fund.scheme_name}</div>
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
                                        );
                                    })}
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

            {/* Floating Compare Dock */}
            <AnimatePresence>
                {compareList.length > 0 && (
                    <motion.div 
                        initial={{ y: 200, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 200, opacity: 0 }}
                        className="fixed bottom-12 left-1/2 -translate-x-1/2 z-[100] w-full max-w-6xl px-6"
                    >
                        <div className="glass-panel p-8 rounded-[3rem] border border-primary/20 shadow-[0_-32px_64px_rgba(0,0,0,0.5)] flex flex-col md:flex-row items-center justify-between gap-12 bg-[#0f1419]/95 backdrop-blur-3xl">
                            <div className="flex items-center gap-8 flex-1 overflow-x-auto w-full no-scrollbar px-4">
                                <div className="flex flex-col">
                                    <span className="text-[10px] font-black text-primary uppercase tracking-[0.4em] leading-none mb-1">Matrix Active</span>
                                    <span className="text-2xl font-black text-white tracking-widest uppercase">{compareList.length}/4</span>
                                </div>
                                <div className="h-10 w-px bg-white/10 mx-4 hidden md:block"></div>
                                <div className="flex gap-4">
                                    {compareList.map((fund) => (
                                        <motion.div 
                                            layout
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            key={fund.scheme_code}
                                            className="px-6 py-3 rounded-2xl bg-white/5 border border-white/5 flex items-center gap-4 group hover:border-primary/40 transition-all cursor-default whitespace-nowrap"
                                        >
                                            <span className="text-[11px] font-black text-white/80 uppercase tracking-widest">{fund.scheme_name.substring(0, 15)}...</span>
                                            <button 
                                                onClick={() => dispatch(removeFromCompare(fund.scheme_code))}
                                                className="material-symbols-outlined text-slate-500 hover:text-error text-lg transition-colors"
                                            >
                                                close
                                            </button>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>

                            <div className="flex items-center gap-8">
                                <button 
                                    onClick={() => dispatch(clearCompare())}
                                    className="px-8 py-4 rounded-xl text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 hover:text-error transition-all"
                                >
                                    Purge All
                                </button>
                                <button 
                                    onClick={() => navigate('/compare')}
                                    disabled={compareList.length < 2}
                                    className={`px-12 py-5 rounded-2xl gold-gradient text-on-primary font-black text-xs uppercase tracking-[0.3em] shadow-2xl transition-all active:scale-95 flex items-center gap-4 ${compareList.length < 2 ? 'opacity-30 grayscale cursor-not-allowed' : 'hover:brightness-110'}`}
                                >
                                    <span className="material-symbols-outlined">analytics</span>
                                    Initialize Comparison
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Benchmark Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

export default MFListing;
