import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchScreener } from "../store/slices/stocksSlice";

const SECTORS = ["Banking","IT","Pharma","Auto","FMCG","Energy","Telecom","NBFC","Infrastructure","Metals"];
const RATINGS = ["STRONG_BUY","BUY","HOLD","SELL","STRONG_SELL"];
const MKT_CAPS = [["Large","Large Cap"],["Mid","Mid Cap"],["Small","Small Cap"]];

export default function Screener() {
  const dispatch = useDispatch();
  const { screenerResult, status } = useSelector(s => s.stocks);
  const [filters, setFilters] = useState({
    min_roe: "", max_pe: "", max_debt_equity: "",
    min_pat_margin: "", min_revenue_growth: "",
    sector: "", market_cap_cat: "", rating_label: "",
    sort_by: "total_score", order: "desc",
  });

  const setF = (key, val) => setFilters(f => ({ ...f, [key]: val }));

  const apply = () => {
    const clean = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== "" && v !== null)
    );
    dispatch(fetchScreener(clean));
  };

  const reset = () => {
    setFilters({ 
      min_roe: "", max_pe: "", max_debt_equity: "",
      min_pat_margin: "", min_revenue_growth: "",
      sector: "", market_cap_cat: "", rating_label: "",
      sort_by: "total_score", order: "desc" 
    });
  };

  return (
    <div className="min-h-screen bg-surface flex gap-6 p-6">
      {/* Filter Sidebar */}
      <aside className="w-80 space-y-4">
        <h2 className="text-xl font-bold text-on-surface font-headline">Filters</h2>

        {/* Sector */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Sector
          </label>
          <select 
            value={filters.sector} 
            onChange={e => setF("sector", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          >
            <option value="">All Sectors</option>
            {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {/* Market Cap */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Market Cap
          </label>
          <div className="flex flex-col gap-2">
            {MKT_CAPS.map(([val, label]) => (
              <button
                key={val}
                onClick={() => setF("market_cap_cat", filters.market_cap_cat === val ? "" : val)}
                className={`px-3 py-2 rounded-lg text-sm font-label transition ${
                  filters.market_cap_cat === val
                    ? "bg-secondary text-background font-semibold"
                    : "bg-surface-container text-on-surface-variant border border-outline-variant hover:border-secondary"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Rating */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Rating
          </label>
          <div className="flex flex-col gap-2">
            {RATINGS.map(r => (
              <button
                key={r}
                onClick={() => setF("rating_label", filters.rating_label === r ? "" : r)}
                className={`px-3 py-2 rounded-lg text-sm font-label transition ${
                  filters.rating_label === r
                    ? "bg-secondary text-background font-semibold"
                    : "bg-surface-container text-on-surface-variant border border-outline-variant hover:border-secondary"
                }`}
              >
                {r.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Min ROE */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Min ROE (%)
          </label>
          <input 
            type="number" 
            placeholder="e.g. 15"
            value={filters.min_roe} 
            onChange={e => setF("min_roe", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Max P/E */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Max P/E
          </label>
          <input 
            type="number" 
            placeholder="e.g. 30"
            value={filters.max_pe} 
            onChange={e => setF("max_pe", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Max Debt/Equity */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Max Debt/Equity
          </label>
          <input 
            type="number" 
            placeholder="e.g. 1.0"
            value={filters.max_debt_equity} 
            onChange={e => setF("max_debt_equity", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Min PAT Margin */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Min PAT Margin (%)
          </label>
          <input 
            type="number" 
            placeholder="e.g. 10"
            value={filters.min_pat_margin} 
            onChange={e => setF("min_pat_margin", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Min Revenue Growth */}
        <div>
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-label block mb-2">
            Min Revenue Growth (%)
          </label>
          <input 
            type="number" 
            placeholder="e.g. 15"
            value={filters.min_revenue_growth} 
            onChange={e => setF("min_revenue_growth", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-4">
          <button 
            onClick={apply}
            className="flex-1 px-4 py-2 rounded-lg bg-secondary text-background font-semibold hover:bg-opacity-90 transition"
          >
            Apply Filters
          </button>
          <button 
            onClick={reset}
            className="flex-1 px-4 py-2 rounded-lg bg-surface-container text-on-surface border border-outline-variant hover:border-secondary transition"
          >
            Reset
          </button>
        </div>
      </aside>

      {/* Results */}
      <main className="flex-1">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-on-surface font-headline">
            {screenerResult?.length || 0} stocks found
          </h3>
          <select 
            value={filters.sort_by}
            onChange={e => setF("sort_by", e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm border border-outline-variant focus:border-secondary focus:outline-none transition"
          >
            <option value="total_score">Rating Score</option>
            <option value="roe">ROE</option>
            <option value="pe_ratio">P/E</option>
            <option value="revenue_growth">Revenue Growth</option>
            <option value="symbol">Symbol</option>
          </select>
        </div>

        {status === "loading" ? (
          <div className="h-96 bg-surface-container rounded-xl animate-pulse" />
        ) : screenerResult?.length > 0 ? (
          <div className="overflow-x-auto rounded-xl" style={{
            background: "rgba(48, 53, 59, 0.6)",
            backdropFilter: "blur(20px)",
            borderTop: "1px solid rgba(69, 70, 76, 0.2)",
            borderLeft: "1px solid rgba(69, 70, 76, 0.2)",
          }}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-outline-variant">
                  <th className="text-left p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Symbol</th>
                  <th className="text-left p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Company</th>
                  <th className="text-left p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Sector</th>
                  <th className="text-right p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Price</th>
                  <th className="text-right p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">P/E</th>
                  <th className="text-right p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">ROE %</th>
                  <th className="text-right p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">D/E</th>
                  <th className="text-right p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Rev Growth %</th>
                  <th className="text-left p-4 text-on-surface-variant font-label uppercase text-xs tracking-wider">Rating</th>
                </tr>
              </thead>
              <tbody>
                {screenerResult.map(s => (
                  <tr 
                    key={s.symbol} 
                    className="border-b border-outline-variant hover:bg-surface-container hover:bg-opacity-30 transition cursor-pointer"
                    onClick={() => { window.location.hash = `#/stocks/${s.symbol}` }}
                  >
                    <td className="p-4 font-headline text-on-surface">{s.symbol}</td>
                    <td className="p-4 text-on-surface-variant">{s.company_name}</td>
                    <td className="p-4 text-on-surface-variant">{s.sector}</td>
                    <td className="p-4 text-right text-on-surface">₹{s.latest_close?.toFixed(2) ?? "—"}</td>
                    <td className="p-4 text-right text-on-surface">{s.pe_ratio?.toFixed(1) ?? "—"}</td>
                    <td className={`p-4 text-right font-semibold ${s.roe >= 15 ? "text-secondary" : "text-on-surface"}`}>
                      {s.roe?.toFixed(1) ?? "—"}%
                    </td>
                    <td className={`p-4 text-right ${s.debt_equity > 1 ? "text-error" : "text-on-surface"}`}>
                      {s.debt_equity?.toFixed(2) ?? "—"}
                    </td>
                    <td className={`p-4 text-right ${s.revenue_growth >= 0 ? "text-secondary" : "text-error"}`}>
                      {s.revenue_growth?.toFixed(1) ?? "—"}%
                    </td>
                    <td className="p-4"><RatingBadge label={s.rating_label} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-on-surface-variant">
            {status === "failed" ? "Failed to load results" : "No stocks found. Adjust your filters."}
          </div>
        )}
      </main>
    </div>
  );
}

function RatingBadge({ label }) {
  if (!label) return <span className="text-xs text-on-surface-variant">—</span>;
  const colors = {
    STRONG_BUY: { bg: "bg-secondary", text: "text-background" },
    BUY: { bg: "bg-secondary", text: "text-background" },
    HOLD: { bg: "bg-surface-tint", text: "text-on-primary" },
    SELL: { bg: "bg-error", text: "text-on-error" },
    STRONG_SELL: { bg: "bg-error", text: "text-on-error" },
  };
  const style = colors[label] || { bg: "bg-surface-container", text: "text-on-surface-variant" };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-semibold font-label ${style.bg} ${style.text}`}>
      {label.replace("_", " ")}
    </span>
  );
}
