import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { triggerGlobalSync, clearGlobalSync } from '../store/slices/syncSlice';
import fundService from '../api/services/fundService';
import './Dashboard.css';

const Dashboard = () => {
    const dispatch = useDispatch();
    const globalSync = useSelector(state => state.sync.globalSync);
    const isSyncing = globalSync.status === 'RUNNING';
    const [stats, setStats] = useState({ totalFunds: 0 });

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const data = await fundService.getFunds(0, 1);
                setStats({ totalFunds: data.total });
            } catch (err) {
                console.error("Dashboard fetch failed", err);
            }
        };
        fetchStats();

        if (globalSync.status === 'COMPLETED' || globalSync.status === 'FAILED') {
            const timer = setTimeout(() => {
                dispatch(clearGlobalSync());
            }, 5000);
            return () => clearTimeout(timer);
        }
    }, [globalSync.status, dispatch]);

    const handleSync = () => {
        dispatch(triggerGlobalSync());
    };

    return (
        <div className="dashboard container reveal active">
            {globalSync.message && (
                <div className={`sync-status-banner-dashboard ${globalSync.status.toLowerCase()}`}>
                    <div className="banner-content">
                        <span className="spinner-lux small"></span>
                        <span className="banner-msg">{globalSync.message}</span>
                    </div>
                </div>
            )}

            <header className="dashboard-header-lux">
                <div className="reveal active flex flex-column items-center">
                    <span className="label-accent uppercase tracking-widest text-xs">Intelligence Layer v2.0</span>
                    <h1 className="heading-xl">Market Command</h1>
                    <p className="text-secondary max-w-lg mt-5 text-center">
                        Synthesizing real-time market signals across your diversified equity and debt portfolio.
                    </p>
                    <button
                        onClick={handleSync}
                        disabled={isSyncing}
                        className={`btn-sync-icon ${isSyncing ? 'loading' : ''}`}
                        title={isSyncing ? 'Syncing Ecosystem...' : 'Force Sync Data Hub'}
                    >
                        {isSyncing ? '⌛' : '🔄'}
                    </button>
                </div>
            </header>

            <div className="hero-stats-row">
                <div className="glass-panel main-stat-card glow-card">
                    <span className="label-accent uppercase tracking-widest text-xs">Total Managed Assets</span>
                    <div className="value">{stats.totalFunds}</div>
                    <div className="flex gap-5 items-center mt-5">
                        <div className="trend-positive">↑ 12.4% THIS MONTH</div>
                    </div>
                </div>

                <div className="market-pulse-stack">
                    <div className="glass-panel pulse-card glow-card">
                        <div>
                            <span className="name">Nifty 50</span>
                            <div className="val">22,056.40</div>
                        </div>
                        <span className="trend">+0.45%</span>
                    </div>
                    <div className="glass-panel pulse-card glow-card">
                        <div>
                            <span className="name">Sensex</span>
                            <div className="val">72,641.19</div>
                        </div>
                        <span className="trend negative">-0.12%</span>
                    </div>
                </div>
            </div>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h2 className="font-heading text-lg uppercase tracking-widest opacity-60">Platform Segments</h2>
                    <div className="h-px bg-white/10 flex-1 mx-10"></div>
                </div>
                
                <div className="venture-grid">
                    <a href="#stocks" className="venture-card-elite reveal active">
                        <div className="v-icon-box">📈</div>
                        <h3>Direct Equities</h3>
                        <p>High-conviction stock picks and sector-specific equity allocations.</p>
                        <span className="link-primary text-xs mt-auto">ACCESS VAULT →</span>
                    </a>
                    <a href="#mf" className="venture-card-elite reveal active" style={{ animationDelay: '0.1s' }}>
                        <div className="v-icon-box">💰</div>
                        <h3>Mutual Funds</h3>
                        <p>Professional risk-adjusted capital pools and thematic index funds.</p>
                        <span className="link-primary text-xs mt-auto">ACCESS VAULT →</span>
                    </a>
                    <a href="#portfolio" className="venture-card-elite reveal active" style={{ animationDelay: '0.2s' }}>
                        <div className="v-icon-box">💼</div>
                        <h3>Master Portfolio</h3>
                        <p>Aggregated wealth view and cross-asset performance analytics.</p>
                        <span className="link-primary text-xs mt-auto">ACCESS VAULT →</span>
                    </a>
                </div>
            </section>
        </div>
    );
};

export default Dashboard;
