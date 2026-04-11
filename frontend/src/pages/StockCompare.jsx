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
            <div className="min-h-[85vh] w-full flex flex-col items-center justify-center p-12 bg-surface relative overflow-hidden">
                {/* Background Ambient Decor */}
                <div className="absolute top-1/4 -right-20 w-96 h-96 bg-primary/5 rounded-full blur-[100px] pointer-events-none"></div>
                <div className="absolute bottom-1/4 -left-20 w-96 h-96 bg-primary/5 rounded-full blur-[100px] pointer-events-none"></div>

                <motion.div 
                    initial={{ scale: 0.95, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="relative z-10 flex flex-col items-center text-center max-w-2xl"
                >
                    <div className="w-24 h-24 rounded-2xl bg-surface-container-low border border-outline-variant/10 flex items-center justify-center mb-10 shadow-xl relative group">
                        <div className="absolute inset-0 bg-primary/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
                        <span className="material-symbols-outlined text-primary text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>analytics</span>
                    </div>
                    
                    <span className="font-label text-[9px] text-primary font-black uppercase tracking-[0.4em] mb-4 italic">Protocol: Initialization Pending</span>
                    <h2 className="text-4xl sm:text-5xl font-headline font-black text-white mb-6 uppercase tracking-tight italic leading-none">
                        Insufficient <span className="text-primary/20 italic">Intelligence</span>
                    </h2>
                    <p className="text-slate-500 text-base font-medium leading-relaxed italic mb-12 border-l-2 border-primary/20 pl-6 mx-auto max-w-lg">
                        A minimum of two stock symbols must be selected to initialize the differential comparison matrix and activate AI consensus protocols.
                    </p>
                    
                    <Link to="/stocks" className="group relative px-10 py-4 overflow-hidden rounded-xl bg-primary text-on-primary font-black uppercase tracking-[0.15em] shadow-lg shadow-primary/10 transition-all active:scale-95 flex items-center gap-4 font-label text-xs">
                        <span className="relative z-10">Return to Stock Vault</span>
                        <span className="material-symbols-outlined text-sm relative z-10 group-hover:translate-x-1 transition-transform">arrow_forward</span>
                    </Link>
                </motion.div>
            </div>
        );
    }

    const renderMetricRow = (label, key, isPercentage = false, isCurrency = false) => {
        return (
            <tr className="border-b border-outline-variant/10 hover:bg-white/[0.02] transition-colors group">
                <td className="p-4 pl-8 font-label text-[10px] text-slate-500 font-black tracking-widest uppercase italic group-hover:text-primary transition-colors">{label}</td>
                {comparisonResult?.map((stock, i) => {
                    const val = stock[key];
                    const display = val != null 
                        ? (isCurrency ? `₹${val.toLocaleString()}` : (isPercentage ? `${val.toFixed(2)}%` : val.toFixed(2)))
                        : "—";
                    return (
                        <td key={`${stock.symbol}-${i}`} className="p-4 text-center">
                            <span className="text-lg font-headline font-black text-white tracking-tight uppercase italic group-hover:text-secondary/80 transition-colors">
                                {display}
                            </span>
                        </td>
                    );
                })}
            </tr>
        );
    };

    return (
        <div className="relative min-h-screen p-6 md:p-12 lg:p-16 xl:p-24 w-full animate-fadeIn transition-all duration-500 pb-60 bg-surface">
            <div className="relative z-10 flex flex-col gap-12 max-w-[1400px] mx-auto">
                <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-8 border-b border-outline-variant/10 pb-12">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-[9px] text-primary font-black uppercase tracking-[0.4em] font-label italic">Phase B: Differential Analysis</span>
                            <div className="h-[1px] w-12 bg-primary/20"></div>
                        </div>
                        <h1 className="text-5xl sm:text-7xl font-headline font-black tracking-tight leading-none uppercase italic">
                            Consensus <span className="text-primary/10 italic">Engine</span>
                        </h1>
                    </div>

                    <div className="flex shrink-0">
                        <button 
                            onClick={() => dispatch(clearStockCompare())}
                            className="px-8 py-4 rounded-xl bg-surface-container-low border border-outline-variant/10 text-slate-500 font-black text-[9px] uppercase tracking-[0.2em] hover:bg-error hover:text-white hover:border-error transition-all flex items-center gap-4 shadow-lg group font-label"
                        >
                            <span className="material-symbols-outlined text-base group-hover:rotate-90 transition-transform">close</span>
                            Purge Matrix
                        </button>
                    </div>
                </header>

                {comparisonError && (
                    <div className="p-8 bg-error/5 border border-error/10 rounded-2xl text-error font-black uppercase tracking-[0.2em] text-center shadow-lg font-label flex flex-col items-center gap-4">
                        <span className="material-symbols-outlined text-2xl">warning</span>
                        <span className="text-[10px]">System Malfunction: {comparisonError}</span>
                    </div>
                )}

                <AnimatePresence>
                    {comparisonLoading && (
                        <motion.div 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center justify-center py-40"
                        >
                            <div className="w-16 h-16 border-2 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.1)]"></div>
                            <p className="text-primary font-black uppercase tracking-[0.4em] animate-pulse text-[10px] italic font-label">Synchronizing Neural Vectors...</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {!comparisonLoading && comparisonResult?.length > 0 && (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-surface-container-low rounded-2xl shadow-2xl border border-outline-variant/10 overflow-hidden"
                    >
                        <div className="overflow-x-auto">
                            <table className="w-full text-left table-fixed min-w-[1000px]">
                                <thead>
                                    <tr>
                                        <th className="w-1/4 p-8 border-b border-outline-variant/10"></th>
                                        {comparisonResult.map((stock, i) => {
                                            const colors = ['#4ade80', '#818cf8', '#fbbf24', '#fb7185'];
                                            const accentColor = colors[i % colors.length];
                                            
                                            return (
                                                <th key={stock.symbol} className="w-1/4 p-0 border-b border-outline-variant/10 text-center relative overflow-hidden bg-surface-container-low">
                                                    {/* Column Identification Accent */}
                                                    <div 
                                                        className="absolute top-0 left-0 right-0 h-1 z-50 transition-all duration-700"
                                                        style={{ backgroundColor: accentColor, boxShadow: `0 2px 10px ${accentColor}33` }}
                                                    ></div>

                                                    <button 
                                                        onClick={() => dispatch(removeStockFromCompare(stock.symbol))}
                                                        className="absolute top-4 right-4 text-slate-600 hover:text-error transition-colors z-10"
                                                    >
                                                        <span className="material-symbols-outlined text-base">close</span>
                                                    </button>

                                                    <div className="flex flex-col items-center gap-4 p-8 pt-10">
                                                        <div 
                                                            className="w-16 h-16 rounded-2xl flex items-center justify-center font-black text-xl border shadow-lg uppercase italic transition-all duration-700"
                                                            style={{ backgroundColor: `${accentColor}11`, borderColor: `${accentColor}22`, color: accentColor }}
                                                        >
                                                            {stock.symbol.substring(0, 3)}
                                                        </div>
                                                        <div className="flex flex-col items-center gap-1">
                                                            <h3 className="text-xl font-headline font-black text-white uppercase italic tracking-tight">{stock.symbol}</h3>
                                                            <p className="text-[9px] text-slate-500 font-black tracking-widest uppercase font-label opacity-40">{stock.sector || 'Sector'}</p>
                                                        </div>
                                                    </div>
                                                </th>
                                            );
                                        })}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="bg-white/[0.02]">
                                        <td colSpan={5} className="p-4 text-[9px] text-primary font-black uppercase tracking-[0.4em] text-center italic border-y border-outline-variant/10 group">Valuation & Profitability</td>
                                    </tr>
                                    {renderMetricRow("Current Price", "latest_close", false, true)}
                                    {renderMetricRow("P/E Ratio", "pe_ratio")}
                                    {renderMetricRow("P/B Ratio", "pb_ratio")}
                                    {renderMetricRow("Return on Equity (ROE)", "roe", true)}
                                    {renderMetricRow("Return on Capital (ROCE)", "roce", true)}
                                    
                                    <tr className="bg-white/[0.02]">
                                        <td colSpan={5} className="p-4 text-[9px] text-primary font-black uppercase tracking-[0.4em] text-center italic border-y border-outline-variant/10">Growth & Margins</td>
                                    </tr>
                                    {renderMetricRow("Revenue Growth", "revenue_growth", true)}
                                    {renderMetricRow("PAT Growth", "pat_growth", true)}
                                    {renderMetricRow("PAT Margin", "pat_margin", true)}
                                    {renderMetricRow("EBITDA Margin", "ebitda_margin", true)}
                                    
                                    <tr className="bg-white/[0.02]">
                                        <td colSpan={5} className="p-4 text-[9px] text-primary font-black uppercase tracking-[0.4em] text-center italic border-y border-outline-variant/10">Financial Health</td>
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
