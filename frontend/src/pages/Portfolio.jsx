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
        <div className="portfolio container reveal active">
            <header className="portfolio-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Tactical Allocation Hub</span>
                <h1 className="font-heading heading-xl">Master Portfolio</h1>

                <div className="overall-stats-lux">
                    <div className="glass-panel stat-lux glow-card">
                        <span className="label-lux">Net Asset Value</span>
                        <span className="value-lux">₹1,85,000.00</span>
                    </div>
                    <div className="glass-panel stat-lux glow-card highlight">
                        <span className="label-lux">Mark-to-Market</span>
                        <span className="value-lux text-primary">₹2,12,450.50</span>
                    </div>
                    <div className="glass-panel stat-lux glow-card">
                        <span className="label-lux">Unrealized Performance</span>
                        <span className="value-lux positive">+14.84%</span>
                    </div>
                </div>
            </header>

            <div className="portfolio-tabs-lux">
                {['stocks', 'mf'].map(t => (
                    <button
                        key={t}
                        className={`tab-btn-lux ${activeTab === t ? 'active' : ''}`}
                        onClick={() => setActiveTab(t)}
                    >
                        {t === 'stocks' ? 'DIRECT EQUITIES' : 'MANAGED FUNDS'}
                    </button>
                ))}
            </div>

            <div className="glass-panel pro-table-container reveal active">
                <table className="pro-table">
                    <thead>
                        <tr>
                            <th>IDENTIFIER</th>
                            <th>VOLUME</th>
                            <th>COST BASIS</th>
                            <th>MARKET CAP</th>
                            <th className="text-right">RETENTION P&L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {activeTab === 'stocks' ? (
                            stockHoldings.map(stock => (
                                <tr key={stock.symbol}>
                                    <td>
                                        <div className="flex flex-col">
                                            <span className="font-heading font-bold">{stock.symbol}</span>
                                            <span className="text-xs text-muted">{stock.name}</span>
                                        </div>
                                    </td>
                                    <td className="font-mono text-sm">{stock.qty} UN</td>
                                    <td className="font-mono text-sm">₹{stock.avgPrice.toLocaleString()}</td>
                                    <td className="font-mono text-sm font-bold">₹{stock.ltp.toLocaleString()}</td>
                                    <td className={`text-right font-bold ${stock.pl >= 0 ? 'text-primary' : 'text-error'}`}>
                                        {stock.pl >= 0 ? '+' : ''}{stock.pl}%
                                    </td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="5" className="empty-state p-10 text-center opacity-30 font-heading">SECTOR EXPOSURE VACANT</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h3 className="section-heading-lux uppercase">Intelligence & Insights</h3>
                    <div className="h-px bg-white/10 flex-1 mx-10"></div>
                </div>
                
                <div className="allocation-grid-lux">
                    <div className="glass-panel allocation-visual glow-card flex flex-col items-center">
                        <div className="donut-lux">
                            <div className="center-lux text-xs text-center">65%<br/>EQUITY</div>
                        </div>
                        <div className="legend-lux w-full">
                            <div className="legend-item"><span className="dot primary"></span> Strategic Equities (65%)</div>
                            <div className="legend-item"><span className="dot secondary"></span> Diversified Funds (35%)</div>
                        </div>
                    </div>
                    <div className="glass-panel allocation-insight glow-card">
                        <span className="label-accent uppercase tracking-widest text-xs">Capital Advisor AI</span>
                        <h4 className="font-heading text-lg mt-4 mb-4">Strategic Sector Imbalance Detected</h4>
                        <p className="text-secondary text-sm leading-relaxed">
                            System analysis indicates a heavy concentration in Energy and Technology sectors. 
                            Recommendation: Execute defensive rotation into healthcare or debt instruments 
                            to mitigate systemic volatility in the upcoming fiscal quarter.
                        </p>
                    </div>
                </div>
            </section>
        </div>
    );
};

export default Portfolio;
