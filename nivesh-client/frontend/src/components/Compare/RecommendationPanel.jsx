import React from 'react';
import { motion } from 'framer-motion';

const RecommendationPanel = ({ recommendation, funds }) => {
    if (!recommendation) return null;

    const recommendedFund = funds.find(f => f.scheme_code === recommendation.best_fund);
    if (!recommendedFund) return null;

    // Simple Radar Chart Component
    const RadarChart = ({ data, dimensions }) => {
        const size = 300;
        const center = size / 2;
        const radius = size * 0.4;
        const angleStep = (Math.PI * 2) / dimensions.length;

        const getPoint = (dimIdx, score) => {
            const angle = dimIdx * angleStep - Math.PI / 2;
            const r = (score / 100) * radius;
            return {
                x: center + r * Math.cos(angle),
                y: center + r * Math.sin(angle)
            };
        };

        return (
            <div className="relative w-[300px] h-[300px] mx-auto">
                <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
                    {/* Background Grid */}
                    {[20, 40, 60, 80, 100].map((level, i) => (
                        <circle 
                            key={i}
                            cx={center} 
                            cy={center} 
                            r={(level / 100) * radius} 
                            fill="none" 
                            stroke="rgba(69, 70, 76, 0.15)" 
                            strokeWidth="1"
                        />
                    ))}

                    {/* Axis lines */}
                    {dimensions.map((dim, i) => {
                        const point = getPoint(i, 100);
                        return (
                            <line 
                                key={i}
                                x1={center} 
                                y1={center} 
                                x2={point.x} 
                                y2={point.y} 
                                stroke="rgba(69, 70, 76, 0.15)" 
                                strokeWidth="1"
                            />
                        );
                    })}

                    {/* Data Polygons */}
                    {data.map((item, idx) => {
                        const points = dimensions.map((dim, i) => {
                            const score = item.scores[dim.key] || 0;
                            const p = getPoint(i, score);
                            return `${p.x},${p.y}`;
                        }).join(' ');

                        const isBest = item.scheme_code === recommendation.best_fund;

                        return (
                            <motion.polygon 
                                key={idx}
                                initial={{ opacity: 0, scale: 0.8 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: 0.5 + idx * 0.1 }}
                                points={points}
                                fill={isBest ? 'rgba(102, 221, 139, 0.15)' : 'rgba(233, 195, 73, 0.05)'}
                                stroke={isBest ? '#66dd8b' : '#e9c349'}
                                strokeWidth={isBest ? '3' : '1.5'}
                                className="transition-all duration-500"
                            />
                        );
                    })}
                </svg>
                
                {/* Labels */}
                {dimensions.map((dim, i) => {
                    const point = getPoint(i, 115);
                    return (
                        <div 
                            key={i}
                            className="absolute text-[9px] font-black uppercase tracking-widest text-slate-600 whitespace-nowrap text-center -translate-x-1/2 -translate-y-1/2 font-label"
                            style={{ left: point.x, top: point.y }}
                        >
                            {dim.label}
                        </div>
                    );
                })}
            </div>
        );
    };

    const chartDimensions = [
        { key: 'annualized_return_3y', label: 'Returns (3Y)' },
        { key: 'alpha', label: 'Alpha' },
        { key: 'sharpe_ratio', label: 'Sharpe' },
        { key: 'standard_deviation', label: 'Volatility' },
        { key: 'expense_ratio', label: 'Efficiency' },
    ];

    return (
        <section className="mb-12 animate-fadeIn">
            <header className="mb-8 flex flex-col gap-1">
                <div className="flex items-center gap-3">
                    <span className="text-[9px] text-secondary font-black uppercase tracking-[0.4em] font-label italic">Phase C: Strategic Intelligence</span>
                    <div className="h-[1px] w-12 bg-secondary/20"></div>
                </div>
                <h2 className="text-3xl font-headline font-black text-white tracking-tight uppercase italic leading-none">
                    AI <span className="text-secondary/20 italic">Consensus</span>
                </h2>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                {/* Executive Summary Card */}
                <div className="lg:col-span-8 bg-surface-container-low border border-outline-variant/10 p-8 rounded-2xl relative overflow-hidden group flex flex-col shadow-lg">
                    <div className="absolute -right-10 -top-10 w-40 h-40 bg-secondary/5 rounded-full blur-[60px] group-hover:bg-secondary/10 transition-all duration-700"></div>
                    
                    <div className="relative z-10 flex flex-col h-full">
                        <div className="flex items-center gap-3 mb-6">
                            <span className="material-symbols-outlined text-secondary text-base" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                            <h3 className="font-headline text-lg font-bold tracking-tight text-white uppercase italic">Executive Summary</h3>
                        </div>

                        <p className="text-base sm:text-lg text-on-surface-variant leading-relaxed font-light italic mb-8 flex-1 border-l border-secondary/20 pl-6 ml-1">
                           "{recommendation.reason}"
                        </p>

                        <div className="flex items-center gap-4 pt-6 border-t border-outline-variant/5">
                            <div className="flex -space-x-2">
                                {[1, 2].map(i => (
                                    <div key={i} className="w-8 h-8 rounded-full border-2 border-surface bg-surface-container-high flex items-center justify-center text-[8px] font-black text-slate-500 font-label">
                                        AN
                                    </div>
                                ))}
                            </div>
                            <span className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-500 font-label">Verified by Nivesh Elite Matrix</span>
                        </div>
                    </div>
                </div>

                {/* Alpha Signal Card */}
                <div className="lg:col-span-4 bg-primary p-8 rounded-2xl flex flex-col justify-between overflow-hidden relative group shadow-xl border border-primary/20">
                    <div className="relative z-10">
                        <span className="text-[8px] uppercase font-black tracking-[0.3em] text-on-primary/60 block mb-2 font-label">Actionable Signal</span>
                        <h3 className="text-on-primary font-headline text-2xl font-black leading-tight uppercase italic tracking-tight">Execute Deployment?</h3>
                    </div>

                    <button className="relative z-10 mt-6 w-full bg-white text-primary font-black py-3 rounded-xl flex items-center justify-center gap-3 hover:shadow-2xl transition-all active:scale-[0.98] group/btn">
                        <span className="font-label text-xs uppercase tracking-widest">Execute Load</span>
                        <span className="material-symbols-outlined text-sm group-hover/btn:translate-x-1 transition-transform">trending_up</span>
                    </button>

                    <div className="absolute -bottom-6 -right-6 opacity-10 pointer-events-none">
                        <span className="material-symbols-outlined text-8xl font-thin">payments</span>
                    </div>
                </div>
            </div>

            {/* Radar Analysis Section */}
            <div className="mt-6 bg-surface-container-low border border-outline-variant/10 p-8 rounded-2xl flex flex-col md:flex-row items-center gap-12 shadow-lg">
                 <div className="flex-1">
                     <div className="inline-flex items-center gap-3 bg-secondary/10 border border-secondary/20 px-4 py-1.5 rounded-lg mb-6">
                        <span className="material-symbols-outlined text-secondary text-base">psychology</span>
                        <span className="text-[9px] font-black text-secondary uppercase tracking-[0.2em] font-label">Vector Analysis</span>
                    </div>
                    <h3 className="text-xl font-headline font-black text-white uppercase italic mb-4 tracking-tight">Performance <span className="text-secondary/20">Fingerprint</span></h3>
                    <p className="text-slate-500 text-sm font-medium leading-relaxed max-w-md italic">
                        Multidimensional efficiency matrix. The <span className="text-secondary font-bold">Emerald Vector</span> represents the optimal candidate across returns, risk, and stability.
                    </p>
                 </div>
                 
                 <div className="relative flex flex-col items-center">
                    <RadarChart 
                        data={recommendation.score_breakdown} 
                        dimensions={chartDimensions}
                    />
                    
                    <div className="mt-6 flex flex-wrap justify-center gap-4">
                        {funds.map((fund) => (
                            <div key={fund.scheme_code} className="flex items-center gap-2">
                                <div className={`w-1.5 h-1.5 rounded-full ${fund.scheme_code === recommendation.best_fund ? 'bg-secondary' : 'bg-primary/30'}`}></div>
                                <span className={`text-[8px] font-black uppercase tracking-[0.2em] font-label ${fund.scheme_code === recommendation.best_fund ? 'text-white' : 'text-slate-600'}`}>
                                    {fund.scheme_name.substring(0, 10)}...
                                </span>
                            </div>
                        ))}
                    </div>
                 </div>
            </div>
        </section>

    );
};

export default RecommendationPanel;
