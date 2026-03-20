import React from 'react';
import './Dashboard.css';

const Dashboard = () => {
    return (
        <div className="dashboard reveal active">
            <header className="dashboard-header-lux">
                <h4 className="label-accent uppercase tracking-widest">Global Portfolio</h4>
                <h1 className="font-heading heading-xl">Performance Overview</h1>
                <p className="text-secondary max-w-lg">Monitoring international markets and your diversified assets across equity and debt instruments.</p>
            </header>

            <div className="stats-grid-lux">
                <div className="summary-card-lux main-card">
                    <div className="card-top">
                        <span className="label-accent uppercase">Total Net Worth</span>
                        <div className="value font-heading">₹2,12,450.50</div>
                    </div>
                    <div className="card-bottom">
                        <div className="trend-positive">
                            <span className="icon">↑</span>
                            <span>1.02%</span>
                            <span className="text-muted">(Last 24h)</span>
                        </div>
                    </div>
                </div>

                <div className="indices-stack">
                    <div className="index-row-lux">
                        <span className="index-name">NIFTY 50</span>
                        <span className="index-val">22,056.40 <span className="positive">+0.45%</span></span>
                    </div>
                    <div className="index-row-lux">
                        <span className="index-name">SENSEX</span>
                        <span className="index-val">72,641.19 <span className="negative">-0.12%</span></span>
                    </div>
                </div>
            </div>

            <section className="section-spacer">
                <h2 className="section-heading-lux uppercase letter-spacing-lg">Our Ventures</h2>
                <div className="venture-grid">
                    <a href="#stocks" className="venture-card shadow-card">
                        <div className="venture-icon">📈</div>
                        <h3>Equities</h3>
                        <p>Direct stock investments across blue-chip and small-cap segments.</p>
                    </a>
                    <a href="#mf" className="venture-card shadow-card">
                        <div className="venture-icon">💰</div>
                        <h3>Mutual Funds</h3>
                        <p>Expertly curated pools of capital for diversified market exposure.</p>
                    </a>
                    <a href="#portfolio" className="venture-card shadow-card">
                        <div className="venture-icon">💼</div>
                        <h3>Private Portfolio</h3>
                        <p>Your aggregated wealth view and historical transaction ledger.</p>
                    </a>
                </div>
            </section>

            <section className="section-spacer">
                <div className="split-header">
                    <h2 className="section-heading-lux uppercase letter-spacing-lg">Primary Holdings</h2>
                    <a href="#portfolio" className="link-primary uppercase text-xs tracking-widest">Full Ledger →</a>
                </div>
                <div className="holdings-list-lux shadow-card">
                    <div className="holding-row-lux">
                        <div className="info">
                            <div className="symbol">RELIANCE</div>
                            <div className="full-name">Reliance Industries</div>
                        </div>
                        <div className="val text-right">
                            <div className="price">₹2,845.50</div>
                            <div className="change positive">+1.42%</div>
                        </div>
                    </div>
                    <div className="holding-row-lux">
                        <div className="info">
                            <div className="symbol">QUANT SM</div>
                            <div className="full-name">Quant Small Cap Fund</div>
                        </div>
                        <div className="val text-right">
                            <div className="price">₹245.10</div>
                            <div className="change positive">+0.86%</div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
};

export default Dashboard;
