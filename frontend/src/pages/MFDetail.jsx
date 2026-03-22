import React, { useState, useEffect, useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { triggerSync, fetchSyncStatus } from '../store/slices/syncSlice';
import fundService from '../api/services/fundService';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './MFDetail.css';

const MFDetail = ({ schemeCode }) => {
    const dispatch = useDispatch();
    const syncJob = useSelector(state => state.sync.jobs[schemeCode]);
    const refreshing = syncJob?.status === 'RUNNING';

    const [fund, setFund] = useState(null);
    const [navHistory, setNavHistory] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [timeRange, setTimeRange] = useState('ALL');

    const fetchAllData = async (force = false) => {
        if (!schemeCode) return;
        if (!force) setLoading(true);
        
        try {
            const [fundData, historyData] = await Promise.all([
                fundService.getFundDetail(schemeCode),
                fundService.getFundNavHistory(schemeCode, 500),
            ]);
            
            setFund(fundData);
            setNavHistory(historyData);

            const res = await fundService.getFundMetrics(schemeCode).catch(() => null);
            if (res) {
                setMetrics(res.metrics);
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

    useEffect(() => {
        fetchAllData();
        dispatch(fetchSyncStatus(schemeCode));
    }, [schemeCode, dispatch]);

    useEffect(() => {
        let interval;
        if (refreshing) {
            interval = setInterval(() => {
                dispatch(fetchSyncStatus(schemeCode)).then((action) => {
                    if (action.payload?.status === 'COMPLETED') {
                        fundService.getFundMetrics(schemeCode).then(res => {
                            if (res) setMetrics(res.metrics);
                        });
                        fundService.getFundNavHistory(schemeCode, 500).then(data => setNavHistory(data));
                    }
                });
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [refreshing, schemeCode, dispatch]);

    const chartData = useMemo(() => {
        if (!navHistory.length) return [];
        const sorted = navHistory.slice().reverse();
        
        let filtered = sorted;
        const now = new Date();
        if (timeRange === '1M') {
            const monthAgo = new Date().setMonth(now.getMonth() - 1);
            filtered = sorted.filter(n => new Date(n.nav_date) >= monthAgo);
        } else if (timeRange === '6M') {
            const sixMonthsAgo = new Date().setMonth(now.getMonth() - 6);
            filtered = sorted.filter(n => new Date(n.nav_date) >= sixMonthsAgo);
        } else if (timeRange === '1Y') {
            const yearAgo = new Date().setFullYear(now.getFullYear() - 1);
            filtered = sorted.filter(n => new Date(n.nav_date) >= yearAgo);
        }

        return filtered.map(n => ({
            date: new Date(n.nav_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
            nav: parseFloat(n.nav_value)
        }));
    }, [navHistory, timeRange]);

    if (loading) return <div className="loading-container p-20 text-center font-heading uppercase tracking-widest">Compiling Performance History...</div>;
    if (!fund) return <div className="error-container p-20 text-center font-heading">Asset Identification Failed.</div>;

    const latestNav = navHistory.length > 0 ? navHistory[0].nav_value : 0;
    const prevNav = navHistory.length > 1 ? navHistory[1].nav_value : latestNav;
    const changePercent = ((latestNav - prevNav) / prevNav * 100).toFixed(2);

    const formatMetric = (val, precision = 2) => {
        if (val === null || val === undefined) return '0.00';
        return val.toFixed(precision);
    };

    const formatPercent = (val) => {
        if (val === null || val === undefined) return '0.00%';
        return `${(val * 100).toFixed(2)}%`;
    };

    return (
        <div className="mf-detail container reveal active">
            <header className="detail-header-lux">
                <div className="back-nav-lux mb-12">
                    <a href="#mf" className="btn-back-elite">
                        <span className="back-icon">←</span>
                        <span className="back-text">BACK TO VAULT OVERVIEW</span>
                    </a>
                </div>
                
                <div className="fund-hero-stack">
                    <span className="label-accent uppercase tracking-widest text-xs">{fund.scheme_category}</span>
                    <h1 className="heading-xl mt-4">{fund.scheme_name}</h1>
                    <p className="text-muted text-xs uppercase tracking-widest mt-3">
                        {fund.amc_name} <span className="mx-2 opacity-30">•</span> IDENTIFIER: {fund.scheme_code}
                    </p>

                    <div className="price-performance-row mt-10">
                        <span className="price-val font-heading">₹{latestNav}</span>
                        <div className={`change-badge-elite ${changePercent >= 0 ? 'positive' : 'negative'}`}>
                            {changePercent >= 0 ? '▲' : '▼'} {Math.abs(changePercent)}%
                        </div>
                    </div>

                    <div className="flex gap-4 mt-12">
                        <button 
                            className={`btn-premium btn-premium-refresh ${refreshing ? 'loading' : ''}`}
                            onClick={() => fetchAllData(true)}
                            disabled={refreshing}
                        >
                            <span className="btn-label">{refreshing ? 'REFRESHING ASSET...' : 'SYNC MARKET METRICS'}</span>
                        </button>
                        <button className="btn-premium btn-premium-primary px-10">EXECUTE ALLOCATION</button>
                    </div>
                </div>
            </header>

            {syncJob?.status === 'RUNNING' && (
                <div className="glass-panel sync-progress-banner reveal active">
                    <div className="sync-loader"></div>
                    <div>
                        <span className="label-accent uppercase tracking-widest text-xs">Synchronization Active</span>
                        <p className="font-heading text-lg">{syncJob.message}</p>
                    </div>
                </div>
            )}

            <div className="detail-grid-lux">
                <div className="glass-panel chart-box-lux glow-card">
                    <div className="chart-head-lux">
                        <h3 className="font-heading text-md uppercase tracking-widest opacity-60">Growth Index</h3>
                        <div className="flex gap-3">
                            {['1M', '6M', '1Y', 'ALL'].map(t => (
                                <button 
                                    key={t} 
                                    className={`t-btn ${timeRange === t ? 'active' : ''}`}
                                    onClick={() => setTimeRange(t)}
                                >{t}</button>
                            ))}
                        </div>
                    </div>
                    
                    <div style={{ height: '350px', width: '100%' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData}>
                                <defs>
                                    <linearGradient id="navGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis 
                                    dataKey="date" 
                                    axisLine={false} 
                                    tickLine={false} 
                                    tick={{fontSize: 10, fill: 'var(--color-text-muted)'}}
                                    interval={Math.floor(chartData.length / 6)}
                                />
                                <YAxis 
                                    domain={['auto', 'auto']} 
                                    axisLine={false} 
                                    tickLine={false}
                                    tick={{fontSize: 10, fill: 'var(--color-text-muted)'}}
                                />
                                <Tooltip 
                                    contentStyle={{backgroundColor: '#0f172a', border: '1px solid var(--color-glass-border)', borderRadius: '8px', fontSize: '12px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)'}}
                                    itemStyle={{color: 'var(--color-primary)'}}
                                />
                                <Area 
                                    type="monotone" 
                                    dataKey="nav" 
                                    stroke="var(--color-primary)" 
                                    strokeWidth={3}
                                    fill="url(#navGradient)" 
                                    animationDuration={1500}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="info-stack-lux">
                    <div className="glass-panel info-card-lux glow-card highlighted">
                        <span className="label-accent uppercase tracking-widest text-xs">3Y Rolling Return</span>
                        <div className="font-heading">{formatPercent(metrics?.rolling_return_3year)}</div>
                    </div>
                    <div className="glass-panel info-card-lux glow-card highlighted">
                        <span className="label-accent uppercase tracking-widest text-xs">5Y Rolling Return</span>
                        <div className="font-heading">{formatPercent(metrics?.rolling_return_5year)}</div>
                    </div>
                    <div className="glass-panel info-card-lux glow-card">
                        <span className="label-accent uppercase tracking-widest text-xs">AUM (Cr)</span>
                        <div className="font-heading text-primary">₹{formatMetric(metrics?.aum_in_crores, 1)}</div>
                    </div>
                </div>
            </div>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h3 className="section-heading-lux uppercase">Risk Intelligence Parameters</h3>
                    {metrics?.metrics_calculated_at && (
                        <span className="text-xs text-muted opacity-50 uppercase tracking-tighter">
                            Last Logic Execution: {new Date(metrics.metrics_calculated_at).toLocaleString()}
                        </span>
                    )}
                </div>
                
                <div className="metrics-grid-lux">
                    {[
                        { l: "Sharpe Ratio", v: formatMetric(metrics?.sharpe_ratio) },
                        { l: "Sortino Ratio", v: formatMetric(metrics?.sortino_ratio) },
                        { l: "Alpha", v: formatMetric(metrics?.alpha) },
                        { l: "Beta", v: formatMetric(metrics?.beta) },
                        { l: "Standard Dev.", v: formatMetric(metrics?.standard_deviation) },
                        { l: "Max Drawdown", v: formatPercent(metrics?.maximum_drawdown * -1) },
                        { l: "Tracking Error", v: formatMetric(metrics?.tracking_error) },
                        { l: "Info Ratio", v: formatMetric(metrics?.information_ratio) }
                    ].map((m, i) => (
                        <div key={i} className="glass-panel metric-box glow-card reveal active" style={{ animationDelay: `${i * 0.05}s` }}>
                            <span className="metric-label">{m.l}</span>
                            <span className="metric-value font-heading">{m.v}</span>
                        </div>
                    ))}
                </div>
            </section>

            <section className="section-spacer">
                <div className="flex justify-between items-center mb-10">
                    <h3 className="section-heading-lux uppercase">Asset Metadata</h3>
                    <div className="h-px bg-white/10 flex-1 mx-10"></div>
                </div>
                <div className="flex flex-wrap gap-5">
                    <div className="chip-lux py-4 px-8 border-white/5 bg-white/5 opacity-80 uppercase tracking-widest text-xs">CODE: {fund.scheme_code}</div>
                    <div className="chip-lux py-4 px-8 border-white/5 bg-white/5 opacity-80 uppercase tracking-widest text-xs">VARIANT: {fund.plan_type}</div>
                    <div className="chip-lux py-4 px-8 border-white/5 bg-white/5 opacity-80 uppercase tracking-widest text-xs">GENESIS: {fund.inception_date}</div>
                    <div className="chip-lux py-4 px-8 border-white/5 bg-white/5 opacity-80 uppercase tracking-widest text-xs">AMC: {fund.amc_name}</div>
                </div>
            </section>
        </div>
    );
};

export default MFDetail;
