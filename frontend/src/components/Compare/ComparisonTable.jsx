import React from 'react';
import { motion } from 'framer-motion';

const ComparisonTable = ({ funds, ranking }) => {
    if (!funds || funds.length === 0) return null;

    // Metric groups for organization
    const metricGroups = [
        {
            title: "Performance & Alpha",
            metrics: [
                { key: 'annualized_return_3y', label: '3-Year Annualized Return', unit: '%' },
                { key: 'annualized_return_5y', label: '5-Year Annualized Return', unit: '%' },
                { key: 'alpha', label: 'Alpha (Benchmark Outperformance)', unit: '%' },
                { key: 'beta', label: 'Beta (Market Sensitivity)', unit: '' },
                { key: 'sharpe_ratio', label: 'Sharpe Ratio (Risk-Adjusted)', unit: '' },
            ]
        },
        {
            title: "Risk & Volatility",
            metrics: [
                { key: 'standard_deviation', label: 'Standard Deviation', unit: '%' },
                { key: 'sortino_ratio', label: 'Sortino Ratio (Downside Risk)', unit: '' },
                { key: 'expense_ratio', label: 'Expense Ratio', unit: '%' },
            ]
        },
        {
            title: "Portfolio Valuation",
            metrics: [
                { key: 'aum', label: 'AUM (Asset Under Management)', unit: ' Cr' },
                { key: 'exit_load', label: 'Exit Load (Early Redemption)', unit: '%' },
            ]
        }
    ];

    const getMetricValue = (fund, key) => {
        const val = fund.metrics?.[key];
        return val !== undefined && val !== null ? val : 'N/A';
    };

    const isBest = (fundCode, metricKey) => ranking?.[metricKey]?.best === fundCode;
    const isWorst = (fundCode, metricKey) => ranking?.[metricKey]?.worst === fundCode;

    return (
        <section className="mb-12 animate-fadeIn">
            <header className="mb-8 flex flex-col gap-1">
                <div className="flex items-center gap-3">
                    <span className="text-[9px] text-primary font-black uppercase tracking-[0.4em] font-label">Phase B: Analytical Ledger</span>
                    <div className="h-[1px] w-12 bg-primary/20"></div>
                </div>
                <h2 className="text-3xl font-headline font-black text-white tracking-tight uppercase italic leading-none">
                    Intelligence <span className="text-primary/20 italic">Matrix</span>
                </h2>
            </header>

            <div className="relative overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-low shadow-xl">
                <div className="overflow-x-auto no-scrollbar">
                    <table className="w-full border-collapse min-w-[900px]">
                        <thead>
                            <tr className="border-b border-outline-variant/10 bg-surface-container-high/40">
                                <th className="sticky left-0 z-40 bg-surface-container-high p-6 text-left min-w-[280px] align-middle border-r border-outline-variant/10">
                                    <span className="font-label text-[9px] uppercase tracking-[0.3em] text-primary/60 font-black">Metric Category</span>
                                </th>
                                {funds.map((fund) => (
                                    <th key={fund.scheme_code} className="p-6 border-r border-outline-variant/10 bg-surface-container-low min-w-[220px]">
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="w-8 h-8 rounded-lg bg-primary/5 flex items-center justify-center border border-primary/10">
                                                <span className="material-symbols-outlined text-primary text-lg">query_stats</span>
                                            </div>
                                            <h3 className="font-headline text-sm font-bold text-white tracking-tight leading-tight uppercase italic line-clamp-1">
                                                {fund.scheme_name}
                                            </h3>
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {metricGroups.map((group, gIdx) => (
                                <React.Fragment key={gIdx}>
                                    <tr className="bg-surface-container-lowest/20">
                                        <td colSpan={funds.length + 1} className="px-6 py-3 border-b border-outline-variant/10">
                                            <span className="font-headline font-black text-primary text-[10px] uppercase tracking-[0.3em] italic opacity-80">
                                                {group.title}
                                            </span>
                                        </td>
                                    </tr>
                                    {group.metrics.map((metric, mIdx) => (
                                        <tr key={mIdx} className="group hover:bg-white/[0.02] transition-colors border-b border-outline-variant/5">
                                            <td className="sticky left-0 z-30 bg-surface-container-low p-6 font-label text-[10px] font-black text-slate-400 uppercase tracking-widest border-r border-outline-variant/10">
                                                {metric.label}
                                            </td>
                                            {funds.map((fund) => {
                                                const val = getMetricValue(fund, metric.key);
                                                const best = isBest(fund.scheme_code, metric.key);
                                                const worst = isWorst(fund.scheme_code, metric.key);
                                                
                                                return (
                                                    <td 
                                                        key={fund.scheme_code} 
                                                        className="p-6 text-center border-r border-outline-variant/10"
                                                    >
                                                        <div className="flex flex-col items-center gap-1">
                                                            <div className={`font-headline text-2xl font-black tracking-tight ${best ? 'text-secondary' : worst ? 'text-error opacity-40' : 'text-white'}`}>
                                                                {val !== 'N/A' ? `${val}${metric.unit}` : val}
                                                            </div>
                                                            {best && (
                                                                <div className="flex items-center gap-1 bg-secondary/10 px-2 py-0.5 rounded border border-secondary/20">
                                                                    <span className="text-[8px] font-black text-secondary tracking-widest uppercase font-label">OPTIMAL</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    ))}
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div className="mt-8 flex justify-center gap-10 font-label">
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-secondary"></div>
                    <span className="text-[8px] font-black text-slate-500 uppercase tracking-[0.2em]">Peak Performance</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-error opacity-30"></div>
                    <span className="text-[8px] font-black text-slate-500 uppercase tracking-[0.2em]">Risk Floor</span>
                </div>
            </div>
        </section>

    );
};

export default ComparisonTable;
