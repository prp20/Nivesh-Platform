import React from 'react';
import './BottomNavBar.css';

const BottomNavBar = () => {
    return (
        <div className="bottom-nav">
            <div className="bottom-nav-content">
                <a href="#dashboard" className="nav-item active">
                    <span className="icon">🏠</span>
                    <span className="label">Dashboard</span>
                </a>
                <a href="#stocks" className="nav-item">
                    <span className="icon">📈</span>
                    <span className="label">Stocks</span>
                </a>
                <a href="#mf" className="nav-item">
                    <span className="icon">💰</span>
                    <span className="label">Funds</span>
                </a>
                <a href="#portfolio" className="nav-item">
                    <span className="icon">💼</span>
                    <span className="label">Portfolio</span>
                </a>
            </div>
        </div>
    );
};

export default BottomNavBar;
