import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from "react-redux";
import { Link, useNavigate } from "react-router-dom";
import { fetchStocks, setFilter, setPage } from "../store/slices/stocksSlice";
import { addStockToCompare, removeStockFromCompare, clearStockCompare } from "../store/slices/stockCompareSlice";
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';

const SECTORS = ["Banking", "IT", "Pharma", "Auto", "FMCG", "Energy", "Telecom"];

const StockListing = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();

    const { list, pagination, filters, status } = useSelector(s => s.stocks);
    const { compareList } = useSelector(s => s.stockCompare);

    const [search, setSearch] = useState("");
    const [viewMode, setViewMode] = useState('card');

    useEffect(() => {
        dispatch(fetchStocks({ ...filters, page: pagination.page, limit: 25 }));
    }, [filters, pagination.page, dispatch]);

    const handleSearch = (e) => {
        if (e.key === "Enter" && search.trim()) {
            dispatch(fetchStocks({ ...filters, q: search, limit: 25, page: 1 }));
        }
    };

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
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500 relative pb-64 bg-surface text-on-surface">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 3xl:flex-row 3xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Institutional Wealth surveillance</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Equity <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Vault</span>
                    </h1>
                </div>

                <div className="flex flex-wrap gap-8 items-center bg-surface-container-high/40 p-6 rounded-[2.5rem] border border-white/5 backdrop-blur-2xl">
                    {/* Search Field */}
                    <div className="flex bg-black/40 p-1 rounded-2xl border border-white/5 w-64 md:w-80 relative">
                        <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">search</span>
                        <input
                            type="text"
                            placeholder="Identify Ticker..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            onKeyDown={handleSearch}
                            className="w-full bg-transparent border-none pl-12 pr-4 py-3 text-xs font-label uppercase tracking-widest text-white placeholder-slate-600 focus:outline-none focus:ring-0"
                        />
                    </div>

                    <div className="h-12 w-px bg-white/10 hidden md:block"></div>

                    {/* Sector Filter Chips */}
                    <div className="flex flex-wrap gap-2">
                        {SECTORS.map(sector => (
                            <button
                                key={sector}
                                onClick={() => dispatch(setFilter({
                                    key: "sector",
                                    val: filters.sector === sector ? "" : sector
                                }))}
                                className={`px-5 py-2 text-[10px] font-black tracking-[0.3em] uppercase rounded-xl transition-all ${filters.sector === sector
                                        ? 'bg-primary text-on-primary shadow-lg shadow-primary/40'
                                        : 'bg-black/40 border border-white/5 text-slate-500 hover:text-white'
                                    }`}
                            >
                                {sector}
                            </button>
                        ))}
                    </div>

                    <div className="h-12 w-px bg-white/10 hidden xl:block"></div>

                    {/* View Toggle */}
                    <div className="flex bg-black/40 p-2 rounded-2xl border border-white/5">
                        <button
                            onClick={() => setViewMode('card')}
                            className={`p-3 rounded-xl transition-all flex items-center gap-3 ${viewMode === 'card' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Grid Perspective"
                        >
                            <span className="material-symbols-outlined text-xl">grid_view</span>
                        </button>
                        <button
                            onClick={() => setViewMode('table')}
                            className={`p-3 rounded-xl transition-all flex items-center gap-3 ${viewMode === 'table' ? 'bg-white/10 text-primary shadow-inner' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Analytical Ledger"
                        >
                            <span className="material-symbols-outlined text-xl">table_rows</span>
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
                                    initial={{ opacity: 0, y: 30 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: idx * 0.05 }}
                                    key={stock.symbol}
                                    className={`bg-surface-container p-12 rounded-[3.5rem] border ${isComparing ? 'border-primary/60 shadow-[0_0_40px_rgba(233,195,73,0.1)]' : 'border-outline-variant/10'} hover:border-primary/40 transition-all duration-700 flex flex-col group relative overflow-hidden shadow-2xl hover:translate-y-[-16px] cursor-crosshair`}
                                >
                                    <div className="absolute top-0 right-0 p-12 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100">
                                        <span className="material-symbols-outlined text-[150px] text-primary">monitoring</span>
                                    </div>

                                    <div className="mb-10 flex justify-between items-start relative z-10">
                                        <span className={`text-[11px] font-black tracking-[0.3em] uppercase px-5 py-2 rounded-xl bg-white/5 border border-white/5 transition-all group-hover:border-primary/30 text-secondary`}>
                                            {stock.sector}
                                        </span>

                                        <button
                                            onClick={() => isComparing ? dispatch(removeStockFromCompare(stock.symbol)) : handleAddToCompare(stock)}
                                            className={`p-3 rounded-full transition-all ${isComparing ? 'bg-primary text-on-primary ring-4 ring-primary/20' : 'bg-white/5 text-slate-500 hover:text-white hover:bg-white/10'}`}
                                            title={isComparing ? "Remove from Matrix" : "Inject into Matrix"}
                                        >
                                            <span className="material-symbols-outlined text-2xl">{isComparing ? 'check_circle' : 'add_circle'}</span>
                                        </button>
                                    </div>

                                    <Link
                                        to={`/stocks/${stock.symbol}`}
                                        onClick={(e) => handleDetailNavigation(e, stock.symbol)}
                                        className="text-4xl sm:text-5xl font-headline font-bold text-white mb-4 group-hover:text-primary transition-colors tracking-tight leading-tight uppercase relative z-10"
                                    >
                                        {stock.symbol}
                                    </Link>
                                    <p className="text-xs text-slate-500 font-label font-bold tracking-[0.2em] uppercase line-clamp-2 min-h-[2.5rem] mb-12 opacity-80 relative z-10">
                                        {stock.company_name}
                                    </p>

                                    <div className="grid grid-cols-2 gap-10 mb-12 py-8 border-y border-white/5 bg-white/[0.01] backdrop-blur-sm relative z-10">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Market Cap</p>
                                            <p className="font-extrabold text-lg text-white tracking-widest uppercase">{stock.market_cap_cat || "—"}</p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">CMP</p>
                                            <p className="font-extrabold text-2xl text-white tracking-tighter">₹{stock.latest_close?.toFixed(2) ?? "—"}</p>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-end mt-auto relative z-10">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-3">Session Alpha</p>
                                            <p className={`text-4xl font-black ${changeColor} tracking-tighter`}>
                                                {stock.change_pct != null
                                                    ? `${stock.change_pct > 0 ? "+" : ""}${stock.change_pct}%`
                                                    : "—"}
                                            </p>
                                        </div>
                                        {stock.rating_label && (
                                            <RatingBadge label={stock.rating_label} />
                                        )}
                                    </div>
                                    <div className={`absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-primary to-[#9d7e00] transition-opacity ${isComparing ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}></div>
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
                        className="bg-surface-container-low rounded-[4rem] overflow-hidden shadow-[0_64px_128px_rgba(0,0,0,0.6)] border border-outline-variant/10 mb-12"
                    >
                        <div className="w-full overflow-x-auto border-collapse">
                            <table className="w-full text-left min-w-[1200px]">
                                <thead>
                                    <tr className="border-b border-outline-variant/20 bg-surface-container/50">
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black w-24 text-center">Matrix</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black">Asset Identity</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Sector</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Latest Close</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-right">Alpha Delta</th>
                                        <th className="px-16 py-12 text-[11px] uppercase tracking-[0.5em] text-slate-500 font-black text-center">Analyst Rating</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {list.map((stock, i) => {
                                        const isComparing = compareList.some(s => s.symbol === stock.symbol);
                                        const changeColor = stock.change_pct >= 0 ? "text-secondary" : "text-error";

                                        return (
                                            <tr key={stock.symbol} className={`border-b border-outline-variant/10 hover:bg-white/[0.03] transition-all duration-500 group cursor-crosshair ${isComparing ? 'bg-primary/[0.03]' : ''}`}>
                                                <td className="px-10 py-16 text-center">
                                                    <button
                                                        onClick={() => isComparing ? dispatch(removeStockFromCompare(stock.symbol)) : handleAddToCompare(stock)}
                                                        className={`p-3 rounded-full transition-all ${isComparing ? 'bg-primary text-on-primary shadow-[0_0_20px_rgba(233,195,73,0.3)]' : 'bg-white/5 text-slate-500 hover:text-white'}`}
                                                    >
                                                        <span className="material-symbols-outlined text-xl">{isComparing ? 'check' : 'add'}</span>
                                                    </button>
                                                </td>
                                                <td className="px-16 py-16">
                                                    <Link
                                                        to={`/stocks/${stock.symbol}`}
                                                        onClick={(e) => handleDetailNavigation(e, stock.symbol)}
                                                        className="flex items-center gap-10"
                                                    >
                                                        <div className={`w-20 h-20 rounded-[1.5rem] flex items-center justify-center font-black text-2xl border shadow-2xl group-hover:scale-110 transition-transform tracking-widest uppercase ${isComparing ? 'bg-primary text-on-primary border-primary' : 'bg-gradient-to-br from-white/10 to-white/5 text-primary border-white/5'}`}>
                                                            {stock.symbol.substring(0, 2)}
                                                        </div>
                                                        <div>
                                                            <div className={`font-extrabold text-3xl mb-2 tracking-tighter truncate max-w-xl transition-colors uppercase ${isComparing ? 'text-primary' : 'text-white group-hover:text-primary'}`}>{stock.symbol}</div>
                                                            <div className="text-[10px] text-slate-500 font-black tracking-[0.2em] uppercase opacity-80 whitespace-nowrap overflow-hidden text-ellipsis max-w-sm">{stock.company_name}</div>
                                                        </div>
                                                    </Link>
                                                </td>
                                                <td className="px-16 py-16 text-center">
                                                    <span className="px-5 py-2 rounded-xl text-[10px] font-black tracking-widest bg-white/5 border border-white/5 text-secondary uppercase">
                                                        {stock.sector}
                                                    </span>
                                                </td>
                                                <td className="px-16 py-16 text-right">
                                                    <div className="text-3xl font-extrabold text-white tracking-tighter">₹{stock.latest_close?.toFixed(2) ?? "—"}</div>
                                                </td>
                                                <td className="px-16 py-16 text-right">
                                                    <div className={`text-4xl font-black ${changeColor} tracking-tighter`}>
                                                        {stock.change_pct != null ? `${stock.change_pct > 0 ? "+" : ""}${stock.change_pct}%` : "—"}
                                                    </div>
                                                </td>
                                                <td className="px-16 py-16 text-center">
                                                    <RatingBadge label={stock.rating_label} />
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
            {list.length > 0 && (
                <div className="flex justify-center items-center gap-10 mt-24 mb-20">
                    <button
                        disabled={pagination.page <= 1}
                        onClick={() => dispatch(setPage(pagination.page - 1))}
                        className="px-12 py-5 rounded-3xl border border-outline-variant/30 text-xs font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                    >
                        PREV_LEVEL
                    </button>
                    <div className="text-2xl font-black text-primary font-mono tracking-widest">L-{pagination.page}</div>
                    <button
                        onClick={() => dispatch(setPage(pagination.page + 1))}
                        disabled={pagination.page * pagination.limit >= pagination.total}
                        className="px-12 py-5 rounded-3xl border border-outline-variant/30 text-xs font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                    >
                        NEXT_LEVEL
                    </button>
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
                                    {compareList.map((stock) => (
                                        <motion.div
                                            layout
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            key={stock.symbol}
                                            className="px-6 py-3 rounded-2xl bg-white/5 border border-white/5 flex items-center gap-4 group hover:border-primary/40 transition-all cursor-default whitespace-nowrap"
                                        >
                                            <span className="text-[11px] font-black text-white/80 uppercase tracking-widest">{stock.symbol}</span>
                                            <button
                                                onClick={() => dispatch(removeStockFromCompare(stock.symbol))}
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
                Equity Consensus Protocol Active • Decentralized Market Surveillance • Epoch {new Date().getFullYear()}
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
