import React, { useState, useEffect } from 'react';
import './BottomNavBar.css';

const NAV_ITEMS = [
    { href: '#dashboard', icon: '🏠', label: 'Dashboard', tab: 'dashboard' },
    { href: '#stocks',    icon: '📈', label: 'Stocks',    tab: 'stocks' },
    { href: '#mf',        icon: '💰', label: 'Funds',     tab: 'mf' },
    { href: '#indices',   icon: '📊', label: 'Indices',   tab: 'indices' },
    { href: '#portfolio', icon: '💼', label: 'Portfolio', tab: 'portfolio' },
];

const getActiveTab = () => {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    // Normalize detail-level hashes back to their parent tab
    if (hash.startsWith('stock-detail')) return 'stocks';
    if (hash.startsWith('mf-detail') || hash.startsWith('compare')) return 'mf';
    if (hash.startsWith('index-detail')) return 'indices';
    return hash;
};

const BottomNavBar = () => {
    const [activeTab, setActiveTab] = useState(getActiveTab);

    useEffect(() => {
        const onHashChange = () => setActiveTab(getActiveTab());
        window.addEventListener('hashchange', onHashChange);
        return () => window.removeEventListener('hashchange', onHashChange);
    }, []);

    return (
        <div className="bottom-nav">
            <div className="bottom-nav-content">
                {NAV_ITEMS.map(({ href, icon, label, tab }) => (
                    <a key={tab} href={href} className={`nav-item ${activeTab === tab ? 'active' : ''}`}>
                        <span className="icon">{icon}</span>
                        <span className="label">{label}</span>
                    </a>
                ))}
            </div>
        </div>
    );
};

export default BottomNavBar;

