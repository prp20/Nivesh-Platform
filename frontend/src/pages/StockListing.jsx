import React from 'react';
import './StockListing.css';

const StockListing = () => {
    return (
        <div className="stock-listing container reveal active">
            <header className="listing-header-lux">
                <span className="label-accent uppercase tracking-widest text-xs">Direct Equity Access</span>
                <h1 className="font-heading heading-xl">Global Markets</h1>
            </header>

            <div className="glass-panel pro-table-container reveal active">
                <div className="flex flex-col items-center justify-center p-20 text-center opacity-40 gap-6">
                    <div className="text-5xl">📈</div>
                    <h3 className="font-heading text-xl uppercase tracking-widest">Direct Equities — Coming Soon</h3>
                    <p className="text-sm text-muted max-w-lg leading-relaxed">
                        Live stock market data, real-time price tracking, and direct equity management
                        will be available once the equities backend API is integrated.
                    </p>
                    <p className="text-xs text-muted opacity-60 uppercase tracking-widest">
                        Planned: NSE / BSE live feed integration
                    </p>
                </div>
            </div>
        </div>
    );
};

export default StockListing;

