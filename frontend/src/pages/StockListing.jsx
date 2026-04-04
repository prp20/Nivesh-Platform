import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchFunds, setCategoryFilter, setCurrentPage } from '../store/slices/fundsSlice';
import { motion } from 'framer-motion';

const StockListing = () => {
    const dispatch = useDispatch();
    const { items, loading, error, currentPage, pageSize, categoryFilter } = useSelector((state) => state.funds);

    useEffect(() => {
        // For stocks, we simulate by fetching Equity funds for now or all funds
        dispatch(fetchFunds({ 
            skip: (currentPage - 1) * pageSize, 
            limit: pageSize, 
            category: 'Equity' 
        }));
    }, [dispatch, currentPage, pageSize]);

    if (loading && items.length === 0) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0a0f12]">
                <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
                <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Scanning Global Equity Matrices...</p>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 2xl:flex-row 2xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Institutional Equity Surveillance</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Stock <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Navigator</span>
                    </h1>
                </div>

                <div className="flex flex-wrap gap-8 items-center bg-surface-container-high/40 p-4 rounded-3xl border border-white/5 backdrop-blur-2xl">
                    <span className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500 pl-4">Sector Focus:</span>
                    <div className="flex gap-4">
                        {['Technology', 'Global Infrastructure', 'Energy', 'Sovereign Debt'].map((sector) => (
                            <button key={sector} className="px-8 py-3 text-[10px] font-black tracking-[0.3em] uppercase rounded-xl border border-white/5 hover:bg-white/5 transition-all text-slate-400 hover:text-white">
                                {sector}
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {error && (
                <div className="p-10 bg-error/10 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-widest text-center shadow-lg">
                    {error}
                </div>
            )}

            {/* Stock Grid - Ultra Scaling */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5 gap-12 xl:gap-16">
                {items.map((stock, idx) => (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        key={stock.scheme_code} 
                        className="bg-surface-container p-12 rounded-[3.5rem] border border-white/5 hover:border-primary/40 transition-all duration-700 flex flex-col group relative overflow-hidden shadow-2xl hover:translate-y-[-16px] group"
                    >
                         <div className="absolute top-0 right-0 p-12 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100">
                             <span className="material-symbols-outlined text-[180px] text-primary">trending_up</span>
                         </div>

                        <div className="mb-10 flex justify-between items-start">
                            <span className="text-[11px] font-black tracking-[0.3em] uppercase px-5 py-2 rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-lg">
                                {stock.isin?.substring(0, 4) || 'T-1'}
                            </span>
                            <span className="material-symbols-outlined text-slate-700 group-hover:text-primary transition-colors text-3xl">token</span>
                        </div>

                        <Link to={`/stock/${stock.scheme_code}`} className="text-4xl sm:text-5xl font-headline font-bold text-white mb-4 group-hover:text-primary transition-colors tracking-tighter leading-none truncate block">
                            {stock.scheme_name.split(' - ')[0]}
                        </Link>
                        <p className="text-xs text-slate-500 font-black tracking-[0.4em] uppercase mb-12 opacity-60">NASDAQ: {stock.isin || 'NIV-X'} • SECTOR: TECH</p>

                        <div className="grid grid-cols-2 gap-10 mb-12 py-10 border-y border-white/5 bg-white/[0.01] backdrop-blur-3xl rounded-2xl">
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-4">Market Cap</p>
                                <p className="font-extrabold text-3xl text-white tracking-tighter truncate">{stock.displayMetrics.aum}</p>
                            </div>
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-4">Price Identity</p>
                                <p className="font-extrabold text-3xl text-white tracking-tighter">₹{stock.displayMetrics.nav}</p>
                            </div>
                        </div>

                        <div className="flex justify-between items-end mt-auto">
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500 font-black mb-4">Daily Momentum</p>
                                <div className="flex items-center gap-3">
                                    <span className={`material-symbols-outlined text-2xl ${stock.displayMetrics.change.startsWith('+') ? 'text-secondary animate-bounce' : 'text-error animate-pulse'}`}>
                                        {stock.displayMetrics.change.startsWith('+') ? 'arrow_upward' : 'arrow_downward'}
                                    </span>
                                    <p className={`text-4xl font-black tracking-tighter ${stock.displayMetrics.change.startsWith('+') ? 'text-secondary' : 'text-error'}`}>
                                        {stock.displayMetrics.change}
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="absolute inset-x-0 bottom-0 h-1 gold-gradient opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    </motion.div>
                ))}
            </div>

             {/* Pagination */}
             <div className="flex justify-center items-center gap-10 mt-24">
                <button 
                    disabled={currentPage === 1}
                    onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                    className="px-10 py-5 rounded-2xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 disabled:opacity-20 transition-all font-mono"
                >
                    PREV_HASH
                </button>
                <div className="flex gap-4">
                    {[1, 2, 3].map(p => (
                        <span key={p} className={`w-3 h-3 rounded-full transition-all ${p === currentPage ? 'bg-primary scale-125 shadow-[0_0_15px_rgba(233,195,73,0.6)]' : 'bg-slate-800'}`}></span>
                    ))}
                </div>
                <button 
                    onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                    className="px-10 py-5 rounded-2xl border border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5 transition-all font-mono"
                >
                    NEXT_HASH
                </button>
            </div>
        </div>
    );
};

export default StockListing;
