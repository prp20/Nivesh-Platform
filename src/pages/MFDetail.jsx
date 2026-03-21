import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { triggerSync, fetchSyncStatus } from '../store/slices/syncSlice';
import fundService from '../api/services/fundService';
import './MFDetail.css';

const MFDetail = ({ schemeCode }) => {
    const dispatch = useDispatch();
    const syncJob = useSelector(state => state.sync.jobs[schemeCode]);
    const refreshing = syncJob?.status === 'RUNNING';

    const [fund, setFund] = useState(null);
    const [navHistory, setNavHistory] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchAllData = async (force = false) => {
        if (!schemeCode) return;
        if (!force) setLoading(true);
        
        try {
            const [fundData, historyData] = await Promise.all([
                fundService.getFundDetail(schemeCode),
                fundService.getFundNavHistory(schemeCode, 200),
            ]);
            
            setFund(fundData);
            setNavHistory(historyData);

            // Fetch metrics
            const res = await fundService.getFundMetrics(schemeCode).catch(() => null);
            if (res) {
                setMetrics(res.metrics);
                // Sync status will be handled by the initial fetchSyncStatus call in useEffect
            }

            if (force) {
                dispatch(triggerSync(schemeCode));
            }

        } catch (err) {
            console.error("Failed to fetch fund details", err);
        } finally {
            setLoading(false);
        }
    };

    // Initial load and periodic status polling
    useEffect(() => {
        fetchAllData();
        dispatch(fetchSyncStatus(schemeCode));
    }, [schemeCode]);

    useEffect(() => {
        let interval;
        if (refreshing) {
            interval = setInterval(() => {
                dispatch(fetchSyncStatus(schemeCode)).then((action) => {
                    if (action.payload?.status === 'COMPLETED') {
                        // Refresh metrics once done
                        fundService.getFundMetrics(schemeCode).then(res => {
                            if (res) setMetrics(res.metrics);
                        });
                    }
                });
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [refreshing, schemeCode]);

    const handleRefresh = () => {
        fetchAllData(true);
    };

    if (loading) return <div className="loading-container p-20">Analyzing Fund Performance...</div>;
    if (!fund) return <div className="error-container p-20">Fund not found.</div>;

    const latestNav = navHistory.length > 0 ? navHistory[0].nav_value : 0;
    const prevNav = navHistory.length > 1 ? navHistory[1].nav_value : latestNav;
    const changePercent = ((latestNav - prevNav) / prevNav * 100).toFixed(2);

    const formatMetric = (val, suffix = '', precision = 2) => {
        if (val === null || val === undefined) return 'N/A';
        return `${val.toFixed(precision)}${suffix}`;
    };

    const formatPercent = (val) => {
        if (val === null || val === undefined) return 'N/A';
        return `${(val * 100).toFixed(2)}%`;
    };

    return (
        <div className="mf-detail reveal active">
            <header className="detail-header-lux">
                <div className="identity-lux">
                    <div className="logo-lux-mf">{fund.scheme_name[0]}</div>
                    <div className="titles-lux">
                        <h4 className="label-accent uppercase tracking-widest">{fund.scheme_category}</h4>
                        <h1 className="font-heading heading-lg">{fund.scheme_name}</h1>
                    </div>
                </div>

                <div className="val-actions-lux">
                    <div className="price-lux">
                        <span className="price-val font-heading">₹{latestNav}</span>
                        <span className={`change-val ${changePercent >= 0 ? 'positive' : 'negative'}`}>
                            {changePercent >= 0 ? '+' : ''}{changePercent}%
                        </span>
                    </div>
                    <div className="buttons-lux">
                        <button 
                            className={`btn-secondary-lux uppercase tracking-widest ${refreshing ? 'loading' : ''}`}
                            onClick={handleRefresh}
                            disabled={refreshing}
                        >
                            {refreshing ? 'Refreshing...' : 'Refresh Metrics'}
                        </button>
                        <button className="btn-primary-lux uppercase tracking-widest">Allocate</button>
                    </div>
                </div>
            </header>

            {syncJob && syncJob.status === 'RUNNING' && (
                <div className="sync-progress-banner shadow-card">
                    <div className="sync-loader"></div>
                    <div className="sync-info">
                        <span className="sync-label uppercase tracking-widest">Sync in Progress</span>
                        <p className="sync-message">{syncJob.message}</p>
                    </div>
                </div>
            )}

            <div className="detail-grid-lux section-spacer">
                <div className="chart-box-lux shadow-card">
                    <div className="chart-head-lux">
                        <h3 className="uppercase tracking-widest text-xs">Growth Index (NAV)</h3>
                        <div className="toggles-lux">
                            {['1M', '6M', '1Y', 'ALL'].map(t => (
                                <button key={t} className={`t-btn ${t === 'ALL' ? 'active' : ''}`}>{t}</button>
                            ))}
                        </div>
                    </div>
                    <div className="visual-lux">
                        <div className="mf-chart-sim">
                            <svg viewBox="0 0 100 40" className="sparkline">
                                <path
                                    d={`M 0 40 ${navHistory.slice(0, 40).reverse().map((n, i) => `L ${i * (100/39)} ${40 - ((n.nav_value / Math.max(...navHistory.map(x=>x.nav_value))) * 35)}`).join(' ')}`}
                                    fill="none"
                                    stroke="var(--primary)"
                                    strokeWidth="0.5"
                                />
                            </svg>
                        </div>
                    </div>
                </div>

                <div className="info-stack-lux">
                    <div className="info-card-lux shadow-card highlighted">
                        <h4 className="label-accent uppercase text-xs">3Y Rolling Return</h4>
                        <p className="font-heading">{formatPercent(metrics?.rolling_return_3year)}</p>
                    </div>
                    <div className="info-card-lux shadow-card highlighted">
                        <h4 className="label-accent uppercase text-xs">5Y Rolling Return</h4>
                        <p className="font-heading">{formatPercent(metrics?.rolling_return_5year)}</p>
                    </div>
                    <div className="info-card-lux shadow-card">
                        <h4 className="label-accent uppercase text-xs">AUM (Cr)</h4>
                        <p className="font-heading">₹{formatMetric(metrics?.aum_in_crores, '', 1)}</p>
                    </div>
                </div>
            </div>

            <section className="section-spacer">
                <div className="section-header-row">
                    <h3 className="section-heading-lux uppercase letter-spacing-lg">Performance & Risk Metrics</h3>
                    {metrics?.metrics_calculated_at && (
                        <span className="last-updated-text text-xs uppercase tracking-tighter">
                            Last Updated: {new Date(metrics.metrics_calculated_at).toLocaleString()}
                        </span>
                    )}
                </div>
                
                <div className="metrics-grid-lux">
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Sharpe Ratio</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.sharpe_ratio)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Sortino Ratio</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.sortino_ratio)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Alpha</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.alpha)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Beta</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.beta)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Standard Dev.</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.standard_deviation)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Max Drawdown</span>
                        <span className="metric-value font-heading">{formatPercent(metrics?.maximum_drawdown)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Tracking Error</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.tracking_error)}</span>
                    </div>
                    <div className="metric-box shadow-card">
                        <span className="metric-label">Information Ratio</span>
                        <span className="metric-value font-heading">{formatMetric(metrics?.information_ratio)}</span>
                    </div>
                </div>
            </section>

            <section className="section-spacer">
                <h3 className="section-heading-lux uppercase letter-spacing-lg">Fund Details</h3>
                <div className="holdings-row-lux">
                    <div className="holding-tag shadow-card">CODE: {fund.scheme_code}</div>
                    <div className="holding-tag shadow-card">TYPE: {fund.plan_type}</div>
                    <div className="holding-tag shadow-card">INCEPTION: {fund.inception_date}</div>
                    <div className="holding-tag shadow-card">AMC: {fund.amc_name}</div>
                </div>
            </section>
        </div>
    );
};

export default MFDetail;
