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
        <section className="mb-20 animate-fadeInUp">
            <header className="mb-12">
                <span className="text-[10px] text-primary font-black uppercase tracking-[0.4em] mb-4 block font-label">Deployment Phase B</span>
                <h2 className="text-5xl sm:text-6xl font-headline font-bold text-white tracking-tighter uppercase italic leading-none">
                    Analytical <span className="text-primary/40 italic">Ledger</span>
                </h2>
                <div className="flex items-center gap-6 mt-4">
                    <div className="h-[1px] w-16 bg-[#45464c]/30"></div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em] font-label">Matrix Intelligence Protocol Active</span>
                </div>
            </header>

            <div className="relative overflow-hidden rounded-[2.5rem] ghost-border bg-[#0f1419] shadow-[0_64px_128px_rgba(0,0,0,0.4)]">
                <div className="overflow-x-auto no-scrollbar">
                    <table className="w-full border-collapse min-w-[1000px]">
                        <thead>
                            <tr className="border-b-2 border-[#45464c]/10 bg-surface">
                                <th className="sticky left-0 z-40 bg-surface p-10 text-left min-w-[300px] align-bottom">
                                    <span className="font-label text-[10px] uppercase tracking-[0.4em] text-primary/60 font-black">Instrument Details</span>
                                </th>
                                {funds.map((fund) => (
                                    <th key={fund.scheme_code} className="p-10 border-l border-[#45464c]/10 bg-surface-container-low/30 min-w-[250px]">
                                        <div className="flex flex-col items-center text-center">
                                            <div className="w-14 h-14 rounded-full bg-primary/5 flex items-center justify-center border border-primary/10 mb-6">
                                                <span className="material-symbols-outlined text-primary text-2xl">query_stats</span>
                                            </div>
                                            <h3 className="font-headline text-lg font-bold text-white tracking-tight leading-tight uppercase italic line-clamp-2">
                                                {fund.scheme_name}
                                            </h3>
                                            <p className="font-label text-[9px] text-slate-500 tracking-[0.3em] uppercase font-black mt-3">ID: {fund.scheme_code}</p>
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {metricGroups.map((group, gIdx) => (
                                <React.Fragment key={gIdx}>
                                    <tr className="bg-surface-container-lowest/40">
                                        <td colSpan={funds.length + 1} className="px-10 py-5 border-b border-[#45464c]/10">
                                            <span className="font-headline font-black text-primary text-xs uppercase tracking-[0.4em] italic opacity-80">
                                                {gIdx + 1}. {group.title}
                                            </span>
                                        </td>
                                    </tr>
                                    {group.metrics.map((metric, mIdx) => (
                                        <tr key={mIdx} className="group hover:bg-surface-container-high/20 transition-colors">
                                            <td className="sticky left-0 z-30 bg-surface p-10 font-label text-[11px] font-black text-slate-400 uppercase tracking-widest border-b border-[#45464c]/5">
                                                {metric.label}
                                            </td>
                                            {funds.map((fund) => {
                                                const val = getMetricValue(fund, metric.key);
                                                const best = isBest(fund.scheme_code, metric.key);
                                                const worst = isWorst(fund.scheme_code, metric.key);
                                                
                                                return (
                                                    <td 
                                                        key={fund.scheme_code} 
                                                        className={`p-10 text-center border-l border-[#45464c]/5 border-b border-[#45464c]/5 transition-all duration-500`}
                                                    >
                                                        <div className={`font-headline text-3xl font-black tracking-tighter ${best ? 'text-secondary drop-shadow-[0_0_15px_rgba(102,221,139,0.3)]' : worst ? 'text-error opacity-40' : 'text-white'}`}>
                                                            {val !== 'N/A' ? `${val}${metric.unit}` : val}
                                                        </div>
                                                        {best && (
                                                            <div className="mt-3 inline-flex items-center gap-2 bg-secondary/10 px-3 py-1 rounded-full border border-secondary/20">
                                                                <span className="material-symbols-outlined text-[10px] text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
                                                                <span className="text-[9px] font-black text-secondary tracking-widest uppercase">OPTIMAL</span>
                                                            </div>
                                                        )}
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
            
            <div className="mt-12 flex justify-center gap-12 font-label">
                <div className="flex items-center gap-4">
                    <div className="w-2.5 h-2.5 rounded-full bg-secondary shadow-[0_0_10px_rgba(102,221,139,0.5)]"></div>
                    <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Sovereign Peak</span>
                </div>
                <div className="flex items-center gap-4">
                    <div className="w-2.5 h-2.5 rounded-full bg-error opacity-30"></div>
                    <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Risk Floor</span>
                </div>
            </div>
        </section>
    );
};

export default ComparisonTable;
