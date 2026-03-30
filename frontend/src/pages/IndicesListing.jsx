import React, { useState, useEffect, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { fetchIndices, setCurrentPage, setPageSize, setSearchQuery } from '../store/slices/indicesSlice';
import fundService from '../api/services/fundService';
import './MFListing.css'; // Utilizing primary design system

// SVG Icons (mirrored from MFListing for 100% parity)
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

const IndicesListing = () => {
    // UI State (component-local only)
    const [viewMode, setViewMode] = useState('grid');
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [deletingCode, setDeletingCode] = useState(null);
    const [editingIndex, setEditingIndex] = useState(null);
    const [formData, setFormData] = useState({
        benchmark_code: '', benchmark_name: '', ticker: '',
        benchmark_type: 'Equity', asset_class: 'Equity', is_active: true
    });

    // Redux — indices data & pagination
    const dispatch = useDispatch();
    const { items: indices, total, loading, error, currentPage, pageSize, searchQuery } = useSelector(state => state.indices);

    const loadIndices = useCallback(() => {
        const skip = (currentPage - 1) * pageSize;
        dispatch(fetchIndices({ skip, limit: pageSize, search: searchQuery }));
    }, [currentPage, pageSize, searchQuery, dispatch]);

    useEffect(() => {
        loadIndices();
    }, [loadIndices]);

    const handleSearchChange = (e) => {
        dispatch(setSearchQuery(e.target.value));
    };

    const handlePageSizeChange = (e) => {
        dispatch(setPageSize(parseInt(e.target.value)));
    };

    const handleDelete = (code) => {
        setDeletingCode(code);
        setIsDeleteModalOpen(true);
    };

    const confirmDelete = async () => {
        if (!deletingCode) return;
        try {
            await fundService.deleteBenchmark(deletingCode);
            setIsDeleteModalOpen(false);
            setDeletingCode(null);
            loadIndices();
        } catch (err) {
            alert("Protocol breach detected. Delete operation aborted.");
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        try {
            if (editingIndex) {
                await fundService.updateBenchmark(editingIndex.benchmark_code, formData);
            } else {
                await fundService.createBenchmark(formData);
            }
            setIsFormOpen(false);
            setEditingIndex(null);
            loadIndices();
        } catch (err) {
            alert("Ledger update failed. Check constraints.");
        }
    };

    const openEdit = (idx) => {
        setEditingIndex(idx);
        setFormData({ ...idx });
        setIsFormOpen(true);
    };

    const openAdd = () => {
        setEditingIndex(null);
        setFormData({
            benchmark_code: '', benchmark_name: '', ticker: '',
            benchmark_type: 'Equity', asset_class: 'Equity', is_active: true
        });
        setIsFormOpen(true);
    };

    const totalPages = Math.ceil(total / pageSize);

    if (loading && indices.length === 0) return <div className="loading-container p-20 text-center uppercase tracking-widest font-heading">Scanning Market Intelligence...</div>;

    return (
        <div className="mf-listing container reveal active">
            <header className="listing-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Market Intelligence Layer</span>
                <h1 className="font-heading heading-xl">Market Indices</h1>

                <div className="glass-panel p-6 flex justify-between items-center mb-10 control-bar-elite">
                    <button onClick={openAdd} className="btn-premium btn-premium-primary py-2 px-6 text-xs whitespace-nowrap">
                        + Register Index
                    </button>

                    <div className="filter-chips-lux flex gap-4">
                        {/* Placeholder chips for future filtering by asset class if needed */}
                        <button className="chip-lux active">ALL INDICES</button>
                    </div>

                    <form onSubmit={(e) => e.preventDefault()} className="search-box-lux">
                        <input
                            type="text"
                            placeholder="SEARCH BY NAME OR CODE..."
                            value={searchQuery}
                            onChange={handleSearchChange}
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
                        <h2 className="font-heading heading-md mb-10 uppercase tracking-widest text-primary">Index Configuration</h2>
                        <form onSubmit={handleSave} className="flex flex-col gap-8">
                            <div className="grid grid-cols-2 gap-6">
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Index Code</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="UNIQUE IDENTIFIER"
                                        value={formData.benchmark_code}
                                        disabled={!!editingIndex}
                                        onChange={e => setFormData({ ...formData, benchmark_code: e.target.value.toUpperCase() })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Ticker Symbol</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="E.G. ^NSEI"
                                        value={formData.ticker}
                                        onChange={e => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Formal Name</label>
                                    <input
                                        className="form-input-elite"
                                        placeholder="FULL INDEX NAME"
                                        value={formData.benchmark_name}
                                        onChange={e => setFormData({ ...formData, benchmark_name: e.target.value })}
                                    />
                                </div>
                                <div className="input-group-lux">
                                    <label className="text-xs uppercase tracking-widest opacity-40 mb-2 block">Index Type</label>
                                    <select 
                                        className="form-input-elite"
                                        value={formData.benchmark_type}
                                        onChange={e => setFormData({ ...formData, benchmark_type: e.target.value })}
                                    >
                                        <option value="Equity">Equity Index</option>
                                        <option value="Debt">Debt Index</option>
                                        <option value="Hybrid">Hybrid Index</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex items-center gap-3 py-4 border-y border-white/5">
                                <input 
                                    type="checkbox" checked={formData.is_active}
                                    onChange={e => setFormData({...formData, is_active: e.target.checked})}
                                    style={{ width: '20px', height: '20px', cursor: 'pointer' }}
                                />
                                <span className="text-xs uppercase tracking-widest opacity-60">ACTIVE MONITORING ENABLED</span>
                            </div>
                            <div className="flex gap-5 mt-5">
                                <button type="submit" className="btn-premium btn-premium-primary flex-1">
                                    {editingIndex ? 'COMMIT UPDATES' : 'REGISTER INDEX'}
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
                            Are you certain you wish to purge index <span className="text-white font-bold">{deletingCode}</span> from the core ledger? Metadata loss is permanent.
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
                <div className="loading-container p-20 text-center font-heading uppercase opacity-50">Decoding Feeds...</div>
            ) : (
                <>
                    {viewMode === 'grid' ? (
                        <div className="fund-grid-lux reveal active">
                            {indices.map(idx => (
                                <div key={idx.benchmark_code} className="glass-panel glow-card fund-card-lux-elite">
                                    <div className="card-identity-row flex justify-between items-start">
                                        <div className="logo-circle">{idx.benchmark_name[0]}</div>
                                        <div className="flex gap-3">
                                            <button 
                                                onClick={() => openEdit(idx)} 
                                                className="btn-management-lux"
                                                title="Edit Protocol"
                                            >
                                                <IconPencil />
                                            </button>
                                            <button 
                                                onClick={() => handleDelete(idx.benchmark_code)} 
                                                className="btn-management-lux delete"
                                                title="Delete Index"
                                            >
                                                <IconTrash />
                                            </button>
                                        </div>
                                    </div>

                                    <div className="fund-title-box mt-auto">
                                        <h3 className="font-heading">{idx.benchmark_name}</h3>
                                        <p className="text-xs uppercase tracking-widest text-muted">
                                            {idx.asset_class} • {idx.benchmark_type} Index
                                        </p>
                                    </div>

                                    <div className="fund-metrics-row">
                                        <div className="metric-item">
                                            <span className="m-label">ROLLING 3Y</span>
                                            <span className={`m-value font-heading ${idx.metrics?.rolling_return_3year >= 0 ? 'text-success' : 'text-error'}`}>
                                                {idx.metrics?.rolling_return_3year != null ? `${(idx.metrics.rolling_return_3year * 100).toFixed(2)}%` : '--'}
                                            </span>
                                        </div>
                                        <div className="metric-item">
                                            <span className="m-label">RISK (STD)</span>
                                            <span className="m-value font-heading text-white">
                                                {idx.metrics?.standard_deviation != null ? `${(idx.metrics.standard_deviation * 100).toFixed(2)}%` : '--'}
                                            </span>
                                        </div>
                                        <div className="metric-item items-end">
                                            <span className="m-label text-right">TICKER</span>
                                            <span className="m-value text-primary font-heading">{idx.ticker}</span>
                                        </div>
                                    </div>

                                    <div className="card-action-row mt-5">
                                        <a href={`#index-detail-${idx.benchmark_code}`} className="btn-premium btn-premium-outline">DETAILS</a>
                                        <div className={idx.is_active ? "text-success text-[10px] font-bold uppercase tracking-widest flex items-center gap-2" : "text-error text-[10px] font-bold uppercase tracking-widest flex items-center gap-2"}>
                                            <span className={`w-2 h-2 rounded-full ${idx.is_active ? 'bg-success' : 'bg-error'} animate-pulse`}></span>
                                            {idx.is_active ? 'ACTIVE' : 'INACTIVE'}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="glass-panel pro-table-container reveal active">
                            <table className="pro-table">
                                <thead>
                                    <tr>
                                        <th>INDEX IDENTITY</th>
                                        <th>TICKER / TYPE</th>
                                        <th>3Y CAGR</th>
                                        <th>RISK (STD)</th>
                                        <th>STATUS</th>
                                        <th className="text-right">OPERATIONS</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {indices.map(idx => (
                                        <tr key={idx.benchmark_code} className="hover:bg-white/5 transition-colors cursor-pointer group"
                                            onClick={(e) => {
                                                if (e.target.closest('button')) return;
                                                window.location.hash = `#index-detail-${idx.benchmark_code}`;
                                            }}>
                                            <td className="font-heading text-sm font-semibold">
                                                <div className="flex flex-col">
                                                    <span className="text-white group-hover:text-primary transition-colors">{idx.benchmark_name}</span>
                                                    <span className="text-[10px] opacity-40 uppercase tracking-widest">{idx.benchmark_code}</span>
                                                </div>
                                            </td>
                                            <td>
                                                <div className="flex flex-col">
                                                    <span className="text-xs uppercase text-muted font-bold tracking-wider">{idx.ticker}</span>
                                                    <span className="text-[10px] text-muted font-bold tracking-widest uppercase">{idx.benchmark_type}</span>
                                                </div>
                                            </td>
                                            <td className={`text-xs font-bold ${idx.metrics?.rolling_return_3year >= 0 ? 'text-success' : 'text-error'}`}>
                                                {idx.metrics?.rolling_return_3year != null ? `${(idx.metrics.rolling_return_3year * 100).toFixed(2)}%` : '--'}
                                            </td>
                                            <td className="text-xs font-bold text-white">
                                                {idx.metrics?.standard_deviation != null ? `${(idx.metrics.standard_deviation * 100).toFixed(2)}%` : '--'}
                                            </td>
                                            <td>
                                                <span className={idx.is_active ? "text-success text-[10px] font-bold uppercase tracking-widest" : "text-error text-[10px] font-bold uppercase tracking-widest"}>
                                                    {idx.is_active ? 'ACTIVE' : 'INACTIVE'}
                                                </span>
                                            </td>
                                            <td className="text-right">
                                                <div className="flex justify-end gap-3" onClick={e => e.stopPropagation()}>
                                                    <button onClick={() => openEdit(idx)} className="btn-management-lux" title="Edit"><IconPencil /></button>
                                                    <button onClick={() => handleDelete(idx.benchmark_code)} className="btn-management-lux delete" title="Delete"><IconTrash /></button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {total > 0 && (
                        <div className="pagination-elite reveal active">
                            <div className="flex gap-4 items-center">
                                <span className="page-info">SHOW</span>
                                <select value={pageSize} onChange={handlePageSizeChange} className="chip-lux text-xs" style={{ background: 'transparent', padding: '0.2rem 0.5rem' }}>
                                    {[10, 20, 50].map(sz => (
                                        <option key={sz} value={sz} style={{ color: 'black' }}>{sz}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex gap-8 items-center">
                                <button
                                    disabled={currentPage === 1}
                                    onClick={() => dispatch(setCurrentPage(currentPage - 1))}
                                    className="bck-btn btn-premium btn-premium-outline"
                                >← BACK</button>
                                <span className="page-info">
                                    {currentPage} / {totalPages}
                                </span>
                                <button
                                    disabled={currentPage === totalPages}
                                    onClick={() => dispatch(setCurrentPage(currentPage + 1))}
                                    className="fwd-btn btn-premium btn-premium-outline"
                                >NEXT →</button>
                            </div>

                            <div className="page-info opacity-30">
                                {total} TOTAL RECORDS
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default IndicesListing;
