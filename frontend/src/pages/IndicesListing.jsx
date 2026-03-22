import React, { useState, useEffect } from 'react';
import fundService from '../api/services/fundService';
import './MFListing.css';

const IndicesListing = () => {
    const [indices, setIndices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchIndices = async () => {
            try {
                const data = await fundService.getBenchmarks(0, 20);
                setIndices(data);
                setLoading(false);
            } catch (err) {
                console.error("Failed to fetch indices", err);
                setError("Market monitoring feeds currently unavailable.");
                setLoading(false);
            }
        };
        fetchIndices();
    }, []);

    if (loading) return <div className="loading-container p-20 text-center font-heading uppercase tracking-widest opacity-50">Scanning Global Indices...</div>;

    return (
        <div className="mf-listing container reveal active">
            <header className="listing-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Market Intelligence Layer</span>
                <h1 className="font-heading heading-xl">Global Indices</h1>
                <p className="text-secondary mt-5 max-w-lg">
                    Real-time performance benchmarks across equity and fixed-income sectors, synchronized with international exchanges.
                </p>
            </header>

            {error && <div className="glass-panel p-5 text-center text-error border-error/30 mb-10">{error}</div>}

            <div className="fund-grid-lux reveal active">
                {indices.length > 0 ? (
                    indices.map(idx => (
                        <div key={idx.benchmark_code} className="glass-panel glow-card fund-card-lux-elite">
                            <div className="card-identity-row">
                                <div className="logo-circle">{idx.benchmark_name[0]}</div>
                                <div className="rating-stars uppercase tracking-tighter opacity-50">BENCHMARK</div>
                            </div>
                            
                            <div className="fund-title-box mt-auto">
                                <h3 className="font-heading">{idx.benchmark_name}</h3>
                                <p className="text-xs uppercase tracking-widest text-muted">
                                    {idx.asset_class || 'Equity'} • {idx.ticker}
                                </p>
                            </div>

                            <div className="fund-metrics-row">
                                <div className="metric-item">
                                    <span className="m-label">Ticker Code</span>
                                    <span className="m-value">{idx.ticker}</span>
                                </div>
                                <div className="metric-item items-end">
                                    <span className="m-label text-right">Latest Delta</span>
                                    <span className="m-value text-primary">--</span>
                                </div>
                            </div>

                            <div className="flex justify-between items-center mt-5">
                                <span className="text-primary text-xs font-bold uppercase tracking-widest">Live Monitoring Active</span>
                                <button className="btn-premium btn-premium-outline py-2 px-6">DETAILS</button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="glass-panel p-20 text-center w-full opacity-30 font-heading uppercase">
                        No indices detected in current scope.
                    </div>
                )}
            </div>
        </div>
    );
};

export default IndicesListing;
