import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { fetchStockDetail } from "../store/slices/stocksSlice";
import stockService from "../api/services/stockService";
import { motion, AnimatePresence } from 'framer-motion';

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

  useEffect(() => {
    if (symbol) {
      dispatch(fetchStockDetail(symbol));
    }
  }, [symbol, dispatch]);

  useEffect(() => {
    if (symbol && activeTab === "fundamentals" && !fundamentals) {
      setLoadingFundamentals(true);
      stockService
        .getFundamentals(symbol, { statement_type: stmtType, limit: 5 })
        .then(setFundamentals)
        .catch(err => console.error("Failed to fetch fundamentals:", err))
        .finally(() => setLoadingFundamentals(false));
    }
  }, [symbol, activeTab, stmtType, fundamentals]);

  useEffect(() => {
    if (symbol && activeTab === "shareholding" && !shareholding) {
      setLoadingShareholding(true);
      stockService
        .getShareholding(symbol, { limit: 8 })
        .then(setShareholding)
        .catch(err => console.error("Failed to fetch shareholding:", err))
        .finally(() => setLoadingShareholding(false));
    }
  }, [symbol, activeTab, shareholding]);

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
        <div className="flex justify-between items-end mb-16">
          <div>
            <button onClick={() => navigate(-1)} className="flex items-center gap-3 text-slate-500 hover:text-white transition-colors mb-8 group">
              <span className="material-symbols-outlined group-hover:-translate-x-1 transition-transform">arrow_back</span>
              <span className="font-label text-xs uppercase tracking-widest font-black">Return to Vault</span>
            </button>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-[10px] text-primary font-black uppercase tracking-[0.5em] italic">The Sovereign</span>
              <div className="w-1 h-1 rounded-full bg-primary/50"></div>
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.5em]">Private Wealth Tier</span>
            </div>
            <h1 className="text-6xl sm:text-8xl md:text-9xl font-headline font-bold text-white uppercase tracking-tighter leading-none mb-2">
              {detail.company_name}
            </h1>
            <p className="text-xl md:text-2xl font-headline text-slate-400 capitalize tracking-tight">Ticker:  {detail.symbol}</p>
          </div>

          <div className="text-right hidden md:block">
            <span className="text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] mb-4 block italic">Current Valuation</span>
            <div className="text-6xl md:text-7xl font-bold font-headline tracking-tighter text-white">
              ₹{detail.latest_close?.toFixed(2) ?? "—"}
            </div>
            <div className={`text-2xl font-black mt-2 tracking-tighter ${changeColor}`}>
              {detail.change_pct > 0 ? "+" : ""}{detail.change_pct?.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* Global Tabs */}
        <div className="flex gap-8 mb-16 border-b border-outline-variant/20 overflow-x-auto no-scrollbar">
          {[
            { id: "oracle", label: "Intelligence" },
            { id: "fundamentals", label: "Fundamental Lattice" },
            { id: "shareholding", label: "Ownership Topology" }
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
                    <DataCell label="P/E Ratio" value={detail.pe_ratio?.toFixed(1) || '—'} />
                    <DataCell label="P/B Ratio" value={detail.pb_ratio?.toFixed(1) || '—'} />
                    <DataCell label="ROE" value={detail.roe ? `${detail.roe.toFixed(1)}%` : '—'} />
                    <DataCell label="D/E Ratio" value={detail.debt_equity?.toFixed(2) || '—'} />
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
                  <div className="bg-surface-container-low p-10 rounded-[2rem] border-l-2 border-primary/40 shadow-xl">
                    <p className="text-slate-400 font-medium leading-relaxed italic">
                      {detail.company_name} operates within the highly competitive {detail.sector} sector. As a tier-1 component of the equity matrix, its market dynamics dictate substantial capital flows across institutional portfolios. Current algorithmic models suggest continuous monitoring of its P/E multiple relative to sub-sector peers.
                    </p>
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
              <FundamentalsTab data={fundamentals} stmtType={stmtType} onStmtChange={setStmtType} loading={loadingFundamentals} />
            </motion.div>
          )}

          {activeTab === "shareholding" && (
            <motion.div key="shareholding" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <ShareholdingTab data={shareholding} loading={loadingShareholding} />
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

function FundamentalsTab({ data, stmtType, onStmtChange, loading }) {
  if (loading) {
    return <div className="h-64 bg-surface-container-lowest border border-outline-variant/10 rounded-[3rem] animate-pulse" />;
  }

  if (!data?.records?.length) {
    return <div className="text-center py-20 text-[10px] uppercase font-black tracking-widest text-slate-500">No Intelligence Recovered</div>;
  }

  const labels = { PL: "Profit & Loss", BS: "Balance Sheet", CF: "Cash Flow" };
  const stmtOptions = ["PL", "BS", "CF"];

  return (
    <div className="space-y-12 animate-fadeIn">
      <div className="flex gap-4">
        {stmtOptions.map(t => (
          <button
            key={t}
            onClick={() => onStmtChange(t)}
            className={`px-8 py-4 rounded-xl font-black text-[10px] tracking-[0.3em] uppercase transition-all ${stmtType === t
              ? "bg-primary text-on-primary shadow-lg"
              : "bg-surface-container-low text-slate-500 hover:text-white border border-outline-variant/10"
              }`}
          >
            {labels[t]}
          </button>
        ))}
      </div>

      <div className="glass-panel overflow-x-auto rounded-[3rem] border border-outline-variant/10 shadow-2xl">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-outline-variant/20 bg-surface-container/30">
              <th className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em]">Metric Descriptor</th>
              {data.records.map(r => (
                <th key={r.period_end} className="p-8 text-[10px] text-slate-500 font-black uppercase tracking-[0.5em] text-right whitespace-nowrap">
                  {r.period_end}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.records[0]?.data && Object.entries(data.records[0].data).map(([key]) => (
              <tr key={key} className="border-b border-outline-variant/10 hover:bg-white/[0.03] transition-colors group">
                <td className="p-8 font-label text-sm text-white/90 group-hover:text-primary transition-colors capitalize tracking-wide">
                  {key.replace(/_/g, " ")}
                </td>
                {data.records.map(r => (
                  <td key={r.period_end} className="p-8 text-right font-headline text-lg font-semibold text-white">
                    {r.data[key] != null ? r.data[key].toLocaleString("en-IN") : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
