import React, { useEffect, useState, useRef } from "react";
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
  const [agentInsights, setAgentInsights] = useState(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [isSummaryExpanded, setIsSummaryExpanded] = useState(false);
  const fundamentalsPollRef = useRef(null);
  const safetyTimeoutRef = useRef(null);

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
    // Clear any existing poll
    if (fundamentalsPollRef.current) {
      clearInterval(fundamentalsPollRef.current);
      fundamentalsPollRef.current = null;
    }

    setSyncingFundamentals(true);
    let timeoutId = null;

    try {
      const triggerTime = new Date();
      await stockService.triggerScreenerScrape(symbol, true); // Returns immediately (background job)

      const stopPolling = () => {
        if (fundamentalsPollRef.current) {
          clearInterval(fundamentalsPollRef.current);
          fundamentalsPollRef.current = null;
        }
        if (safetyTimeoutRef.current) {
          clearTimeout(safetyTimeoutRef.current);
          safetyTimeoutRef.current = null;
        }
      };

      const poll = async () => {
        try {
          const statusRes = await stockService.getPipelineStatus();
          const job = (statusRes.jobs || []).find(
            j => j.job_name === 'fundamental_scrape_single' &&
              new Date(j.started_at) >= triggerTime
          );
          if (job?.status === 'SUCCESS') {
            stopPolling();
            const [rat, fund] = await Promise.all([
              stockService.getRatios(symbol),
              stockService.getFundamentals(symbol, { statement_type: stmtType, limit: 5 })
            ]);
            if (rat.records?.length > 0) setRatios(rat.records[0]);
            setFundamentals(fund);
            dispatch(fetchStockDetail(symbol));
            toast.success('Fundamental data synced successfully');
            setSyncingFundamentals(false);
          } else if (job?.status === 'FAILED') {
            stopPolling();
            toast.error('Fundamental sync failed on the server. Check pipeline logs.');
            setSyncingFundamentals(false);
          }
        } catch (pollErr) {
          console.error('Status poll error:', pollErr);
        }
      };

      fundamentalsPollRef.current = setInterval(poll, 5000);

      // Safety timeout: reset button after 5 minutes regardless
      safetyTimeoutRef.current = setTimeout(() => {
        stopPolling();
        setSyncingFundamentals(false);
        toast.error('Fundamental sync timed out. Check the Admin pipeline status page.');
      }, 300000);

    } catch (error) {
      console.error('Failed to trigger fundamental sync:', error);
      toast.error('Failed to start fundamental sync. Please try again.');
      setSyncingFundamentals(false);
    }
  };

  const fetchInsights = async () => {
    if (!symbol) return;
    setLoadingInsights(true);
    try {
      const data = await stockService.getAgentInsights(symbol);
      setAgentInsights(data);
    } catch (err) {
      console.error("Failed to fetch agent insights:", err);
      toast.error("Cloud resonance failure: Could not synthesize AI insights.");
    } finally {
      setLoadingInsights(false);
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (fundamentalsPollRef.current) clearInterval(fundamentalsPollRef.current);
      if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current);
    };
  }, []);

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

  useEffect(() => {
    if (activeTab === "agent_insights" && !agentInsights && !loadingInsights) {
      fetchInsights();
    }
  }, [activeTab, symbol, agentInsights, loadingInsights]);

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
    <div className="min-h-screen bg-surface text-on-surface overflow-hidden relative pb-16">
      {/* Editorial Watermark */}
      <div className="absolute top-40 -right-20 pointer-events-none opacity-[0.02] select-none origin-top-right">
        <span className="text-[25vw] font-headline font-black uppercase tracking-tighter leading-none">{detail.symbol}</span>
      </div>

      <div className="px-6 md:px-10 lg:px-14 xl:px-16 2xl:px-20 pt-12 relative z-10">

        {/* Breadcrumb & Tier Header */}
        {/* Compact Sovereign Header */}
        <header className="mb-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 pt-8 border-b border-outline-variant/10 pb-8">
          <div className="flex items-center gap-6">
            <button onClick={() => navigate(-1)} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group">
              <span className="material-symbols-outlined text-sm group-hover:-translate-x-0.5 transition-transform">arrow_back</span>
            </button>
            <div className="space-y-1">
              <h2 className="font-headline text-4xl md:text-5xl tracking-tight text-white uppercase">
                <span className="font-bold text-primary mr-3">{detail.company_name}</span>
                <span className="italic font-light text-white text-3xl">{detail.symbol}</span>
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
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Prev Close</p>
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
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Market Cap</p>
              <span className="material-symbols-outlined text-primary text-lg">account_balance_wallet</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-4xl font-extrabold text-white capitalize">{detail.market_cap_cat.toUpperCase() || 'N/A'}</p>
              {/* <div className="flex flex-col mb-1">
                <span className="text-[10px] text-secondary font-black uppercase">Tier 1</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Equity Scale</span>
              </div> */}
            </div>
          </div>

          {/* Fundamental Health Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Sector</p>
              <span className="material-symbols-outlined text-primary text-lg">category</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-3xl font-extrabold text-white uppercase leading-tight">{detail.sector || '—'}</p>
              {/* <div className="flex flex-col mb-1 shrink-0">
                <span className="text-[10px] text-secondary font-black uppercase">Optimal</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Sector Relative</span>
              </div> */}
            </div>
          </div>

          {/* Analyst Stance Card */}
          <div className="glass-panel p-6 rounded-2xl relative overflow-hidden group border-l-4 border-l-primary">
            <div className="flex justify-between items-start mb-4">
              <p className="font-label text-[10px] uppercase tracking-widest text-slate-500 group-hover:text-primary transition-colors">Industry</p>
              <span className="material-symbols-outlined text-primary text-lg">domain</span>
            </div>
            <div className="flex items-end gap-2">
              <p className="font-headline text-3xl font-extrabold text-white uppercase tracking-tighter leading-tight">{detail.industry.toUpperCase() || '—'}</p>
              {/* <div className="flex flex-col mb-1 shrink-0">
                <span className="text-[10px] text-secondary font-black uppercase">Consensus</span>
                <span className="text-[8px] text-slate-600 uppercase font-bold tracking-tighter">Institutional</span>
              </div> */}
            </div>
          </div>
        </div>


        {/* Global Tabs */}
        <div className="flex justify-center gap-8 mb-16 border-b border-outline-variant/20 overflow-x-auto no-scrollbar">
          {[
            { id: "oracle", label: "Intelligence" },
            { id: "fundamentals", label: "Fundamental Lattice" },
            { id: "agent_insights", label: "Agent Insights" }
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
            <motion.div key="oracle" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-16">

              {/* Full-Width Price Performance Header */}
              <section className="animate-fadeIn">
                <div className="flex items-center justify-between mb-8">
                  <h3 className="font-headline text-3xl font-bold italic tracking-tighter">Price Performance</h3>
                  <div className="flex bg-surface-container-low rounded-xl p-1 shadow-lg border border-outline-variant/5">
                    {timeframes.map(tf => (
                      <button
                        key={tf.id}
                        onClick={() => setActiveTimeframe(tf.id)}
                        className={`px-4 py-2 rounded-lg text-xs font-black tracking-widest transition-all ${activeTimeframe === tf.id
                          ? 'bg-primary text-on-primary shadow shadow-primary/20'
                          : 'text-slate-500 hover:text-white hover:bg-white/5'
                          }`}
                      >
                        {tf.id}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="glass-panel p-8 rounded-[2rem] border border-outline-variant/10 h-[450px] relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none blur-3xl opacity-30"></div>
                  {priceHistory.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={priceHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#e9c349" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#e9c349" stopOpacity={0} />
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
                              ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
                              : d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
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

              <div className="flex flex-col xl:flex-row gap-16">

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

                  <section className="mb-12">
                    <h3 className="font-headline text-3xl font-bold italic mb-8 tracking-tighter">About {detail.company_name}</h3>
                    <div className="bg-surface-container-low p-10 rounded-[3rem] border-l-2 border-primary/40 shadow-xl transition-all duration-500 overflow-hidden relative">
                      <p className={`text-slate-400 font-medium leading-relaxed italic ${!isSummaryExpanded ? 'line-clamp-3' : ''}`}>
                        {detail.summary || `No summary available for ${detail.company_name} at this time.`}
                      </p>

                      <div className="mt-6 flex justify-end">
                        <button
                          onClick={() => setIsSummaryExpanded(!isSummaryExpanded)}
                          className="flex items-center gap-2 group"
                        >
                          <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">{isSummaryExpanded ? 'Less' : 'More'}</span>
                          <span className={`material-symbols-outlined text-primary text-sm transition-transform duration-300 ${isSummaryExpanded ? 'rotate-180' : ''}`}>
                            expand_more
                          </span>
                        </button>
                      </div>

                      {!isSummaryExpanded && (
                        <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-surface-container-low to-transparent pointer-events-none"></div>
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

          {activeTab === "agent_insights" && (
            <motion.div key="agent_insights" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <AgentInsightsTab
                data={agentInsights}
                loading={loadingInsights}
                onRefresh={fetchInsights}
                symbol={symbol}
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
            className={`px-8 py-3 rounded-xl font-black text-[10px] tracking-[0.2em] uppercase transition-all ${stmtType === t
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
                          Sovereign Verified Metric
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

function AgentInsightsTab({ data, loading, onRefresh, symbol }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-20 space-y-8 animate-pulse">
        <div className="w-20 h-20 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="font-label text-xs uppercase tracking-[0.4em] text-primary">Synthesizing Neural Lattice...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-panel p-20 text-center rounded-[3rem] border border-white/5">
        <span className="material-symbols-outlined text-4xl text-slate-800 mb-4 block">smart_toy</span>
        <p className="text-[10px] uppercase font-black tracking-widest text-slate-600 mb-8">No Intelligence Recovered</p>
        <button
          onClick={onRefresh}
          className="px-8 py-3 bg-primary text-black rounded-xl font-black text-[10px] tracking-[0.2em] uppercase hover:shadow-lg hover:shadow-primary/20 transition-all font-headline"
        >
          Initialize Agent Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-12 animate-fadeIn pb-20">
      {/* Header Score & Reasoning */}
      <div className="flex flex-col lg:flex-row gap-8">
        <div className="lg:w-1/3 glass-panel p-10 rounded-[3rem] border border-white/5 flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent pointer-events-none"></div>
          <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] mb-6 relative z-10">Composite Alpha Score</p>
          <div className="relative w-48 h-48 flex items-center justify-center z-10">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="2" fill="transparent" className="text-white/5" />
              <circle
                cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="10" fill="transparent"
                strokeDasharray={552.92}
                strokeDashoffset={552.92 - (552.92 * (data.composite_score || 0)) / 100}
                className="text-primary drop-shadow-[0_0_10px_rgba(233,195,73,0.5)]"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-5xl font-headline font-black text-white">{data.composite_score?.toFixed(1) || '0.0'}</span>
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Quantum Rank</span>
            </div>
          </div>
          <div className="mt-8 px-6 py-2 bg-primary/10 border border-primary/20 rounded-full z-10">
            <span className="text-[10px] font-black text-primary uppercase tracking-widest">{data.reasoning_label}</span>
          </div>
        </div>

        <div className="lg:flex-1 glass-panel p-10 rounded-[3rem] border border-white/5 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <span className="material-symbols-outlined text-8xl text-primary">format_quote</span>
          </div>
          <h4 className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500 mb-6">Neural Synthesis</h4>
          <p className="text-xl md:text-2xl font-headline font-light italic leading-relaxed text-white/90 relative z-10">
            "{data.reasoning_text}"
          </p>
          <div className="mt-12 flex justify-between items-center relative z-10">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-secondary animate-pulse"></div>
              <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Model Version {data.score_version}</span>
            </div>
            <button
              onClick={onRefresh}
              className="flex items-center gap-2 px-6 py-2 rounded-xl border border-white/5 hover:bg-white/5 transition-all group"
            >
              <span className="material-symbols-outlined text-sm group-hover:rotate-180 transition-transform duration-500 text-primary">sync</span>
              <span className="text-[9px] font-black text-slate-400 group-hover:text-white uppercase tracking-widest">Re-run Analysis</span>
            </button>
          </div>
        </div>
      </div>

      {/* Granular Pillar Scores */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <ScoreCard
          title="Profit & Loss"
          score={data.pl_results?.score}
          metrics={[
            { label: 'Revenue CAGR', value: `${data.pl_results?.metrics?.rev_cagr?.toFixed(2)}%` },
            { label: 'PAT CAGR', value: `${data.pl_results?.metrics?.pat_cagr?.toFixed(2)}%` },
            { label: 'Latest OPM', value: `${data.pl_results?.metrics?.latest_opm?.toFixed(2)}%` }
          ]}
          accent="primary"
        />
        <ScoreCard
          title="Balance Sheet"
          score={data.bs_results?.score}
          metrics={[
            { label: 'Debt/Equity', value: data.bs_results?.metrics?.debt_to_equity?.toFixed(2) },
            { label: 'Current Ratio', value: data.bs_results?.metrics?.current_ratio?.toFixed(2) },
            { label: 'Reserves CAGR', value: `${data.bs_results?.metrics?.reserves_cagr?.toFixed(2)}%` }
          ]}
          accent="secondary"
        />
        <ScoreCard
          title="Cash Flow"
          score={data.cf_results?.score}
          metrics={[
            { label: 'CFO/PAT', value: data.cf_results?.metrics?.cfo_to_pat?.toFixed(2) },
            { label: 'FCF +ve Years', value: data.cf_results?.metrics?.fcf_positive_years }
          ]}
          accent="error"
        />
      </div>

      {/* Pipeline Logs */}
      <div className="glass-panel rounded-[2rem] border border-white/5 overflow-hidden">
        <div className="px-8 py-4 bg-white/5 flex items-center justify-between">
          <h5 className="text-[9px] font-black uppercase tracking-[0.4em] text-slate-500">Pipeline Execution Trace</h5>
          <span className="text-[10px] font-bold text-secondary font-headline uppercase tracking-widest">{data.status}</span>
        </div>
        <div className="p-8 space-y-2 bg-black/20">
          {data.logs?.map((log, i) => (
            <div key={i} className="flex gap-4 font-mono text-[10px]">
              <span className="text-slate-700">[{i + 1}]</span>
              <span className="text-slate-400">{log}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ScoreCard({ title, score, metrics, accent }) {
  const accentColor = accent === 'primary' ? 'text-primary' : accent === 'secondary' ? 'text-secondary' : 'text-error';
  const borderColor = accent === 'primary' ? 'group-hover:border-primary/20' : accent === 'secondary' ? 'group-hover:border-secondary/20' : 'group-hover:border-error/20';

  return (
    <div className={`glass-panel p-8 rounded-[2.5rem] border border-white/5 relative overflow-hidden group ${borderColor} transition-colors`}>
      <h5 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6">{title}</h5>
      <div className="flex items-baseline gap-2 mb-8">
        <span className={`text-4xl font-headline font-black ${accentColor}`}>{score?.toFixed(1) || '0.0'}</span>
        <span className="text-xs text-slate-600 font-bold uppercase tracking-tighter">/100</span>
      </div>
      <div className="space-y-4">
        {metrics.map((m, i) => (
          <div key={i} className="flex justify-between items-center py-2 border-b border-white/[0.02]">
            <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">{m.label}</span>
            <span className="text-sm font-headline font-bold text-white tracking-tighter">{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
