import React from 'react';
import './MFDetail.css';

const MFDetail = ({ name = 'Quant Small Cap Fund' }) => {
    const fundName = name.replace(/-/g, ' ');

    return (
        <div className="mf-detail reveal active">
            <header className="detail-header-lux">
                <div className="identity-lux">
                    <div className="logo-lux-mf">{fundName[0]}</div>
                    <div className="titles-lux">
                        <h4 className="label-accent uppercase tracking-widest">Asset Analysis</h4>
                        <h1 className="font-heading heading-lg">{fundName}</h1>
                    </div>
                </div>

                <div className="val-actions-lux">
                    <div className="price-lux">
                        <span className="price-val font-heading">₹245.10</span>
                        <span className="change-val positive">+0.86%</span>
                    </div>
                    <div className="buttons-lux">
                        <button className="btn-primary-lux uppercase tracking-widest">Allocate</button>
                        <button className="btn-outline-lux uppercase tracking-widest">SIP Setup</button>
                    </div>
                </div>
            </header>

            <div className="detail-grid-lux section-spacer">
                <div className="chart-box-lux shadow-card">
                    <div className="chart-head-lux">
                        <h3 className="uppercase tracking-widest text-xs">Growth Index</h3>
                        <div className="toggles-lux">
                            {['1M', '6M', '1Y', '3Y', '5Y'].map(t => (
                                <button key={t} className={`t-btn ${t === '3Y' ? 'active' : ''}`}>{t}</button>
                            ))}
                        </div>
                    </div>
                    <div className="visual-lux">
                        <div className="mf-chart-sim"></div>
                    </div>
                </div>

                <div className="info-stack-lux">
                    <div className="info-card-lux shadow-card">
                        <h4 className="label-accent uppercase text-xs">AUM</h4>
                        <p className="font-heading">₹5,420 Cr</p>
                    </div>
                    <div className="info-card-lux shadow-card">
                        <h4 className="label-accent uppercase text-xs">Expense Ratio</h4>
                        <p className="font-heading">0.72%</p>
                    </div>
                    <div className="info-card-lux shadow-card">
                        <h4 className="label-accent uppercase text-xs">Fund House</h4>
                        <p className="font-heading">Quant Mutual Fund</p>
                    </div>
                </div>
            </div>

            <section className="section-spacer">
                <h3 className="section-heading-lux uppercase letter-spacing-lg">Portfolio Concentration</h3>
                <div className="holdings-row-lux">
                    {['RELIANCE (8.5%)', 'HDFC BANK (7.2%)', 'TCS (6.4%)', 'INFOSYS (5.1%)'].map(h => (
                        <div key={h} className="holding-tag shadow-card">{h}</div>
                    ))}
                </div>
            </section>
        </div>
    );
};

export default MFDetail;
