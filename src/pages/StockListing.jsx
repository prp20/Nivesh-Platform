import React, { useState } from 'react';
import './StockListing.css';

const StockListing = () => {
    const [filter, setFilter] = useState('All');

    const stocks = [
        { symbol: 'RELIANCE', name: 'Reliance Industries', price: 2845.50, change: +1.42, marketCap: 'Large', sector: 'Energy' },
        { symbol: 'TCS', name: 'Tata Consultancy Services', price: 3912.00, change: +0.85, marketCap: 'Large', sector: 'IT' },
        { symbol: 'HDFCBANK', name: 'HDFC Bank', price: 1420.00, change: -0.12, marketCap: 'Large', sector: 'Banking' },
        { symbol: 'INFY', name: 'Infosys', price: 1640.25, change: +2.11, marketCap: 'Large', sector: 'IT' },
        { symbol: 'ICICIBANK', name: 'ICICI Bank', price: 1085.60, change: -0.45, marketCap: 'Large', sector: 'Banking' },
    ];

    const filteredStocks = filter === 'All' ? stocks : stocks.filter(s => s.sector === filter);

    return (
        <div className="stock-listing reveal active">
            <header className="listing-header-lux">
                <h4 className="label-accent uppercase tracking-widest">Equities</h4>
                <h1 className="font-heading heading-xl">Global Markets</h1>

                <div className="filters-row-lux">
                    <div className="filter-chips-lux">
                        {['All', 'IT', 'Banking', 'Energy', 'Telecom'].map(f => (
                            <button
                                key={f}
                                className={`chip-lux ${filter === f ? 'active' : ''}`}
                                onClick={() => setFilter(f)}
                            >
                                {f.toUpperCase()}
                            </button>
                        ))}
                    </div>
                    <div className="search-lux">
                        <input type="text" placeholder="SEARCH ASSETS" />
                    </div>
                </div>
            </header>

            <div className="listing-grid-lux">
                <div className="table-container-lux shadow-card">
                    <table className="table-lux">
                        <thead>
                            <tr>
                                <th>ASSET</th>
                                <th>MARKET PRICE</th>
                                <th>NET CHANGE</th>
                                <th>EXCHANGES</th>
                                <th>ACTIONS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredStocks.map(stock => (
                                <tr key={stock.symbol}>
                                    <td>
                                        <div className="asset-info">
                                            <span className="symbol font-heading">{stock.symbol}</span>
                                            <span className="name text-muted">{stock.name}</span>
                                        </div>
                                    </td>
                                    <td className="font-heading">₹{stock.price.toLocaleString()}</td>
                                    <td className={stock.change >= 0 ? 'positive' : 'negative'}>
                                        {stock.change >= 0 ? '+' : ''}{stock.change}%
                                    </td>
                                    <td><span className="badge-lux">NSE / BSE</span></td>
                                    <td>
                                        <a href={`#stock-detail-${stock.symbol}`} className="link-primary text-xs uppercase tracking-widest">Inspect →</a>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default StockListing;
