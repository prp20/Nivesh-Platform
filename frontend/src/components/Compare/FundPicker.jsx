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
        <section className="mb-20">
            <header className="mb-12">
                <span className="text-[10px] text-primary font-black uppercase tracking-[0.4em] mb-4 block font-label">Deployment Phase A</span>
                <h2 className="text-5xl sm:text-6xl font-headline font-bold text-white tracking-tighter uppercase italic leading-none">
                    Selection <span className="text-primary/40 italic">Matrix</span>
                </h2>
                <div className="flex items-center gap-6 mt-4">
                    <div className="h-[1px] w-16 bg-[#45464c]/30"></div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em] font-label">
                        {selectedCategory} • {selectedSubcategory}
                    </span>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-12">
                {/* Current Slots */}
                {[...Array(4)].map((_, i) => {
                    const fund = compareList[i];
                    return (
                        <div key={i} className={`relative group h-60 rounded-[2.5rem] transition-all duration-500 flex flex-col items-center justify-center p-8 text-center ${fund ? 'bg-surface-container-low/50 ghost-border shadow-2xl' : 'bg-surface-container-lowest/40 border border-dashed border-[#45464c]/20 hover:border-primary/20'}`}>
                            {fund ? (
                                <motion.div 
                                    initial={{ scale: 0.9, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    className="w-full h-full flex flex-col items-center"
                                >
                                    <div className="w-14 h-14 rounded-full bg-primary/5 flex items-center justify-center border border-primary/10 mb-6">
                                        <span className="material-symbols-outlined text-primary text-2xl">query_stats</span>
                                    </div>
                                    <h4 className="text-lg font-headline font-bold text-white uppercase tracking-tight leading-tight line-clamp-2 italic mb-2">{fund.scheme_name}</h4>
                                    <p className="font-label text-[9px] text-slate-500 tracking-[0.3em] uppercase font-black mb-6">ID: {fund.scheme_code}</p>
                                    
                                    <button 
                                        onClick={() => dispatch(removeFromCompare(fund.scheme_code))}
                                        className="mt-auto inline-flex items-center gap-2 group/btn"
                                    >
                                        <span className="material-symbols-outlined text-sm text-slate-600 group-hover/btn:text-error transition-colors">close</span>
                                        <span className="text-[9px] font-black uppercase tracking-[0.4em] text-slate-600 group-hover/btn:text-error transition-colors font-label">Eject Asset</span>
                                    </button>
                                </motion.div>
                            ) : (
                                <div className="text-slate-800 flex flex-col items-center gap-5">
                                    <div className="w-12 h-12 rounded-full border border-dashed border-[#45464c]/40 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-2xl opacity-20">add</span>
                                    </div>
                                    <p className="text-[9px] font-black uppercase tracking-[0.4em] opacity-30 italic font-label">Matrix Slot 0{i+1}</p>
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
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="relative max-w-2xl mx-auto"
                    >
                        <div className="relative group">
                            <input 
                                type="text" 
                                placeholder="INJECT ADDITIONAL ASSET BY NAME..."
                                value={searchTerm}
                                onChange={(e) => {
                                    setSearchTerm(e.target.value);
                                    setShowDropdown(true);
                                }}
                                onFocus={() => setShowDropdown(true)}
                                className="w-full bg-surface-container-lowest/60 ghost-border rounded-2xl px-12 py-6 text-sm font-bold text-white focus:outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/5 transition-all uppercase tracking-[0.2em] placeholder:text-slate-700 font-label italic"
                            />
                            <span className="absolute left-12 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-700 font-thin scale-125">search</span>
                            {searchTerm && (
                                <button 
                                    onClick={() => setSearchTerm('')}
                                    className="absolute right-12 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-700 hover:text-white transition-colors"
                                >
                                    close
                                </button>
                            )}
                        </div>

                        <AnimatePresence>
                            {showDropdown && (searchTerm.length > 0 || categoryFundsLoading) && (
                                <motion.div 
                                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 10, scale: 0.98 }}
                                    className="absolute z-50 left-0 right-0 top-full mt-6 bg-[#0f1419]/95 border border-[#45464c]/20 rounded-3xl shadow-[0_64px_128px_rgba(0,0,0,0.8)] overflow-hidden max-h-[500px] overflow-y-auto no-scrollbar backdrop-blur-3xl"
                                >
                                    {categoryFundsLoading ? (
                                        <div className="p-16 text-center">
                                            <div className="w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-6 shadow-[0_0_30px_rgba(233,195,73,0.1)]"></div>
                                            <p className="text-[10px] font-black text-primary uppercase tracking-[0.5em] italic animate-pulse font-label">Syncing Database...</p>
                                        </div>
                                    ) : filteredFunds.length > 0 ? (
                                        <div className="p-3">
                                            {filteredFunds.slice(0, 10).map((fund) => (
                                                <button 
                                                    key={fund.scheme_code}
                                                    onClick={() => handleAdd(fund)}
                                                    className="w-full text-left p-8 hover:bg-white/[0.03] rounded-2xl transition-all group flex items-center justify-between border border-transparent hover:border-white/5 active:scale-[0.99]"
                                                >
                                                    <div>
                                                        <div className="text-base font-headline font-bold text-white group-hover:text-primary transition-colors uppercase italic tracking-tight">{fund.scheme_name}</div>
                                                        <div className="text-[10px] text-slate-500 font-black tracking-[0.3em] uppercase mt-2 opacity-60 font-label">{fund.scheme_code}</div>
                                                    </div>
                                                    <div className="w-10 h-10 rounded-full border border-[#45464c]/30 flex items-center justify-center group-hover:border-primary group-hover:bg-primary transition-all">
                                                        <span className="material-symbols-outlined text-slate-600 font-thin group-hover:text-on-primary transition-colors">add</span>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="p-20 text-center flex flex-col items-center gap-6">
                                            <span className="material-symbols-outlined text-5xl opacity-10 font-thin">search_off</span>
                                            <p className="text-[10px] font-black uppercase tracking-[0.5em] opacity-40 italic font-label">No Cryptographic Matches Found</p>
                                        </div>
                                    )}
                                </motion.div>
                            )}
                        </AnimatePresence>
                        
                        {showDropdown && (
                            <div 
                                className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" 
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
