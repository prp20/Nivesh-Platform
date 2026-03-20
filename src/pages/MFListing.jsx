import React, { useState } from 'react';
import './MFListing.css';

const MFListing = () => {
    const [filter, setFilter] = useState('All');

    const funds = [
        { name: 'Quant Small Cap Fund', category: 'Equity', returns: 32.4, risk: 'Very High', rating: 5, nav: 245.10 },
        { name: 'Parag Parikh Flexi Cap Fund', category: 'Equity', returns: 24.5, risk: 'High', rating: 5, nav: 72.80 },
        { name: 'ICICI Prudential Bluechip Fund', category: 'Equity', returns: 18.2, risk: 'Moderate', rating: 4, nav: 112.50 },
    ];

    const filteredFunds = filter === 'All' ? funds : funds.filter(f => f.category === filter);

    return (
        <div className="mf-listing reveal active">
            <header className="listing-header-lux">
                <h4 className="label-accent uppercase tracking-widest">Asset Management</h4>
                <h1 className="font-heading heading-xl">Mutual Funds</h1>

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

            <div className="fund-grid-lux section-spacer">
                {filteredFunds.map(fund => (
                    <div key={fund.name} className="fund-card-lux shadow-card">
                        <div className="fund-top">
                            <div className="rating-lux">{'★'.repeat(fund.rating)}{'☆'.repeat(5 - fund.rating)}</div>
                            <h3 className="font-heading">{fund.name}</h3>
                            <p className="category-lux text-muted uppercase tracking-widest">{fund.category} • {fund.risk} RISK</p>
                        </div>

                        <div className="fund-metrics-lux">
                            <div className="metric">
                                <span className="label">ANNUALIZED RETURNS</span>
                                <span className="value positive">+{fund.returns}%</span>
                            </div>
                            <div className="metric">
                                <span className="label">LATEST NAV</span>
                                <span className="value">₹{fund.nav}</span>
                            </div>
                        </div>

                        <div className="fund-actions-lux">
                            <a href={`#mf-detail-${fund.name.replace(/\s+/g, '-')}`} className="link-primary text-xs uppercase tracking-widest">FUND SPECS →</a>
                            <button className="btn-primary-lux-sm uppercase tracking-widest">ALLOCATE</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default MFListing;
