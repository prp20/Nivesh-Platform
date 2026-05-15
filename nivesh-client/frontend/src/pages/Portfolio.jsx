import { useState, useEffect, useCallback, useRef } from 'react';
import portfolioService from '../api/services/portfolioService';
import fundService from '../api/services/fundService';
import stockService from '../api/services/stockService';

// ── Add Holding Modal ──────────────────────────────────────────────────────────

const AddHoldingModal = ({ onClose, onSaved }) => {
    const [form, setForm] = useState({
        symbol: '', asset_type: 'STOCK', quantity: '', avg_cost: '',
        buy_date: new Date().toISOString().split('T')[0],
        broker: '', folio_number: '', notes: '',
    });
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSaving(true);
        try {
            await portfolioService.addHolding({
                symbol: form.symbol.toUpperCase(),
                asset_type: form.asset_type,
                quantity: parseFloat(form.quantity),
                avg_cost: parseFloat(form.avg_cost),
                buy_date: form.buy_date,
                broker: form.broker || undefined,
                folio_number: form.folio_number || undefined,
                notes: form.notes || undefined,
            });
            onSaved();
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to save holding');
        } finally {
            setSaving(false);
        }
    };

    const field = (key, label, type = 'text', required = false) => (
        <div className="flex flex-col gap-1">
            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">{label}</label>
            <input
                type={type}
                value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                required={required}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50 transition-colors"
            />
        </div>
    );

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
             onClick={onClose}>
            <div className="bg-[#161c22] border border-white/8 rounded-2xl p-6 w-full max-w-md shadow-2xl"
                 onClick={e => e.stopPropagation()}>
                <h3 className="text-base font-bold text-white mb-4">Add Holding</h3>
                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                    {field('symbol', 'Symbol / Scheme Code', 'text', true)}
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Type</label>
                        <select
                            value={form.asset_type}
                            onChange={e => setForm(f => ({ ...f, asset_type: e.target.value }))}
                            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                        >
                            <option value="STOCK">Stock</option>
                            <option value="FUND">Mutual Fund</option>
                        </select>
                    </div>
                    {field('quantity', 'Quantity', 'number', true)}
                    {field('avg_cost', 'Avg Cost (₹)', 'number', true)}
                    {field('buy_date', 'Buy Date', 'date', true)}
                    {field('broker', 'Broker / AMC')}
                    {form.asset_type === 'FUND' && field('folio_number', 'Folio Number')}
                    {error && <p className="text-red-400 text-xs">{error}</p>}
                    <div className="flex gap-3 pt-2">
                        <button type="button" onClick={onClose}
                            className="flex-1 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors">
                            Cancel
                        </button>
                        <button type="submit" disabled={saving}
                            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] text-sm font-black uppercase tracking-widest disabled:opacity-50">
                            {saving ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

// ── Portfolio Page ────────────────────────────────────────────────────────────

const Portfolio = () => {
    const [holdings, setHoldings] = useState([]);
    const [enriched, setEnriched] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const mountedRef = useRef(true);

    useEffect(() => {
        mountedRef.current = true;
        return () => { mountedRef.current = false; };
    }, []);

    const loadHoldings = useCallback(async () => {
        try {
            const raw = await portfolioService.getHoldings();
            if (!mountedRef.current) return;
            setHoldings(raw);
            const results = await Promise.allSettled(
                raw.map(async (h) => {
                    let currentPrice;
                    try {
                        if (h.asset_type === 'STOCK') {
                            const detail = await stockService.getStockDetail(h.symbol);
                            currentPrice = detail?.latest_close;
                        } else {
                            const detail = await fundService.getFundDetail(h.symbol);
                            currentPrice = detail?.metrics?.current_nav;
                        }
                    } catch {
                        // Offline or not cached — price stays undefined, shows —
                    }
                    const invested = h.avg_cost * h.quantity;
                    const currentValue = currentPrice ? currentPrice * h.quantity : undefined;
                    const pnl = currentValue !== undefined ? currentValue - invested : undefined;
                    const pnlPct = pnl !== undefined && invested > 0 ? (pnl / invested) * 100 : undefined;
                    return { ...h, currentPrice, currentValue, pnl, pnlPct, invested };
                })
            );
            if (!mountedRef.current) return;
            // Map both fulfilled and rejected entries — rejected get raw holding with — values
            setEnriched(results.map((r, i) =>
                r.status === 'fulfilled'
                    ? r.value
                    : { ...raw[i], invested: raw[i].avg_cost * raw[i].quantity }
            ));
        } catch (err) {
            console.error('[Portfolio] Failed to load holdings:', err);
        } finally {
            if (mountedRef.current) setLoading(false);
        }
    }, []);

    useEffect(() => { loadHoldings(); }, [loadHoldings]);

    const handleDelete = async (id) => {
        if (!window.confirm('Remove this holding?')) return;
        try {
            await portfolioService.deleteHolding(id);
            await loadHoldings();
        } catch (err) {
            console.error('[Portfolio] Delete failed:', err);
        }
    };

    const fmt = (n) => n != null ? `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
    const fmtPct = (n) => n != null ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '—';

    const totalInvested = enriched.reduce((s, h) => s + h.invested, 0);
    const totalCurrent  = enriched.reduce((s, h) => s + (h.currentValue ?? h.invested), 0);
    const totalPnl      = totalCurrent - totalInvested;
    const totalPnlPct   = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

    return (
        <div className="min-h-screen bg-[#0a0f12] p-6 md:p-10">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-headline font-bold text-white">Portfolio</h1>
                        <p className="text-[11px] text-slate-500 uppercase tracking-widest mt-1">
                            {enriched.length} holding{enriched.length !== 1 ? 's' : ''}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest"
                    >
                        <span className="material-symbols-outlined text-[16px]">add</span>
                        Add Holding
                    </button>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                    {[
                        { label: 'Invested', value: fmt(totalInvested), color: 'text-white' },
                        { label: 'Current Value', value: fmt(totalCurrent), color: 'text-white' },
                        {
                            label: 'Total P&L',
                            value: `${totalPnl >= 0 ? '+' : '-'}${fmt(totalPnl)} (${fmtPct(totalPnlPct)})`,
                            color: totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400',
                        },
                    ].map(card => (
                        <div key={card.label} className="bg-[#161c22] border border-white/8 rounded-2xl p-5">
                            <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">{card.label}</p>
                            <p className={`text-xl font-bold ${card.color}`}>{card.value}</p>
                        </div>
                    ))}
                </div>

                {/* Holdings Table */}
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-10 h-10 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : enriched.length === 0 ? (
                    <div className="text-center py-16">
                        <span className="material-symbols-outlined text-6xl text-slate-700 font-thin">account_balance_wallet</span>
                        <p className="text-slate-500 text-sm mt-4">No holdings yet. Add your first holding.</p>
                    </div>
                ) : (
                    <div className="bg-[#161c22] border border-white/8 rounded-2xl overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-white/5">
                                        {['Symbol', 'Type', 'Qty', 'Avg Cost', 'Current', 'P&L', 'P&L %', ''].map(h => (
                                            <th key={h} className="px-4 py-3 text-left text-[9px] font-black uppercase tracking-widest text-slate-500">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {enriched.map(h => (
                                        <tr key={h.id} className="border-b border-white/4 hover:bg-white/2 transition-colors">
                                            <td className="px-4 py-3 text-sm font-bold text-white">{h.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full
                                                    ${h.asset_type === 'STOCK' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'}`}>
                                                    {h.asset_type}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-sm text-slate-300">{h.quantity}</td>
                                            <td className="px-4 py-3 text-sm text-slate-300">{fmt(h.avg_cost)}</td>
                                            <td className="px-4 py-3 text-sm text-slate-300">
                                                {h.currentPrice ? fmt(h.currentPrice) : '—'}
                                            </td>
                                            <td className={`px-4 py-3 text-sm font-semibold
                                                ${h.pnl == null ? 'text-slate-500' : h.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {h.pnl != null ? `${h.pnl >= 0 ? '+' : '-'}${fmt(h.pnl)}` : '—'}
                                            </td>
                                            <td className={`px-4 py-3 text-sm font-semibold
                                                ${h.pnlPct == null ? 'text-slate-500' : h.pnlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {fmtPct(h.pnlPct)}
                                            </td>
                                            <td className="px-4 py-3">
                                                <button
                                                    onClick={() => handleDelete(h.id)}
                                                    className="text-slate-600 hover:text-red-400 transition-colors"
                                                    title="Remove holding"
                                                >
                                                    <span className="material-symbols-outlined text-[16px]">delete</span>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>

            {showAdd && (
                <AddHoldingModal
                    onClose={() => setShowAdd(false)}
                    onSaved={() => { setShowAdd(false); loadHoldings(); }}
                />
            )}
        </div>
    );
};

export default Portfolio;
