import React, { useEffect, useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useNavigate } from 'react-router-dom';
import { fetchFunds, fetchFundsMetadata, setCategoryFilter, setAmcFilter, setCurrentPage, setPageSize, setViewMode } from '../store/slices/fundsSlice';
import { addToCompare, removeFromCompare } from '../store/slices/compareSlice';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import CompareDock from '../components/Compare/CompareDock';

// Reusable Filter Dropdown Component (Shadowed from StockListing for consistency)
const FilterDropdown = ({ label, value, options, onChange, icon }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center gap-3 px-6 py-3.5 rounded-2xl border transition-all duration-500 group ${isOpen ? 'bg-primary border-primary shadow-[0_0_30px_rgba(233,195,73,0.3)]' : 'bg-surface-container-low/50 border-outline-variant/10 hover:border-primary/40'}`}
            >
                <span className={`material-symbols-outlined text-xl transition-colors ${isOpen ? 'text-black' : 'text-primary'}`}>{icon}</span>
                <div className="text-left">
                    <p className={`text-[8px] uppercase tracking-[0.2em] font-black ${isOpen ? 'text-black/60' : 'text-slate-500'}`}>{label}</p>
                    <p className={`text-[11px] font-bold tracking-widest uppercase truncate max-w-[120px] ${isOpen ? 'text-black' : 'text-white'}`}>{value}</p>
                </div>
                <span className={`material-symbols-outlined text-sm transition-transform duration-500 ${isOpen ? 'rotate-180 text-black' : 'text-slate-500'}`}>expand_more</span>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.95 }}
                        className="absolute z-[100] mt-3 w-72 bg-[#1a1c1e] border border-outline-variant/20 rounded-[2rem] shadow-[0_32px_64px_rgba(0,0,0,0.8)] overflow-hidden backdrop-blur-3xl"
                    >
                        <div className="max-h-80 overflow-y-auto p-3 custom-scrollbar">
                            <button
                                onClick={() => { onChange('All'); setIsOpen(false); }}
                                className={`w-full text-left px-5 py-4 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all mb-1 ${value === 'All' ? 'bg-primary text-black' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
                            >
                                ALL {label}S
                            </button>
                            {options.map((opt) => (
                                <button
                                    key={opt}
                                    onClick={() => { onChange(opt); setIsOpen(false); }}
                                    className={`w-full text-left px-5 py-4 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all mb-1 ${value === opt ? 'bg-primary text-black' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
                                >
                                    {opt}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const MFListing = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { 
        items, total, loading, error, 
        currentPage, pageSize, 
        categoryFilter, amcFilter,
        categories, amcs,
        viewMode 
    } = useSelector((state) => state.funds);
    const { compareList } = useSelector((state) => state.compare);

    useEffect(() => {
        dispatch(fetchFundsMetadata());
    }, [dispatch]);

    useEffect(() => {
        dispatch(fetchFunds({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize, 
            category: categoryFilter,
            amc: amcFilter
        }));
    }, [dispatch, currentPage, pageSize, categoryFilter, amcFilter]);

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
            if (compareList[0].scheme_category !== fund.scheme_category) {
                toast.error('Strategic Mismatch: Funds must share identical category');
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
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Vault...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-surface text-on-surface pb-32">
            <div className="max-w-[1600px] mx-auto px-6 pt-12">
                
                {/* Center-Aligned Command Bar */}
                <div className="flex flex-col items-center mb-20 gap-10">
                    <div className="text-center space-y-2">
                        <p className="text-primary text-[10px] font-black uppercase tracking-[0.5em] mb-2">Sovereign Asset Surveillance</p>
                        <h1 className="font-headline text-6xl font-light tracking-tight text-white uppercase italic">
                            FUND <span className="font-black text-primary not-italic">VAULT</span>
                        </h1>
                    </div>

                    <div className="flex flex-wrap justify-center items-center gap-6 z-[60]">
                        <FilterDropdown 
                            label="Category" 
                            value={categoryFilter} 
                            options={categories} 
                            onChange={(val) => dispatch(setCategoryFilter(val))} 
                            icon="category" 
                        />
                        <FilterDropdown 
                            label="AMC" 
                            value={amcFilter} 
                            options={amcs} 
                            onChange={(val) => dispatch(setAmcFilter(val))} 
                            icon="account_balance" 
                        />

                        <div className="h-10 w-px bg-outline-variant/20 mx-2"></div>

                        <div className="flex bg-surface-container-low/50 p-1.5 rounded-2xl border border-outline-variant/10">
                            <button
                                onClick={() => dispatch(setViewMode('card'))}
                                className={`p-3 rounded-xl transition-all duration-500 ${viewMode === 'card' ? 'bg-primary text-black shadow-lg shadow-primary/20' : 'text-slate-500 hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-2xl">grid_view</span>
                            </button>
                            <button
                                onClick={() => dispatch(setViewMode('table'))}
                                className={`p-3 rounded-xl transition-all duration-500 ${viewMode === 'table' ? 'bg-primary text-black shadow-lg shadow-primary/20' : 'text-slate-500 hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-2xl">table_rows</span>
                            </button>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="mb-12 p-8 bg-error/10 border border-error/20 rounded-3xl text-error font-black uppercase tracking-widest text-center">
                        {error}
                    </div>
                )}

                <AnimatePresence mode="wait">
                    {viewMode === 'card' ? (
                        <motion.div 
                            key="grid"
                            initial={{ opacity: 0, y: 30 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -30 }}
                            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-10"
                        >
                            {items.map((fund, idx) => {
                                const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);
                                return (
                                    <motion.div 
                                        key={fund.scheme_code}
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: idx * 0.02 }}
                                        className={`group bg-surface-container-low p-7 rounded-[2rem] border transition-all duration-500 relative overflow-hidden flex flex-col ${isComparing ? 'border-primary shadow-[0_0_40px_rgba(233,195,73,0.1)]' : 'border-outline-variant/10 hover:border-primary/40 hover:translate-y-[-8px]'}`}
                                    >
                                        <div className="flex justify-between items-start mb-6">
                                            <div className="px-3 py-1 rounded-lg bg-primary/10 border border-primary/20">
                                                <p className="text-[8px] font-black tracking-widest text-primary uppercase">{fund.scheme_category}</p>
                                            </div>
                                            <button 
                                                onClick={() => isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare(fund)}
                                                className={`p-2.5 rounded-xl transition-all ${isComparing ? 'bg-primary text-black' : 'bg-white/5 text-slate-500 hover:text-white hover:bg-white/10'}`}
                                            >
                                                <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                            </button>
                                        </div>

                                        <Link 
                                            to={`/mf/${fund.scheme_code}`}
                                            onClick={(e) => handleDetailNavigation(e, fund.scheme_code)}
                                            className="flex-grow"
                                        >
                                            <h3 className={`font-headline font-bold text-xl mb-1 tracking-tight uppercase line-clamp-2 transition-colors ${isComparing ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                                                {fund.scheme_name}
                                            </h3>
                                            <p className="text-[9px] text-slate-500 font-bold tracking-[0.2em] uppercase mb-8 line-clamp-1">{fund.amc_name}</p>
                                        </Link>

                                        <div className="space-y-4 pt-6 border-t border-outline-variant/10">
                                            <div className="flex justify-between items-end">
                                                <div>
                                                    <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Current Nav</p>
                                                    <p className="text-2xl font-black text-white tracking-tighter">₹{fund.displayMetrics.nav}</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Sovereign Stance</p>
                                                    <RatingBadge label={fund.score >= 80 ? 'STRONG BUY' : fund.score >= 60 ? 'BUY' : 'HOLD'} />
                                                </div>
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
                            className="bg-surface-container-low rounded-[2.5rem] overflow-hidden shadow-2xl border border-outline-variant/10"
                        >
                            <div className="w-full overflow-x-auto border-collapse no-scrollbar">
                                <table className="w-full text-left min-w-[1000px]">
                                    <thead>
                                        <tr className="border-b border-outline-variant/20 bg-surface-container/50">
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black">Ticker</th>
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black">Name</th>
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center">Category</th>
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center">AMC</th>
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-right">Price</th>
                                            <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center w-24">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {items.map((fund) => {
                                            const isComparing = compareList.some(f => f.scheme_code === fund.scheme_code);
                                            return (
                                                <tr 
                                                    key={fund.scheme_code}
                                                    onClick={() => navigate(`/mf/${fund.scheme_code}`)}
                                                    className={`border-b border-outline-variant/10 hover:bg-white/[0.03] transition-all duration-500 group cursor-pointer ${isComparing ? 'bg-primary/[0.03]' : ''}`}
                                                >
                                                    <td className="px-8 py-8">
                                                        <div className={`font-headline font-bold text-2xl tracking-tighter transition-colors uppercase ${isComparing ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                                                            {fund.scheme_code}
                                                        </div>
                                                    </td>
                                                    <td className="px-8 py-8">
                                                        <div className="text-[11px] text-slate-400 font-label font-bold tracking-widest uppercase truncate max-w-[250px]">
                                                            {fund.scheme_name}
                                                        </div>
                                                    </td>
                                                    <td className="px-8 py-8 text-center text-[10px] font-bold text-white uppercase tracking-widest">
                                                        {fund.scheme_category}
                                                    </td>
                                                    <td className="px-8 py-8 text-center text-[10px] font-black text-primary/80 uppercase tracking-widest">
                                                        {fund.amc_name}
                                                    </td>
                                                    <td className="px-8 py-8 text-right">
                                                        <div className="text-2xl font-black text-white tracking-tighter">₹{fund.displayMetrics.nav}</div>
                                                    </td>
                                                    <td className="px-8 py-8 text-center">
                                                        <button 
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                isComparing ? dispatch(removeFromCompare(fund.scheme_code)) : handleAddToCompare(fund);
                                                            }}
                                                            className={`p-2.5 rounded-xl transition-all ${isComparing ? 'bg-primary text-black shadow-lg scale-110' : 'bg-white/5 text-slate-500 hover:text-white'}`}
                                                        >
                                                            <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                                        </button>
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

                {/* Advanced Pagination Bar */}
                <div className="mt-20 flex flex-col md:flex-row items-center justify-between gap-10">
                    <div className="flex items-center gap-4 bg-surface-container-low/50 p-2 rounded-2xl border border-outline-variant/10">
                        <button 
                            onClick={() => dispatch(setCurrentPage(1))}
                            disabled={currentPage === 1}
                            className="p-3 rounded-xl hover:bg-white/5 disabled:opacity-20 transition-all group"
                            title="First Level"
                        >
                            <span className="material-symbols-outlined text-xl group-hover:text-primary">first_page</span>
                        </button>
                        <button 
                            onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                            disabled={currentPage === 1}
                            className="px-8 py-3 rounded-xl border border-outline-variant/20 text-[10px] font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all"
                        >
                            PREVIOUS
                        </button>
                        
                        <div className="px-6 flex items-center gap-3">
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">LEVEL</span>
                            <span className="text-xl font-black text-primary font-mono">{currentPage}</span>
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">OF {Math.ceil(total / pageSize)}</span>
                        </div>

                        <button 
                            onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                            disabled={currentPage >= Math.ceil(total / pageSize)}
                            className="px-8 py-3 rounded-xl border border-outline-variant/20 text-[10px] font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all"
                        >
                            NEXT
                        </button>
                        <button 
                            onClick={() => dispatch(setCurrentPage(Math.ceil(total / pageSize)))}
                            disabled={currentPage >= Math.ceil(total / pageSize)}
                            className="p-3 rounded-xl hover:bg-white/5 disabled:opacity-20 transition-all group"
                            title="Final Level"
                        >
                            <span className="material-symbols-outlined text-xl group-hover:text-primary">last_page</span>
                        </button>
                    </div>

                    <div className="flex items-center gap-6">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">LOAD_VOLUME:</span>
                        <div className="flex bg-surface-container-low p-1.5 rounded-2xl border border-outline-variant/10">
                            {[10, 20, 30, 50].map((size) => (
                                <button
                                    key={size}
                                    onClick={() => dispatch(setPageSize(size))}
                                    className={`px-4 py-2 rounded-xl text-[10px] font-black transition-all ${pageSize === size ? 'bg-primary text-black' : 'text-slate-500 hover:text-white'}`}
                                >
                                    {size}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <CompareDock />
                
                <footer className="mt-32 py-12 border-t border-outline-variant/10 text-center">
                    <p className="text-[11px] font-black tracking-[0.4em] text-slate-600 uppercase">
                        NIVESH PLATFORM <span className="text-primary/40 mx-2">●</span> COPYRIGHT 2026
                    </p>
                </footer>
            </div>
        </div>
    );
};

// Internal Rating Badge for consistency
function RatingBadge({ label }) {
    let colorClass = "text-primary border-primary/50 bg-primary/10";
    if (label === 'STRONG BUY') colorClass = "text-secondary border-secondary bg-secondary/20";
    if (label === 'BUY') colorClass = "text-secondary border-secondary/50 bg-secondary/10";
    
    return (
        <div className={`px-4 py-1.5 rounded-full text-[9px] uppercase font-black tracking-[0.2em] border shadow-lg ${colorClass}`}>
            {label}
        </div>
    );
}

export default MFListing;
