import React, { useState, useEffect } from 'react';
import fundService from '../api/services/fundService';
import './MFListing.css';

const MFListing = () => {
    const [filter, setFilter] = useState('All');
    const [funds, setFunds] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingFund, setEditingFund] = useState(null);
    const [formData, setFormData] = useState({
        scheme_code: '', scheme_name: '', amc_name: '',
        scheme_category: 'Equity Scheme', plan_type: 'Direct'
    });

    const fetchFunds = async () => {
        setLoading(true);
        try {
            const data = await fundService.getFunds(0, 100);
            setFunds(data);
            setLoading(false);
        } catch (err) {
            console.error("Failed to fetch funds", err);
            setError("Could not load funds. Please try syncing from Dashboard.");
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFunds();
    }, []);

    const handleDelete = async (code) => {
        if (window.confirm(`Are you sure you want to remove fund ${code}?`)) {
            try {
                await fundService.deleteFund(code);
                fetchFunds();
            } catch (err) {
                alert("Failed to delete fund.");
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
            alert("Error saving fund information.");
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
            scheme_category: 'Equity Scheme', plan_type: 'Direct'
        });
        setIsFormOpen(true);
    };

    const filteredFunds = filter === 'All'
        ? funds
        : funds.filter(f => f.scheme_category?.includes(filter));

    if (loading) return <div className="loading-container p-20">Monitoring Markets...</div>;

    return (
        <div className="mf-listing reveal active">
            <header className="listing-header-lux">
                <div className="flex justify-between items-end">
                    <div>
                        <h4 className="label-accent uppercase tracking-widest">Asset Management</h4>
                        <h1 className="font-heading heading-xl">Mutual Funds</h1>
                    </div>
                    <button onClick={openAdd} className="btn-secondary-lux-sm mb-5">
                        + REGISTER NEW ASSET
                    </button>
                </div>

                <div className="filters-row-lux">
                    <div className="filter-chips-lux">
                        {['All', 'Equity', 'Debt', 'Hybrid'].map(f => (
                            <button
                                key={f}
                                className={`chip-lux ${filter === f ? 'active' : ''}`}
                                onClick={() => setFilter(f)}
                            >
                                {f.toUpperCase()}
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {isFormOpen && (
                <div className="modal-overlay glass">
                    <div className="modal-content shadow-card p-10 bg-dark">
                        <h2 className="font-heading heading-md mb-5">{editingFund ? 'Edit Asset' : 'Register New Asset'}</h2>
                        <form onSubmit={handleSave} className="crud-form">
                            <input
                                placeholder="Scheme Code (e.g. 120592)"
                                value={formData.scheme_code}
                                disabled={!!editingFund}
                                onChange={e => setFormData({ ...formData, scheme_code: e.target.value })}
                                required
                            />
                            <input
                                placeholder="Scheme Name"
                                value={formData.scheme_name}
                                onChange={e => setFormData({ ...formData, scheme_name: e.target.value })}
                                required
                            />
                            <input
                                placeholder="AMC Name"
                                value={formData.amc_name}
                                onChange={e => setFormData({ ...formData, amc_name: e.target.value })}
                                required
                            />
                            <div className="flex gap-10 mt-5">
                                <button type="submit" className="btn-primary-lux flex-1">SAVE ASSET</button>
                                <button type="button" onClick={() => setIsFormOpen(false)} className="btn-secondary-lux">CANCEL</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {error && <div className="error-banner glass m-10 p-5 text-center">{error}</div>}

            <div className="fund-grid-lux section-spacer">
                {filteredFunds.length > 0 ? (
                    filteredFunds.map(fund => (
                        <div key={fund.scheme_code} className="fund-card-lux shadow-card hover-glow">
                            <div className="fund-top">
                                <div className="flex justify-between items-start">
                                    <div className="rating-lux">★★★★★</div>
                                    <div className="crud-actions-small">
                                        <button onClick={() => openEdit(fund)} title="Edit">✎</button>
                                        <button onClick={() => handleDelete(fund.scheme_code)} title="Delete">✖</button>
                                    </div>
                                </div>
                                <h3 className="font-heading">{fund.scheme_name}</h3>
                                <p className="category-lux text-muted uppercase tracking-widest">
                                    {fund.scheme_category} • {fund.plan_type}
                                </p>
                            </div>

                            <div className="fund-metrics-lux">
                                <div className="metric">
                                    <span className="label">SCHEME CODE</span>
                                    <span className="value">{fund.scheme_code}</span>
                                </div>
                                <div className="metric">
                                    <span className="label">LATEST NAV</span>
                                    <span className="value">₹--</span>
                                </div>
                            </div>

                            <div className="fund-actions-lux">
                                <a href={`#mf-detail-${fund.scheme_code}`} className="link-primary text-xs uppercase tracking-widest">ANALYSIS →</a>
                                <button className="btn-primary-lux-sm uppercase tracking-widest">ALLOCATE</button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="empty-state p-20 text-center glass w-full">
                        <p className="text-secondary">No funds detected in the vault.</p>
                        <button
                            onClick={() => window.location.hash = '#dashboard'}
                            className="btn-primary-lux-sm m-5"
                        >
                            SYNC DATA FROM DASHBOARD
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MFListing;
