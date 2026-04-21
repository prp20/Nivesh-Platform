import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchDashboardData } from '../store/slices/dashboardSlice';
import { fetchIndices } from '../store/slices/indicesSlice';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';

const Dashboard = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { data: dashboardData, loading: dashLoading } = useSelector((state) => state.dashboard);
    const { items: indices, loading: indicesLoading } = useSelector((state) => state.indices);

    useEffect(() => {
        dispatch(fetchDashboardData());
        dispatch(fetchIndices({ skip: 0, limit: 100 }));
    }, [dispatch]);

    // Filter for requested: Sensex, Nifty 100, Nifty Midcap 150
    const targetIndices = indices.filter(idx => 
        idx.benchmark_code === 'SENSEX' || 
        idx.benchmark_code === 'NIFTY100' ||
        idx.benchmark_code === 'NIFTYMIDCAP150'
    ).slice(0, 3);

    // High-Fidelity UI Fallbacks if data is missing
    const displayIndices = targetIndices.length > 0 ? targetIndices : [
        { 
            benchmark_name: 'S&P BSE SENSEX', 
            ticker: 'SENSEX', 
            latest_close: 74248.22, 
            displayMetrics: { nav: '74,248.22', change: '+0.34%', status: 'ACTIVE' } 
        },
        { 
            benchmark_name: 'NIFTY 100', 
            ticker: 'NIF100', 
            latest_close: 24812.15, 
            displayMetrics: { nav: '24,812.15', change: '+0.42%', status: 'ACTIVE' } 
        },
        { 
            benchmark_name: 'NIFTY MIDCAP 150', 
            ticker: 'MID150', 
            latest_close: 18452.90, 
            displayMetrics: { nav: '18,452.90', change: '-0.12%', status: 'ACTIVE' } 
        }
    ];

    const data = dashboardData || {
        portfolioValue: 48210950, // Updated to match v2 design sample
        growthPercent: 12.4,
    };

    if (dashLoading) {
        return (
            <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#0f1419]">
                <div className="w-12 h-12 border-2 border-[#e9c349] border-t-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    return (
        <div className="text-[#dee3ea] font-body overflow-x-hidden selection:bg-[#e9c349]/30">
            {/* Design System v2: Sovereign Gateway - Nivesh Platform */}
            
            <div className="px-6 md:px-12 pt-12 pb-24">
                
                {/* 1. Hero Section - Welcome to Nivesh Platform */}
                <section className="grid grid-cols-12 gap-8 items-center mb-32">
                    <motion.div 
                        initial={{ opacity: 0, x: -50 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="col-span-12 lg:col-span-7"
                    >
                        <span className="font-label text-[#e9c349] text-xs uppercase tracking-[0.4em] mb-6 block font-black">The Sovereign Gateway</span>
                        <h1 className="font-headline text-[3rem] sm:text-[4rem] md:text-[5rem] lg:text-[6rem] xl:text-[7.5rem] leading-[0.9] font-black tracking-tighter mb-8 text-white uppercase italic">
                            Welcome to <br />
                            Nivesh Platform<span className="text-[#e9c349] not-italic">.</span>
                        </h1>
                        <p className="font-headline text-2xl text-slate-400 font-light max-w-xl mb-12 leading-relaxed">
                            Wealth management so smooth, it’s almost unfair.
                        </p>
                        <div className="flex gap-6">
                            <Link to="/stocks" className="bg-gradient-to-r from-[#e9c349] to-[#9d7e00] text-black px-10 py-5 rounded-md font-label uppercase tracking-widest text-xs font-black shadow-2xl hover:opacity-90 transition-all active:scale-95">
                                Explore Alpha
                            </Link>
                            <button className="border border-white/10 text-white px-10 py-5 rounded-md font-label uppercase tracking-widest text-xs font-black hover:bg-white/5 transition-all">
                                View Institutions
                            </button>
                        </div>
                    </motion.div>

                    <motion.div 
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="col-span-12 lg:col-span-5 relative hidden lg:block"
                    >
                        <div className="absolute inset-0 bg-[#e9c349]/5 blur-[120px] rounded-full"></div>
                        <div className="relative bg-[#171c21]/60 backdrop-blur-3xl p-10 rounded-2xl border border-white/5 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.5)]">
                            <div className="flex justify-between items-center mb-10">
                                <div>
                                    <p className="font-label text-[10px] text-slate-500 uppercase tracking-[0.3em] font-black mb-2">Total Sovereign Assets</p>
                                    <h2 className="font-headline text-5xl font-black text-white mt-1 tracking-tighter">
                                        ₹ {data.portfolioValue.toLocaleString('en-IN')}
                                    </h2>
                                </div>
                                <div className="bg-[#66dd8b]/10 p-4 rounded-full shadow-[0_0_20px_rgba(102,221,139,0.1)]">
                                    <span className="material-symbols-outlined text-[#66dd8b] text-3xl">trending_up</span>
                                </div>
                            </div>
                            <div className="space-y-8">
                                <div className="flex justify-between items-end border-b border-white/5 pb-4">
                                    <span className="font-label text-[10px] text-slate-500 uppercase tracking-widest font-black">24h Performance</span>
                                    <span className="text-[#66dd8b] font-headline font-black text-xl tracking-tighter">+₹ 12,400.00 (0.26%)</span>
                                </div>
                                <div className="h-32 w-full bg-gradient-to-t from-[#66dd8b]/5 to-transparent relative overflow-hidden rounded-xl">
                                    <svg className="absolute bottom-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 400 100">
                                        <motion.path 
                                            initial={{ pathLength: 0 }}
                                            animate={{ pathLength: 1 }}
                                            transition={{ duration: 2 }}
                                            d="M0,80 Q50,20 100,50 T200,30 T300,70 T400,10" 
                                            fill="none" 
                                            stroke="#66dd8b" 
                                            strokeWidth="3" 
                                        />
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </section>

                {/* 2. Market Pulse - Target Indices at Closing Price */}
                <section className="mb-32">
                    <div className="flex justify-between items-end mb-12 border-b border-white/5 pb-6">
                        <div>
                            <h3 className="font-headline text-4xl font-black mb-2 tracking-tighter uppercase">Market Pulse</h3>
                            <p className="font-label text-[10px] text-slate-500 uppercase tracking-[0.4em] font-black">Real-time Indian Sovereign Indices</p>
                        </div>
                        <div className="flex gap-3 items-center">
                            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#66dd8b] animate-pulse shadow-[0_0_15px_rgba(102,221,139,0.5)]"></span>
                            <span className="font-label text-[10px] text-[#66dd8b] uppercase tracking-[0.3em] font-black">Markets Open</span>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                        {displayIndices.map((idx, i) => (
                            <motion.div 
                                key={i}
                                whileHover={{ scale: 1.02 }}
                                className="bg-[#171c21]/40 backdrop-blur-xl p-8 rounded-xl border border-white/5 hover:border-[#e9c349]/20 transition-all group shadow-xl"
                            >
                                <div className="flex justify-between items-start mb-6">
                                    <span className="font-label text-[10px] text-slate-500 tracking-[0.3em] font-black uppercase">{idx.ticker || (idx.benchmark_code ? idx.benchmark_code.split('_')[0] : 'IDX')}</span>
                                    <span className={`font-headline font-black text-xl tracking-tighter ${idx.displayMetrics?.change?.startsWith('+') ? 'text-[#66dd8b]' : 'text-[#ffb4ab]'}`}>
                                        {idx.displayMetrics?.change || '+0.00%'}
                                    </span>
                                </div>
                                <div className="flex flex-col mb-6">
                                    <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-1">{idx.benchmark_name}</span>
                                    <div className="text-4xl font-black font-headline text-white tracking-tighter">
                                        {idx.latest_close ? idx.latest_close.toLocaleString('en-IN') : idx.displayMetrics?.nav}
                                    </div>
                                </div>
                                <div className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em] mb-4">Official Session Close</div>
                                <div className="h-16 w-full opacity-40">
                                    <svg className="w-full h-full" viewBox="0 0 100 40">
                                        <path 
                                            d="M0,35 L20,30 L40,32 L60,15 L80,18 L100,5" 
                                            fill="none" 
                                            stroke={idx.displayMetrics?.change?.startsWith('+') ? '#66dd8b' : '#ffb4ab'} 
                                            strokeWidth="2" 
                                        />
                                    </svg>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </section>

                {/* 3. Navigation Grid */}
                <section className="mb-32">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
                        {/* Elite Stocks */}
                        <motion.div 
                            onClick={() => navigate('/stocks')}
                            whileHover={{ y: -10 }} 
                            className="group relative aspect-[4/5] rounded-3xl overflow-hidden bg-[#171c21] border border-white/5 cursor-pointer shadow-2xl"
                        >
                            <img className="absolute inset-0 w-full h-full object-cover opacity-30 group-hover:scale-110 transition-transform duration-1000 grayscale group-hover:grayscale-0" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCYqNnYd03zIrlco-EF-yq5GR8N-YsGSxWfea4d7NoIpWklIB9BKWWLHJVZFdWWnyNRW80v3HVWRTlfgbxoGFOgZO06FV9hStk6C4wl3gTe8gODhn32ZxBuzNChy-q-vGFyljw2mUl2LHKgKEz00bpSZhEW2BikCiOlarFNE-lAuE2kpExq-Xx97aa4hQ89D21btN5z2wWqzueoC-UQcmQ57rK1FwOqUL82plTFAQfqCU73RoBkzcXOTCuThAo9wIlYwlZg-RrXJa7O" alt="Elite" />
                            <div className="absolute inset-0 bg-gradient-to-t from-[#0f1419] via-[#0f1419]/40 to-transparent"></div>
                            <div className="absolute bottom-0 p-10 w-full">
                                <span className="material-symbols-outlined text-[#e9c349] text-4xl mb-6">diamond</span>
                                <h4 className="font-headline text-4xl font-black text-white mb-4 tracking-tighter uppercase">Elite Stocks</h4>
                                <p className="text-slate-400 mb-8 leading-relaxed font-light">Access algorithmically curated equity baskets for the sophisticated investor.</p>
                                <div className="flex items-center justify-between">
                                    <span className="font-black text-[10px] text-[#e9c349] uppercase tracking-[0.2em]">+12.4% Average Alpha</span>
                                    <span className="material-symbols-outlined text-white group-hover:translate-x-3 transition-transform">arrow_forward</span>
                                </div>
                            </div>
                        </motion.div>

                        {/* Premium Funds */}
                        <motion.div 
                            onClick={() => navigate('/mf')}
                            whileHover={{ y: -10 }} 
                            className="group relative aspect-[4/5] rounded-3xl overflow-hidden bg-[#171c21] border border-white/5 cursor-pointer shadow-2xl"
                        >
                            <img className="absolute inset-0 w-full h-full object-cover opacity-30 group-hover:scale-110 transition-transform duration-1000 grayscale group-hover:grayscale-0" src="https://lh3.googleusercontent.com/aida-public/AB6AXuClQNFuPCTRO7K8cHuLLkZCub3xoTEvMHzSNdQ80YY0nVZatRSF2a5EFlTWf4LH7JO9vg27lEtHLJA8EGMpb9io0WjibPGCTH9b9cyqId7X8_3Sdv0t94uojKMcZ_PbMDjuTKonvDzxADYUzG-fR1_qZUK5r2cuxDJHgCO5p2x8ajTbTvrdhxZerFLMuc44VDCi3XQ5jaiJw6D1CxUKg-hxWkjyxUCMOgWziVJPZ5eaLwgXfxquUTUT_YD4bX0Fxgk8ECoitKyk9ljG" alt="Funds" />
                            <div className="absolute inset-0 bg-gradient-to-t from-[#0f1419] via-[#0f1419]/40 to-transparent"></div>
                            <div className="absolute bottom-0 p-10 w-full">
                                <span className="material-symbols-outlined text-[#e9c349] text-4xl mb-6">account_balance</span>
                                <h4 className="font-headline text-4xl font-black text-white mb-4 tracking-tighter uppercase">Premium Funds</h4>
                                <p className="text-slate-400 mb-8 leading-relaxed font-light">Institutional grade mutual funds and ETFs with zero hidden management fees.</p>
                                <div className="flex items-center justify-between">
                                    <span className="font-black text-[10px] text-[#e9c349] uppercase tracking-[0.2em]">98th Percentile Returns</span>
                                    <span className="material-symbols-outlined text-white group-hover:translate-x-3 transition-transform">arrow_forward</span>
                                </div>
                            </div>
                        </motion.div>

                        {/* Private Portfolio */}
                        <motion.div 
                            onClick={() => navigate('/portfolio')}
                            whileHover={{ y: -10 }} 
                            className="group relative aspect-[4/5] rounded-3xl overflow-hidden bg-[#171c21] border border-white/5 cursor-pointer shadow-2xl"
                        >
                            <img className="absolute inset-0 w-full h-full object-cover opacity-30 group-hover:scale-110 transition-transform duration-1000 grayscale group-hover:grayscale-0" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB7pBXaFi2OiEa2riLkzbONjiQIBdrfQK9UPgP90B31ArODKpIhyXn3T5Diea0vyL-z5FmTedCYCDGFPSmgrdAOKCMgMK-oFbvhczxC_db80bH7XZCIJ-fA61qJDcNvJMQTvqE_Rco3JlpnUEgCbI6sjuI9uTQ06akQQhiiJBEm0H6jFZJSRwU5hMFGL2zDBekbMFs5zAhFtJG-b_hRI6r03VUK8-x8zyLS98SljDZNNbkrGOJTMuZZ1B-IdRfbTw76kq4GKQz8TtdG" alt="Portfolio" />
                            <div className="absolute inset-0 bg-gradient-to-t from-[#0f1419] via-[#0f1419]/40 to-transparent"></div>
                            <div className="absolute bottom-0 p-10 w-full">
                                <span className="material-symbols-outlined text-[#e9c349] text-4xl mb-6">verified_user</span>
                                <h4 className="font-headline text-4xl font-black text-white mb-4 tracking-tighter uppercase">Private Vault</h4>
                                <p className="text-slate-400 mb-8 leading-relaxed font-light">Unified viewing of your entire net worth across all asset classes and custodians.</p>
                                <div className="flex items-center justify-between">
                                    <span className="font-black text-[10px] text-[#e9c349] uppercase tracking-[0.2em]">Zero-Latency Sync</span>
                                    <span className="material-symbols-outlined text-white group-hover:translate-x-3 transition-transform">arrow_forward</span>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                </section>

                {/* 4. Asset Allocation Bento */}
                <section className="grid grid-cols-12 gap-10 mb-32">
                    <div className="col-span-12 lg:col-span-8 bg-[#171c21]/60 backdrop-blur-3xl rounded-3xl p-12 border border-white/5 shadow-2xl relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-64 h-64 bg-[#e9c349]/5 blur-[100px] rounded-full"></div>
                        <div className="flex justify-between items-center mb-16">
                            <h3 className="font-headline text-3xl font-black uppercase tracking-tighter text-white">Top Asset Classes</h3>
                            <button className="font-label text-[10px] text-[#e9c349] tracking-[0.3em] uppercase font-black hover:underline">Full Analysis</button>
                        </div>
                        <div className="space-y-12">
                            {[
                                { label: "Small-Cap Alpha", value: 85, returns: "+34.2%", icon: "analytics" },
                                { label: "Sovereign Debt", value: 62, returns: "+12.8%", icon: "candlestick_chart" },
                                { label: "Digital Assets", value: 45, returns: "+9.1%", icon: "monetization_on" }
                            ].map((row, i) => (
                                <div key={i} className="grid grid-cols-12 items-center gap-6">
                                    <div className="col-span-4 flex items-center gap-6">
                                        <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center text-[#e9c349] shadow-inner">
                                            <span className="material-symbols-outlined text-2xl">{row.icon}</span>
                                        </div>
                                        <span className="font-headline font-black text-lg text-white uppercase tracking-tight">{row.label}</span>
                                    </div>
                                    <div className="col-span-6 h-2 bg-white/5 rounded-full overflow-hidden">
                                        <motion.div 
                                            initial={{ width: 0 }}
                                            animate={{ width: `${row.value}%` }}
                                            transition={{ delay: 0.5 + i * 0.2, duration: 1 }}
                                            className="h-full bg-gradient-to-r from-[#e9c349] to-[#9d7e00]"
                                        />
                                    </div>
                                    <div className="col-span-2 text-right">
                                        <span className="text-[#66dd8b] font-headline font-black text-xl tracking-tighter">{row.returns}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="col-span-12 lg:col-span-4 bg-gradient-to-br from-[#1b2025] to-[#0f1419] rounded-3xl p-12 border border-[#e9c349]/20 relative overflow-hidden shadow-2xl">
                        <div className="absolute top-0 right-0 w-48 h-48 bg-[#e9c349]/10 blur-[80px] rounded-full -mr-24 -mt-24"></div>
                        <h3 className="font-headline text-3xl font-black mb-8 tracking-tighter uppercase text-white">Market Insight</h3>
                        <p className="font-body text-slate-400 leading-relaxed mb-12 text-lg font-light italic">
                            "Institutional sentiment suggests a strong rotation toward energy and infrastructure in the coming quarter. Nivesh clients are currently 14% overweighted in these sectors."
                        </p>
                        <div className="flex items-center gap-6 mt-auto">
                            <div className="w-16 h-16 rounded-full border-2 border-[#e9c349] p-0.5 shadow-[0_0_15px_rgba(233,195,73,0.3)]">
                                <img 
                                    className="w-full h-full rounded-full object-cover" 
                                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuAnZrLVGWKfdmggTEcnXQy_M23D9FYb6S98i2s9oHMaMbHO15jBBtvDWVgxXMZCfB4RQKk2UgLT0sowVWl_fc0xsd7eTZq4ueW6F15Vz7Z-esTH2S627685tmuU_YdDprrJrjg7DpI6di4ODGEvrCtI2JkO2ys3g5VHchUAmCA-IadQR9fL1PayhSOik9f-B_4gH44xpqc8etV7EjYkpEz9r67qZvFym4OG7hl95iAjHinTyIpGl66K5YD4istmCinrzkxl24o3HA7P" 
                                    alt="CIO" 
                                />
                            </div>
                            <div>
                                <p className="font-headline font-black text-lg text-white tracking-tight uppercase">Vikram Malhotra</p>
                                <p className="font-label text-[10px] font-black uppercase text-slate-500 tracking-[0.3em]">Chief Investment Officer</p>
                            </div>
                        </div>
                    </div>
                </section>


            </div>
        </div>

    );
};

export default Dashboard;
