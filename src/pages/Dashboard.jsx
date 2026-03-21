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
                const data = await fundService.getFunds(0, 10);
                setStats({ totalFunds: data.length });
            } catch (err) {
                console.error("Dashboard fetch failed", err);
            }
        };
        fetchStats();

        // Clear global sync message after some time if it's completed or failed
        if (globalSync.status === 'COMPLETED' || globalSync.status === 'FAILED') {
            const timer = setTimeout(() => {
                dispatch(clearGlobalSync());
            }, 5000);
            return () => clearTimeout(timer);
        }
    }, [globalSync.status]);

    const handleSync = () => {
        dispatch(triggerGlobalSync());
    };

    return (
        <div className="dashboard reveal active">
            {globalSync.message && (
                <div className={`sync-status-banner-dashboard ${globalSync.status.toLowerCase()}`}>
                    <div className="banner-content">
                        <span className="spinner-lux small"></span>
                        <span className="banner-msg">{globalSync.message}</span>
                    </div>
                </div>
            )}

            <header className="dashboard-header-lux">
                <div className="flex justify-between items-center">
                    <div>
                        <h4 className="label-accent uppercase tracking-widest">Elite Portfolio</h4>
                        <h1 className="font-heading heading-xl">Performance Overview</h1>
                    </div>
                    <button
                        onClick={handleSync}
                        disabled={isSyncing}
                        className={`btn-secondary-lux uppercase tracking-widest ${isSyncing ? 'loading' : ''}`}
                    >
                        {isSyncing ? 'Synchronizing...' : 'Sync Data Hub'}
                    </button>
                </div>
                <p className="text-secondary max-w-lg">Monitoring international markets and your diversified assets across equity and debt instruments.</p>
            </header>

            <div className="stats-grid-lux">
                <div className="summary-card-lux main-card">
                    <div className="card-top">
                        <span className="label-accent uppercase">Current Holdings</span>
                        <div className="value font-heading">{stats.totalFunds} <span style={{ fontSize: '1.2rem', color: '#888' }}>Asset Classes</span></div>
                    </div>
                    <div className="card-bottom">
                        <div className="trend-positive">
                            <span className="icon">↑</span>
                            <span>Live Integration Active</span>
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
        </div>
    );
};

export default Dashboard;
