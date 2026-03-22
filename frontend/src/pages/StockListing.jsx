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
        <div className="stock-listing container reveal active">
            <header className="listing-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Direct Equity Access</span>
                <h1 className="font-heading heading-xl">Global Markets</h1>

                <div className="flex justify-between items-center mb-10">
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
                        <input type="text" placeholder="IDENTIFY ASSET..." />
                    </div>
                </div>
            </header>

            <div className="glass-panel pro-table-container reveal active">
                <table className="pro-table">
                    <thead>
                        <tr>
                            <th>IDENTIFIER</th>
                            <th>MARKET PRICE</th>
                            <th>NET CHANGE</th>
                            <th>EXCHANGES</th>
                            <th className="text-right">OPERATIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredStocks.map(stock => (
                            <tr key={stock.symbol}>
                                <td>
                                    <div className="flex flex-col">
                                        <span className="font-heading font-bold">{stock.symbol}</span>
                                        <span className="text-xs text-muted">{stock.name}</span>
                                    </div>
                                </td>
                                <td className="font-heading font-extrabold text-md">₹{stock.price.toLocaleString()}</td>
                                <td className={`font-bold ${stock.change >= 0 ? 'text-primary' : 'text-error'}`}>
                                    {stock.change >= 0 ? '+' : ''}{stock.change}%
                                </td>
                                <td><span className="badge-lux">NSE / BSE</span></td>
                                <td className="text-right">
                                    <a href={`#stock-detail-${stock.symbol}`} className="btn-premium btn-premium-outline py-2 px-6">INSPECT →</a>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h3 className="section-heading-lux uppercase">Market Liquidity Index</h3>
                    <div className="h-px bg-white/10 flex-1 mx-10"></div>
                </div>
                <div className="grid grid-cols-4 gap-5">
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} className="glass-panel p-6 glow-card">
                            <span className="label-accent text-xs">MARKET HEALTH</span>
                            <div className="font-heading text-lg mt-2">OPTIMAL</div>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
};

export default StockListing;
