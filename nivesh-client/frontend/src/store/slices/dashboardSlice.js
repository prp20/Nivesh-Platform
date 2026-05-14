import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import apiClient from '../../api/apiClient';

export const fetchDashboardData = createAsyncThunk(
    'dashboard/fetchData',
    async (_, { rejectWithValue }) => {
        try {
            // Fetch top funds to populate holdings and derive stats
            const fundsRes = await apiClient.get('/funds/?limit=5&is_active=true');
            const topFunds = fundsRes.data.items || [];

            let performanceHistory = [];
            let portfolioValue = 4280550; // Regional placeholder if no portfolio API
            
            if (topFunds.length > 0) {
                try {
                    // Use the first fund as a proxy for market movement
                    const proxyCode = topFunds[0].scheme_code;
                    const navRes = await apiClient.get(`/navs/${proxyCode}?limit=30`);
                    const navData = navRes.data || [];
                    
                    performanceHistory = navData.map(pt => ({
                        month: new Date(pt.nav_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                        value: parseFloat(pt.nav_value)
                    })).reverse();
                } catch (navErr) {
                    console.warn("NAV history fetch failed, using fallback points");
                }
            }

            // Derive holdings from real fund data
            const holdings = topFunds.map(fund => {
                const metrics = fund.metrics || {};
                return {
                    symbol: fund.scheme_code,
                    ticker: fund.isin || fund.scheme_code.split('-')[0],
                    name: fund.scheme_name,
                    allocation: fund.scheme_category,
                    value: metrics.current_nav ? `$${(parseFloat(metrics.current_nav) * 1000).toLocaleString()}` : '$124,000',
                    return: metrics.absolute_return_1y ? `${metrics.absolute_return_1y > 0 ? '+' : ''}${metrics.absolute_return_1y}%` : '+2.4%',
                    cap: metrics.aum_in_crores ? `${(metrics.aum_in_crores / 100).toFixed(1)}%` : '8.2%',
                    trend: metrics.absolute_return_1y >= 0 ? 'up' : 'down'
                };
            });

            return {
                momentum: 'BULLISH',
                growthPercent: 4.8,
                growthDriver: 'Algorithmic capital allocation in tech and private infrastructure assets',
                portfolioValue: portfolioValue,
                absoluteGain: 524190,
                liquidityReserve: 845000,
                
                performanceHistory: performanceHistory.length > 0 ? performanceHistory : [
                    { month: 'Jan 24', value: 10500 }, { month: 'Feb 24', value: 10800 },
                    { month: 'Mar 24', value: 10600 }, { month: 'Apr 24', value: 11100 },
                    { month: 'May 24', value: 11500 }
                ],
                
                assetAllocation: [
                    { name: 'Elite Equities', value: 65, color: 'bg-primary' },
                    { name: 'Private Assets', value: 20, color: 'bg-secondary' },
                    { name: 'Global Debt', value: 15, color: 'bg-slate-600' }
                ],

                holdings: holdings,

                activities: [
                    { id: 1, type: 'dividend', text: 'Commercial RE Fund VII distributed $124,000 in quarterly dividends.', date: '2 hours ago', icon: 'payments' },
                    { id: 2, type: 'transfer', text: 'Moved $450,000 from Cash Reserves to Global Tech Index.', date: '1 day ago', icon: 'sync' },
                    { id: 3, type: 'note', text: 'Alpha Strategy updated for FY25 Tax Optimization.', date: '3 days ago', icon: 'description' },
                ]
            };
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to load dashboard telemetry.');
        }
    }
);

const dashboardSlice = createSlice({
    name: 'dashboard',
    initialState: {
        data: null,
        loading: false,
        error: null,
    },
    reducers: {
        resetDashboard: (state) => {
            state.data = null;
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchDashboardData.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchDashboardData.fulfilled, (state, action) => {
                state.loading = false;
                state.data = action.payload;
            })
            .addCase(fetchDashboardData.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            });
    }
});

export const { resetDashboard } = dashboardSlice.actions;
export default dashboardSlice.reducer;
