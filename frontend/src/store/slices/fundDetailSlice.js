import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

export const fetchFundDetail = createAsyncThunk(
    'fundDetail/fetchDetail',
    async (schemeCode, { rejectWithValue }) => {
        try {
            const [fundRes, navHistory, similarFunds] = await Promise.all([
                fundService.getFundDetail(schemeCode),
                fundService.getFundNavHistory(schemeCode, 1000), 
                fundService.getSimilarFunds(schemeCode).catch(() => [])
            ]);
            
            // The fund detail response itself contains the nested metrics according to the user's Postman output.
            const fund = fundRes;
            const metrics = fund.metrics || null;
            
            return {
                fund,
                navHistory: navHistory.map(pt => ({
                    date: pt.nav_date,
                    nav: parseFloat(pt.nav_value || pt.index_value)
                })).reverse(),
                metrics,
                similarFunds
            };
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Asset synchronization failed.');
        }
    }
);

export const syncFundMetrics = createAsyncThunk(
    'fundDetail/syncMetrics',
    async (schemeCode, { dispatch, rejectWithValue }) => {
        try {
            await fundService.syncFund(schemeCode);
            // Refresh detail after sync
            dispatch(fetchFundDetail(schemeCode));
            return schemeCode;
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Sync trigger failed.');
        }
    }
);

const fundDetailSlice = createSlice({
    name: 'fundDetail',
    initialState: {
        fund: null,
        navHistory: [],
        metrics: null,
        similarFunds: [],
        loading: false,
        error: null,
        syncing: false,
    },
    reducers: {
        clearDetail: (state) => {
            state.fund = null;
            state.navHistory = [];
            state.metrics = null;
            state.similarFunds = [];
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchFundDetail.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFundDetail.fulfilled, (state, action) => {
                state.loading = false;
                state.fund = action.payload.fund;
                state.navHistory = action.payload.navHistory;
                state.metrics = action.payload.metrics;
                state.similarFunds = action.payload.similarFunds;
            })
            .addCase(fetchFundDetail.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            .addCase(syncFundMetrics.pending, (state) => {
                state.syncing = true;
            })
            .addCase(syncFundMetrics.fulfilled, (state) => {
                state.syncing = false;
            })
            .addCase(syncFundMetrics.rejected, (state) => {
                state.syncing = false;
            });
    }
});

export const { clearDetail } = fundDetailSlice.actions;
export default fundDetailSlice.reducer;
