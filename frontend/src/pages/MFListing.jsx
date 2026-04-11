import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import { fetchFunds, setCategoryFilter, setCurrentPage, setViewMode } from '../store/slices/fundsSlice';
import { addToCompare, removeFromCompare } from '../store/slices/compareSlice';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import CompareDock from '../components/Compare/CompareDock';

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
            <header className="mb-12 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-8 pt-8">
                <div className="space-y-1">
                    <p className="font-label text-xs font-semibold uppercase tracking-[0.3em] text-primary">Sovereign Asset Surveillance</p>
                    <h2 className="font-headline text-5xl font-light tracking-tight text-white uppercase">
                        Fund <span className="font-extrabold italic text-primary">Vault</span>
                    </h2>
                </div>

                <div className="flex flex-wrap gap-4 items-center bg-surface-container-low p-2 rounded-2xl border border-outline-variant/10">
                    {/* Category Filter */}
                    <div className="flex bg-black/20 p-1 rounded-xl border border-outline-variant/10">
                        {['All', 'Equity', 'Debt', 'Hybrid'].map((cat) => (
                            <button 
                                key={cat} 
                                onClick={() => dispatch(setCategoryFilter(cat))}
                                className={`px-6 py-2 text-[9px] font-black tracking-widest uppercase rounded-lg transition-all ${categoryFilter === cat ? 'bg-primary text-on-primary shadow-lg shadow-primary/20' : 'text-slate-500 hover:text-white'}`}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>

                    {/* View Toggle */}
                    <div className="h-8 w-px bg-outline-variant/20 hidden xl:block"></div>
                    
                    <div className="flex bg-black/20 p-1 rounded-xl border border-outline-variant/10">
                        <button
                            onClick={() => dispatch(setViewMode('card'))}
                            className={`p-2 rounded-lg transition-all flex items-center gap-2 ${viewMode === 'card' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Grid Perspective"
                        >
                            <span className="material-symbols-outlined text-lg">grid_view</span>
                        </button>
                        <button
                            onClick={() => dispatch(setViewMode('table'))}
                            className={`p-2 rounded-lg transition-all flex items-center gap-2 ${viewMode === 'table' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Analytical Ledger"
                        >
                            <span className="material-symbols-outlined text-lg">table_rows</span>
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
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ delay: idx * 0.03 }}
                                    key={fund.scheme_code} 
                                    className={`bg-surface-container-low p-6 rounded-2xl border ${isComparing ? 'border-primary/60 shadow-[0_0_40px_rgba(233,195,73,0.1)]' : 'border-outline-variant/10'} hover:border-primary/40 transition-all duration-500 flex flex-col group relative overflow-hidden shadow-xl hover:translate-y-[-8px] cursor-crosshair`}
                                >
                                    <div className="mb-6 flex justify-between items-start relative z-10">
                                        <span className={`text-[9px] font-black tracking-[0.2em] uppercase px-3 py-1 rounded-lg bg-white/5 border border-outline-variant/10 text-secondary`}>
                                            {fund.scheme_category}
                                        </span>
                                        
                                        <button 
                                            onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare(fund)}
                                            className={`p-2 rounded-xl transition-all ${isComparing ? 'bg-primary text-on-primary' : 'bg-white/5 text-slate-500 hover:text-white hover:bg-white/10'} ${isLocked && !isComparing ? 'opacity-20 cursor-not-allowed' : ''}`}
                                        >
                                            <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                        </button>
                                    </div>

                                    <Link 
                                        to={`/mf/${fund.scheme_code}`} 
                                        onClick={(e) => handleDetailNavigation(e, fund.scheme_code)}
                                        className="text-2xl font-headline font-bold text-white mb-1 group-hover:text-primary transition-colors tracking-tight uppercase line-clamp-2 min-h-[4rem] flex items-center relative z-10"
                                    >
                                        {fund.scheme_name}
                                    </Link>
                                    <p className="text-[10px] text-slate-500 font-label font-bold tracking-widest uppercase truncate mb-6 opacity-60 relative z-10">ID: {fund.scheme_code} • {fund.amc_name}</p>

                                    <div className="grid grid-cols-2 gap-4 mb-6 py-4 border-y border-outline-variant/10 relative z-10">
                                        <div>
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Vault AUM</p>
                                            <p className="font-bold text-sm text-white tracking-tighter truncate">{fund.displayMetrics.aum}</p>
                                        </div>
                                        <div>
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Current Nav</p>
                                            <p className="font-bold text-sm text-white tracking-tighter">₹{fund.displayMetrics.nav}</p>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-end mt-auto relative z-10">
                                        <div>
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Session Alpha</p>
                                            <p className={`text-2xl font-black ${fund.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>
                                                {fund.displayMetrics.change}
                                            </p>
                                        </div>
                                        <div className="flex flex-col items-end">
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1 text-right">Sovereign Stance</p>
                                            <RatingBadge score={fund.score} />
                                        </div>
                                    </div>
                                    <div className={`absolute inset-x-0 bottom-0 h-0.5 bg-primary transition-opacity ${isComparing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
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
            <CompareDock />

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Benchmark Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
            </footer>
        </div>
    );
};

function RatingBadge({ score }) {
    if (score === undefined || score === null) return null;
    
    let label = "HOLD";
    let colorClass = "text-primary border-primary/50 bg-primary/10";
    
    if (score >= 80) {
        label = "STRONG BUY";
        colorClass = "text-secondary border-secondary bg-secondary/20";
    } else if (score >= 60) {
        label = "BUY";
        colorClass = "text-secondary border-secondary/50 bg-secondary/10";
    } else if (score < 40) {
        label = "SELL";
        colorClass = "text-error border-error/50 bg-error/10";
    }

    return (
        <div className={`px-3 py-1 rounded-full text-[9px] uppercase font-black tracking-widest border ${colorClass}`}>
            {label}
        </div>
    );
}

export default MFListing;
