import React, { useState } from 'react';
import './Portfolio.css';

const Portfolio = () => {
    const [activeTab, setActiveTab] = useState('stocks');

    return (
        <div className="portfolio container reveal active">
            <header className="portfolio-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Tactical Allocation Hub</span>
                <h1 className="font-heading heading-xl">Master Portfolio</h1>

                <div className="overall-stats-lux">
                    <div className="glass-panel stat-lux glow-card">
                        <span className="label-lux">Net Asset Value</span>
                        <span className="value-lux text-muted">-- Pending Integration --</span>
                    </div>
                    <div className="glass-panel stat-lux glow-card highlight">
                        <span className="label-lux">Mark-to-Market</span>
                        <span className="value-lux text-muted">-- Pending Integration --</span>
                    </div>
                    <div className="glass-panel stat-lux glow-card">
                        <span className="label-lux">Unrealized Performance</span>
                        <span className="value-lux text-muted">-- Pending Integration --</span>
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
                        <tr>
                            <td colSpan="5" className="p-12 text-center">
                                <div className="flex flex-col items-center gap-4 opacity-40">
                                    <span className="text-3xl">{activeTab === 'stocks' ? '📈' : '💰'}</span>
                                    <p className="font-heading uppercase tracking-widest text-sm">
                                        {activeTab === 'stocks' ? 'Direct Equity Holdings' : 'Managed Fund Holdings'} — Coming Soon
                                    </p>
                                    <p className="text-xs text-muted max-w-sm text-center">
                                        Portfolio tracking will be available once the holdings backend API is integrated.
                                    </p>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h3 className="section-heading-lux uppercase">Intelligence & Insights</h3>
                    <div className="h-px bg-white/10 flex-1 mx-10"></div>
                </div>
                
                <div className="glass-panel p-10 glow-card flex flex-col items-center justify-center text-center" style={{ minHeight: '180px' }}>
                    <span className="text-3xl mb-4 opacity-30">🏗️</span>
                    <h4 className="font-heading text-sm uppercase tracking-widest opacity-40">Portfolio Analytics — Coming Soon</h4>
                    <p className="text-xs text-muted opacity-40 mt-2 max-w-sm">
                        Allocation charts, sector exposure analysis, and AI-powered rebalancing suggestions will be available in the next release.
                    </p>
                </div>
            </section>
        </div>
    );
};

export default Portfolio;
