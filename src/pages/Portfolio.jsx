import React, { useState } from 'react';
import './Portfolio.css';

const Portfolio = () => {
    const [activeTab, setActiveTab] = useState('stocks');

    const stockHoldings = [
        { name: 'Reliance Industries', symbol: 'RELIANCE', qty: 10, avgPrice: 2400.00, ltp: 2845.50, pl: 18.5 },
        { name: 'Tata Consultancy Services', symbol: 'TCS', qty: 5, avgPrice: 3500.00, ltp: 3912.00, pl: 11.8 },
        { name: 'HDFC Bank', symbol: 'HDFCBANK', qty: 20, avgPrice: 1450.00, ltp: 1420.00, pl: -2.1 },
    ];

    return (
        <div className="portfolio reveal active">
            <header className="portfolio-header-lux">
                <h4 className="label-accent uppercase tracking-widest">Aggregate Wealth</h4>
                <h1 className="font-heading heading-xl">My Portfolio</h1>

                <div className="overall-stats-lux section-spacer-sm">
                    <div className="stat-lux">
                        <span className="label-lux">Invested Value</span>
                        <span className="value-lux">₹1,85,000.00</span>
                    </div>
                    <div className="stat-lux highlight">
                        <span className="label-lux">Current Portfolio</span>
                        <span className="value-lux">₹2,12,450.50</span>
                    </div>
                    <div className="stat-lux">
                        <span className="label-lux">Unrealized P&L</span>
                        <span className="value-lux positive">+₹27,450.50 (14.84%)</span>
                    </div>
                </div>
            </header>

            <div className="portfolio-tabs-lux">
                <button
                    className={`tab-btn-lux ${activeTab === 'stocks' ? 'active' : ''}`}
                    onClick={() => setActiveTab('stocks')}
                >
                    EQUITIES
                </button>
                <button
                    className={`tab-btn-lux ${activeTab === 'mf' ? 'active' : ''}`}
                    onClick={() => setActiveTab('mf')}
                >
                    MUTUAL FUNDS
                </button>
            </div>

            <div className="table-container-lux shadow-card">
                <table className="table-lux">
                    <thead>
                        <tr>
                            <th>ASSET CLASS</th>
                            <th>QUANTITY</th>
                            <th>AVG. PURCHASE</th>
                            <th>MARKET PRICE</th>
                            <th>RETURNS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {activeTab === 'stocks' ? (
                            stockHoldings.map(stock => (
                                <tr key={stock.symbol}>
                                    <td>
                                        <div className="asset-info">
                                            <span className="symbol font-heading">{stock.symbol}</span>
                                            <span className="name text-muted">{stock.name}</span>
                                        </div>
                                    </td>
                                    <td>{stock.qty}</td>
                                    <td>₹{stock.avgPrice.toLocaleString()}</td>
                                    <td>₹{stock.ltp.toLocaleString()}</td>
                                    <td className={stock.pl >= 0 ? 'positive' : 'negative'}>
                                        {stock.pl >= 0 ? '+' : ''}{stock.pl}%
                                    </td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="5" className="empty-state">No holdings available in this segment.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <section className="section-spacer">
                <h3 className="section-heading-lux uppercase letter-spacing-lg">Strategic Allocation</h3>
                <div className="allocation-grid-lux">
                    <div className="allocation-visual shadow-card">
                        <div className="donut-lux">
                            <div className="center-lux">65% Equity</div>
                        </div>
                        <div className="legend-lux">
                            <div className="legend-item"><span className="dot primary"></span> Equities (65%)</div>
                            <div className="legend-item"><span className="dot secondary"></span> Funds (35%)</div>
                        </div>
                    </div>
                    <div className="allocation-insight shadow-card">
                        <h4 className="label-accent uppercase">Advisor Insight</h4>
                        <p className="text-secondary">Your portfolio is currently overweight in Energy and Technology sectors. Consider defensive rotation into FMCG or Debt instruments for balanced volatility.</p>
                    </div>
                </div>
            </section>
        </div>
    );
};

export default Portfolio;
