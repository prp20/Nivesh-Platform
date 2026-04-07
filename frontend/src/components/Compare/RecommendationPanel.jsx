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
        <section className="mb-20 animate-fadeInUp">
            <header className="mb-12">
                <span className="text-[10px] text-secondary font-black uppercase tracking-[0.4em] mb-4 block font-label italic">Deployment Phase C</span>
                <h2 className="text-5xl sm:text-6xl font-headline font-bold text-white tracking-tighter uppercase italic leading-none">
                    Strategic <span className="text-secondary/40 italic">Intelligence</span>
                </h2>
                <div className="flex items-center gap-6 mt-4">
                    <div className="h-[1px] w-16 bg-[#45464c]/30"></div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em] font-label">AI Consensus Engine Active</span>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
                {/* Executive Summary Card (Lg: 8) */}
                <div className="lg:col-span-8 bg-surface-container-low/40 p-12 rounded-[3rem] ghost-border relative overflow-hidden group flex flex-col">
                    <div className="absolute -right-20 -top-20 w-80 h-80 bg-secondary/5 rounded-full blur-[80px] group-hover:bg-secondary/10 transition-all duration-700"></div>
                    
                    <div className="relative z-10 flex flex-col h-full">
                        <div className="flex items-center gap-4 mb-10">
                            <span className="material-symbols-outlined text-secondary opacity-60" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                            <h3 className="font-headline text-2xl font-bold tracking-tight text-white uppercase italic">Executive Summary</h3>
                        </div>

                        <p className="text-xl sm:text-2xl text-on-surface-variant leading-relaxed font-light italic mb-12 flex-1 border-l-2 border-secondary/20 pl-10 ml-2">
                           "{recommendation.reason}"
                        </p>

                        <div className="flex flex-wrap items-center gap-8 pt-10 border-t border-[#45464c]/15">
                            <div className="flex -space-x-4">
                                {[1, 2, 3].map(i => (
                                    <div key={i} className="w-12 h-12 rounded-full border-4 border-[#0f1419] bg-surface-container-highest overflow-hidden">
                                        <img className="w-full h-full object-cover grayscale opacity-60 hover:grayscale-0 hover:opacity-100 transition-all cursor-crosshair" src={`https://i.pravatar.cc/150?u=${i+10}`} alt="Analyst" />
                                    </div>
                                ))}
                                <div className="w-12 h-12 rounded-full border-4 border-[#0f1419] bg-surface-container-highest flex items-center justify-center text-[10px] font-black text-slate-500 font-label">+4</div>
                            </div>
                            <span className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 font-label">Verified by Nivesh Elite Analysis Board</span>
                        </div>
                    </div>
                </div>

                {/* Alpha Signal Card (Lg: 4) */}
                <div className="lg:col-span-4 gold-leaf-gradient rounded-[3rem] p-12 flex flex-col justify-between overflow-hidden relative group shadow-2xl">
                    <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    
                    <div className="relative z-10">
                        <span className="text-[9px] uppercase font-black tracking-[0.4em] text-on-primary/60 block mb-3 font-label">Alpha Signal Alpha</span>
                        <h3 className="text-on-primary font-headline text-4xl font-black leading-tight uppercase italic tracking-tighter">Ready to Deploy?</h3>
                        <p className="text-on-primary/70 mt-6 text-sm leading-relaxed font-medium">Execute a precision capital allocation to align your portfolio with these high-performance insights instantly.</p>
                    </div>

                    <button className="relative z-10 mt-10 w-full bg-on-primary text-primary font-black py-5 rounded-2xl flex items-center justify-center gap-4 hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] transition-all active:scale-[0.98] group/btn">
                        <span className="font-label text-xs uppercase tracking-widest">Execute Tactical Load</span>
                        <span className="material-symbols-outlined group-hover/btn:translate-x-2 transition-transform">trending_up</span>
                    </button>

                    {/* Decorative Background Icon */}
                    <div className="absolute -bottom-10 -right-10 opacity-20 transform rotate-12 pointer-events-none">
                        <span className="material-symbols-outlined text-[180px] font-thin" style={{ fontVariationSettings: "'wght' 100" }}>payments</span>
                    </div>
                </div>
            </div>

            {/* Radar Analysis Section */}
            <div className="mt-12 glass-panel p-16 rounded-[3rem] ghost-border flex flex-col md:flex-row items-center gap-16">
                 <div className="flex-1">
                     <div className="inline-flex items-center gap-4 bg-secondary/10 border border-secondary/20 px-6 py-2 rounded-full mb-8">
                        <span className="material-symbols-outlined text-secondary text-lg">psychology</span>
                        <span className="text-[10px] font-black text-secondary uppercase tracking-[0.3em] font-label">Neural Vector Analysis</span>
                    </div>
                    <h3 className="text-3xl font-headline font-black text-white uppercase italic mb-6 tracking-tight">Performance <span className="text-secondary/40">Fingerprint</span></h3>
                    <p className="text-slate-500 font-medium leading-relaxed max-w-xl">
                        A visual representation of the asset's multidimensional efficiency. The <span className="text-secondary font-bold">Emerald Vector</span> represents the optimal candidate across returns, risk, and structural efficiency.
                    </p>
                 </div>
                 
                 <div className="relative">
                    <RadarChart 
                        data={recommendation.score_breakdown} 
                        dimensions={chartDimensions}
                    />
                    
                    <div className="mt-10 flex flex-wrap justify-center gap-6">
                        {funds.map((fund) => (
                            <div key={fund.scheme_code} className="flex items-center gap-3">
                                <div className={`w-2.5 h-2.5 rounded-full ${fund.scheme_code === recommendation.best_fund ? 'bg-secondary drop-shadow-[0_0_8px_rgba(102,221,139,0.5)]' : 'bg-primary/30 opacity-40'}`}></div>
                                <span className={`text-[9px] font-black uppercase tracking-[0.3em] font-label ${fund.scheme_code === recommendation.best_fund ? 'text-white' : 'text-slate-600'}`}>
                                    {fund.scheme_name.substring(0, 15)}...
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
