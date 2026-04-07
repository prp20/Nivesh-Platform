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
            <div className="min-h-[85vh] w-full flex flex-col items-center justify-center p-12 bg-surface">
                <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.03]">
                    <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none select-none">Sovereign</span>
                </div>
                
                <motion.div 
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="relative z-10 flex flex-col items-center text-center max-w-4xl"
                >
                    <div className="w-32 h-32 rounded-[2.5rem] bg-surface-container-lowest ghost-border flex items-center justify-center mb-16 shadow-2xl relative">
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
                        A minimum of two identified asset artifacts are required to initialize the differential comparison matrix and activate AI consensus protocols.
                    </p>
                    
                    <Link to="/mf" className="group relative px-14 py-6 overflow-hidden rounded-2xl gold-leaf-gradient text-on-primary font-black uppercase tracking-[0.2em] shadow-[0_24px_48px_rgba(233,195,73,0.15)] transition-all active:scale-95 flex items-center gap-6 font-label text-sm">
                        <span className="relative z-10 transition-transform group-hover:-translate-x-2">Return to Resource Vault</span>
                        <span className="material-symbols-outlined relative z-10 group-hover:translate-x-2 transition-transform">arrow_forward</span>
                    </Link>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn transition-all duration-500 pb-60 overflow-hidden bg-surface">
            {/* Background Watermark */}
            <div className="absolute top-40 -left-20 pointer-events-none opacity-[0.02] select-none rotate-90 origin-top-left">
                <span className="text-[18vw] font-headline font-black uppercase tracking-tighter leading-none">The Ledger</span>
            </div>

            <div className="relative z-10 flex flex-col gap-24 max-w-[1400px] mx-auto">
                {/* Header - Ultra Scale */}
                <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-16 border-b border-[#45464c]/10 pb-16">
                    <div className="flex-1">
                        <span className="text-[10px] text-primary font-black uppercase tracking-[0.5em] mb-6 block font-label italic">Asymmetric Intelligence Matrix</span>
                        <h1 className="text-6xl sm:text-8xl lg:text-9xl font-headline font-bold tracking-tighter leading-none group uppercase italic">
                            Consensus <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Engine</span>
                        </h1>
                        <div className="flex items-center gap-6 mt-8">
                            <div className="h-[1px] w-20 bg-primary/20"></div>
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.4em] font-label">Status: Differential Analysis Engaged</span>
                        </div>
                    </div>

                    <div className="flex shrink-0">
                        <button 
                            onClick={() => dispatch(clearCompare())}
                            className="px-10 py-5 rounded-[1.5rem] bg-surface-container-lowest ghost-border text-slate-400 font-black text-[10px] uppercase tracking-[0.3em] hover:bg-error hover:text-white hover:border-error transition-all flex items-center gap-6 shadow-xl group font-label"
                        >
                            <span className="material-symbols-outlined text-xl group-hover:rotate-180 transition-transform">delete_sweep</span>
                            Purge Matrix
                        </button>
                    </div>
                </header>

                {comparisonError && (
                    <div className="p-12 bg-error/5 ghost-border rounded-[2.5rem] text-error font-black uppercase tracking-[0.3em] text-center shadow-2xl animate-shake font-label flex flex-col items-center gap-6">
                        <div className="w-14 h-14 rounded-full bg-error/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-2xl">warning</span>
                        </div>
                        <span className="text-sm">System Malfunction: {comparisonError}</span>
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
                            className="flex flex-col items-center justify-center py-40 bg-surface-container-lowest/40 rounded-[3rem] ghost-border shadow-2xl"
                        >
                            <div className="w-20 h-20 border-2 border-primary border-t-transparent rounded-full animate-spin mb-10 shadow-[0_0_60px_rgba(233,195,73,0.1)]"></div>
                            <p className="text-primary font-black uppercase tracking-[0.6em] animate-pulse text-xs italic font-label">Synchronizing Neural Vectors...</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Section B & C: Analysis & Recommendation */}
                {!comparisonLoading && comparisonResult && (
                    <motion.div 
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className="flex flex-col gap-32"
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

                {/* Footer Style Refined */}
                <footer className="mt-32 pt-20 border-t border-[#45464c]/10 opacity-30 italic text-[10px] tracking-[0.6em] uppercase font-black text-center leading-relaxed font-label">
                     Protocol: COMP-ELITE-X9 • Sovereign Analysis Enabled • Neural Logic Epoch {new Date().getFullYear()}
                </footer>
            </div>
        </div>
    );
};

export default MFCompare;
