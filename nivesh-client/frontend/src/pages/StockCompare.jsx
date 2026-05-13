import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchStockComparisonData, clearStockCompare, clearStockComparisonResult } from '../store/slices/stockCompareSlice';
import { motion, AnimatePresence } from 'framer-motion';
import StockPicker from '../components/Compare/StockPicker';
import StockComparisonTable from '../components/Compare/StockComparisonTable';

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
                    
                    <Link to="/stocks" className="group relative px-10 py-5 overflow-hidden rounded-2xl bg-surface-container-high border border-outline-variant/10 text-white font-black uppercase tracking-[0.2em] transition-all active:scale-95 flex items-center gap-4 font-label text-[11px] hover:border-primary/30">
                        <span className="relative z-10">Return to Equity Vault</span>
                        <span className="material-symbols-outlined text-sm relative z-10 group-hover:translate-x-1 transition-transform">arrow_forward</span>
                    </Link>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen p-6 md:p-12 lg:p-16 w-full animate-fadeIn transition-all duration-500 pb-60 bg-surface">
            {/* Ambient Background */}
            <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary/5 blur-[120px] rounded-full pointer-events-none"></div>

            <div className="relative z-10 flex flex-col gap-12 max-w-[1600px] mx-auto">
                <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-8 border-b border-outline-variant/10 pb-12">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-[9px] text-primary font-black uppercase tracking-[0.4em] font-label italic">Phase B: Differential Analysis</span>
                            <div className="h-[1px] w-12 bg-primary/20"></div>
                        </div>
                        <h1 className="text-5xl md:text-6xl font-headline font-black tracking-tight leading-none uppercase italic text-white">
                            Consensus <span className="text-primary/10 italic">Engine</span>
                        </h1>
                        <p className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em] font-label mt-4 flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>
                            System status: equity surveillance active
                        </p>
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

                {/* Section A: Selection Matrix */}
                <StockPicker />

                <AnimatePresence>
                    {comparisonLoading && (
                        <motion.div 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center justify-center py-40 bg-surface-container-low/50 rounded-3xl border border-outline-variant/10 shadow-2xl backdrop-blur-md"
                        >
                            <div className="w-16 h-16 border-2 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.1)]"></div>
                            <p className="text-primary font-black uppercase tracking-[0.4em] animate-pulse text-[10px] italic font-label">Synchronizing Neural Vectors...</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {!comparisonLoading && comparisonResult?.comparison && (
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <StockComparisonTable comparisonResult={comparisonResult.comparison} />
                    </motion.div>
                )}

                {/* Compact Footer */}
                <footer className="mt-20 pt-8 border-t border-outline-variant/5 opacity-50 italic text-[9px] tracking-[0.4em] uppercase font-black text-center leading-relaxed font-label">
                     Protocol: STOCK-ELITE-V2 • Sovereign Surveillance Enabled • Neural Logic Epoch {new Date().getFullYear()}
                </footer>
            </div>
        </div>
    );
};

export default StockCompare;
