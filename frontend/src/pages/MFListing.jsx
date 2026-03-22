import React, { useState, useEffect, useCallback } from 'react';
import fundService from '../api/services/fundService';
import './MFListing.css';

const MFListing = () => {
    // UI State
    const [viewMode, setViewMode] = useState('grid');
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingFund, setEditingFund] = useState(null);
    const [formData, setFormData] = useState({
        scheme_code: '', scheme_name: '', amc_name: '',
        scheme_category: 'Equity Scheme', plan_type: 'Direct',
        inception_date: new Date().toISOString().split('T')[0]
    });

    // Data & Pagination State
    const [funds, setFunds] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Filter State
    const [categoryFilter, setCategoryFilter] = useState('All');
    const [amcSearch, setAmcSearch] = useState('');

    const fetchFunds = useCallback(async () => {
        setLoading(true);
        try {
            const skip = (currentPage - 1) * pageSize;
            const data = await fundService.getFunds(skip, pageSize, categoryFilter, amcSearch);
            setFunds(data.items);
            setTotal(data.total);
            setLoading(false);
        } catch (err) {
            console.error("Failed to fetch funds", err);
            setError("Connectivity error. Security protocol engaged.");
            setLoading(false);
        }
    }, [currentPage, pageSize, categoryFilter, amcSearch]);

    useEffect(() => {
        fetchFunds();
    }, [fetchFunds]);

    const handlePageSizeChange = (e) => {
        setPageSize(parseInt(e.target.value));
        setCurrentPage(1);
    };

    const handleDelete = async (code) => {
        if (window.confirm(`Permanently decommission scheme ${code} from the vault?`)) {
            try {
                await fundService.deleteFund(code);
                fetchFunds();
            } catch (err) {
                alert("Operation failed. Unauthorized access?");
            }
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        try {
            if (editingFund) {
                await fundService.updateFund(editingFund.scheme_code, formData);
            } else {
                await fundService.createFund(formData);
            }
            setIsFormOpen(false);
            setEditingFund(null);
            fetchFunds();
        } catch (err) {
            alert("Entry rejected by the ledger.");
        }
    };

    const openEdit = (fund) => {
        setEditingFund(fund);
        setFormData({ ...fund });
        setIsFormOpen(true);
    };

    const openAdd = () => {
        setEditingFund(null);
        setFormData({
            scheme_code: '', scheme_name: '', amc_name: '',
            scheme_category: 'Equity Scheme', plan_type: 'Direct',
            inception_date: new Date().toISOString().split('T')[0]
        });
        setIsFormOpen(true);
    };

    const totalPages = Math.ceil(total / pageSize);

    if (loading && funds.length === 0) return <div className="loading-container p-20 text-center uppercase tracking-widest font-heading">Scanning Vault Assets...</div>;

    return (
        <div className="mf-listing container reveal active">
            <header className="listing-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">High-Conviction Assets</span>
                <h1 className="font-heading heading-xl">Mutual Fund Vault</h1>

                <div className="glass-panel p-6 flex justify-between items-center mb-10 control-bar-elite">
                    <button onClick={openAdd} className="btn-premium btn-premium-primary py-2 px-6 text-xs whitespace-nowrap">
                        + New Mutual Fund
                    </button>

                    <div className="filter-chips-lux flex gap-4">
                        {['All', 'Equity', 'Debt', 'Hybrid'].map(f => (
                            <button
                                key={f}
                                className={`chip-lux ${categoryFilter === f ? 'active' : ''}`}
                                onClick={() => { setCategoryFilter(f); setCurrentPage(1); }}
                            >
                                {f.toUpperCase()}
                            </button>
                        ))}
                    </div>

                    <form onSubmit={(e) => e.preventDefault()} className="search-box-lux">
                        <input
                            type="text"
                            placeholder="SEARCH ASSETS..."
                            value={amcSearch}
                            onChange={(e) => { setAmcSearch(e.target.value); setCurrentPage(1); }}
                            className="search-input-elite"
                            style={{ width: '220px' }}
                        />
                    </form>

                    <div className="view-toggle-lux flex flex-row gap-2 items-center">
                        <button
                            className={`view-btn-icon ${viewMode === 'grid' ? 'active' : ''}`}
                            onClick={() => setViewMode('grid')}
                            title="Grid View"
                        >⊞</button>
                        <button
                            className={`view-btn-icon ${viewMode === 'list' ? 'active' : ''}`}
                            onClick={() => setViewMode('list')}
                            title="List View"
                        >≡</button>
                    </div>
                </div>
            </header>

            {isFormOpen && (
                <div className="modal-overlay glass">
                    <div className="glass-panel p-20 max-w-2xl w-full mx-5">
                        <h2 className="font-heading heading-md mb-10 uppercase tracking-widest">Asset Configuration</h2>
                        <form onSubmit={handleSave} className="flex flex-col gap-6">
                            <div className="grid grid-cols-2 gap-5">
                                <input
                                    className="chip-lux py-4 px-6 text-sm"
                                    placeholder="SCHEME CODE"
                                    value={formData.scheme_code}
                                    disabled={!!editingFund}
                                    onChange={e => setFormData({ ...formData, scheme_code: e.target.value })}
                                />
                                <input
                                    className="chip-lux py-4 px-6 text-sm"
                                    placeholder="SCHEME NAME"
                                    value={formData.scheme_name}
                                    onChange={e => setFormData({ ...formData, scheme_name: e.target.value })}
                                />
                                <input
                                    className="chip-lux py-4 px-6 text-sm"
                                    placeholder="AMC NAME"
                                    value={formData.amc_name}
                                    onChange={e => setFormData({ ...formData, amc_name: e.target.value })}
                                />
                                <input
                                    className="chip-lux py-4 px-6 text-sm"
                                    type="date"
                                    value={formData.inception_date}
                                    onChange={e => setFormData({ ...formData, inception_date: e.target.value })}
                                />
                            </div>
                            <div className="flex gap-5 mt-5">
                                <button type="submit" className="btn-premium btn-premium-primary flex-1">COMMIT CHANGES</button>
                                <button type="button" onClick={() => setIsFormOpen(false)} className="btn-premium btn-premium-outline">CANCEL</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {error && <div className="glass-panel p-5 text-center text-error border-error/30 mb-10">{error}</div>}

            {loading ? (
                <div className="loading-container p-20 text-center font-heading uppercase opacity-50">Synchronizing...</div>
            ) : (
                <>
                    {viewMode === 'grid' ? (
                        <div className="fund-grid-lux reveal active">
                            {funds.map(fund => (
                                <div key={fund.scheme_code} className="glass-panel glow-card fund-card-lux-elite">
                                    <div className="card-identity-row">
                                        {/* <div className="flex flex-col items-end"> */}

                                        <div className="rating-stars">★★★★★</div>
                                        <div className="flex gap-2 mt-4">
                                            <button onClick={() => openEdit(fund)} className="btn-action-small">✎</button>
                                            <button onClick={() => handleDelete(fund.scheme_code)} className="btn-action-small delete">✖</button>
                                        </div>
                                        {/* </div> */}
                                    </div>

                                    <div className="fund-title-box mt-auto">
                                        <h3 className="font-heading">{fund.scheme_name}</h3>
                                        <p className="text-xs uppercase tracking-widest text-muted">{fund.scheme_category} • {fund.plan_type}</p>
                                    </div>

                                    <div className="fund-metrics-row">
                                        <div className="metric-item items-end">
                                            <span className="m-label text-right">Latest NAV</span>
                                            <span className="m-value text-primary">₹{fund.metrics?.current_nav || '--'}</span>
                                        </div>
                                    </div>

                                    <div className="card-action-row mt-5">
                                        <a href={`#mf-detail-${fund.scheme_code}`} className="btn-premium btn-premium-outline">ANALYZE</a>
                                        <button className="btn-premium btn-premium-primary">ALLOCATE</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="glass-panel pro-table-container reveal active">
                            <table className="pro-table">
                                <thead>
                                    <tr>
                                        <th>ASSET NAME</th>
                                        <th>CATEGORY</th>
                                        <th>AMC LAYER</th>
                                        <th>CURRENT NAV</th>
                                        <th className="text-right">OPERATION</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {funds.map(fund => (
                                        <tr key={fund.scheme_code} className="hover:bg-white/5 transition-colors">
                                            <td className="font-heading text-sm font-semibold">
                                                <a href={`#mf-detail-${fund.scheme_code}`} className="text-white hover:text-primary transition-colors">{fund.scheme_name}</a>
                                            </td>
                                            <td className="text-xs uppercase text-muted font-bold tracking-wider">{fund.scheme_category}</td>
                                            <td className="text-xs text-muted">{fund.amc_name}</td>
                                            <td className="text-md font-extrabold text-primary">₹{fund.metrics?.current_nav || '--'}</td>
                                            <td className="text-right">
                                                <button onClick={() => openEdit(fund)} className="btn-action-small">✎</button>
                                                <button onClick={() => handleDelete(fund.scheme_code)} className="btn-action-small delete">✖</button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {total > pageSize && (
                        <div className="pagination-elite reveal active">
                            <div className="flex gap-4 items-center">
                                <span className="page-info">SHOW</span>
                                <select value={pageSize} onChange={handlePageSizeChange} className="chip-lux text-xs" style={{ background: 'transparent', padding: '0.2rem 0.5rem' }}>
                                    {[10, 20, 30, 50].map(sz => (
                                        <option key={sz} value={sz} style={{ color: 'black' }}>{sz}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex gap-8 items-center">
                                <button
                                    disabled={currentPage === 1}
                                    onClick={() => setCurrentPage(p => p - 1)}
                                    className="bck-btn btn-premium btn-premium-outline"
                                >← BACK</button>
                                <span className="page-info">
                                    {currentPage} / {totalPages}
                                </span>
                                <button
                                    disabled={currentPage === totalPages}
                                    onClick={() => setCurrentPage(p => p + 1)}
                                    className="fwd-btn btn-premium btn-premium-outline"
                                >NEXT →</button>
                            </div>

                            <div className="page-info opacity-30">
                                {total} TOTAL ASSETS
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default MFListing;
