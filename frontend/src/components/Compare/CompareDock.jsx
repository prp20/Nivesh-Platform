import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { removeFromCompare, clearCompare } from '../../store/slices/compareSlice';

const CompareDock = () => {
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const { compareList } = useSelector((state) => state.compare);

    if (compareList.length === 0) return null;

    return (
        <AnimatePresence>
            <motion.div 
                initial={{ y: 200, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 200, opacity: 0 }}
                className="fixed bottom-12 left-1/2 -translate-x-1/2 z-[100] w-full max-w-6xl px-6"
            >
                <div className="glass-panel p-8 rounded-[3rem] border border-primary/20 shadow-[0_-32px_64px_rgba(0,0,0,0.5)] flex flex-col md:flex-row items-center justify-between gap-12 bg-[#0f1419]/95 backdrop-blur-3xl">
                    <div className="flex items-center gap-8 flex-1 overflow-x-auto w-full no-scrollbar px-4">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-black text-primary uppercase tracking-[0.4em] leading-none mb-1">Matrix Active</span>
                            <span className="text-2xl font-black text-white tracking-widest uppercase">{compareList.length}/4</span>
                        </div>
                        <div className="h-10 w-px bg-white/10 mx-4 hidden md:block"></div>
                        <div className="flex gap-4">
                            {compareList.map((fund) => (
                                <motion.div 
                                    layout
                                    initial={{ scale: 0.8, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    key={fund.scheme_code}
                                    className="px-6 py-3 rounded-2xl bg-white/5 border border-white/5 flex items-center gap-4 group hover:border-primary/40 transition-all cursor-default whitespace-nowrap"
                                >
                                    <span className="text-[11px] font-black text-white/80 uppercase tracking-widest">{fund.scheme_name.substring(0, 15)}...</span>
                                    <button 
                                        onClick={() => dispatch(removeFromCompare(fund.scheme_code))}
                                        className="material-symbols-outlined text-slate-500 hover:text-error text-lg transition-colors"
                                    >
                                        close
                                    </button>
                                </motion.div>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center gap-8">
                        <button 
                            onClick={() => dispatch(clearCompare())}
                            className="px-8 py-4 rounded-xl text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 hover:text-error transition-all"
                        >
                            Purge All
                        </button>
                        <button 
                            onClick={() => navigate('/compare')}
                            disabled={compareList.length < 2}
                            className={`px-12 py-5 rounded-2xl gold-gradient text-on-primary font-black text-xs uppercase tracking-[0.3em] shadow-2xl transition-all active:scale-95 flex items-center gap-4 ${compareList.length < 2 ? 'opacity-30 grayscale cursor-not-allowed' : 'hover:brightness-110'}`}
                        >
                            <span className="material-symbols-outlined">analytics</span>
                            Initialize Comparison
                        </button>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};

export default CompareDock;
