import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

export const fetchFundDetail = createAsyncThunk(
    'fundDetail/fetchDetail',
    async (schemeCode, { rejectWithValue }) => {
        try {
            const [fund, navHistory, metrics, similarFunds] = await Promise.all([
                fundService.getFundDetail(schemeCode),
                fundService.getFundNavHistory(schemeCode, 2000), // Fetch more for better charts
                fundService.getFundMetrics(schemeCode).catch(() => ({ metrics: null })),
                fundService.getSimilarFunds(schemeCode).catch(() => [])
            ]);
            
            return {
                fund,
                navHistory,
                metrics: metrics.metrics,
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
            // Polling is normally handled in the component or a middleware, 
            // but we'll just return the intent here.
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
