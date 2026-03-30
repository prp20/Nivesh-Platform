import React, { useState, useEffect, useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { triggerIndexSync, fetchIndexSyncStatus } from '../store/slices/syncSlice';
import fundService from '../api/services/fundService';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './MFDetail.css';

const IndexDetail = ({ benchmarkCode }) => {
    const dispatch = useDispatch();
    const syncJob = useSelector(state => state.sync.indexJobs[benchmarkCode]);
    const isSyncing = syncJob?.status === 'RUNNING';

    const [index, setIndex] = useState(null);
    const [navHistory, setNavHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [timeRange, setTimeRange] = useState('ALL');
    const [uploading, setUploading] = useState(false);
    const [uploadMsg, setUploadMsg] = useState(null);

    const navigateBack = () => {
        window.location.hash = '#indices';
    };

    const fetchHistory = async () => {
        try {
            const historyData = await fundService.getBenchmarkNavHistory(benchmarkCode, 1000);
            setNavHistory(historyData);
        } catch (err) {
            console.error("Failed to refresh history", err);
        }
    }

    useEffect(() => {
        const fetchDetail = async () => {
            if (!benchmarkCode) return;
            try {
                const [indexData, historyData] = await Promise.all([
                    fundService.getBenchmarkDetail(benchmarkCode),
                    fundService.getBenchmarkNavHistory(benchmarkCode, 1000)
                ]);
                setIndex(indexData);
                setNavHistory(historyData);
                setLoading(false);
            } catch (err) {
                console.error("Failed to fetch index details", err);
                setError("Index data stream intermittent. Security protocol active.");
                setLoading(false);
            }
        };
        fetchDetail();
        dispatch(fetchIndexSyncStatus(benchmarkCode));
    }, [benchmarkCode, dispatch]);

    // Poll for sync status when a sync is in progress
    useEffect(() => {
        let interval;
        if (isSyncing) {
            interval = setInterval(() => {
                dispatch(fetchIndexSyncStatus(benchmarkCode)).then((action) => {
                    if (action.payload?.status === 'COMPLETED') {
                        fetchHistory();
                    }
                });
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [isSyncing, benchmarkCode, dispatch]);

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        setUploading(true);
        setUploadMsg(null);
        try {
            const res = await fundService.uploadBenchmarkCsv(benchmarkCode, file);
            setUploadMsg({ type: 'success', text: res.message });
            await fetchHistory();
        } catch (err) {
            setUploadMsg({ type: 'error', text: err.response?.data?.detail || "Intake protocol failure." });
        } finally {
            setUploading(false);
        }
    };

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
            nav: parseFloat(n.index_value)
        }));
    }, [navHistory, timeRange]);

    if (loading) return <div className="loading-container p-20 text-center uppercase tracking-widest font-heading">Decrypting Market Intelligence...</div>;
    if (error) return <div className="glass-panel p-10 text-center text-error border-error/20 m-10">{error}</div>;
    if (!index) return <div className="glass-panel p-10 text-center m-10">Intelligence record not found.</div>;

    const hasNavData = navHistory && navHistory.length > 0;

    const latestNav = navHistory.length > 0 ? navHistory[0].index_value : 0;
    const prevNav = navHistory.length > 1 ? navHistory[1].index_value : latestNav;
    const changePercent = prevNav !== 0 ? ((latestNav - prevNav) / prevNav * 100).toFixed(2) : "0.00";

    const calculateReturn = (days) => {
        if (navHistory.length < 2) return "0.00%";
        // navHistory is sorted by date DESC (latest first)
        const current = navHistory[0].index_value;
        const pastIndex = navHistory.length > days ? days : navHistory.length - 1;
        const past = navHistory[pastIndex].index_value;
        return `${(((current - past) / past) * 100).toFixed(2)}%`;
    };

    return (
        <div className="mf-detail container reveal active">
            <header className="detail-header-lux">
                <div className="back-nav-lux">
                    <button onClick={navigateBack} className="btn-back-elite">
                        <span className="back-icon">←</span>
                        <span className="back-text">RETURN TO MARKET REPOSITORY</span>
                    </button>
                </div>

                <div className="fund-hero-stack">
                    <span className="scheme-badge">MARKET INDEX</span>
                    <h1 className="heading-xl">{index.benchmark_name}</h1>
                    <p className="text-muted text-xs uppercase tracking-widest mt-2">{index.benchmark_code}</p>

                    <div className="price-performance-row">
                        <span className="price-val font-heading">₹{latestNav}</span>
                        <div className={`change-badge-elite ${parseFloat(changePercent) >= 0 ? 'positive' : 'negative'}`}>
                            {parseFloat(changePercent) >= 0 ? '▲' : '▼'} {Math.abs(changePercent)}%
                        </div>
                    </div>

                    <div className="flex justify-center gap-4 mt-10">
                        <button
                            className={`btn-premium btn-premium-refresh ${isSyncing ? 'loading' : ''}`}
                            onClick={() => dispatch(triggerIndexSync(benchmarkCode))}
                            disabled={isSyncing}
                        >
                            {isSyncing ? 'Syncing Market Stream...' : 'Sync Market Stream'}
                        </button>
                        <button className="btn-premium btn-premium-primary px-12">Monitor Integration</button>
                    </div>
                </div>
            </header>

            <div className="metrics-strip-lux">
                <div className="glass-panel metric-strip-item glow-card">
                    <span className="m-label">1Y Performance</span>
                    <div className="m-value font-heading text-primary">{calculateReturn(252)}</div>
                </div>
                <div className="glass-panel metric-strip-item glow-card">
                    <span className="m-label">3Y Performance</span>
                    <div className="m-value font-heading text-primary">{calculateReturn(756)}</div>
                </div>
                <div className="glass-panel metric-strip-item glow-card">
                    <span className="m-label">Volatility Delta</span>
                    <div className="m-value font-heading text-primary">HEALTHY</div>
                </div>
            </div>

            <div className="detail-grid-lux">
                <div className="glass-panel chart-box-lux glow-card">
                    <div className="chart-head-lux">
                        <h3 className="section-heading-lux uppercase">Performance Trajectory</h3>
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
                    
                    {!hasNavData ? (
                        <div className="flex flex-col items-center justify-center p-10 border border-white/5 bg-white/5 mx-6 mb-6" style={{ height: '450px' }}>
                            <div className="text-4xl mb-4 opacity-30">⚠️</div>
                            <h4 className="font-heading text-xl text-primary mb-2 uppercase tracking-widest">Metadata Sequence Offline</h4>
                            <p className="text-muted tracking-widest uppercase text-xs opacity-70">NAV historical data is not present in the core ledger.</p>
                        </div>
                    ) : (
                        <div style={{ height: '450px', width: '100%' }}>
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
                                        interval={Math.floor(chartData.length / 8)}
                                    />
                                    <YAxis 
                                        domain={['auto', 'auto']} 
                                        axisLine={false} 
                                        tickLine={false}
                                        tick={{fontSize: 10, fill: 'var(--color-text-muted)'}}
                                    />
                                    <Tooltip 
                                        contentStyle={{backgroundColor: '#0f172a', border: '1px solid var(--color-glass-border)', borderRadius: '8px', fontSize: '12px'}}
                                        itemStyle={{color: 'var(--color-primary)'}}
                                    />
                                    <Area 
                                        type="monotone" 
                                        dataKey="nav" 
                                        stroke="var(--color-primary)" 
                                        strokeWidth={3}
                                        fill="url(#navGradient)" 
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            </div>

            {/* Historical Data Management */}
            <section className="section-spacer">
                <div className="flex justify-between items-center mb-8">
                    <h3 className="section-heading-lux uppercase">Historical Intelligence Integration</h3>
                    <div className="flex items-center gap-4">
                        {uploadMsg && (
                            <span className={`text-xs uppercase tracking-widest ${uploadMsg.type === 'success' ? 'text-success' : 'text-error'}`}>
                                {uploadMsg.text}
                            </span>
                        )}
                        <label className={`btn-premium ${uploading ? 'opacity-50' : ''}`} style={{ cursor: uploading ? 'not-allowed' : 'pointer' }}>
                            {uploading ? 'PROCESSING...' : 'UPLOAD NIFTY CSV'}
                            <input 
                                type="file" 
                                accept=".csv" 
                                onChange={handleFileUpload} 
                                disabled={uploading}
                                style={{ display: 'none' }} 
                            />
                        </label>
                    </div>
                </div>
                <div className="glass-panel p-8 bg-primary/5 border-primary/10 text-center">
                    <p className="text-secondary text-xs uppercase tracking-widest opacity-60">
                        Drop high-density architectural CSV files here to recalibrate historical performance trends. 
                        Protocol requires columns: <span className="text-primary italic">"Date"</span> and <span className="text-primary italic">"Close"</span>.
                    </p>
                </div>
            </section>

            <section className="section-spacer">
                <h3 className="section-heading-lux uppercase mb-8">Asset Metadata & Identification</h3>
                <div className="glass-panel glow-card p-0 overflow-hidden">
                    <table className="metadata-table-lux">
                        <tbody>
                            <tr>
                                <td className="m-label">Index Identifier</td>
                                <td className="m-value">{index.benchmark_code}</td>
                            </tr>
                            <tr>
                                <td className="m-label">Ticker Symbol</td>
                                <td className="m-value">{index.ticker}</td>
                            </tr>
                            <tr>
                                <td className="m-label">Benchmark Type</td>
                                <td className="m-value">{index.benchmark_type}</td>
                            </tr>
                            <tr>
                                <td className="m-label">Asset Class</td>
                                <td className="m-value">{index.asset_class || 'EQUITY'}</td>
                            </tr>
                            <tr>
                                <td className="m-label">Strategic Importance</td>
                                <td className="m-value text-primary font-bold">PRIMARY BENCHMARK</td>
                            </tr>
                            <tr>
                                <td className="m-label">Monitoring Status</td>
                                <td className="m-value">
                                    <span style={{ color: 'var(--color-accent)' }}>HEALTHY INTEGRATION</span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
};

export default IndexDetail;
