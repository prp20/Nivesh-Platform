import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { fetchStockDetail, triggerFullStockSync } from "../store/slices/stocksSlice";
import stockService from "../api/services/stockService";
import { motion, AnimatePresence } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import toast from 'react-hot-toast';

export default function StockDetail() {
  const { symbol } = useParams();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { detail, status } = useSelector(s => s.stocks);
  const [activeTab, setActiveTab] = useState("oracle");
  const [fundamentals, setFundamentals] = useState(null);
  const [shareholding, setShareholding] = useState(null);
  const [stmtType, setStmtType] = useState("PL");
  const [loadingFundamentals, setLoadingFundamentals] = useState(false);
  const [loadingShareholding, setLoadingShareholding] = useState(false);

  const [ratios, setRatios] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [syncingPrices, setSyncingPrices] = useState(false);
  const [syncingFundamentals, setSyncingFundamentals] = useState(false);

  const timeframes = [
    { id: '1M', interval: '1d', limit: 20 },
    { id: '6M', interval: '1d', limit: 120 },
    { id: '1Y', interval: '1d', limit: 260 },
    { id: '5Y', interval: '1w', limit: 260 },
    { id: '10Y', interval: '1mo', limit: 120 },
    { id: 'MAX', interval: '1mo', limit: 300 }
  ];
  const [activeTimeframe, setActiveTimeframe] = useState('1Y');

  useEffect(() => {
    if (symbol) {
      dispatch(fetchStockDetail(symbol));
    }
  }, [symbol, dispatch]);
  
  useEffect(() => {
    if (symbol && detail?.symbol === symbol) {
      const tf = timeframes.find(t => t.id === activeTimeframe) || timeframes[2];
      stockService.getPriceHistory(symbol, { interval: tf.interval, limit: tf.limit })
        .then(res => setPriceHistory(res.data))
        .catch(err => console.error("Failed to fetch price history:", err));
      
      stockService.getRatios(symbol)
        .then(res => {
          if (res.records && res.records.length > 0) {
            setRatios(res.records[0]);
          }
        })
        .catch(err => console.error("Failed to fetch ratios:", err));
    }
  }, [symbol, detail?.symbol, activeTimeframe]);

  const handleSyncDaily = async () => {
    setSyncingPrices(true);
    try {
      await stockService.triggerDeepPriceSync(symbol, "1y");
      await stockService.triggerTechnicalAnalysis(symbol);
      await stockService.triggerRatingCompute(symbol);
      const tf = timeframes.find(t => t.id === activeTimeframe) || timeframes[2];
      const hist = await stockService.getPriceHistory(symbol, { interval: tf.interval, limit: tf.limit });
      setPriceHistory(hist.data);
      dispatch(fetchStockDetail(symbol));
      toast.success('Price data synced successfully');
    } catch (error) {
      console.error('Sync failed:', error);
      toast.error('Failed to sync price data. Please try again.');
    } finally {
      setSyncingPrices(false);
    }
  };

  const handleSyncFundamentals = async () => {
    setSyncingFundamentals(true);
    try {
      await stockService.triggerScreenerScrape(symbol, true);
      const [rat, fund] = await Promise.all([
        stockService.getRatios(symbol),
        stockService.getFundamentals(symbol, { statement_type: stmtType, limit: 5 })
      ]);
      if (rat.records?.length > 0) setRatios(rat.records[0]);
      setFundamentals(fund);
      dispatch(fetchStockDetail(symbol));
      toast.success('Fundamental data synced successfully');
    } catch (error) {
      console.error('Fundamental sync failed:', error);
      toast.error('Failed to sync fundamental data. Please try again.');
    } finally {
      setSyncingFundamentals(false);
    }
  };

  useEffect(() => {
    if (symbol && activeTab === "fundamentals" && ["PL", "BS", "CF"].includes(stmtType)) {
      setLoadingFundamentals(true);
      stockService
        .getFundamentals(symbol, { statement_type: stmtType, limit: 5 })
        .then(setFundamentals)
        .catch(err => console.error("Failed to fetch fundamentals:", err))
        .finally(() => setLoadingFundamentals(false));
    }
  }, [symbol, activeTab, stmtType]);

  useEffect(() => {
    if (symbol && activeTab === "fundamentals" && stmtType === "Ownership" && !shareholding) {
      setLoadingShareholding(true);
      stockService
        .getShareholding(symbol, { limit: 8 })
        .then(setShareholding)
        .catch(err => console.error("Failed to fetch shareholding:", err))
        .finally(() => setLoadingShareholding(false));
    }
  }, [symbol, activeTab, stmtType, shareholding]);

  if (status === "loading" || !detail) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-6">
        <div className="w-24 h-24 border-4 border-primary border-t-transparent rounded-full animate-spin mb-8 shadow-[0_0_30px_rgba(233,195,73,0.2)]"></div>
        <p className="text-primary font-black uppercase tracking-[0.5em] animate-pulse">Decrypting Asset Vector...</p>
      </div>
    );
  }

  const changeColor = detail.change_pct >= 0 ? "text-secondary" : "text-error";
  const glowClass = detail.change_pct >= 0 ? "shadow-[0_0_40px_rgba(102,221,139,0.1)]" : "shadow-[0_0_40px_rgba(255,180,171,0.1)]";

  return (
    <div className="min-h-screen bg-surface text-on-surface overflow-hidden relative pb-32">
      {/* Editorial Watermark */}
      <div className="absolute top-40 -right-20 pointer-events-none opacity-[0.02] select-none origin-top-right">
        <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none">{detail.symbol}</span>
      </div>

      <div className="max-w-[1400px] mx-auto px-6 lg:px-16 pt-12 relative z-10">

        {/* Breadcrumb & Tier Header */}
      {/* Compact Sovereign Header */}
      <header className="mb-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 pt-8 border-b border-outline-variant/10 pb-8">
        <div className="flex items-center gap-6">
          <button onClick={() => navigate(-1)} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group">
            <span className="material-symbols-outlined text-sm group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
          </button>
          <div className="space-y-1">
            <p className="font-label text-[10px] font-semibold uppercase tracking-[0.3em] text-primary flex items-center gap-2">
              Sovereign Core Architecture <span className="w-1 h-1 rounded-full bg-primary/50"></span> {detail.sector}
            </p>
            <h2 className="font-headline text-4xl md:text-5xl font-light tracking-tight text-white uppercase">
              {detail.company_name} <span className="font-extrabold italic text-primary">{detail.symbol}</span>
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-4 self-end md:self-center">
           <div className="flex bg-surface-container-low border border-outline-variant/20 p-1 rounded-xl">
             <button 
               onClick={handleSyncDaily} 
               disabled={syncingPrices}
               className="p-2.5 hover:bg-white/5 rounded-lg transition-colors text-slate-400 hover:text-emerald-500"
               title="Sync Market Data"
             >
               <span className={`material-symbols-outlined text-xl ${syncingPrices ? 'animate-spin' : ''}`}>sync</span>
             </button>
             <button 
               onClick={handleSyncFundamentals} 
               disabled={syncingFundamentals}
               className="p-2.5 hover:bg-white/5 rounded-lg transition-colors text-slate-400 hover:text-primary"
               title="Sync Fundamentals"
             >
               <span className={`material-symbols-outlined text-xl ${syncingFundamentals ? 'animate-spin' : ''}`}>database</span>
             </button>
           </div>
           <div className="bg-surface-container-low border border-outline-variant/20 px-4 py-2 rounded-xl flex items-center gap-3">
             <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
             <span className="text-[10px] font-black uppercase tracking-widest text-secondary">Live Nexus Active</span>
           </div>
        </div>
      </header>

      {/* High-Density Metric Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {/* Price Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Current Valuation</p>
              <span className="material-symbols-outlined text-primary text-lg">payments</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-4xl font-extrabold text-white">₹{detail.latest_close?.toFixed(2)}</p>
              <div className="flex flex-col mb-1">
                <span className={`text-[10px] font-black ${detail.change_pct >= 0 ? 'text-secondary' : 'text-error'}`}>
                  {detail.change_pct >= 0 ? '+' : ''}{detail.change_pct?.toFixed(2)}%
                </span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Session Delta</span>
              </div>
            </div>
            <div className={`absolute bottom-0 left-0 h-1 transition-all duration-700 ${detail.change_pct >= 0 ? 'bg-secondary w-full' : 'bg-error w-full'}`}></div>
          </div>

          {/* Scale Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Market Presence</p>
              <span className="material-symbols-outlined text-primary text-lg">account_balance_wallet</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-4xl font-extrabold text-white capitalize">{detail.market_cap_cat || 'N/A'}</p>
              <div className="flex flex-col mb-1">
                <span className="text-[10px] text-secondary font-black uppercase">Tier 1</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Equity Scale</span>
              </div>
            </div>
          </div>

          {/* Fundamental Health Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Price Multiplier (P/E)</p>
              <span className="material-symbols-outlined text-primary text-lg">analytics</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-4xl font-extrabold text-white">{ratios?.pe_ratio?.toFixed(1) || '—'}</p>
              <div className="flex flex-col mb-1">
                <span className="text-[10px] text-secondary font-black uppercase">Optimal</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Sector Relative</span>
              </div>
            </div>
          </div>

          {/* Analyst Stance Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group border-l-4 border-l-primary">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Sovereign Rating</p>
              <span className="material-symbols-outlined text-primary text-lg">verified</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-4xl font-extrabold text-white uppercase tracking-tighter">{detail.rating_label ? detail.rating_label.replace("_", " ") : 'HOLD'}</p>
              <div className="flex flex-col mb-1">
                <span className="text-[10px] text-secondary font-black uppercase">Consensus</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Institutional</span>
              </div>
            </div>
          </div>
      </div>


        {/* Global Tabs */}
        <div className="flex justify-center gap-8 mb-16 border-b border-outline-variant/20 overflow-x-auto no-scrollbar">
          {[
            { id: "oracle", label: "Intelligence" },
            { id: "fundamentals", label: "Fundamental Lattice" }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-4 font-label text-[11px] font-black uppercase tracking-[0.4em] transition-all whitespace-nowrap ${activeTab === tab.id
                ? "text-primary border-b-2 border-primary"
                : "text-slate-500 hover:text-white"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Dynamic Content */}
        <AnimatePresence mode="wait">
          {activeTab === "oracle" && (
            <motion.div key="oracle" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col xl:flex-row gap-16">

              {/* Left Column: Data Grid & Profile */}
              <div className="flex-1 flex flex-col gap-12">

                {/* Mobile Price View */}
                <div className="md:hidden glass-panel p-8 rounded-[2rem] border border-outline-variant/10">
                  <span className="text-[10px] text-slate-500 font-black uppercase tracking-widest block mb-2">Valuation</span>
                  <div className="text-5xl font-bold font-headline tracking-tighter text-white">₹{detail.latest_close?.toFixed(2)}</div>
                  <div className={`text-xl font-black mt-2 tracking-tighter ${changeColor}`}>{detail.change_pct > 0 ? "+" : ""}{detail.change_pct?.toFixed(2)}%</div>
                </div>

                <section>
                  <h3 className="font-headline text-3xl font-bold italic mb-8 tracking-tighter">Capitalization & Multiples</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-1">
                    <DataCell label="Sector" value={detail.sector} />
                    <DataCell label="P/E Ratio" value={ratios?.pe_ratio?.toFixed(1) || '—'} />
                    <DataCell label="P/B Ratio" value={ratios?.pb_ratio?.toFixed(1) || '—'} />
                    <DataCell label="ROE" value={ratios?.roe ? `${ratios.roe.toFixed(1)}%` : '—'} />
                    <DataCell label="D/E Ratio" value={ratios?.debt_equity?.toFixed(2) || '—'} />
                    <DataCell label="Rating" value={detail.rating_label ? detail.rating_label.replace("_", " ") : '—'} highlight />
                  </div>
                </section>

                <section>
                  <h3 className="font-headline text-3xl font-bold italic mb-8 tracking-tighter">Technical Gauge</h3>
                  <div className="grid grid-cols-2 gap-1">
                    <DataCell label="RSI (14)" value={detail.rsi_14?.toFixed(1) || '—'} />
                    <DataCell label="MACD Hist" value={detail.macd_hist?.toFixed(3) || '—'} />
                    <DataCell label="Close vs 50 SMA" value={detail.latest_close && detail.sma_50 ? `${((detail.latest_close / detail.sma_50 - 1) * 100).toFixed(1)}%` : '—'} />
                    <DataCell label="Close vs 200 SMA" value={detail.latest_close && detail.sma_200 ? `${((detail.latest_close / detail.sma_200 - 1) * 100).toFixed(1)}%` : '—'} />
                  </div>
                </section>

                <section>
                  <h3 className="font-headline text-3xl font-bold italic mb-6 tracking-tighter">Market Stance & Profile</h3>
                  <div className="bg-surface-container-low p-10 rounded-[2rem] border-l-2 border-primary/40 shadow-xl mb-12">
                    <p className="text-slate-400 font-medium leading-relaxed italic">
                      {detail.company_name} operates within the highly competitive {detail.sector} sector. As a tier-1 component of the equity matrix, its market dynamics dictate substantial capital flows across institutional portfolios. Current algorithmic models suggest continuous monitoring of its P/E multiple relative to sub-sector peers.
                    </p>
                  </div>
                </section>
                
                <section>
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="font-headline text-3xl font-bold italic tracking-tighter">Price Performance</h3>
                    <div className="flex bg-surface-container-low rounded-xl p-1 shadow-lg border border-outline-variant/5">
                      {timeframes.map(tf => (
                        <button
                          key={tf.id}
                          onClick={() => setActiveTimeframe(tf.id)}
                          className={`px-4 py-2 rounded-lg text-xs font-black tracking-widest transition-all ${
                            activeTimeframe === tf.id 
                              ? 'bg-primary text-on-primary shadow shadow-primary/20' 
                              : 'text-slate-500 hover:text-white hover:bg-white/5'
                          }`}
                        >
                          {tf.id}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div className="glass-panel p-8 rounded-[2rem] border border-outline-variant/10 h-80 relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none blur-3xl opacity-30"></div>
                    {priceHistory.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={priceHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs>
                              <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#e9c349" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#e9c349" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <XAxis 
                              dataKey="time" 
                              stroke="#64748b" 
                              fontSize={10} 
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={(val) => {
                                const d = new Date(val);
                                return activeTimeframe === '1M' || activeTimeframe === '6M' 
                                  ? d.toLocaleDateString('en-IN', {day: 'numeric', month:'short'})
                                  : d.toLocaleDateString('en-IN', {month:'short', year:'2-digit'});
                              }} 
                            />
                            <YAxis 
                              stroke="#64748b" 
                              fontSize={10} 
                              tickLine={false}
                              axisLine={false}
                              domain={['auto', 'auto']} 
                              tickFormatter={(val) => `₹${val}`} 
                            />
                            <Tooltip 
                              contentStyle={{ backgroundColor: 'rgba(27, 32, 37, 0.9)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '1rem', color: '#fff', fontSize: '12px' }} 
                              itemStyle={{ color: '#e9c349', fontWeight: 'bold' }}
                              labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                            />
                            <Area 
                              type="monotone" 
                              dataKey="close" 
                              stroke="#e9c349" 
                              strokeWidth={3} 
                              fillOpacity={1} 
                              fill="url(#colorClose)" 
                              animationDuration={1500}
                            />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 font-label text-xs uppercase tracking-widest relative z-10">No Price Data Retained</div>
                    )}
                  </div>
                </section>
              </div>

              {/* Right Column: Sovereign's Oracle */}
              <div className="xl:w-[450px] shrink-0">
                <div className={`sticky top-32 glass-panel rounded-[3rem] p-10 border border-outline-variant/10 ${glowClass} relative overflow-hidden`}>
                  {/* Glass Sheen */}
                  <div className="absolute inset-x-0 -top-10 h-32 bg-gradient-to-b from-white/5 to-transparent blur-2xl"></div>

                  <div className="flex items-center gap-4 mb-8 relative z-10">
                    <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center border border-primary/30">
                      <span className="material-symbols-outlined text-primary">psychology</span>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">The Sovereign's Oracle</h4>
                      <p className="text-xs text-slate-500 font-label tracking-widest uppercase">Deep Generative Analysis</p>
                    </div>
                  </div>

                  <div className="space-y-8 relative z-10">
                    <div>
                      <h5 className="font-headline text-white font-bold mb-3 italic">Investment Thesis</h5>
                      <p className="text-sm text-slate-400 font-label leading-relaxed">
                        {detail.symbol} currently maintains a robust vector in {detail.sector}. Our agentic models indicate that systemic value capture is stabilizing. Retail sentiment is fractured, yet institutional accumulation remains at {detail.roe > 15 ? 'elevated' : 'moderate'} levels. The algorithmic rating registers a definitive <strong className="text-white">{detail.rating_label ? detail.rating_label.replace("_", " ") : 'HOLD'}</strong>.
                      </p>
                    </div>

                    <div>
                      <h5 className="text-[10px] font-black tracking-[0.3em] uppercase text-secondary mb-4">• Upside Catalysts</h5>
                      <ul className="text-xs font-label text-white/80 space-y-3 pl-4 border-l border-white/5">
                        <li>Institutional portfolio recalibration towards {detail.sector}.</li>
                        <li>Potential multiple expansion if trailing metrics hold.</li>
                      </ul>
                    </div>

                    <div>
                      <h5 className="text-[10px] font-black tracking-[0.3em] uppercase text-error mb-4">• Risk Vectors</h5>
                      <ul className="text-xs font-label text-white/80 space-y-3 pl-4 border-l border-white/5">
                        <li>Macroeconomic liquidity tightening affecting capitalization.</li>
                        <li>Sub-sector momentum divergence indicating exhaustion.</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

            </motion.div>
          )}

          {activeTab === "fundamentals" && (
            <motion.div key="fundamentals" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <FundamentalsTab 
                data={fundamentals} 
                stmtType={stmtType} 
                onStmtChange={setStmtType} 
                loading={loadingFundamentals} 
                shareholdingData={shareholding}
                shareholdingLoading={loadingShareholding}
              />
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  );
}

function DataCell({ label, value, highlight }) {
  return (
    <div className={`bg-surface-container-low p-8 first:rounded-tl-[2rem] last:rounded-br-[2rem] border-[0.5px] border-surface transition-colors hover:bg-surface-container`}>
      <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.3em] mb-4">{label}</p>
      <p className={`text-2xl md:text-3xl font-headline font-bold tracking-tighter ${highlight ? 'text-primary' : 'text-white'}`}>{value}</p>
    </div>
  );
}

function FundamentalsTab({ data, stmtType, onStmtChange, loading, shareholdingData, shareholdingLoading }) {
  const labels = { PL: "Profit & Loss", BS: "Balance Sheet", CF: "Cash Flow", Ownership: "Ownership Topology" };
  const stmtOptions = ["PL", "BS", "CF", "Ownership"];

  return (
    <div className="space-y-12 animate-fadeIn">
      {/* High-Fidelity Statement Toggles */}
      <div className="flex bg-surface-container-low/40 p-2 rounded-2xl border border-white/5 w-fit mx-auto">
        {stmtOptions.map(t => (
          <button
            key={t}
            onClick={() => onStmtChange(t)}
            className={`px-8 py-3 rounded-xl font-black text-[10px] tracking-[0.2em] uppercase transition-all ${
              stmtType === t
                ? "bg-primary text-black shadow-lg shadow-primary/20"
                : "text-slate-500 hover:text-white hover:bg-white/5"
            }`}
          >
            {labels[t]}
          </button>
        ))}
      </div>

      {stmtType === 'Ownership' ? (
        <ShareholdingTab data={shareholdingData} loading={shareholdingLoading} />
      ) : loading ? (
        <div className="space-y-8">
          <div className="flex gap-4 animate-pulse">
            {[1, 2, 3].map(i => <div key={i} className="h-10 w-32 bg-white/5 rounded-xl"></div>)}
          </div>
          <div className="h-96 bg-surface-container-low/30 border border-white/5 rounded-[2.5rem] animate-pulse" />
        </div>
      ) : !data?.records?.length ? (
        <div className="glass-panel p-20 text-center rounded-[3rem] border border-white/5">
          <span className="material-symbols-outlined text-4xl text-slate-800 mb-4 block">database_off</span>
          <p className="text-[10px] uppercase font-black tracking-widest text-slate-600">No Intelligence Recovered</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden rounded-[2.5rem] border border-white/5 shadow-2xl bg-surface-container-lowest/20">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 bg-white/[0.02]">
                  <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.4em]">Metric Architecture</th>
                  {data.records.map(r => (
                    <th key={r.period_end} className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] text-right whitespace-nowrap">
                      {r.period_end}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.records[0]?.data && Object.entries(data.records[0].data).map(([key]) => (
                  <tr key={key} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-all group">
                    <td className="p-8">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-bold text-white/90 group-hover:text-primary transition-colors uppercase tracking-tight font-headline">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-[9px] text-slate-600 font-medium uppercase tracking-widest group-hover:text-slate-400 transition-colors">
                          Soverign Verified Metric
                        </span>
                      </div>
                    </td>
                    {data.records.map(r => (
                      <td key={r.period_end} className="p-8 text-right align-middle">
                        <span className="font-headline text-lg font-semibold text-white tracking-tighter">
                          {r.data[key] != null ? r.data[key].toLocaleString("en-IN") : "—"}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function ShareholdingTab({ data, loading }) {
  if (loading) {
    return <div className="h-64 bg-surface-container-lowest border border-outline-variant/10 rounded-[3rem] animate-pulse" />;
  }

  if (!data?.records?.length) {
    return <div className="text-center py-20 text-[10px] uppercase font-black tracking-widest text-slate-500">No Intelligence Recovered</div>;
  }

  return (
    <div className="glass-panel overflow-x-auto rounded-[3rem] border border-outline-variant/10 shadow-2xl animate-fadeIn">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-outline-variant/20 bg-surface-container/30">
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em]">Epoch Filter</th>
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right">Promoter %</th>
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right">FII %</th>
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right">DII %</th>
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right">Public %</th>
            <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right">Pledged %</th>
          </tr>
        </thead>
        <tbody>
          {data.records.map(r => (
            <tr key={r.period_end} className="border-b border-outline-variant/10 hover:bg-white/[0.03] transition-colors">
              <td className="p-8 font-headline text-lg font-bold text-white">{r.period_end}</td>
              <td className="p-8 text-right font-headline text-lg text-white">{r.promoter_pct?.toFixed(2) ?? "—"}</td>
              <td className="p-8 text-right font-headline text-xl text-secondary font-black bg-secondary/5">{r.fii_pct?.toFixed(2) ?? "—"}</td>
              <td className="p-8 text-right font-headline text-lg text-white">{r.dii_pct?.toFixed(2) ?? "—"}</td>
              <td className="p-8 text-right font-headline text-lg text-slate-400">{r.public_pct?.toFixed(2) ?? "—"}</td>
              <td className="p-8 text-right font-headline text-lg text-error/80">{r.pledged_pct?.toFixed(2) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
