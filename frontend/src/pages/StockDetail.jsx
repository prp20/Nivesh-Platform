import React from 'react';
import './StockDetail.css';

const StockDetail = ({ symbol = 'STOCK' }) => {
    return (
        <div className="stock-detail reveal active">
            <header className="detail-header-lux">
                <div className="back-nav-lux">
                    <a href="#stocks" className="btn-back-elite">
                        <span className="back-icon">←</span>
                        <span className="back-text">BACK TO MARKETS</span>
                    </a>
                </div>
                <div className="identity-lux">
                    <div className="logo-lux">{symbol[0]}</div>
                    <div className="titles-lux">
                        <h4 className="label-accent uppercase tracking-widest">{symbol}</h4>
                        <h1 className="font-heading heading-lg">Market Performance</h1>
                    </div>
                </div>
            </header>

            <div className="glass-panel flex flex-col items-center justify-center text-center p-20 opacity-40 gap-6" style={{ minHeight: '400px' }}>
                <div className="text-5xl">📊</div>
                <h3 className="font-heading text-xl uppercase tracking-widest">Stock Detail — Coming Soon</h3>
                <p className="text-sm text-muted max-w-lg leading-relaxed">
                    Real-time price charts, key financials, and trading actions for{' '}
                    <strong>{symbol}</strong> will be available once the equities data API is integrated.
                </p>
                <p className="text-xs text-muted opacity-60 uppercase tracking-widest">
                    Planned: Candlestick charts, P/E, EPS, AUM, and order management
                </p>
            </div>
        </div>
    );
};

export default StockDetail;

