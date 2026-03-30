import React, { Component, useEffect, useMemo, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { fetchFundDetail, clearDetail, syncFundMetrics } from '../store/slices/fundDetailSlice';
import { fetchSyncStatus } from '../store/slices/syncSlice';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './MFDetail.css';

const MFDetail = ({ schemeCode }) => {
    const dispatch = useDispatch();
    const { fund, navHistory, metrics, expenseRatios, similarFunds, loading, error, syncing } = useSelector(state => state.fundDetail);
    const syncJob = useSelector(state => state.sync.jobs[schemeCode]);
    const isRefreshing = syncJob?.status === 'RUNNING' || syncing;

    const [timeRange, setTimeRange] = useState('ALL');
    const [expandedSections, setExpandedSections] = useState({
        profile: true,
        performance: false,
        metrics: false,
        management: false,
        peers: false,
        verdict: false
    });

    useEffect(() => {
        if (schemeCode) {
            dispatch(fetchFundDetail(schemeCode));
            dispatch(fetchSyncStatus(schemeCode));
        }
        return () => dispatch(clearDetail());
    }, [schemeCode, dispatch]);

    // Background sync polling
    useEffect(() => {
        let interval;
        if (isRefreshing) {
            interval = setInterval(() => {
                dispatch(fetchSyncStatus(schemeCode)).then((action) => {
                    if (action.payload?.status === 'COMPLETED') {
                        dispatch(fetchFundDetail(schemeCode));
                        clearInterval(interval);
                    }
                });
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [isRefreshing, schemeCode, dispatch]);

    const chartData = useMemo(() => {
        if (!navHistory.length) return [];
        const sorted = navHistory.slice().reverse();

        let filtered = sorted;
        const now = new Date();
        if (timeRange === '1M') {
            const dateLimit = new Date();
            dateLimit.setMonth(now.getMonth() - 1);
            filtered = sorted.filter(n => new Date(n.nav_date) >= dateLimit);
        } else if (timeRange === '6M') {
            const dateLimit = new Date();
            dateLimit.setMonth(now.getMonth() - 6);
            filtered = sorted.filter(n => new Date(n.nav_date) >= dateLimit);
        } else if (timeRange === '1Y') {
            const dateLimit = new Date();
            dateLimit.setFullYear(now.getFullYear() - 1);
            filtered = sorted.filter(n => new Date(n.nav_date) >= dateLimit);
        } else if (timeRange === '3Y') {
            const dateLimit = new Date();
            dateLimit.setFullYear(now.getFullYear() - 3);
            filtered = sorted.filter(n => new Date(n.nav_date) >= dateLimit);
        }

        return filtered.map(n => ({
            date: new Date(n.nav_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }),
            nav: parseFloat(n.nav_value)
        }));
    }, [navHistory, timeRange]);

    if (loading && !fund) return (
        <div className="mf-detail-loading">
            <div className="loader-elite"></div>
            <p className="loading-text">SYNCHRONIZING ASSET INTELLIGENCE...</p>
        </div>
    );

    if (error) return <div className="error-container-lux p-20 text-center">{error}</div>;
    if (!fund) return null;

    const toggleSection = (section) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    const latestNav = navHistory.length > 0 ? navHistory[0].nav_value : 0;
    const prevNav = navHistory.length > 1 ? navHistory[1].nav_value : latestNav;
    const changePercent = prevNav !== 0 ? ((latestNav - prevNav) / prevNav * 100).toFixed(2) : "0.00";

    const formatMetric = (val, precision = 2, suffix = '') => {
        if (val === null || val === undefined) return '--';
        return `${val.toFixed(precision)}${suffix}`;
    };

    const formatPercent = (val) => {
        if (val === null || val === undefined) return '--';
        return `${(val * 100).toFixed(2)}%`;
    };

    return (
        <div className="mf-detail container reveal active">
            {/* BACK BUTTON AS TOP BANNER */}
            <div className="top-banner-lux">
                <a href="#mf" className="btn-back-minimal">
                    <span className="back-icon">←</span>
                    <span className="back-text">BACK TO VAULT OVERVIEW</span>
                </a>
            </div>

            {/* 1. CENTERED HERO */}
            <header className="detail-header-centered">
                <div className="fund-hero-stack-centered">
                    <span className="scheme-type-badge">{fund.scheme_category}</span>
                    <h1 className="heading-xl-centered">{fund.scheme_name}</h1>

                    <div className="hero-action-row-centered">
                        <button
                            className={`btn-sync-minimal ${isRefreshing ? 'loading' : ''}`}
                            onClick={() => dispatch(syncFundMetrics(schemeCode))}
                            disabled={isRefreshing}
                        >
                            {isRefreshing ? 'RECALCULATING INTELLIGENCE...' : 'REFRESH LIVE METRICS'}
                        </button>
                    </div>

                    <div className="hero-stats-panel-lux">
                        <div className="h-stat">
                            <span className="h-stat-label">Current NAV</span>
                            <span className="h-stat-value">₹{latestNav}</span>
                            <span className={`h-stat-change ${parseFloat(changePercent) >= 0 ? 'pos' : 'neg'}`}>
                                {parseFloat(changePercent) >= 0 ? '▲' : '▼'} {Math.abs(changePercent)}%
                            </span>
                        </div>
                        <div className="h-stat">
                            <span className="h-stat-label">3Y CAGR</span>
                            <span className="h-stat-value primary">{formatPercent(metrics?.rolling_return_3year)}</span>
                        </div>
                        <div className="h-stat">
                            <span className="h-stat-label">AUM</span>
                            <span className="h-stat-value primary">₹{formatMetric(metrics?.aum_in_crores, 1)} Cr</span>
                        </div>
                    </div>
                </div>
            </header>

            {/* 2. ASSET PROFILE (COLLAPSIBLE, OPEN BY DEFAULT) */}
            <section className="collapsible-section-lux">
                <header className="section-header-lux" onClick={() => toggleSection('profile')}>
                    <h3 className="section-label-lux">ASSET PROFILE & IDENTIFICATION</h3>
                    <span className={`toggle-icon-lux ${expandedSections.profile ? 'open' : ''}`}>▼</span>
                </header>
                {expandedSections.profile && (
                    <div className="section-content-lux reveal active">
                        <div className="glass-panel-elite p-0 overflow-hidden mt-4">
                            <table className="profile-table-lux">
                                <tbody>
                                    <tr>
                                        <td className="p-label">Asset Management Co.</td>
                                        <td className="p-value">{fund.amc_name}</td>
                                        <td className="p-label">Plan Type</td>
                                        <td className="p-value">{fund.plan_type}</td>
                                    </tr>
                                    <tr>
                                        <td className="p-label">Primary Category</td>
                                        <td className="p-value">{fund.scheme_category}</td>
                                        <td className="p-label">Sub-Category</td>
                                        <td className="p-value">{fund.scheme_subcategory || 'N/A'}</td>
                                    </tr>
                                    <tr>
                                        <td className="p-label">ISIN Identifier</td>
                                        <td className="p-value font-mono text-primary">{fund.isin || 'UNASSIGNED'}</td>
                                        <td className="p-label">Inception Date</td>
                                        <td className="p-value">{fund.inception_date || 'N/A'}</td>
                                    </tr>
                                    <tr>
                                        <td className="p-label">Scheme Code</td>
                                        <td className="p-value font-mono">{fund.scheme_code}</td>
                                        <td className="p-label">Benchmark Index</td>
                                        <td className="p-value">{fund.benchmark_index_code || 'N/A'}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </section>

            {/* 3. NAV PERFORMANCE (COLLAPSIBLE) */}
            <section className="collapsible-section-lux">
                <header className="section-header-lux" onClick={() => toggleSection('performance')}>
                    <h3 className="section-label-lux">PERFORMANCE ANALYTICS</h3>
                    <span className={`toggle-icon-lux ${expandedSections.performance ? 'open' : ''}`}>▼</span>
                </header>
                {expandedSections.performance && (
                    <div className="section-content-lux reveal active">
                        <div className="flex justify-between items-center mb-6 mt-6">
                            <div className="time-range-picker">
                                {['1M', '6M', '1Y', '3Y', 'ALL'].map(t => (
                                    <button
                                        key={t}
                                        className={`t-btn-lux ${timeRange === t ? 'active' : ''}`}
                                        onClick={() => setTimeRange(t)}
                                    >{t}</button>
                                ))}
                            </div>
                        </div>
                        <div className="glass-panel-elite p-8">
                            <div style={{ height: '400px', width: '100%' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData}>
                                        <defs>
                                            <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
                                        <XAxis
                                            dataKey="date"
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fontSize: 9, fill: 'var(--color-text-muted)', fontWeight: 600 }}
                                            minTickGap={30}
                                        />
                                        <YAxis
                                            domain={['auto', 'auto']}
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                                        />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.95)', border: '1px solid var(--color-glass-border)', borderRadius: '12px' }}
                                            itemStyle={{ color: 'var(--color-primary)' }}
                                        />
                                        <Area type="monotone" dataKey="nav" stroke="var(--color-primary)" strokeWidth={3} fill="url(#navGradient)" animationDuration={1000} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}
            </section>

            {/* 4. QUANTITATIVE METRICS (COLLAPSIBLE) */}
            <section className="collapsible-section-lux">
                <header className="section-header-lux" onClick={() => toggleSection('metrics')}>
                    <h3 className="section-label-lux">QUANTITATIVE RISK METRICS</h3>
                    <span className={`toggle-icon-lux ${expandedSections.metrics ? 'open' : ''}`}>▼</span>
                </header>
                {expandedSections.metrics && (
                    <div className="section-content-lux reveal active">
                        <div className="glass-panel-elite overflow-hidden mt-6">
                            <table className="metrics-tabular-lux">
                                <thead>
                                    <tr>
                                        <th>METRIC ATTRIBUTE</th>
                                        <th>VALUE</th>
                                        <th>METRIC ATTRIBUTE</th>
                                        <th>VALUE</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td className="m-name">Expense Ratio (TER)</td>
                                        <td className="m-val text-primary font-bold">{formatPercent(metrics?.expense_ratio)}</td>
                                        <td className="m-name">Fund Rating</td>
                                        <td className="m-val text-accent font-bold">{formatMetric(metrics?.fund_rating, 1, ' ★')}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Volatility</td>
                                        <td className="m-val">{formatMetric(metrics?.volatility, 2, '%')}</td>
                                        <td className="m-name">Standard Deviation</td>
                                        <td className="m-val">{formatMetric(metrics?.standard_deviation, 2, '%')}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Sharpe Ratio</td>
                                        <td className="m-val">{formatMetric(metrics?.sharpe_ratio)}</td>
                                        <td className="m-name">Sortino Ratio</td>
                                        <td className="m-val">{formatMetric(metrics?.sortino_ratio)}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Beta (Relative to Index)</td>
                                        <td className="m-val">{formatMetric(metrics?.beta)}</td>
                                        <td className="m-name">Alpha</td>
                                        <td className="m-val text-accent">{formatMetric(metrics?.alpha, 2, '%')}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Max Drawdown</td>
                                        <td className="m-val text-error">{metrics?.maximum_drawdown != null ? formatPercent(metrics.maximum_drawdown * -1) : '--'}</td>
                                        <td className="m-name">Information Ratio</td>
                                        <td className="m-val">{formatMetric(metrics?.information_ratio)}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Tracking Error</td>
                                        <td className="m-val">{formatMetric(metrics?.tracking_error, 2, '%')}</td>
                                        <td className="m-name">Upside Capture</td>
                                        <td className="m-val text-accent">{formatMetric(metrics?.upside_capture, 2, '%')}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">Downside Capture</td>
                                        <td className="m-val text-error">{formatMetric(metrics?.downside_capture, 2, '%')}</td>
                                        <td className="m-name"></td>
                                        <td className="m-val"></td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">6 Month Absolute</td>
                                        <td className="m-val">{formatPercent(metrics?.short_term_return_6m)}</td>
                                        <td className="m-name">1 Year Absolute</td>
                                        <td className="m-val">{formatPercent(metrics?.absolute_return_1y)}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">3 Year Absolute</td>
                                        <td className="m-val">{formatPercent(metrics?.absolute_return_3y)}</td>
                                        <td className="m-name">5 Year Absolute</td>
                                        <td className="m-val">{formatPercent(metrics?.absolute_return_5y)}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">10 Year Absolute</td>
                                        <td className="m-val">{formatPercent(metrics?.absolute_return_10y)}</td>
                                        <td className="m-name">3 Year Rolling (CAGR)</td>
                                        <td className="m-val font-bold text-primary">{formatPercent(metrics?.rolling_return_3year)}</td>
                                    </tr>
                                    <tr>
                                        <td className="m-name">5 Year Rolling (CAGR)</td>
                                        <td className="m-val font-bold text-primary">{formatPercent(metrics?.rolling_return_5year)}</td>
                                        <td className="m-name"></td>
                                        <td className="m-val"></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </section>

            {/* 6. PEER COMPARISON (COLLAPSIBLE) */}
            {similarFunds.length > 0 && (
                <section className="collapsible-section-lux">
                    <header className="section-header-lux" onClick={() => toggleSection('peers')}>
                        <h3 className="section-label-lux">PEER BENCHMARKING</h3>
                        <span className={`toggle-icon-lux ${expandedSections.peers ? 'open' : ''}`}>▼</span>
                    </header>
                    {expandedSections.peers && (
                        <div className="section-content-lux reveal active">
                            <div className="glass-panel-elite overflow-hidden mt-6">
                                <table className="peer-comparison-table">
                                    <thead>
                                        <tr>
                                            <th>PEER NAME</th>
                                            <th>CATEGORY</th>
                                            <th>3Y ROLLING</th>
                                            <th>5Y ROLLING</th>
                                            <th>SHARPE</th>
                                            <th>ACTION</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {similarFunds.map(peer => (
                                            <tr key={peer.scheme_code}>
                                                <td className="peer-name">
                                                    <div>{peer.scheme_name}</div>
                                                    <div className="text-[9px] text-muted uppercase mt-1">{peer.amc_name}</div>
                                                </td>
                                                <td className="peer-category"><span className="peer-badge">{peer.scheme_subcategory || peer.scheme_category}</span></td>
                                                <td className="peer-stat">{peer.metrics?.rolling_return_3year ? (peer.metrics.rolling_return_3year * 100).toFixed(2) + '%' : '--'}</td>
                                                <td className="peer-stat">{peer.metrics?.rolling_return_5year ? (peer.metrics.rolling_return_5year * 100).toFixed(2) + '%' : '--'}</td>
                                                <td className="peer-stat">{peer.metrics?.sharpe_ratio?.toFixed(2) || '--'}</td>
                                                <td><a href={`#mf-detail-${peer.scheme_code}`} className="btn-view-peer">VIEW</a></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* 7. FINAL VERDICT (COLLAPSIBLE) */}
            <section className="collapsible-section-lux">
                <header className="section-header-lux" onClick={() => toggleSection('verdict')}>
                    <h3 className="section-label-lux">NIVESH INTELLIGENCE VERDICT</h3>
                    <span className={`toggle-icon-lux ${expandedSections.verdict ? 'open' : ''}`}>▼</span>
                </header>
                {expandedSections.verdict && (
                    <div className="section-content-lux reveal active">
                        <div className="glass-panel-elite verdict-box p-8 grow-hover mt-6">
                            <div className="verdict-icon">✦</div>
                            <p className="verdict-text">{metrics?.final_verdict || "Insufficient dynamic data for a final verdict."}</p>
                            <div className="verdict-footer mt-4 text-[9px] text-muted uppercase tracking-[0.2em]">Generated by Nivesh Engine • {new Date().toLocaleDateString()}</div>
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
};

class MFDetailErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }
    static getDerivedStateFromError(error) { return { hasError: true }; }
    componentDidCatch(error, errorInfo) { console.error("MFDetail Error:", error, errorInfo); }
    render() {
        if (this.state.hasError) {
            return (
                <div className="error-container-lux p-20 text-center">
                    <h2 className="text-error font-heading mb-4">ASSET RENDER FAILURE</h2>
                    <p className="text-muted text-xs uppercase tracking-widest">The intelligence engine encountered an anomaly while mapping this asset.</p>
                    <button className="btn-premium btn-premium-primary mt-8" onClick={() => window.location.reload()}>RETRY SYNCHRONIZATION</button>
                </div>
            );
        }
        return this.props.children;
    }
}

const MFDetailWithBoundary = (props) => (
    <MFDetailErrorBoundary>
        <MFDetail {...props} />
    </MFDetailErrorBoundary>
);

export default MFDetailWithBoundary;
