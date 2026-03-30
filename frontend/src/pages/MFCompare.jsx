import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import fundService from '../api/services/fundService';
import './MFDetail.css';

const MFCompare = () => {
    const reduxCompareList = useSelector(state => state.compare.compareList);

    const parseCodesFromHash = () => {
        const hashParams = window.location.hash.split('?')[1];
        if (!hashParams) return [];
        const codeParam = new URLSearchParams(hashParams).get('codes');
        return codeParam ? codeParam.split(',').filter(c => c.trim()) : [];
    };

    const [schemeCodes, setSchemeCodes] = useState(() => {
        const urlCodes = parseCodesFromHash();
        return urlCodes.length > 0 ? urlCodes : reduxCompareList.map(f => f.scheme_code);
    });

    useEffect(() => {
        const onHashChange = () => {
            const urlCodes = parseCodesFromHash();
            if (urlCodes.length > 0) {
                setSchemeCodes(urlCodes);
            }
        };
        window.addEventListener('hashchange', onHashChange);
        return () => window.removeEventListener('hashchange', onHashChange);
    }, []);

    useEffect(() => {
        if (parseCodesFromHash().length === 0) {
            setSchemeCodes(reduxCompareList.map(f => f.scheme_code));
        }
    }, [reduxCompareList]);

    const [comparing, setComparing] = useState(true);
    const [error, setError] = useState(null);
    const [fundsData, setFundsData] = useState([]);

    useEffect(() => {
        if (schemeCodes.length < 2) {
            setComparing(false);
            return;
        }

        const fetchCompare = async () => {
            try {
                setComparing(true);
                const data = await fundService.compareFunds(schemeCodes);
                // The API now returns { funds: [...], metrics_comparison: {} }
                setFundsData(data.funds || []);
            } catch (err) {
                console.error("Comparison data fetch failed", err);
                setError(err.response?.data?.detail || "Failed to compile crossover metrics.");
            } finally {
                setComparing(false);
            }
        };
        fetchCompare();
    }, [schemeCodes]);

    const formatMetric = (val, precision = 2) => {
        if (val === null || val === undefined) return '--';
        return Number(val).toFixed(precision);
    };

    const formatPercent = (val) => {
        if (val === null || val === undefined) return '--';
        return `${(Number(val) * 100).toFixed(2)}%`;
    };

    if (schemeCodes.length < 2) {
        return (
            <div className="container p-20 text-center font-heading uppercase tracking-widest text-muted mt-20 flex flex-col items-center gap-6">
                <h2 className="text-xl text-primary">Insufficient Assets</h2>
                <p className="max-w-md mx-auto">Please select at least two assets of the same category to initiate comparison protocols.</p>
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

    const ComparisonTable = () => {
        const categories = [
            {
                label: "Performance Overview",
                metrics: [
                    { key: 'current_nav', label: 'Latest NAV', prefix: '₹' },
                    { key: 'aum_in_crores', label: 'AUM (Cr)', precision: 1 },
                    { key: 'rolling_return_3year', label: '3Y Rolling Return', isPercent: true },
                    { key: 'rolling_return_5year', label: '5Y Rolling Return', isPercent: true },
                    { key: 'absolute_return_1y', label: '1Y Abs Return', isPercent: true },
                    { key: 'short_term_return_6m', label: '6M Return', isPercent: true },
                ]
            },
            {
                label: "Risk & Volatility",
                metrics: [
                    { key: 'sharpe_ratio', label: 'Sharpe Ratio' },
                    { key: 'sortino_ratio', label: 'Sortino Ratio' },
                    { key: 'standard_deviation', label: 'Std Deviation (Vol)', higherIsBetter: false },
                    { key: 'maximum_drawdown', label: 'Max Drawdown', isPercent: true, higherIsBetter: true },
                    { key: 'beta', label: 'Beta (Market Correlation)', higherIsBetter: false },
                ]
            },
            {
                label: "Relative Efficiency",
                metrics: [
                    { key: 'alpha', label: 'Alpha (Excess Return)' },
                    { key: 'tracking_error', label: 'Tracking Error', higherIsBetter: false },
                    { key: 'information_ratio', label: 'Information Ratio' },
                    { key: 'upside_capture', label: 'Upside Capture' },
                    { key: 'downside_capture', label: 'Downside Capture', higherIsBetter: false },
                ]
            }
        ];

        return (
            <div className="compare-table-container">
                <table className="compare-table-elite">
                    <thead>
                        <tr>
                            <th className="metric-col">Metric</th>
                            {fundsData.map((fund, idx) => {
                                const fundInfo = reduxCompareList.find(c => c.scheme_code === fund.scheme_code);
                                return (
                                    <th key={idx} className="fund-col">
                                        <div className="compare-fund-header">
                                            <div className="compare-fund-name" title={fundInfo?.scheme_name || `Fund ${fund.scheme_code}`}>
                                                {fundInfo?.scheme_name || `Fund ${fund.scheme_code}`}
                                            </div>
                                            <div className="compare-fund-amc">
                                                {fundInfo?.amc_name || 'Asset Vault'}
                                            </div>
                                        </div>
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {categories.map((cat, catIdx) => (
                            <React.Fragment key={catIdx}>
                                <tr className="category-row">
                                    <td colSpan={fundsData.length + 1}>
                                        {cat.label}
                                    </td>
                                </tr>
                                {cat.metrics.map((m, mIdx) => {
                                    const values = fundsData.map(f => f.metrics?.[m.key]);
                                    const numericValues = values.filter(v => v !== null && v !== undefined).map(v => Number(v));
                                    const bestValue = numericValues.length ? (m.higherIsBetter === false ? Math.min(...numericValues) : Math.max(...numericValues)) : null;

                                    return (
                                        <tr key={mIdx}>
                                            <td className="metric-col">{m.label}</td>
                                            {values.map((v, vIdx) => {
                                                const isBest = v !== null && v !== undefined && Number(v) === bestValue && numericValues.length > 1;
                                                return (
                                                    <td key={vIdx} className={`fund-col ${isBest ? 'elite-highlight' : ''}`}>
                                                        <span className="compare-val-numeric">
                                                            {m.prefix || ''}{m.isPercent ? formatPercent(v) : formatMetric(v, m.precision || 2)}
                                                        </span>
                                                        {isBest && <span className="elite-badge">ELITE</span>}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    );
                                })}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="mf-detail container reveal active">
            <header className="detail-header-lux">
                <div className="fund-hero-stack">
                    <span className="scheme-badge">COMPARATIVE ANALYSIS ({fundsData.length} ASSETS)</span>
                    <h1 className="heading-xl">Multi-Fund Intelligence</h1>
                    <p className="max-w-2xl mx-auto text-muted text-sm mt-4 leading-relaxed">
                        Side-by-side performance audit and risk-coefficient verification for selected vault assets.
                        Star indicators (★) highlight superior statistical outcomes in the current category.
                    </p>
                </div>
            </header>

            {fundsData.length > 0 ? (
                <section className="section-spacer mt-12">
                    <ComparisonTable />
                    <br />
                    <div className="compare-actions">
                        <a href="#mf" className="btn-premium btn-premium-outline px-10">MODIFY VAULT SELECTION</a>
                        <button className="btn-premium btn-premium-primary px-12">EXPORT AUDIT REPORT</button>
                    </div>
                </section>
            ) : (
                <div className="text-center p-20 opacity-40 uppercase tracking-widest text-xs">
                    Executing data alignment...
                </div>
            )}
        </div>
    );
};

export default MFCompare;

