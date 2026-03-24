import React, { useState, useEffect, useMemo } from 'react';
import fundService from '../api/services/fundService';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import './MFDetail.css';

const MFCompare = () => {
    // Read from URL: #compare?a=CODE1&b=CODE2
    const params = new URLSearchParams(window.location.hash.split('?')[1]);
    const fundA_Code = params.get('a');
    const fundB_Code = params.get('b');
    
    // Data state
    const [comparing, setComparing] = useState(true);
    const [error, setError] = useState(null);
    
    // Comparison results
    const [dataA, setDataA] = useState(null);
    const [dataB, setDataB] = useState(null);

    useEffect(() => {
        if (!fundA_Code || !fundB_Code) {
            setComparing(false);
            return;
        }

        const fetchCompare = async () => {
            try {
                const data = await fundService.compareFunds(fundA_Code, fundB_Code);
                setDataA(data.fund_a);
                setDataB(data.fund_b);
            } catch (err) {
                console.error("Comparison data fetch failed", err);
                setError("Failed to compile crossover metrics or verify asset identities.");
            } finally {
                setComparing(false);
            }
        };
        fetchCompare();
    }, [fundA_Code, fundB_Code]);


    const formatMetric = (val, precision = 2) => {
        if (val === null || val === undefined) return '--';
        return Number(val).toFixed(precision);
    };

    const formatPercent = (val) => {
        if (val === null || val === undefined) return '--';
        return `${(Number(val) * 100).toFixed(2)}%`;
    };

    // Prepare unified chart data
    const chartData = useMemo(() => {
        if (!dataA || !dataB) return [];
        const dateMap = {};
        
        const addToMap = (history, key, valKey = 'nav_value') => {
            history.forEach(item => {
                const dateRaw = valKey === 'nav_value' ? item.nav_date : item.nav_date;
                const date = new Date(dateRaw).toISOString().split('T')[0];
                if (!dateMap[date]) dateMap[date] = { dateRaw };
                dateMap[date][key] = parseFloat(item[valKey] || item.index_value);
            });
        };

        if (dataA.history) addToMap(dataA.history, 'FundA', 'nav_value');
        if (dataB.history) addToMap(dataB.history, 'FundB', 'nav_value');
        if (dataA.benchHistory?.length) addToMap(dataA.benchHistory, 'BenchA', 'index_value');
        if (dataB.benchHistory?.length && dataA.detail.benchmark_index_code !== dataB.detail.benchmark_index_code) {
            addToMap(dataB.benchHistory, 'BenchB', 'index_value');
        }

        const sortedDates = Object.keys(dateMap).sort();
        return sortedDates.map(d_str => {
            const row = dateMap[d_str];
            const result = {
                date: new Date(row.dateRaw).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
            };
            if (row.FundA) result.FundA = row.FundA;
            if (row.FundB) result.FundB = row.FundB;
            if (row.BenchA) result.BenchA = row.BenchA;
            if (row.BenchB) result.BenchB = row.BenchB;
            return result;
        });
    }, [dataA, dataB]);

    if (!fundA_Code || !fundB_Code) {
        return (
            <div className="container p-20 text-center font-heading uppercase tracking-widest text-muted mt-20 flex flex-col items-center gap-6">
                <h2 className="text-xl text-primary">No Assets Selected</h2>
                <p className="max-w-md mx-auto">Please select two assets from the Vault to initiate comparison protocols.</p>
                <a href="#mf" className="btn-premium btn-premium-primary py-2 px-8 mt-2 inline-block">RETURN TO VAULT</a>
            </div>
        );
    }

    if (comparing) return <div className="loading-container p-20 text-center font-heading uppercase tracking-widest mt-20">Compiling Intelligence...</div>;

    if (error) {
        return (
            <div className="container p-20 text-center font-heading tracking-widest text-error mt-20">
                <h2 className="text-xl mb-4 uppercase">Verification Error</h2>
                <p className="mb-8 font-sans">{error}</p>
                <a href="#mf" className="btn-premium btn-premium-outline py-2 px-8">Return to Vault</a>
            </div>
        );
    }

    const ComparisonCard = ({ title, valA, valB, isBetter = () => null }) => {
        const better = isBetter(valA, valB);
        return (
            <div className="glass-panel metric-box glow-card flex justify-between items-center px-6 py-4">
                <div className="w-1/3 text-left font-heading text-lg" style={{ color: better === 'A' ? 'var(--color-success)' : 'white'}}>{valA}</div>
                <div className="w-1/3 text-center metric-label">{title}</div>
                <div className="w-1/3 text-right font-heading text-lg" style={{ color: better === 'B' ? 'var(--color-success)' : 'white'}}>{valB}</div>
            </div>
        );
    };

    return (
        <div className="mf-detail container reveal active">
            <header className="detail-header-lux">
                <div className="fund-hero-stack">
                    <span className="scheme-badge">COMPARATIVE ANALYSIS</span>
                    <h1 className="heading-xl">Fund vs Fund</h1>
                </div>
            </header>

            {dataA && dataB && (
                <>
                    <div className="detail-grid-lux mt-10">
                        <div className="glass-panel chart-box-lux glow-card">
                            <div className="chart-head-lux mb-5">
                                <h3 className="section-heading-lux uppercase">Relative Trajectory</h3>
                            </div>
                            
                            <div style={{ height: '400px', width: '100%' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fontSize: 10, fill: 'var(--color-text-muted)'}} />
                                        <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{fontSize: 10, fill: 'var(--color-text-muted)'}} />
                                        <Tooltip 
                                            contentStyle={{backgroundColor: '#0f172a', border: '1px solid var(--color-glass-border)', borderRadius: '8px', fontSize: '12px'}}
                                        />
                                        <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '20px' }} />
                                        <Line type="monotone" name={dataA.detail.scheme_name} dataKey="FundA" stroke="#3b82f6" strokeWidth={3} dot={false} />
                                        <Line type="monotone" name={dataB.detail.scheme_name} dataKey="FundB" stroke="#f43f5e" strokeWidth={3} dot={false} />
                                        {dataA.detail.benchmark_index_code && (
                                            <Line type="monotone" name={`${dataA.detail.benchmark_index_code} (Index)`} dataKey="BenchA" stroke="#10b981" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                                        )}
                                        {dataB.detail.benchmark_index_code && dataA.detail.benchmark_index_code !== dataB.detail.benchmark_index_code && (
                                            <Line type="monotone" name={`${dataB.detail.benchmark_index_code} (Index)`} dataKey="BenchB" stroke="#f59e0b" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                                        )}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>

                    <section className="section-spacer">
                        <h3 className="section-heading-lux uppercase mb-8 text-center">Head-to-Head Metrics</h3>
                        
                        <div className="flex flex-col gap-4 max-w-4xl mx-auto">
                            <div className="flex justify-between px-6 mb-2 mt-4 items-center">
                                <div className="w-5/12 text-left">
                                    <span className="font-heading text-primary text-xl truncate tracking-tight">{dataA.detail.scheme_name}</span>
                                    <p className="text-muted uppercase tracking-widest text-[10px] mt-1">{dataA.detail.scheme_category}</p>
                                </div>
                                <div className="w-2/12 text-center text-muted uppercase tracking-widest text-xs opacity-50">Versus</div>
                                <div className="w-5/12 text-right">
                                    <span className="font-heading text-error text-xl truncate tracking-tight">{dataB.detail.scheme_name}</span>
                                    <p className="text-muted uppercase tracking-widest text-[10px] mt-1">{dataB.detail.scheme_category}</p>
                                </div>
                            </div>

                            <ComparisonCard 
                                title="3Y Rolling Return" 
                                valA={formatPercent(dataA.metrics?.rolling_return_3year)} 
                                valB={formatPercent(dataB.metrics?.rolling_return_3year)}
                                isBetter={(a,b) => parseFloat(a) > parseFloat(b) ? 'A' : (parseFloat(b) > parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="5Y Rolling Return" 
                                valA={formatPercent(dataA.metrics?.rolling_return_5year)} 
                                valB={formatPercent(dataB.metrics?.rolling_return_5year)}
                                isBetter={(a,b) => parseFloat(a) > parseFloat(b) ? 'A' : (parseFloat(b) > parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="Sharpe Ratio" 
                                valA={formatMetric(dataA.metrics?.sharpe_ratio)} 
                                valB={formatMetric(dataB.metrics?.sharpe_ratio)}
                                isBetter={(a,b) => parseFloat(a) > parseFloat(b) ? 'A' : (parseFloat(b) > parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="Sortino Ratio" 
                                valA={formatMetric(dataA.metrics?.sortino_ratio)} 
                                valB={formatMetric(dataB.metrics?.sortino_ratio)}
                                isBetter={(a,b) => parseFloat(a) > parseFloat(b) ? 'A' : (parseFloat(b) > parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="Alpha" 
                                valA={formatMetric(dataA.metrics?.alpha)} 
                                valB={formatMetric(dataB.metrics?.alpha)}
                                isBetter={(a,b) => parseFloat(a) > parseFloat(b) ? 'A' : (parseFloat(b) > parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="Beta" 
                                valA={formatMetric(dataA.metrics?.beta)} 
                                valB={formatMetric(dataB.metrics?.beta)}
                            />
                            <ComparisonCard 
                                title="Standard Deviation (Vol.)" 
                                valA={formatMetric(dataA.metrics?.standard_deviation)} 
                                valB={formatMetric(dataB.metrics?.standard_deviation)}
                                isBetter={(a,b) => parseFloat(a) < parseFloat(b) ? 'A' : (parseFloat(b) < parseFloat(a) ? 'B' : null)}
                            />
                            <ComparisonCard 
                                title="AUM (Cr)" 
                                valA={`₹${formatMetric(dataA.metrics?.aum_in_crores, 1)}`} 
                                valB={`₹${formatMetric(dataB.metrics?.aum_in_crores, 1)}`}
                            />
                        </div>
                    </section>
                </>
            )}
        </div>
    );
};

export default MFCompare;
