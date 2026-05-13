import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Link } from 'react-router-dom';
import { clearCompare, fetchComparisonData, clearComparisonResult } from '../store/slices/compareSlice';
import { motion, AnimatePresence } from 'framer-motion';
import FundPicker from '../components/Compare/FundPicker';
import ComparisonTable from '../components/Compare/ComparisonTable';
import RecommendationPanel from '../components/Compare/RecommendationPanel';

const MFCompare = () => {
    const dispatch = useDispatch();
    const { 
        compareList, 
        comparisonResult, 
        comparisonLoading, 
        comparisonError 
    } = useSelector((state) => state.compare);

    useEffect(() => {
        if (compareList.length >= 2) {
            const codes = compareList.map(f => f.scheme_code);
            dispatch(fetchComparisonData(codes));
        } else {
            dispatch(clearComparisonResult());
        }
    }, [dispatch, compareList]);

    if (compareList.length < 2) {
        return (
            <div className="min-h-[85vh] w-full flex flex-col items-center justify-center p-8 bg-surface relative overflow-hidden">
                {/* Background Pattern */}
                <div className="absolute inset-0 opacity-[0.02] pointer-events-none">
                    <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/20 blur-[150px] rounded-full"></div>
                    <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-secondary/10 blur-[150px] rounded-full"></div>
                </div>

                <motion.div 
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="relative z-10 flex flex-col items-center text-center max-w-2xl px-6"
                >
                    <div className="w-20 h-20 rounded-3xl bg-surface-container-low ghost-border flex items-center justify-center mb-10 shadow-xl relative group">
                        <span className="material-symbols-outlined text-primary text-3xl group-hover:scale-110 transition-transform">lock_open</span>
                        <div className="absolute -top-1 -right-1 w-6 h-6 rounded-lg bg-error flex items-center justify-center border-2 border-surface shadow-lg">
                            <span className="material-symbols-outlined text-[10px] text-white">priority_high</span>
                        </div>
                    </div>
                    
                    <span className="font-label text-[10px] text-primary font-black uppercase tracking-[0.5em] mb-4 opacity-70 italic">Status: Access Restricted</span>
                    <h2 className="text-4xl sm:text-5xl font-headline font-bold text-white mb-6 uppercase tracking-tight italic leading-tight">
                        Insufficient <span className="text-primary/20 italic">Intelligence</span>
                    </h2>
                    <p className="text-slate-500 text-base font-medium tracking-tight mb-12 max-w-md leading-relaxed italic border-l-2 border-primary/20 pl-8 mx-auto">
                        A minimum of two identified asset artifacts are required to initialize the differential comparison matrix and activate AI consensus protocols.
                    </p>
                    
                    <Link to="/mf" className="group relative px-10 py-5 overflow-hidden rounded-2xl bg-surface-container-high border border-outline-variant/10 text-white font-black uppercase tracking-[0.2em] transition-all active:scale-95 flex items-center gap-4 font-label text-[11px] hover:border-primary/30">
                        <span className="relative z-10">Return to Wealth Vault</span>
                        <span className="material-symbols-outlined relative z-10 text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
                    </Link>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen p-4 md:p-8 lg:p-10 w-full animate-fadeIn transition-all duration-500 pb-32 overflow-hidden bg-surface">
            {/* Ambient Background */}
            <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary/5 blur-[120px] rounded-full pointer-events-none"></div>

            <div className="relative z-10 flex flex-col gap-16 max-w-[1600px] mx-auto">
                {/* Modern Compact Header */}
                <header className="flex flex-col md:flex-row md:items-center justify-between gap-8 border-b border-outline-variant/10 pb-10">
                    <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center border border-primary/20">
                                <span className="material-symbols-outlined text-primary text-lg">analytics</span>
                            </div>
                            <span className="text-[10px] text-primary font-black uppercase tracking-[0.4em] font-label italic">Matrix Protocol v4.2</span>
                        </div>
                        <h1 className="text-4xl md:text-5xl font-headline font-bold tracking-tight leading-none group uppercase italic text-white mt-1">
                            Consensus <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Engine</span>
                        </h1>
                        <div className="flex items-center gap-4">
                            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-[0.3em] font-label flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>
                                System status: active surveillance enabled
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <button 
                            onClick={() => dispatch(clearCompare())}
                            className="px-6 py-3 rounded-xl bg-surface-container-low border border-outline-variant/10 text-slate-400 font-black text-[9px] uppercase tracking-[0.2em] hover:bg-error/10 hover:text-error hover:border-error/20 transition-all flex items-center gap-3 font-label"
                        >
                            <span className="material-symbols-outlined text-sm">delete_sweep</span>
                            Purge Matrix
                        </button>
                    </div>
                </header>

                {comparisonError && (
                    <div className="p-8 bg-error/5 border border-error/10 rounded-2xl text-error font-black uppercase tracking-[0.2em] text-center shadow-lg animate-shake font-label flex flex-col items-center gap-3">
                        <span className="text-[10px]">System Malfunction: {comparisonError}</span>
                    </div>
                )}

                {/* Section A: Selection Matrix */}
                <FundPicker />

                {/* Loading State Overlay for Matrix */}
                <AnimatePresence>
                    {comparisonLoading && (
                        <motion.div 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center justify-center py-32 bg-surface-container-low/50 rounded-3xl border border-outline-variant/10 shadow-2xl backdrop-blur-md"
                        >
                            <div className="w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin mb-6"></div>
                            <p className="text-primary font-black uppercase tracking-[0.4em] animate-pulse text-[10px] italic font-label">Synchronizing Neural Vectors...</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Section B & C: Analysis & Recommendation */}
                {!comparisonLoading && comparisonResult && (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col gap-20"
                    >
                        <ComparisonTable 
                            funds={comparisonResult.funds} 
                            ranking={comparisonResult.ranking} 
                        />
                        
                        <RecommendationPanel 
                            recommendation={comparisonResult.recommendation} 
                            funds={comparisonResult.funds}
                        />
                    </motion.div>
                )}

                {/* Compact Footer */}
                <footer className="mt-10 pt-8 border-t border-outline-variant/5 opacity-50 italic text-[9px] tracking-[0.4em] uppercase font-black text-center leading-relaxed font-label">
                     Protocol: COMP-ELITE-X9 • Sovereign Analysis Enabled • Neural Logic Epoch {new Date().getFullYear()}
                </footer>
            </div>
        </div>

    );
};

export default MFCompare;
