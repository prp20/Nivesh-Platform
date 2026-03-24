import React, { useState, useEffect, useCallback } from 'react';
import fundService from '../api/services/fundService';
import './MFListing.css';

// SVG Icons
const IconPencil = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
    </svg>
);

const IconTrash = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="3 6 5 6 21 6"></polyline>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        <line x1="10" y1="11" x2="10" y2="17"></line>
        <line x1="14" y1="11" x2="14" y2="17"></line>
    </svg>
);

const MFListing = () => {
    // UI State
    const [viewMode, setViewMode] = useState('grid');
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [deletingCode, setDeletingCode] = useState(null);
    const [editingFund, setEditingFund] = useState(null);
    const [formData, setFormData] = useState({
        scheme_code: '', scheme_name: '', amc_name: '',
        scheme_category: 'Equity Scheme', plan_type: 'Direct',
        inception_date: new Date().toISOString().split('T')[0],
        benchmark_index_code: ''
    });

    // Data & Pagination State
    const [funds, setFunds] = useState([]);
    const [benchmarks, setBenchmarks] = useState([]);
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

    const fetchBenchmarks = async () => {
        try {
            const data = await fundService.getBenchmarks();
            setBenchmarks(data);
        } catch (err) {
            console.error("Failed to fetch benchmarks", err);
        }
    };

    useEffect(() => {
        fetchFunds();
        fetchBenchmarks();
    }, [fetchFunds]);

    const handlePageSizeChange = (e) => {
        setPageSize(parseInt(e.target.value));
        setCurrentPage(1);
    };

    const handleDelete = (code) => {
        setDeletingCode(code);
        setIsDeleteModalOpen(true);
    };

    const confirmDelete = async () => {
        if (!deletingCode) return;
        try {
            await fundService.deleteFund(deletingCode);
            setIsDeleteModalOpen(false);
            setDeletingCode(null);
            fetchFunds();
        } catch (err) {
            alert("Operation failed. Unauthorized access?");
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        
        // Validation: Benchmark Index is Mandatory
        if (!formData.benchmark_index_code) {
            alert("BENCHMARK SELECTION REQUIRED. Security protocol forbids unreferenced assets.");
            return;
        }

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
        setFormData({ 
            scheme_code: fund.scheme_code,
            scheme_name: fund.scheme_name,
            amc_name: fund.amc_name,
            scheme_category: fund.scheme_category,
            plan_type: fund.plan_type,
            inception_date: fund.inception_date,
            benchmark_index_code: fund.benchmark_index_code || ''
        });
        setIsFormOpen(true);
    };

    const openAdd = () => {
        setEditingFund(null);
        setFormData({
            scheme_code: '', scheme_name: '', amc_name: '',
            scheme_category: 'Equity Scheme', plan_type: 'Direct',
            inception_date: new Date().toISOString().split('T')[0],
            benchmark_index_code: ''
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
                    <div className="glass-panel p-32 max-w-2xl w-full mx-5 reveal active">
                        <h2 className="font-heading heading-md mb-10 uppercase tracking-widest text-primary">Asset Configuration</h2>
                        <form onSubmit={handleSave} className="flex flex-col gap-8">
                            <div className="grid grid-cols-2 gap-6">
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Scheme Code</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="IDENTIFIER"
                                        value={formData.scheme_code}
                                        disabled={!!editingFund}
                                        onChange={e => setFormData({ ...formData, scheme_code: e.target.value })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Scheme Name</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="ASSET FULL NAME"
                                        value={formData.scheme_name}
                                        onChange={e => setFormData({ ...formData, scheme_name: e.target.value })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">AMC Name</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="MANAGEMENT ENTITY"
                                        value={formData.amc_name}
                                        onChange={e => setFormData({ ...formData, amc_name: e.target.value })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Inception Date</label>
                                    <input
                                        className="form-input-elite"
                                        type="date"
                                        value={formData.inception_date}
                                        onChange={e => setFormData({ ...formData, inception_date: e.target.value })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Scheme Category</label>
                                    <select 
                                        className="form-input-elite"
                                        value={formData.scheme_category}
                                        onChange={e => setFormData({ ...formData, scheme_category: e.target.value })}
                                    >
                                        <option value="Equity Scheme">Equity Scheme</option>
                                        <option value="Debt Scheme">Debt Scheme</option>
                                        <option value="Hybrid Scheme">Hybrid Scheme</option>
                                        <option value="Solution Oriented">Solution Oriented</option>
                                        <option value="Other Scheme">Other Scheme</option>
                                    </select>
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block text-primary font-bold">Benchmark Index *</label>
                                    <select 
                                        className="form-input-elite highlight"
                                        value={formData.benchmark_index_code}
                                        onChange={e => setFormData({ ...formData, benchmark_index_code: e.target.value })}
                                    >
                                        <option value="">SELECT BENCHMARK...</option>
                                        {benchmarks.map(b => (
                                            <option key={b.benchmark_code} value={b.benchmark_code}>
                                                {b.benchmark_name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            <div className="flex gap-5 mt-5">
                                <button type="submit" className="btn-premium btn-premium-primary flex-1">
                                    {editingFund ? 'COMMIT UPDATES' : 'REGISTER ASSET'}
                                </button>
                                <button type="button" onClick={() => setIsFormOpen(false)} className="btn-premium btn-premium-outline">CANCEL</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {isDeleteModalOpen && (
                <div className="modal-overlay glass">
                    <div className="glass-panel p-32 max-w-md w-full mx-5 reveal active text-center">
                        <div className="delete-warning-icon mb-6">⚠️</div>
                        <h2 className="font-heading heading-md mb-4 uppercase tracking-widest text-error">Security Authorization</h2>
                        <p className="text-sm opacity-60 mb-10 leading-relaxed">
                            Are you certain you wish to permanently decommission asset <span className="text-white font-bold">{deletingCode}</span> from the Mutual Fund Vault? This action is irreversible.
                        </p>
                        <div className="flex gap-5">
                            <button onClick={confirmDelete} className="btn-premium btn-delete-final flex-1">CONFIRM DELETE</button>
                            <button onClick={() => setIsDeleteModalOpen(false)} className="btn-premium btn-premium-outline flex-1">CANCEL</button>
                        </div>
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
                                    <div className="card-identity-row flex justify-between items-start">
                                        <div className="rating-stars">★★★★★</div>
                                        <div className="flex gap-3">
                                            <button 
                                                onClick={() => openEdit(fund)} 
                                                className="btn-management-lux"
                                                title="Edit Protocol"
                                            >
                                                <IconPencil />
                                            </button>
                                            <button 
                                                onClick={() => handleDelete(fund.scheme_code)} 
                                                className="btn-management-lux delete"
                                                title="Decommission Asset"
                                            >
                                                <IconTrash />
                                            </button>
                                        </div>
                                    </div>

                                    <div className="fund-title-box mt-auto">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="font-heading">{fund.scheme_name}</h3>
                                            {!fund.benchmark_index_code && (
                                                <span className="badge-warning-lux">NO BENCHMARK</span>
                                            )}
                                        </div>
                                        <p className="text-xs uppercase tracking-widest text-muted">{fund.scheme_category} • {fund.plan_type}</p>
                                    </div>

                                    <div className="fund-metrics-row">
                                        <div className="metric-item items-end">
                                            <span className="m-label text-right">Latest NAV</span>
                                            <span className="m-value text-primary font-heading">₹{fund.metrics?.current_nav || '--'}</span>
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
                                        <th className="text-right">OPERATIONS</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {funds.map(fund => (
                                        <tr key={fund.scheme_code} className="hover:bg-white/5 transition-colors">
                                            <td className="font-heading text-sm font-semibold">
                                                <div className="flex flex-col">
                                                    <a href={`#mf-detail-${fund.scheme_code}`} className="text-white hover:text-primary transition-colors">{fund.scheme_name}</a>
                                                    {!fund.benchmark_index_code && (
                                                        <span className="text-[10px] text-error font-bold uppercase tracking-tight">Benchmark Unassigned</span>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="text-xs uppercase text-muted font-bold tracking-wider">{fund.scheme_category}</td>
                                            <td className="text-xs text-muted">{fund.amc_name}</td>
                                            <td className="text-md font-extrabold text-primary">₹{fund.metrics?.current_nav || '--'}</td>
                                            <td className="text-right">
                                                <div className="flex justify-end gap-3">
                                                    <button onClick={() => openEdit(fund)} className="btn-management-lux" title="Edit"><IconPencil /></button>
                                                    <button onClick={() => handleDelete(fund.scheme_code)} className="btn-management-lux delete" title="Delete"><IconTrash /></button>
                                                </div>
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
