import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

export const fetchIndices = createAsyncThunk(
    'indices/fetchIndices',
    async ({ skip, limit, search }, { rejectWithValue }) => {
        try {
            const data = await fundService.getBenchmarks(skip, limit, search);
            return data; // { items, total }
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to fetch indices');
        }
    }
);

export const fetchIndexDetail = createAsyncThunk(
    'indices/fetchDetail',
    async (benchmarkCode, { rejectWithValue }) => {
        try {
            const [detail, history] = await Promise.all([
                fundService.getBenchmarkDetail(benchmarkCode),
                fundService.getBenchmarkNavHistory(benchmarkCode, 2000)
            ]);
            return {
                detail,
                history: history.map(pt => ({
                    date: pt.nav_date,
                    value: parseFloat(pt.index_value)
                })).reverse()
            };
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Benchmark synchronization failed.');
        }
    }
);

const indicesSlice = createSlice({
    name: 'indices',
    initialState: {
        items: [],
        total: 0,
        currentDetail: null,
        navHistory: [],
        loading: false,
        detailLoading: false,
        error: null,
        detailError: null,
        currentPage: 1,
        pageSize: 10,
        searchQuery: '',
    },
    reducers: {
        setCurrentPage: (state, action) => { state.currentPage = action.payload; },
        setPageSize: (state, action) => { state.pageSize = action.payload; state.currentPage = 1; },
        setSearchQuery: (state, action) => { state.searchQuery = action.payload; state.currentPage = 1; },
        clearDetail: (state) => {
            state.currentDetail = null;
            state.navHistory = [];
            state.detailError = null;
        },
        clearError: (state) => { state.error = null; },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchIndices.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchIndices.fulfilled, (state, action) => {
                state.loading = false;
                state.items = action.payload.items.map(idx => ({
                    ...idx,
                    displayMetrics: {
                        nav: idx.metrics?.current_nav ? idx.metrics.current_nav.toLocaleString() : '0.00',
                        change: idx.metrics?.cagr_1year ? `${idx.metrics.cagr_1year > 0 ? '+' : ''}${idx.metrics.cagr_1year}%` : '+0.0%',
                        status: idx.is_active ? 'ACTIVE' : 'OFFLINE'
                    }
                }));
                state.total = action.payload.total;
            })
            .addCase(fetchIndices.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Market monitoring feeds currently unavailable.';
            })
            .addCase(fetchIndexDetail.pending, (state) => {
                state.detailLoading = true;
                state.detailError = null;
            })
            .addCase(fetchIndexDetail.fulfilled, (state, action) => {
                state.detailLoading = false;
                state.currentDetail = action.payload.detail;
                state.navHistory = action.payload.history;
            })
            .addCase(fetchIndexDetail.rejected, (state, action) => {
                state.detailLoading = false;
                state.detailError = action.payload;
            });
    },
});

export const { setCurrentPage, setPageSize, setSearchQuery, clearError, clearDetail } = indicesSlice.actions;
export default indicesSlice.reducer;
