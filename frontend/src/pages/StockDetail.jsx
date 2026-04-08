import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { fetchStockDetail } from "../store/slices/stocksSlice";
import stockService from "../api/services/stockService";

export default function StockDetail() {
  const { symbol } = useParams();
  const dispatch = useDispatch();
  const { detail, status } = useSelector(s => s.stocks);
  const [activeTab, setActiveTab] = useState("overview");
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
      <div className="min-h-screen bg-surface p-6">
        <div className="h-40 bg-surface-container rounded-xl animate-pulse" />
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "fundamentals", label: "Fundamentals" },
    { id: "shareholding", label: "Shareholding" },
  ];

  return (
    <div className="min-h-screen bg-surface">
      {/* Header Hero */}
      <div className="relative p-6 border-b border-outline-variant">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <p className="text-sm font-label text-secondary uppercase tracking-wider mb-2">
                {detail.sector}
              </p>
              <h1 className="text-4xl font-bold text-on-surface font-headline">
                {detail.symbol}
              </h1>
              <p className="text-on-surface-variant mt-1">{detail.company_name}</p>
            </div>

            <div className="text-right">
              <p className="text-4xl font-bold text-on-surface font-headline">
                ₹{detail.latest_close?.toFixed(2)}
              </p>
              <p
                className={`text-lg font-semibold mt-1 ${
                  detail.change_pct >= 0 ? "text-secondary" : "text-error"
                }`}
              >
                {detail.change_pct > 0 ? "+" : ""}{detail.change_pct?.toFixed(2)}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="sticky top-0 bg-surface border-b border-outline-variant z-40">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 font-label text-sm font-medium border-b-2 transition ${
                  activeTab === tab.id
                    ? "text-secondary border-secondary"
                    : "text-on-surface-variant border-transparent hover:text-on-surface"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto p-6">
        {activeTab === "overview" && <OverviewTab detail={detail} />}
        {activeTab === "fundamentals" && (
          <FundamentalsTab
            data={fundamentals}
            stmtType={stmtType}
            onStmtChange={setStmtType}
            loading={loadingFundamentals}
          />
        )}
        {activeTab === "shareholding" && (
          <ShareholdingTab data={shareholding} loading={loadingShareholding} />
        )}
      </div>
    </div>
  );
}

function OverviewTab({ detail }) {
  const metrics = [
    {
      label: "Latest Close",
      value: detail.latest_close ? `₹${detail.latest_close.toFixed(2)}` : "—",
      highlight: true,
    },
    {
      label: "Day High",
      value: detail.latest_high ? `₹${detail.latest_high.toFixed(2)}` : "—",
    },
    {
      label: "Day Low",
      value: detail.latest_low ? `₹${detail.latest_low.toFixed(2)}` : "—",
    },
    {
      label: "Volume",
      value: detail.latest_volume ? `${(detail.latest_volume / 1000000).toFixed(2)}M` : "—",
    },
  ];

  const ratios = [
    { label: "P/E Ratio", value: detail.pe_ratio?.toFixed(2) },
    { label: "P/B Ratio", value: detail.pb_ratio?.toFixed(2) },
    { label: "ROE", value: detail.roe ? `${detail.roe.toFixed(1)}%` : null },
    { label: "Debt/Equity", value: detail.debt_equity?.toFixed(2) },
    { label: "RSI (14)", value: detail.rsi_14?.toFixed(1) },
    { label: "MACD", value: detail.macd_hist?.toFixed(3) },
  ];

  return (
    <div className="space-y-6">
      {/* OHLCV Section */}
      <div>
        <h3 className="text-lg font-bold text-on-surface font-headline mb-4">
          Trading Metrics
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {metrics.map(m => (
            <GlassCard key={m.label} highlight={m.highlight}>
              <p className="text-xs text-on-surface-variant uppercase tracking-wider mb-2">
                {m.label}
              </p>
              <p
                className={`text-2xl font-bold font-headline ${
                  m.highlight ? "text-secondary" : "text-on-surface"
                }`}
              >
                {m.value}
              </p>
            </GlassCard>
          ))}
        </div>
      </div>

      {/* Ratios Section */}
      <div>
        <h3 className="text-lg font-bold text-on-surface font-headline mb-4">
          Financial Metrics
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {ratios.map(r => (
            <GlassCard key={r.label}>
              <p className="text-xs text-on-surface-variant uppercase tracking-wider mb-2">
                {r.label}
              </p>
              <p className="text-xl font-bold text-on-surface font-headline">
                {r.value ?? "—"}
              </p>
            </GlassCard>
          ))}
        </div>
      </div>
    </div>
  );
}

function FundamentalsTab({ data, stmtType, onStmtChange, loading }) {
  if (loading) {
    return <div className="h-64 bg-surface-container rounded-xl animate-pulse" />;
  }

  if (!data?.records?.length) {
    return (
      <div className="text-center py-12 text-on-surface-variant">
        No financial data available
      </div>
    );
  }

  const labels = { PL: "Profit & Loss", BS: "Balance Sheet", CF: "Cash Flow" };
  const stmtOptions = ["PL", "BS", "CF"];

  return (
    <div className="space-y-4">
      {/* Statement Type Selector */}
      <div className="flex gap-2">
        {stmtOptions.map(t => (
          <button
            key={t}
            onClick={() => onStmtChange(t)}
            className={`px-4 py-2 rounded-lg font-label text-sm transition ${
              stmtType === t
                ? "bg-secondary text-background font-semibold"
                : "bg-surface-container text-on-surface-variant border border-outline-variant hover:border-secondary"
            }`}
          >
            {labels[t]}
          </button>
        ))}
      </div>

      {/* Table */}
      <GlassCard className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant">
              <th className="text-left p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
                Metric
              </th>
              {data.records.map(r => (
                <th
                  key={r.period_end}
                  className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs whitespace-nowrap"
                >
                  {r.period_end}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.records[0]?.data &&
              Object.entries(data.records[0].data).map(([key]) => (
                <tr key={key} className="border-b border-outline-variant hover:bg-surface-container bg-opacity-30 transition">
                  <td className="p-4 text-on-surface font-headline">{key.replace(/_/g, " ").toUpperCase()}</td>
                  {data.records.map(r => (
                    <td key={r.period_end} className="text-right p-4 text-on-surface font-label">
                      {r.data[key] != null ? r.data[key].toLocaleString("en-IN") : "—"}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </GlassCard>
    </div>
  );
}

function ShareholdingTab({ data, loading }) {
  if (loading) {
    return <div className="h-64 bg-surface-container rounded-xl animate-pulse" />;
  }

  if (!data?.records?.length) {
    return (
      <div className="text-center py-12 text-on-surface-variant">
        No shareholding data available
      </div>
    );
  }

  return (
    <GlassCard className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-outline-variant">
            <th className="text-left p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              Period
            </th>
            <th className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              Promoter %
            </th>
            <th className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              FII %
            </th>
            <th className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              DII %
            </th>
            <th className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              Public %
            </th>
            <th className="text-right p-4 text-on-surface-variant font-label uppercase tracking-wider text-xs">
              Pledged %
            </th>
          </tr>
        </thead>
        <tbody>
          {data.records.map(r => (
            <tr key={r.period_end} className="border-b border-outline-variant hover:bg-surface-container bg-opacity-30 transition">
              <td className="p-4 text-on-surface font-headline">{r.period_end}</td>
              <td className="text-right p-4 text-on-surface font-label">
                {r.promoter_pct?.toFixed(2) ?? "—"}
              </td>
              <td className="text-right p-4 text-secondary font-label">
                {r.fii_pct?.toFixed(2) ?? "—"}
              </td>
              <td className="text-right p-4 text-on-surface font-label">
                {r.dii_pct?.toFixed(2) ?? "—"}
              </td>
              <td className="text-right p-4 text-on-surface font-label">
                {r.public_pct?.toFixed(2) ?? "—"}
              </td>
              <td className="text-right p-4 text-on-surface-variant font-label">
                {r.pledged_pct?.toFixed(2) ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </GlassCard>
  );
}

function GlassCard({ children, highlight = false, className = "" }) {
  return (
    <div
      className={`rounded-xl p-6 transition ${className}`}
      style={{
        background: highlight
          ? "rgba(102, 221, 139, 0.05)"
          : "rgba(48, 53, 59, 0.6)",
        backdropFilter: "blur(20px)",
        borderTop: "1px solid rgba(69, 70, 76, 0.2)",
        borderLeft: "1px solid rgba(69, 70, 76, 0.2)",
      }}
    >
      {children}
    </div>
  );
}
