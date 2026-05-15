import { useState, useEffect } from 'react';
import watchlistService from '../api/services/watchlistService';

const Watchlist = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [form, setForm] = useState({ symbol: '', asset_type: 'STOCK', notes: '', alert_above: '', alert_below: '' });
    const [formError, setFormError] = useState(null);

    const load = async () => {
        try {
            const data = await watchlistService.get();
            setItems(data);
        } catch (err) {
            console.error('[Watchlist] Load failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const handleAdd = async (e) => {
        e.preventDefault();
        setFormError(null);
        try {
            await watchlistService.add({
                symbol: form.symbol.toUpperCase(),
                asset_type: form.asset_type,
                notes: form.notes || undefined,
                alert_above: form.alert_above ? parseFloat(form.alert_above) : undefined,
                alert_below: form.alert_below ? parseFloat(form.alert_below) : undefined,
            });
            setForm({ symbol: '', asset_type: 'STOCK', notes: '', alert_above: '', alert_below: '' });
            setShowAdd(false);
            await load();
        } catch (err) {
            setFormError(err.response?.data?.detail ?? 'Failed to add to watchlist');
        }
    };

    const handleRemove = async (id) => {
        try {
            await watchlistService.remove(id);
            await load();
        } catch (err) {
            console.error('[Watchlist] Remove failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0f12] p-6 md:p-10">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-headline font-bold text-white">Watchlist</h1>
                        <p className="text-[11px] text-slate-500 uppercase tracking-widest mt-1">
                            {items.length} item{items.length !== 1 ? 's' : ''}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowAdd(v => !v)}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest"
                    >
                        <span className="material-symbols-outlined text-[16px]">{showAdd ? 'close' : 'add'}</span>
                        {showAdd ? 'Cancel' : 'Add'}
                    </button>
                </div>

                {/* Add Form */}
                {showAdd && (
                    <form onSubmit={handleAdd}
                        className="bg-[#161c22] border border-white/8 rounded-2xl p-5 mb-6 flex flex-wrap gap-3 items-end">
                        <div className="flex flex-col gap-1 flex-1 min-w-[140px]">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Symbol</label>
                            <input
                                required
                                placeholder="RELIANCE"
                                value={form.symbol}
                                onChange={e => setForm(f => ({ ...f, symbol: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Type</label>
                            <select
                                value={form.asset_type}
                                onChange={e => setForm(f => ({ ...f, asset_type: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            >
                                <option value="STOCK">Stock</option>
                                <option value="FUND">Fund</option>
                            </select>
                        </div>
                        <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Notes</label>
                            <input
                                placeholder="Optional notes"
                                value={form.notes}
                                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1 w-24">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Alert ▲</label>
                            <input
                                type="number" step="any"
                                placeholder="₹"
                                value={form.alert_above}
                                onChange={e => setForm(f => ({ ...f, alert_above: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1 w-24">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Alert ▼</label>
                            <input
                                type="number" step="any"
                                placeholder="₹"
                                value={form.alert_below}
                                onChange={e => setForm(f => ({ ...f, alert_below: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        {formError && <p className="w-full text-red-400 text-xs">{formError}</p>}
                        <button type="submit"
                            className="px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest">
                            Add
                        </button>
                    </form>
                )}

                {/* Items Grid */}
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-10 h-10 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-center py-16">
                        <span className="material-symbols-outlined text-6xl text-slate-700 font-thin">bookmark</span>
                        <p className="text-slate-500 text-sm mt-4">No items in watchlist. Add stocks or funds to track.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {items.map(item => (
                            <div key={item.id}
                                className="bg-[#161c22] border border-white/8 rounded-2xl p-4 flex flex-col gap-2 group">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-base font-bold text-white">{item.symbol}</span>
                                        <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full
                                            ${item.asset_type === 'STOCK' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'}`}>
                                            {item.asset_type}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => handleRemove(item.id)}
                                        className="text-slate-700 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                        title="Remove"
                                    >
                                        <span className="material-symbols-outlined text-[16px]">close</span>
                                    </button>
                                </div>
                                {item.display_name && (
                                    <p className="text-[11px] text-slate-400">{item.display_name}</p>
                                )}
                                {item.notes && (
                                    <p className="text-[11px] text-slate-500 italic">{item.notes}</p>
                                )}
                                {(item.alert_above || item.alert_below) && (
                                    <div className="flex gap-3 mt-1">
                                        {item.alert_above && (
                                            <span className="text-[10px] text-emerald-400 font-semibold">
                                                ▲ ₹{item.alert_above}
                                            </span>
                                        )}
                                        {item.alert_below && (
                                            <span className="text-[10px] text-red-400 font-semibold">
                                                ▼ ₹{item.alert_below}
                                            </span>
                                        )}
                                    </div>
                                )}
                                <p className="text-[9px] text-slate-700 mt-auto">
                                    Added {new Date(item.added_at).toLocaleDateString('en-IN')}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Watchlist;
