import React from 'react';
import { useDispatch } from 'react-redux';
import { removeStockFromCompare } from '../../store/slices/stockCompareSlice';
import { motion } from 'framer-motion';

const StockComparisonTable = ({ comparisonResult }) => {
    const dispatch = useDispatch();

    if (!comparisonResult || comparisonResult.length === 0) return null;

    const renderMetricRow = (label, key, isPercentage = false, isCurrency = false, isRaw = false) => {
        return (
            <tr className="border-b border-outline-variant/10 hover:bg-white/[0.02] transition-colors group">
                <td className="p-4 pl-8 font-label text-[10px] text-slate-500 font-black tracking-widest uppercase italic group-hover:text-primary transition-colors">{label}</td>
                {comparisonResult?.map((stock, i) => {
                    const val = stock[key];
                    let display = "—";
                    
                    if (val != null) {
                        if (isRaw) display = val;
                        else if (isCurrency) display = `₹${val.toLocaleString()}`;
                        else if (isPercentage) display = `${parseFloat(val).toFixed(2)}%`;
                        else display = parseFloat(val).toFixed(2);
                    }

                    return (
                        <td key={`${stock.symbol}-${i}`} className="p-4 text-center">
                            <span className={`text-lg font-headline font-black tracking-tight uppercase italic group-hover:text-secondary/8 transition-colors ${key === 'rating_label' ? 'text-primary' : 'text-white'}`}>
                                {display}
                            </span>
                        </td>
                    );
                })}
            </tr>
        );
    };

    return (
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
                            {comparisonResult?.map((stock, i) => {
                                const colors = ['#4ade80', '#818cf8', '#fbbf24', '#fb7185'];
                                const accentColor = colors[i % colors.length];
                                
                                return (
                                    <th key={stock.symbol} className="w-1/4 p-0 border-b border-outline-variant/10 text-center relative overflow-hidden bg-surface-container-low">
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
                            <td colSpan={5} className="p-4 text-[9px] text-primary font-black uppercase tracking-[0.4em] text-center italic border-y border-outline-variant/10 group">Sovereign Rating & Scores</td>
                        </tr>
                        {renderMetricRow("Protocol Verdict", "rating_label", false, false, true)}
                        {renderMetricRow("Total Composite Score", "total_score")}
                        {renderMetricRow("Fundamental Strength", "fundamental_score")}
                        {renderMetricRow("Technical Momentum", "technical_score")}
                        {renderMetricRow("Valuation Identity", "valuation_score")}

                        <tr className="bg-white/[0.02]">
                            <td colSpan={5} className="p-4 text-[9px] text-primary font-black uppercase tracking-[0.4em] text-center italic border-y border-outline-variant/10 group">Valuation & Profitability</td>
                        </tr>
                        {renderMetricRow("Current Price", "latest_close", false, true)}
                        {renderMetricRow("Earnings Pulse (EPS)", "eps", false, true)}
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
                        {renderMetricRow("Interest Coverage", "interest_cov")}
                    </tbody>
                </table>
            </div>
        </motion.div>
    );
};

export default StockComparisonTable;
