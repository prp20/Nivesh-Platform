import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchStocks, setFilter, setPage } from "../store/slices/stocksSlice";

const SECTORS = ["Banking", "IT", "Pharma", "Auto", "FMCG", "Energy", "Telecom"];

export default function StockListing() {
  const dispatch = useDispatch();
  const { list, pagination, filters, status } = useSelector(s => s.stocks);
  const [search, setSearch] = useState("");

  useEffect(() => {
    dispatch(fetchStocks({ ...filters, page: pagination.page, limit: 25 }));
  }, [filters, pagination.page, dispatch]);

  const handleSearch = (e) => {
    if (e.key === "Enter" && search.trim()) {
      dispatch(fetchStocks({ q: search, limit: 25 }));
    }
  };

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold text-on-surface font-headline">Market Stocks</h1>
          <p className="text-on-surface-variant mt-1">Explore NSE & BSE listed equities</p>
        </div>

        {/* Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search symbol or company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleSearch}
            className="w-full px-4 py-3 rounded-lg bg-surface-container text-on-surface placeholder-on-surface-variant border border-outline-variant focus:border-secondary focus:outline-none transition"
          />
        </div>

        {/* Sector Filter Chips */}
        <div className="flex flex-wrap gap-2">
          {SECTORS.map(sector => (
            <button
              key={sector}
              onClick={() => dispatch(setFilter({
                key: "sector",
                val: filters.sector === sector ? "" : sector
              }))}
              className={`px-4 py-2 rounded-lg font-label text-sm transition ${
                filters.sector === sector
                  ? "bg-secondary text-background font-semibold"
                  : "bg-surface-container text-on-surface-variant border border-outline-variant hover:border-secondary"
              }`}
            >
              {sector}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {status === "loading" && (
        <div className="px-6 pb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="h-64 rounded-xl bg-surface-container animate-pulse"
              />
            ))}
          </div>
        </div>
      )}

      {/* Stock Cards Grid */}
      {status !== "loading" && (
        <div className="px-6 pb-6">
          {list.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              {list.map(stock => (
                <StockCard key={stock.symbol} stock={stock} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-on-surface-variant">
              No stocks found
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <button
              disabled={pagination.page <= 1}
              onClick={() => dispatch(setPage(pagination.page - 1))}
              className="px-4 py-2 rounded-lg bg-surface-container text-on-surface disabled:opacity-50 disabled:cursor-not-allowed hover:bg-outline-variant transition"
            >
              ← Previous
            </button>
            <span className="text-on-surface text-sm">
              Page {pagination.page} of {Math.ceil(pagination.total / 25)}
            </span>
            <button
              onClick={() => dispatch(setPage(pagination.page + 1))}
              className="px-4 py-2 rounded-lg bg-surface-container text-on-surface hover:bg-outline-variant transition"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StockCard({ stock }) {
  const changeColor = stock.change_pct >= 0 ? "text-secondary" : "text-error";

  return (
    <a
      href={`#/stocks/${stock.symbol}`}
      className="group relative h-64 rounded-xl overflow-hidden transition hover:scale-105"
    >
      {/* Glass Panel Background */}
      <div
        className="absolute inset-0"
        style={{
          background: "rgba(48, 53, 59, 0.6)",
          backdropFilter: "blur(20px)",
          borderTop: "1px solid rgba(69, 70, 76, 0.2)",
          borderLeft: "1px solid rgba(69, 70, 76, 0.2)",
        }}
      />

      {/* Gradient Accent on Hover */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-10 transition bg-gradient-to-br from-secondary to-primary" />

      {/* Content */}
      <div className="relative p-5 h-full flex flex-col justify-between z-10">
        {/* Top Section */}
        <div>
          <div className="flex items-start justify-between mb-3">
            <div>
              <p className="text-xs font-label text-secondary uppercase tracking-wider">
                {stock.sector}
              </p>
              <h3 className="text-xl font-bold text-on-surface font-headline mt-1">
                {stock.symbol}
              </h3>
            </div>
            <span className="text-xs bg-secondary bg-opacity-20 text-secondary px-2 py-1 rounded-full">
              {stock.market_cap_cat || "—"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant line-clamp-2">
            {stock.company_name}
          </p>
        </div>

        {/* Bottom Section - Metrics */}
        <div className="space-y-3">
          <div className="flex justify-between items-baseline">
            <span className="text-xs text-on-surface-variant">Price</span>
            <span className="text-2xl font-bold text-on-surface font-headline">
              ₹{stock.latest_close?.toFixed(2) ?? "—"}
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-xs text-on-surface-variant">Change</span>
            <span className={`text-sm font-semibold ${changeColor} font-label`}>
              {stock.change_pct != null
                ? `${stock.change_pct > 0 ? "+" : ""}${stock.change_pct}%`
                : "—"}
            </span>
          </div>

          {stock.rating_label && (
            <div className="flex justify-between items-center pt-2 border-t border-outline-variant border-opacity-20">
              <span className="text-xs text-on-surface-variant">Rating</span>
              <RatingBadge label={stock.rating_label} score={stock.total_score} />
            </div>
          )}
        </div>
      </div>
    </a>
  );
}

function RatingBadge({ label, score }) {
  const colors = {
    STRONG_BUY: { bg: "bg-secondary", text: "text-on-secondary" },
    BUY: { bg: "bg-secondary", text: "text-on-secondary" },
    HOLD: { bg: "bg-surface-tint", text: "text-on-primary" },
    SELL: { bg: "bg-error", text: "text-on-error" },
    STRONG_SELL: { bg: "bg-error", text: "text-on-error" },
  };

  const style = colors[label] || { bg: "bg-surface-container", text: "text-on-surface-variant" };

  return (
    <div className={`px-2.5 py-1 rounded-full text-xs font-semibold font-label ${style.bg} ${style.text}`}>
      {label.replace("_", " ")}
    </div>
  );
}
