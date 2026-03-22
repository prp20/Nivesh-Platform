import React from 'react';
import './StockDetail.css';

const StockDetail = ({ symbol = 'RELIANCE' }) => {
    return (
        <div className="stock-detail reveal active">
            <header className="detail-header-lux">
                <div className="identity-lux">
                    <div className="logo-lux">{symbol[0]}</div>
                    <div className="titles-lux">
                        <h4 className="label-accent uppercase tracking-widest">{symbol}</h4>
                        <h1 className="font-heading heading-lg">Market Performance</h1>
                    </div>
                </div>

                <div className="val-actions-lux">
                    <div className="price-lux">
                        <span className="price-val font-heading">₹2,845.50</span>
                        <span className="change-val positive">+1.42%</span>
                    </div>
                    <div className="buttons-lux">
                        <button className="btn-primary-lux uppercase tracking-widest">Acquire</button>
                        <button className="btn-outline-lux uppercase tracking-widest">Liquidate</button>
                    </div>
                </div>
            </header>

            <div className="detail-grid-lux section-spacer">
                <div className="chart-box-lux shadow-card">
                    <div className="chart-head-lux">
                        <h3 className="uppercase tracking-widest text-xs">Technical Index</h3>
                        <div className="toggles-lux">
                            {['1D', '1W', '1M', '1Y', 'MAX'].map(t => (
                                <button key={t} className={`t-btn ${t === '1M' ? 'active' : ''}`}>{t}</button>
                            ))}
                        </div>
                    </div>
                    <div className="visual-lux">
                        <div className="line-chart-sim"></div>
                    </div>
                </div>

                <div className="data-box-lux shadow-card">
                    <h3 className="label-accent uppercase mb-lux">Key Metrics</h3>
                    <div className="metrics-list-lux">
                        <div className="m-row"><span>P/E RATIO</span><strong>28.4</strong></div>
                        <div className="m-row"><span>MARKET CAP</span><strong>₹19.2T</strong></div>
                        <div className="m-row"><span>DIV YIELD</span><strong>0.32%</strong></div>
                        <div className="m-row"><span>ROE</span><strong>15.2%</strong></div>
                        <div className="m-row"><span>EPS</span><strong>₹101.4</strong></div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StockDetail;
