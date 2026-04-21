import React, { useEffect, useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchIndices, setCurrentPage, setSearchQuery } from '../store/slices/indicesSlice';
import { motion, AnimatePresence } from 'framer-motion';

const FilterDropdown = ({ label, options, value, onChange, placeholder }) => {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const selectedOption = options.find(o => (typeof o === 'string' ? o : o.value) === value);
    const displayValue = selectedOption 
        ? (typeof selectedOption === 'string' ? selectedOption : selectedOption.label).toUpperCase() 
        : placeholder.toUpperCase();

    return (
        <div ref={containerRef} className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center justify-between gap-4 bg-black/40 border border-outline-variant/20 rounded-xl px-5 py-3 text-[10px] font-black uppercase tracking-widest transition-all outline-none min-w-[160px] ${isOpen ? 'border-primary text-primary ring-1 ring-primary/20' : 'text-slate-400 focus:border-primary/50'}`}
            >
                <span className="truncate">{displayValue}</span>
                <span className={`material-symbols-outlined text-lg transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}>expand_more</span>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.95 }}
                        transition={{ duration: 0.2, ease: "circOut" }}
                        className="absolute z-[1000] top-full mt-2 left-0 w-full min-w-[200px] bg-surface-container-high/90 backdrop-blur-2xl border border-outline-variant/20 rounded-2xl shadow-[0_16px_32px_rgba(0,0,0,0.4)] overflow-hidden"
                    >
                        <div className="max-h-60 overflow-y-auto py-2 custom-scrollbar">
                            <button
                                onClick={() => { onChange(""); setIsOpen(false); }}
                                className={`w-full text-left px-5 py-3 text-[10px] font-black uppercase tracking-widest transition-all hover:bg-white/5 ${!value ? 'text-primary bg-primary/10' : 'text-slate-400'}`}
                            >
                                {placeholder.toUpperCase()}
                            </button>
                            {options.map((opt) => {
                                const val = typeof opt === 'string' ? opt : opt.value;
                                const lbl = typeof opt === 'string' ? opt : opt.label;
                                const isSelected = val === value;

                                return (
                                    <button
                                        key={val}
                                        onClick={() => { onChange(val); setIsOpen(false); }}
                                        className={`w-full text-left px-5 py-3 text-[10px] font-black uppercase tracking-widest transition-all hover:bg-white/5 ${isSelected ? 'text-primary bg-primary/10' : 'text-slate-400 hover:text-white'}`}
                                    >
                                        {lbl.toUpperCase()}
                                    </button>
                                );
                            })}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const IndicesListing = () => {
    const dispatch = useDispatch();
    const { items, total, loading, error, currentPage, pageSize, searchQuery } = useSelector((state) => state.indices);
    const [viewMode, setViewMode] = useState('card');
    const [localSearch, setLocalSearch] = useState(searchQuery);

    useEffect(() => {
        dispatch(fetchIndices({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize,
            search: searchQuery
        }));
    }, [dispatch, currentPage, pageSize, searchQuery]);

    useEffect(() => {
        const timer = setTimeout(() => {
            dispatch(setSearchQuery(localSearch));
        }, 500);
        return () => clearTimeout(timer);
    }, [localSearch, dispatch]);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Synchronizing Global Benchmarks...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-10 lg:p-12 2xl:p-16 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500 relative pb-64 bg-surface text-on-surface">
            {/* Header - Center-aligned Filter Suite */}
            <header className="mb-20 flex flex-col items-center gap-10 pt-4 relative z-50">
                <div className="text-center">
                    <span className="text-[10px] text-primary font-black uppercase tracking-[0.6em] mb-4 block animate-pulse">Market Intelligence Feed</span>
                    <h1 className="text-6xl md:text-8xl font-headline font-bold tracking-tighter leading-none uppercase">
                        Global <span className="text-primary">Indices</span>
                    </h1>
                </div>

                <div className="flex flex-wrap justify-center gap-6 items-center bg-surface-container-low/40 backdrop-blur-xl p-4 rounded-[2.5rem] border border-outline-variant/10 shadow-2xl w-full max-w-6xl">
                    {/* Search Bar */}
                    <div className="flex-1 min-w-[300px] relative group">
                        <span className="material-symbols-outlined absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-primary transition-colors">search</span>
                        <input 
                            type="text" 
                            placeholder="SEARCH BENCHMARKS..."
                            value={localSearch}
                            onChange={(e) => setLocalSearch(e.target.value)}
                            className="w-full bg-black/40 border border-outline-variant/20 rounded-2xl py-3.5 pl-14 pr-6 text-[10px] font-black uppercase tracking-widest text-white focus:border-primary/50 focus:ring-1 focus:ring-primary/20 outline-none transition-all"
                        />
                    </div>

                    <div className="h-10 w-px bg-outline-variant/20 hidden xl:block"></div>

                    {/* View Toggle */}
                    <div className="flex bg-black/40 p-1 rounded-2xl border border-outline-variant/20">
                        <button
                            onClick={() => setViewMode('card')}
                            className={`p-3 rounded-xl transition-all flex items-center gap-2 ${viewMode === 'card' ? 'bg-primary text-on-primary shadow-lg shadow-primary/20' : 'text-slate-500 hover:text-white'}`}
                        >
                            <span className="material-symbols-outlined text-lg">grid_view</span>
                        </button>
                        <button
                            onClick={() => setViewMode('table')}
                            className={`p-3 rounded-xl transition-all flex items-center gap-2 ${viewMode === 'table' ? 'bg-primary text-on-primary shadow-lg shadow-primary/20' : 'text-slate-500 hover:text-white'}`}
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
                        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-8 xl:gap-10 2xl:gap-12"
                    >
                        {items.length === 0 ? (
                            <div className="col-span-full text-center py-12 text-slate-500 font-label uppercase tracking-widest text-xs">No indices found</div>
                        ) : items.map((idx, i) => (
                            <motion.div
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                                key={idx.benchmark_code}
                                className="bg-surface-container-low p-8 rounded-3xl border border-outline-variant/10 hover:border-primary/40 transition-all duration-500 flex flex-col group relative overflow-hidden shadow-xl hover:translate-y-[-8px] cursor-crosshair"
                            >
                                <div className="mb-8 flex justify-between items-start">
                                    <span className="text-[10px] font-black tracking-[0.3em] uppercase px-4 py-1.5 rounded-xl bg-white/5 text-slate-400 group-hover:text-primary transition-colors border border-outline-variant/10">
                                        {idx.benchmark_type}
                                    </span>
                                    <div className={`w-3 h-3 rounded-full ${idx.is_active ? 'bg-secondary animate-pulse' : 'bg-slate-700'}`}></div>
                                </div>

                                <Link
                                    to={`/indices/${idx.benchmark_code}`}
                                    className="text-4xl font-headline font-bold text-white mb-2 group-hover:text-primary transition-colors tracking-tighter uppercase line-clamp-2"
                                >
                                    {idx.benchmark_name}
                                </Link>
                                <p className="text-[10px] text-slate-500 font-label font-black tracking-[0.4em] uppercase mb-8 opacity-60">
                                    {idx.ticker} • EQUITY / GLOBAL
                                </p>

                                <div className="mt-auto pt-8 border-t border-outline-variant/10 flex justify-between items-end">
                                    <div>
                                        <p className="text-[9px] uppercase tracking-widest text-slate-600 font-black mb-2">Market Level</p>
                                        <p className="text-3xl font-black text-white tracking-tighter">{idx.displayMetrics.nav}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] uppercase tracking-widest text-slate-600 font-black mb-2">Alpha Delta</p>
                                        <p className={`text-2xl font-black ${idx.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>
                                            {idx.displayMetrics.change}
                                        </p>
                                    </div>
                                </div>
                                <div className="absolute inset-x-0 bottom-0 h-0.5 bg-primary opacity-0 group-hover:opacity-100 transition-opacity"></div>
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
                        className="bg-surface-container-low rounded-[3rem] overflow-hidden shadow-2xl border border-outline-variant/10 mb-12"
                    >
                        <div className="w-full overflow-x-auto border-collapse no-scrollbar">
                            <table className="w-full text-left min-w-[1200px]">
                                <thead>
                                    <tr className="border-b border-outline-variant/20 bg-surface-container/50">
                                        <th className="px-12 py-8 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Benchmark Identity</th>
                                        <th className="px-12 py-8 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Ticker</th>
                                        <th className="px-12 py-8 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Protocol</th>
                                        <th className="px-12 py-8 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Current Level</th>
                                        <th className="px-12 py-8 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha Delta</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items.map((idx) => (
                                        <tr 
                                            key={idx.benchmark_code}
                                            className="border-b border-outline-variant/10 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair"
                                        >
                                            <td className="px-12 py-10">
                                                <Link to={`/indices/${idx.benchmark_code}`} className="flex flex-col">
                                                    <div className="text-3xl font-headline font-bold text-white group-hover:text-primary transition-colors tracking-tighter uppercase mb-1">{idx.benchmark_name}</div>
                                                    <div className="text-[9px] text-slate-500 font-black tracking-[0.4em] uppercase italic opacity-60">{idx.benchmark_type}</div>
                                                </Link>
                                            </td>
                                            <td className="px-12 py-10 text-center">
                                                <div className="text-xl font-black text-slate-400 tracking-widest uppercase group-hover:text-white transition-colors">{idx.ticker}</div>
                                            </td>
                                            <td className="px-12 py-10 text-center">
                                                <span className={`px-5 py-2 rounded-xl text-[10px] font-black tracking-widest ${idx.is_active ? 'bg-secondary/10 text-secondary border border-secondary/20 shadow-[0_0_20px_rgba(102,221,139,0.1)]' : 'bg-slate-800 text-slate-400 border border-white/5'}`}>
                                                    {idx.displayMetrics.status}
                                                </span>
                                            </td>
                                            <td className="px-12 py-10 text-right">
                                                <div className="text-3xl font-black text-white tracking-tighter">{idx.displayMetrics.nav}</div>
                                            </td>
                                            <td className="px-12 py-10 text-right">
                                                <div className={`text-3xl font-black ${idx.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'} tracking-tighter`}>{idx.displayMetrics.change}</div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Pagination Suite */}
            {items.length > 0 && (
                <div className="flex flex-col md:flex-row justify-center items-center gap-12 mt-24 mb-20 px-4">
                    <div className="flex items-center gap-6">
                        <button
                            disabled={currentPage <= 1}
                            onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                            className="px-10 py-5 rounded-2xl border border-outline-variant/30 text-[11px] font-black uppercase tracking-[0.3em] text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                        >
                            PREV_LEVEL
                        </button>

                        <div className="px-8 py-5 rounded-2xl bg-primary/10 border border-primary/20 text-primary font-black text-xl tracking-[0.4em] font-mono shadow-[0_0_40px_rgba(233,195,73,0.1)]">
                            L-{currentPage}
                        </div>

                        <button
                            onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                            disabled={currentPage * pageSize >= total}
                            className="px-10 py-5 rounded-2xl border border-outline-variant/30 text-[11px] font-black uppercase tracking-[0.3em] text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                        >
                            NEXT_LEVEL
                        </button>
                    </div>

                    <div className="hidden lg:block text-[10px] font-black text-slate-600 uppercase tracking-[0.6em] italic font-label ml-12">
                        Monitoring {items.length} of {total} Systemic Nodes
                    </div>
                </div>
            )}
        </div>
    );
};

export default IndicesListing;

