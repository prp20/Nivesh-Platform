import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchStockComparisonData, clearStockCompare, clearStockComparisonResult, removeStockFromCompare } from '../store/slices/stockCompareSlice';
import { motion, AnimatePresence } from 'framer-motion';

const StockCompare = () => {
    const dispatch = useDispatch();
    const {
        compareList,
        comparisonResult,
        comparisonLoading,
        comparisonError
    } = useSelector((state) => state.stockCompare);

    useEffect(() => {
        if (compareList.length >= 2) {
            const symbols = compareList.map(s => s.symbol);
            dispatch(fetchStockComparisonData(symbols));
        } else {
            dispatch(clearStockComparisonResult());
        }
    }, [dispatch, compareList]);

    if (compareList.length < 2) {
        return (
            <div className="min-h-[85vh] w-full flex flex-col items-center justify-center p-12 bg-surface">
                <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.03]">
                    <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none select-none">Equities</span>
                </div>
                
                <motion.div 
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="relative z-10 flex flex-col items-center text-center max-w-4xl"
                >
                    <div className="w-32 h-32 rounded-[2.5rem] bg-surface-container-lowest border border-outline-variant/30 flex items-center justify-center mb-16 shadow-2xl relative">
                        <span className="material-symbols-outlined text-primary text-5xl">lock_open</span>
                        <div className="absolute -bottom-2 -right-2 w-8 h-8 rounded-full bg-error flex items-center justify-center border-4 border-surface shadow-xl">
                            <span className="material-symbols-outlined text-xs text-white">priority_high</span>
                        </div>
                    </div>
                    
                    <span className="font-label text-[10px] text-primary font-black uppercase tracking-[0.6em] mb-6 animate-pulse italic">Access Denied: Initialization Failure</span>
                    <h2 className="text-6xl sm:text-8xl font-headline font-bold text-white mb-8 uppercase tracking-tighter italic leading-none">
                        Critical <span className="text-primary/10 italic">Depletion</span>
                    </h2>
                    <p className="text-slate-500 text-lg font-medium tracking-tight mb-16 max-w-2xl leading-relaxed italic border-l-2 border-[#45464c]/40 pl-10 mx-auto">
                        A minimum of two identified stock entities are required to initialize the differential comparison matrix and activate AI consensus protocols.
                    </p>
                    
                    <Link to="/stocks" className="group relative px-14 py-6 overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-[#9d7e00] text-on-primary font-black uppercase tracking-[0.2em] shadow-[0_24px_48px_rgba(233,195,73,0.15)] transition-all active:scale-95 flex items-center gap-6 font-label text-sm">
                        <span className="relative z-10 transition-transform group-hover:-translate-x-2">Return to Stock Vault</span>
                        <span className="material-symbols-outlined relative z-10 group-hover:translate-x-2 transition-transform">arrow_forward</span>
                    </Link>
                </motion.div>
            </div>
        );
    }

    const renderMetricRow = (label, key, isPercentage = false, isCurrency = false) => {
        return (
            <tr className="border-b border-outline-variant/20 hover:bg-surface-container-lowest/50 transition-colors">
                <td className="p-6 font-label text-sm text-slate-400 font-bold tracking-widest uppercase">{label}</td>
                {comparisonResult?.map((stock, i) => {
                    const val = stock[key];
                    const display = val != null 
                        ? (isCurrency ? `₹${val.toFixed(2)}` : (isPercentage ? `${val.toFixed(2)}%` : val.toFixed(2)))
                        : "—";
                    return (
                        <td key={`${stock.symbol}-${i}`} className="p-6 text-center text-xl font-headline font-semibold text-white">
                            {display}
                        </td>
                    );
                })}
            </tr>
        );
    };

    return (
        <div className="relative min-h-screen p-6 md:p-12 lg:p-16 xl:p-24 w-full animate-fadeIn transition-all duration-500 pb-60 bg-surface text-on-surface">
            {/* Background Watermark */}
            <div className="absolute top-40 -left-20 pointer-events-none opacity-[0.02] select-none rotate-90 origin-top-left">
                <span className="text-[18vw] font-headline font-black uppercase tracking-tighter leading-none">The Ledger</span>
            </div>

            <div className="relative z-10 flex flex-col gap-16 max-w-[1400px] mx-auto">
                <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-16 border-b border-outline-variant/20 pb-16">
                    <div className="flex-1">
                        <span className="text-[10px] text-primary font-black uppercase tracking-[0.5em] mb-6 block font-label italic">Equity Intelligence Matrix</span>
                        <h1 className="text-6xl sm:text-8xl lg:text-9xl font-headline font-bold tracking-tighter leading-none group uppercase italic">
                            Consensus <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Engine</span>
                        </h1>
                    </div>

                    <div className="flex shrink-0">
                        <button 
                            onClick={() => dispatch(clearStockCompare())}
                            className="px-10 py-5 rounded-[1.5rem] bg-surface-container-lowest border border-outline-variant/20 text-slate-400 font-black text-[10px] uppercase tracking-[0.3em] hover:bg-error hover:text-white hover:border-error transition-all flex items-center gap-6 shadow-xl group font-label"
                        >
                            <span className="material-symbols-outlined text-xl group-hover:rotate-180 transition-transform">delete_sweep</span>
                            Purge Matrix
                        </button>
                    </div>
                </header>

                {comparisonError && (
                    <div className="p-12 bg-error/5 border border-error/20 rounded-[2.5rem] text-error font-black uppercase tracking-[0.3em] text-center shadow-2xl font-label flex flex-col items-center gap-6">
                        <div className="w-14 h-14 rounded-full bg-error/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-2xl">warning</span>
                        </div>
                        <span className="text-sm">System Malfunction: {comparisonError}</span>
                    </div>
                )}

                <AnimatePresence>
                    {comparisonLoading && (
                        <motion.div 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center justify-center py-40 bg-surface-container-lowest/40 rounded-[3rem] shadow-2xl"
                        >
                            <div className="w-20 h-20 border-2 border-primary border-t-transparent rounded-full animate-spin mb-10 shadow-[0_0_60px_rgba(233,195,73,0.1)]"></div>
                            <p className="text-primary font-black uppercase tracking-[0.6em] animate-pulse text-xs italic font-label">Synchronizing Neural Vectors...</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {!comparisonLoading && comparisonResult?.length > 0 && (
                    <motion.div 
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className="bg-surface-container-low rounded-[3rem] shadow-[0_32px_64px_rgba(0,0,0,0.4)] border border-outline-variant/10 overflow-hidden"
                    >
                        <div className="overflow-x-auto p-4">
                            <table className="w-full text-left table-fixed min-w-[1000px]">
                                <thead>
                                    <tr>
                                        <th className="w-1/4 p-6 border-b border-outline-variant/30"></th>
                                        {comparisonResult.map((stock) => (
                                            <th key={stock.symbol} className="w-1/4 p-6 border-b border-outline-variant/30 text-center relative group">
                                                <button 
                                                    onClick={() => dispatch(removeStockFromCompare(stock.symbol))}
                                                    className="absolute top-4 right-4 text-slate-500 hover:text-error transition-colors"
                                                >
                                                    <span className="material-symbols-outlined">cancel</span>
                                                </button>
                                                <div className="flex justify-center mb-6">
                                                    <div className="w-24 h-24 rounded-[1.5rem] flex items-center justify-center font-black text-3xl border border-primary text-primary shadow-[0_0_30px_rgba(233,195,73,0.15)] bg-primary/5 uppercase">
                                                        {stock.symbol.substring(0, 3)}
                                                    </div>
                                                </div>
                                                <h3 className="text-2xl font-headline font-bold text-white mb-2">{stock.symbol}</h3>
                                                <p className="text-xs text-slate-400 font-label tracking-widest uppercase">{stock.sector || 'Sector'}</p>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td colSpan={5} className="bg-surface/50 p-4 text-[10px] text-primary font-black uppercase tracking-[0.5em] text-center italic border-y border-outline-variant/20">Valuation & Profitability</td>
                                    </tr>
                                    {renderMetricRow("Current Price", "latest_close", false, true)}
                                    {renderMetricRow("P/E Ratio", "pe_ratio")}
                                    {renderMetricRow("P/B Ratio", "pb_ratio")}
                                    {renderMetricRow("Return on Equity (ROE)", "roe", true)}
                                    {renderMetricRow("Return on Capital (ROCE)", "roce", true)}
                                    
                                    <tr>
                                        <td colSpan={5} className="bg-surface/50 p-4 text-[10px] text-primary font-black uppercase tracking-[0.5em] text-center italic border-y border-outline-variant/20 mt-8">Growth & Margins</td>
                                    </tr>
                                    {renderMetricRow("Revenue Growth", "revenue_growth", true)}
                                    {renderMetricRow("PAT Growth", "pat_growth", true)}
                                    {renderMetricRow("PAT Margin", "pat_margin", true)}
                                    {renderMetricRow("EBITDA Margin", "ebitda_margin", true)}
                                    
                                    <tr>
                                        <td colSpan={5} className="bg-surface/50 p-4 text-[10px] text-primary font-black uppercase tracking-[0.5em] text-center italic border-y border-outline-variant/20 mt-8">Financial Health</td>
                                    </tr>
                                    {renderMetricRow("Debt to Equity", "debt_equity")}
                                    {renderMetricRow("Interest Coverage", "interest_coverage")}
                                    {renderMetricRow("Total Score", "total_score")}
                                </tbody>
                            </table>
                        </div>
                    </motion.div>
                )}
            </div>
        </div>
    );
};

export default StockCompare;
