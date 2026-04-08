import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchStocks, setFilter, setPage } from "../store/slices/stocksSlice";

export default function StockListing() {
  const dispatch  = useDispatch();
  const { list, pagination, filters, status } = useSelector(s => s.stocks);
  const [search, setSearch] = useState("");

  useEffect(() => {
    dispatch(fetchStocks({ ...filters, page: pagination.page, limit: 25 }));
  }, [filters, pagination.page, dispatch]);

  return (
    <div className="cal-page">
      <div className="cal-page-header">
        <h1 className="cal-heading">Stocks</h1>
        <input
          className="cal-search-input"
          placeholder="Search symbol or company..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === "Enter" && dispatch(fetchStocks({ q: search }))}
        />
      </div>

      {/* Filter Bar */}
      <div className="cal-filter-bar">
        {["Banking","IT","Pharma","Auto","FMCG","Energy","Telecom"].map(sec => (
          <button
            key={sec}
            className={`cal-chip ${filters.sector === sec ? "cal-chip--active" : ""}`}
            onClick={() => dispatch(setFilter({ key: "sector", val: filters.sector === sec ? "" : sec }))}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* Stock Table */}
      {status === "loading" ? (
        <div className="cal-loading-skeleton" />
      ) : (
        <table className="cal-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Price</th>
              <th>Change</th>
              <th>Rating</th>
            </tr>
          </thead>
          <tbody>
            {list.map(stock => (
              <tr
                key={stock.symbol}
                className="cal-table-row cal-table-row--clickable"
                onClick={() => { window.location.hash = `#/stocks/${stock.symbol}` }}
              >
                <td className="cal-symbol">{stock.symbol}</td>
                <td>{stock.company_name}</td>
                <td><span className="cal-badge">{stock.sector}</span></td>
                <td>₹{stock.latest_close?.toFixed(2) ?? "—"}</td>
                <td className={stock.change_pct >= 0 ? "cal-positive" : "cal-negative"}>
                  {stock.change_pct != null ? `${stock.change_pct > 0 ? "+" : ""}${stock.change_pct}%` : "—"}
                </td>
                <td><RatingBadge label={stock.rating_label} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      <div className="cal-pagination">
        <button disabled={pagination.page <= 1} onClick={() => dispatch(setPage(pagination.page - 1))}>←</button>
        <span>Page {pagination.page} of {Math.ceil(pagination.total / 25)}</span>
        <button onClick={() => dispatch(setPage(pagination.page + 1))}>→</button>
      </div>
    </div>
  );
}

function RatingBadge({ label }) {
  if (!label) return <span className="cal-badge cal-badge--muted">—</span>;
  const colors = {
    STRONG_BUY: "cal-badge--green",
    BUY:        "cal-badge--teal",
    HOLD:       "cal-badge--amber",
    SELL:       "cal-badge--orange",
    STRONG_SELL:"cal-badge--red",
  };
  return <span className={`cal-badge ${colors[label] || "cal-badge--muted"}`}>{label.replace("_", " ")}</span>;
}
