import React, { useState, useEffect } from 'react';
import fundService from '../api/services/fundService';
import './MFListing.css'; // Reusing base listing styles for consistency

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

    if (loading) return <div className="loading-container p-20">Scanning Global Indices...</div>;

    return (
        <div className="mf-listing reveal active">
            <header className="listing-header-lux">
                <h4 className="label-accent uppercase tracking-widest">Market Intelligence</h4>
                <h1 className="font-heading heading-xl">Global Indices</h1>
                <p className="text-secondary mt-2">Real-time performance benchmarks across equity and fixed-income sectors.</p>
            </header>

            {error && <div className="error-banner glass m-10 p-5 text-center">{error}</div>}

            <div className="fund-grid-lux section-spacer">
                {indices.length > 0 ? (
                    indices.map(idx => (
                        <div key={idx.benchmark_code} className="fund-card-lux shadow-card hover-glow">
                            <div className="fund-top">
                                <div className="rating-lux">BENCHMARK</div>
                                <h3 className="font-heading">{idx.benchmark_name}</h3>
                                <p className="category-lux text-muted uppercase tracking-widest">
                                    {idx.asset_class || 'Equity'} • {idx.ticker}
                                </p>
                            </div>

                            <div className="fund-metrics-lux">
                                <div className="metric">
                                    <span className="label">TICKER CODE</span>
                                    <span className="value">{idx.ticker}</span>
                                </div>
                                <div className="metric">
                                    <span className="label">LATEST VALUE</span>
                                    <span className="value">--</span>
                                </div>
                            </div>

                            <div className="fund-actions-lux">
                                <span className="link-primary text-xs uppercase tracking-widest">LIVE TRACKING ACTIVE</span>
                                <button className="btn-secondary-lux-sm">DETAILS</button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="empty-state p-20 text-center glass w-full">
                        <p className="text-secondary">No indices detected in current scope.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default IndicesListing;
