import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { addToCompare, removeFromCompare, fetchFundsByCategory } from '../../store/slices/compareSlice';
import toast from 'react-hot-toast';

const FundPicker = () => {
    const dispatch = useDispatch();
    const { compareList, selectedCategory, selectedSubcategory, categoryFunds, categoryFundsLoading } = useSelector((state) => state.compare);
    const [searchTerm, setSearchTerm] = useState('');
    const [showDropdown, setShowDropdown] = useState(false);

    useEffect(() => {
        if (selectedCategory && categoryFunds.length === 0) {
            dispatch(fetchFundsByCategory({ category: selectedCategory, limit: 100 }));
        }
    }, [dispatch, selectedCategory, categoryFunds.length]);

    const filteredFunds = categoryFunds.filter(fund => 
        fund.scheme_name.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !compareList.some(cf => cf.scheme_code === fund.scheme_code)
    );

    const handleAdd = (fund) => {
        if (compareList.length >= 4) {
            toast.error('Matrix capacity full (Max 4)');
            return;
        }
        dispatch(addToCompare(fund));
        setSearchTerm('');
        setShowDropdown(false);
        toast.success('Asset integrated into matrix');
    };

    return (
        <section className="mb-12">
            <header className="mb-8 flex flex-col gap-1">
                <div className="flex items-center gap-3">
                    <span className="text-[9px] text-primary font-black uppercase tracking-[0.4em] font-label">Phase A: Asset Assembly</span>
                    <div className="h-[1px] w-12 bg-primary/20"></div>
                </div>
                <h2 className="text-3xl font-headline font-black text-white tracking-tight uppercase italic leading-none">
                    Selection <span className="text-primary/20 italic">Matrix</span>
                </h2>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {/* Current Slots */}
                {[...Array(4)].map((_, i) => {
                    const fund = compareList[i];
                    const colors = ['#4ade80', '#818cf8', '#fbbf24', '#fb7185'];
                    const accentColor = colors[i % colors.length];

                    return (
                        <div key={i} className={`relative group h-44 rounded-2xl transition-all duration-300 flex flex-col items-center justify-center p-6 text-center ${fund ? 'bg-surface-container-low border border-outline-variant/10 shadow-lg' : 'bg-surface-container-lowest/30 border border-dashed border-outline-variant/10 hover:border-primary/20 hover:bg-surface-container-low/20'}`}>
                            {fund ? (
                                <motion.div 
                                    initial={{ scale: 0.95, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    className="w-full h-full flex flex-col items-center pt-2 relative"
                                >
                                    <div 
                                        className="absolute -top-6 left-1/2 -translate-x-1/2 h-1 w-12 rounded-full opacity-60 shadow-[0_0_15px_rgba(0,0,0,0.5)] transition-all duration-700"
                                        style={{ backgroundColor: accentColor, boxShadow: `0 -5px 20px ${accentColor}44` }}
                                    ></div>
                                    <div className="w-10 h-10 rounded-xl flex items-center justify-center border mb-4 transition-all duration-700" style={{ backgroundColor: `${accentColor}11`, borderColor: `${accentColor}22` }}>
                                        <span className="material-symbols-outlined text-xl" style={{ color: accentColor }}>query_stats</span>
                                    </div>
                                    <h4 className="text-[10px] font-label font-bold text-white leading-snug line-clamp-3 mb-1 px-2">{fund.scheme_name}</h4>
                                    <p className="font-label text-[8px] text-slate-500 tracking-[0.2em] uppercase font-black mb-4">ID: {fund.scheme_code}</p>
                                    
                                    <button 
                                        onClick={() => dispatch(removeFromCompare(fund.scheme_code))}
                                        className="mt-auto px-4 py-2 rounded-lg bg-error/5 border border-error/10 hover:bg-error/20 transition-all flex items-center gap-2 group/btn"
                                    >
                                        <span className="material-symbols-outlined text-[10px] text-error">close</span>
                                        <span className="text-[8px] font-black uppercase tracking-[0.3em] text-error font-label">Eject</span>
                                    </button>
                                </motion.div>
                            ) : (
                                <div className="text-slate-800 flex flex-col items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg border border-dashed border-outline-variant/20 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-lg opacity-20">add</span>
                                    </div>
                                    <p className="text-[8px] font-black uppercase tracking-[0.3em] opacity-30 italic font-label">Slot 0{i+1}</p>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Add Asset Search */}
            <AnimatePresence>
                {compareList.length < 4 && (
                    <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="relative max-w-xl mx-auto"
                    >
                        <div className="relative group">
                            <input 
                                type="text" 
                                placeholder="INJECT ADDITIONAL ASSET..."
                                value={searchTerm}
                                onChange={(e) => {
                                    setSearchTerm(e.target.value);
                                    setShowDropdown(true);
                                }}
                                onFocus={() => setShowDropdown(true)}
                                className="w-full bg-surface-container-low border border-outline-variant/10 rounded-xl px-12 py-5 text-xs font-bold text-white focus:outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/5 transition-all uppercase tracking-[0.15em] placeholder:text-slate-600 font-label italic"
                            />
                            <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-600 text-lg">search</span>
                            {searchTerm && (
                                <button 
                                    onClick={() => setSearchTerm('')}
                                    className="absolute right-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-600 hover:text-white transition-colors text-lg"
                                >
                                    close
                                </button>
                            )}
                        </div>

                        <AnimatePresence>
                            {showDropdown && (searchTerm.length > 0 || categoryFundsLoading) && (
                                <motion.div 
                                    initial={{ opacity: 0, scale: 0.98 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.98 }}
                                    className="absolute z-50 left-0 right-0 top-full mt-4 bg-surface-container-high border border-outline-variant/20 rounded-2xl shadow-2xl overflow-hidden max-h-[400px] overflow-y-auto no-scrollbar backdrop-blur-3xl"
                                >
                                    {categoryFundsLoading ? (
                                        <div className="p-10 text-center">
                                            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                                            <p className="text-[9px] font-black text-primary uppercase tracking-[0.4em] italic animate-pulse font-label">Syncing...</p>
                                        </div>
                                    ) : filteredFunds.length > 0 ? (
                                        <div className="p-2">
                                            {filteredFunds.slice(0, 10).map((fund) => (
                                                <button 
                                                    key={fund.scheme_code}
                                                    onClick={() => handleAdd(fund)}
                                                    className="w-full text-left p-4 hover:bg-white/[0.03] rounded-xl transition-all group flex items-center justify-between border border-transparent hover:border-white/5 active:scale-[0.99]"
                                                >
                                                    <div className="flex flex-col gap-1">
                                                        <div className="text-sm font-headline font-bold text-white group-hover:text-primary transition-colors uppercase italic tracking-tight">{fund.scheme_name}</div>
                                                        <div className="text-[9px] text-slate-500 font-black tracking-[0.2em] uppercase font-label">{fund.scheme_code}</div>
                                                    </div>
                                                    <div className="w-8 h-8 rounded-lg border border-outline-variant/10 flex items-center justify-center group-hover:bg-primary group-hover:border-primary transition-all">
                                                        <span className="material-symbols-outlined text-slate-500 text-sm group-hover:text-on-primary">add</span>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="p-12 text-center flex flex-col items-center gap-4">
                                            <span className="material-symbols-outlined text-4xl opacity-10">search_off</span>
                                            <p className="text-[9px] font-black uppercase tracking-[0.4em] opacity-40 italic font-label">No Matches Found</p>
                                        </div>
                                    )}
                                </motion.div>
                            )}
                        </AnimatePresence>
                        
                        {showDropdown && (
                            <div 
                                className="fixed inset-0 z-40" 
                                onClick={() => setShowDropdown(false)}
                            ></div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </section>

    );
};

export default FundPicker;
