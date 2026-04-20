import React, { useEffect, useState, useRef } from 'react';
import { useDispatch, useSelector } from "react-redux";
import { Link, useNavigate } from "react-router-dom";
import { fetchStocks, setFilter, setPage, setLimit } from "../store/slices/stocksSlice";
import { addStockToCompare, removeStockFromCompare, clearStockCompare } from "../store/slices/stockCompareSlice";
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

const SECTORS = ["Banking", "IT", "Pharma", "Auto", "FMCG", "Energy", "Telecom"];
const INDUSTRIES = [
    "Banks - Regional", "Auto Manufacturers", "Specialty Chemicals", 
    "Utilities - Renewable", "Medical Care Facilities", "Marine Shipping",
    "Software", "Financial Services", "Energy"
];
const MARKET_CAPS = [
    { label: "Large Cap", value: "Large Cap" },
    { label: "Mid Cap", value: "Mid Cap" },
    { label: "Small Cap", value: "Small Cap" }
];

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

const StockListing = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();

    const { list, pagination, filters, status } = useSelector(s => s.stocks);
    const { compareList } = useSelector(s => s.stockCompare);

    const [search, setSearch] = useState("");
    const [viewMode, setViewMode] = useState('card');

    useEffect(() => {
        dispatch(fetchStocks({ ...filters, page: pagination.page, limit: pagination.limit }));
    }, [filters, pagination.page, pagination.limit, dispatch]);

    useEffect(() => {
        const timer = setTimeout(() => {
            dispatch(fetchStocks({ ...filters, q: search, limit: pagination.limit, page: 1 }));
        }, 500);
        return () => clearTimeout(timer);
    }, [search, dispatch, filters, pagination.limit]);

    const handleDetailNavigation = (e, symbol) => {
        if (compareList.length > 0) {
            e.preventDefault();
            toast.error('Clear comparisons to view equity details', {
                icon: 'lock',
                duration: 4000,
            });
        }
    };

    const handleAddToCompare = (stock) => {
        if (compareList.length >= 4) {
            toast.error('Maximum phase capacity reached (4 assets)');
            return;
        }
        dispatch(addStockToCompare(stock));
        toast.success(`${stock.company_name.substring(0, 20)}... locked into matrix`);
    };

    if (status === "loading" && list.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Equity Archives...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-10 lg:p-12 2xl:p-16 max-w-screen-2xl mx-auto w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500 relative pb-64 bg-surface text-on-surface">
            {/* Header - Ultra Scale */}
            {/* Center-aligned Filter Suite */}
            <header className="mb-20 flex flex-col items-center gap-10 pt-4 relative z-50">
                <div className="flex flex-wrap justify-center gap-6 items-center bg-surface-container-low/40 backdrop-blur-xl p-4 rounded-[2.5rem] border border-outline-variant/10 shadow-2xl w-full max-w-6xl">
                    {/* Matrix Filters */}
                    <div className="flex flex-wrap gap-4 items-center">
                        <FilterDropdown 
                            label="Sector"
                            options={SECTORS}
                            value={filters.sector}
                            onChange={(val) => dispatch(setFilter({ key: "sector", val }))}
                            placeholder="All Sectors"
                        />

                        <FilterDropdown 
                            label="Industry"
                            options={INDUSTRIES}
                            value={filters.industry}
                            onChange={(val) => dispatch(setFilter({ key: "industry", val }))}
                            placeholder="All Industries"
                        />

                        <FilterDropdown 
                            label="Market Cap"
                            options={MARKET_CAPS}
                            value={filters.market_cap_cat}
                            onChange={(val) => dispatch(setFilter({ key: "market_cap_cat", val }))}
                            placeholder="All Caps"
                        />

                        <button 
                            onClick={() => dispatch({ type: 'stocks/resetFilters' })}
                            className="p-3.5 rounded-xl bg-white/5 border border-outline-variant/10 text-slate-500 hover:text-error hover:bg-error/5 transition-all flex items-center justify-center h-[46px] w-[46px]"
                            title="Reset Protocols"
                        >
                            <span className="material-symbols-outlined text-xl">filter_alt_off</span>
                        </button>
                    </div>

                    <div className="h-10 w-px bg-outline-variant/20 hidden xl:block"></div>

                    {/* View Toggle - Micro Component */}
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

            {status === "failed" && (
                <div className="p-10 bg-error/10 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-widest text-center shadow-lg">
                    Communication with Equity Archives Failed.
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
                        {list.length === 0 ? (
                            <div className="col-span-full text-center py-12 text-slate-500 font-label uppercase tracking-widest text-xs">No signals found</div>
                        ) : list.map((stock, idx) => {
                            const isComparing = compareList.some(s => s.symbol === stock.symbol);
                            const changeColor = stock.change_pct >= 0 ? "text-secondary" : "text-error";

                            return (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ delay: idx * 0.03 }}
                                    key={stock.symbol}
                                    className={`bg-surface-container-low p-6 rounded-2xl border ${isComparing ? 'border-primary/60 shadow-[0_0_40px_rgba(233,195,73,0.1)]' : 'border-outline-variant/10'} hover:border-primary/40 transition-all duration-500 flex flex-col group relative overflow-hidden shadow-xl hover:translate-y-[-8px] cursor-crosshair`}
                                >
                                    <div className="mb-6 flex justify-between items-start relative z-10">
                                        <span className="text-[9px] font-black tracking-[0.2em] uppercase px-3 py-1 rounded-lg bg-white/5 text-slate-400 group-hover:text-primary transition-colors border border-outline-variant/10">
                                            {stock.sector}
                                        </span>

                                        <button
                                            onClick={() => isComparing ? dispatch(removeStockFromCompare(stock.symbol)) : handleAddToCompare(stock)}
                                            className={`p-2 rounded-xl transition-all ${isComparing ? 'bg-primary text-on-primary' : 'bg-white/5 text-slate-500 hover:text-white hover:bg-white/10'}`}
                                        >
                                            <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                        </button>
                                    </div>

                                    <Link
                                        to={`/stocks/${stock.symbol}`}
                                        onClick={(e) => handleDetailNavigation(e, stock.symbol)}
                                        className="text-3xl font-headline font-bold text-white mb-1 group-hover:text-primary transition-colors tracking-tight uppercase relative z-10"
                                    >
                                        {stock.symbol}
                                    </Link>
                                    <p className="text-[10px] text-slate-500 font-label font-bold tracking-widest uppercase truncate mb-6 opacity-60 relative z-10">
                                        {stock.company_name}
                                    </p>

                                    <div className="grid grid-cols-1 gap-4 mb-6 py-4 border-y border-outline-variant/10 relative z-10">
                                        <div>
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Market Presence</p>
                                            <p className="font-bold text-xs text-white uppercase tracking-wider">{stock.market_cap_cat || "—"}</p>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-end mt-auto relative z-10">
                                        <div>
                                            <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Latest Close</p>
                                            <p className={`text-2xl font-black text-white tracking-tighter`}>
                                                ₹{stock.latest_close?.toFixed(2) ?? "—"}
                                            </p>
                                        </div>
                                        {stock.rating_label && (
                                            <div className="flex flex-col items-end">
                                              <p className="text-[8px] uppercase tracking-widest text-slate-600 font-black mb-1">Sovereign Stance</p>
                                              <RatingBadge label={stock.rating_label} />
                                            </div>
                                        )}
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
                        className="bg-surface-container-low rounded-[2.5rem] overflow-hidden shadow-2xl border border-outline-variant/10 mb-12"
                    >
                        <div className="w-full overflow-x-auto border-collapse no-scrollbar">
                            <table className="w-full text-left min-w-[1000px]">
                                <thead>
                                    <tr className="border-b border-outline-variant/20 bg-surface-container/50">
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black">Ticker</th>
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black">Name</th>
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center">Market Cap</th>
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center">Sector</th>
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-right">Price</th>
                                        <th className="px-8 py-6 text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black text-center w-24">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {list.map((stock, i) => {
                                        const isComparing = compareList.some(s => s.symbol === stock.symbol);
                                        return (
                                            <tr 
                                                key={stock.symbol} 
                                                onClick={() => navigate(`/stocks/${stock.symbol}`)}
                                                className={`border-b border-outline-variant/10 hover:bg-white/[0.03] transition-all duration-500 group cursor-pointer ${isComparing ? 'bg-primary/[0.03]' : ''}`}
                                            >
                                                <td className="px-8 py-8">
                                                    <div className={`font-headline font-bold text-2xl tracking-tighter transition-colors uppercase ${isComparing ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                                                        {stock.symbol}
                                                    </div>
                                                </td>
                                                <td className="px-8 py-8">
                                                    <div className="text-[11px] text-slate-400 font-label font-bold tracking-widest uppercase truncate max-w-[250px]">
                                                        {stock.company_name}
                                                    </div>
                                                </td>
                                                <td className="px-8 py-8 text-center text-[11px] font-bold text-white uppercase tracking-widest">
                                                    {stock.market_cap_cat || "—"}
                                                </td>
                                                <td className="px-8 py-8 text-center text-[10px] font-black text-primary/80 uppercase tracking-widest">
                                                    {stock.sector}
                                                </td>
                                                <td className="px-8 py-8 text-right">
                                                    <div className="text-2xl font-black text-white tracking-tighter">₹{stock.latest_close?.toFixed(2) ?? "—"}</div>
                                                </td>
                                                <td className="px-8 py-8 text-center">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            isComparing ? dispatch(removeStockFromCompare(stock.symbol)) : handleAddToCompare(stock);
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

            {/* Pagination Suite */}
            {list.length > 0 && (
                <div className="flex flex-col md:flex-row justify-between items-center gap-8 mt-24 mb-20 px-4">
                    {/* Items Per Page */}
                    <div className="flex items-center gap-4 bg-surface-container-low/40 p-2 rounded-2xl border border-outline-variant/10">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-4">Show:</span>
                        {[10, 20, 30, 50].map(size => (
                            <button 
                                key={size}
                                onClick={() => dispatch(setLimit(size))}
                                className={`px-4 py-2 rounded-xl text-[10px] font-black transition-all ${pagination.limit === size ? 'bg-primary text-on-primary' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
                            >
                                {size}
                            </button>
                        ))}
                    </div>

                    {/* Navigation Controls */}
                    <div className="flex items-center gap-4">
                        <button
                            disabled={pagination.page <= 1}
                            onClick={() => dispatch(setPage(1))}
                            className="p-4 rounded-2xl border border-outline-variant/30 text-slate-500 hover:text-primary disabled:opacity-10 transition-all"
                            title="First Page"
                        >
                            <span className="material-symbols-outlined">first_page</span>
                        </button>
                        
                        <button
                            disabled={pagination.page <= 1}
                            onClick={() => dispatch(setPage(pagination.page - 1))}
                            className="px-8 py-4 rounded-2xl border border-outline-variant/30 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                        >
                            Previous
                        </button>

                        <div className="px-6 py-4 rounded-2xl bg-primary/10 border border-primary/20 text-primary font-black text-sm tracking-widest font-mono">
                            {pagination.page} / {Math.ceil(pagination.total / pagination.limit)}
                        </div>

                        <button
                            onClick={() => dispatch(setPage(pagination.page + 1))}
                            disabled={pagination.page * pagination.limit >= pagination.total}
                            className="px-8 py-4 rounded-2xl border border-outline-variant/30 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                        >
                            Next
                        </button>

                        <button
                            onClick={() => dispatch(setPage(Math.ceil(pagination.total / pagination.limit)))}
                            disabled={pagination.page * pagination.limit >= pagination.total}
                            className="p-4 rounded-2xl border border-outline-variant/30 text-slate-500 hover:text-primary disabled:opacity-10 transition-all"
                            title="Last Page"
                        >
                            <span className="material-symbols-outlined">last_page</span>
                        </button>
                    </div>

                    {/* Total Summary */}
                    <div className="hidden lg:block text-[10px] font-black text-slate-600 uppercase tracking-widest italic font-label">
                        Archiving {list.length} of {pagination.total} Assets
                    </div>
                </div>
            )}

            {/* Floating Compare Dock */}
            <AnimatePresence>
                {compareList.length > 0 && (
                    <motion.div
                        initial={{ y: 200, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 200, opacity: 0 }}
                        className="fixed bottom-12 left-1/2 -translate-x-1/2 z-[100] w-full max-w-6xl px-6"
                    >
                        <div className="bg-[#0f1419]/90 backdrop-blur-3xl p-8 rounded-[3rem] border border-primary/20 shadow-[0_-32px_64px_rgba(0,0,0,0.5)] flex flex-col md:flex-row items-center justify-between gap-12">
                            <div className="flex items-center gap-8 flex-1 overflow-x-auto w-full no-scrollbar px-4">
                                <div className="flex flex-col">
                                    <span className="text-[10px] font-black text-primary uppercase tracking-[0.4em] leading-none mb-1">Matrix Active</span>
                                    <span className="text-2xl font-black text-white tracking-widest uppercase">{compareList.length}/4</span>
                                </div>
                                <div className="h-10 w-px bg-white/10 mx-4 hidden md:block"></div>
                                <div className="flex gap-4">
                                    {compareList.map((stock, i) => {
                                        const colors = ['#4ade80', '#818cf8', '#fbbf24', '#fb7185'];
                                        const accentColor = colors[i % colors.length];

                                        return (
                                            <motion.div
                                                layout
                                                initial={{ scale: 0.8, opacity: 0 }}
                                                animate={{ scale: 1, opacity: 1 }}
                                                key={stock.symbol}
                                                className="px-6 py-3 rounded-2xl bg-white/5 border-l-2 flex items-center gap-4 group hover:border-primary/40 transition-all cursor-default whitespace-nowrap"
                                                style={{ borderImageSource: `linear-gradient(to bottom, ${accentColor}, ${accentColor}44)`, borderLeftColor: accentColor }}
                                            >
                                                <span className="text-[11px] font-black text-white/80 uppercase tracking-widest">{stock.symbol}</span>
                                                <button
                                                    onClick={() => dispatch(removeStockFromCompare(stock.symbol))}
                                                    className="material-symbols-outlined text-slate-500 hover:text-error text-lg transition-colors"
                                                >
                                                    close
                                                </button>
                                            </motion.div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="flex items-center gap-8">
                                <button
                                    onClick={() => dispatch(clearStockCompare())}
                                    className="px-8 py-4 rounded-xl text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 hover:text-error transition-all"
                                >
                                    Purge All
                                </button>
                                <button
                                    onClick={() => navigate('/stock-compare')}
                                    disabled={compareList.length < 2}
                                    className={`px-12 py-5 rounded-2xl bg-gradient-to-br from-primary to-[#9d7e00] text-on-primary font-black text-xs uppercase tracking-[0.3em] shadow-2xl transition-all active:scale-95 flex items-center gap-4 ${compareList.length < 2 ? 'opacity-30 grayscale cursor-not-allowed' : 'hover:brightness-110'}`}
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
                NIVESH PLATFORM Copyright {new Date().getFullYear()}
            </footer>
        </div>
    );
};

function RatingBadge({ label }) {
    if (!label) return null;
    const colors = {
        STRONG_BUY: { bg: "bg-secondary/20 border-secondary", text: "text-secondary" },
        BUY: { bg: "bg-secondary/10 border-secondary/50", text: "text-secondary" },
        HOLD: { bg: "bg-primary/10 border-primary/50", text: "text-primary" },
        SELL: { bg: "bg-error/10 border-error/50", text: "text-error" },
        STRONG_SELL: { bg: "bg-error/20 border-error", text: "text-error" },
    };

    const style = colors[label] || { bg: "bg-surface-container", text: "text-slate-400" };

    return (
        <div className={`px-3 py-1 rounded-full text-[10px] uppercase font-black tracking-widest border ${style.bg} ${style.text}`}>
            {label.replace("_", " ")}
        </div>
    );
}

export default StockListing;
