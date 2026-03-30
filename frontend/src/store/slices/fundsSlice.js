import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

/**
 * fundsSlice — Redux state for the MFListing page.
 *
 * Moves funds list, pagination, and filter state into Redux so that:
 * - Data fetched on first load is cached; navigating back to the list does not re-fetch.
 * - Pagination / filter state persists across back navigation.
 */

export const fetchFunds = createAsyncThunk(
    'funds/fetchFunds',
    async ({ skip, limit, category, amc }, { rejectWithValue }) => {
        try {
            const data = await fundService.getFunds(skip, limit, category, amc);
            return data; // { items, total, skip, limit }
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to fetch funds');
        }
    }
);

const fundsSlice = createSlice({
    name: 'funds',
    initialState: {
        items: [],
        total: 0,
        loading: false,
        error: null,
        // Persist filter & pagination state
        currentPage: 1,
        pageSize: 10,
        categoryFilter: 'All',
        amcSearch: '',
    },
    reducers: {
        setCurrentPage: (state, action) => { state.currentPage = action.payload; },
        setPageSize: (state, action) => { state.pageSize = action.payload; state.currentPage = 1; },
        setCategoryFilter: (state, action) => { state.categoryFilter = action.payload; state.currentPage = 1; },
        setAmcSearch: (state, action) => { state.amcSearch = action.payload; state.currentPage = 1; },
        clearError: (state) => { state.error = null; },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchFunds.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFunds.fulfilled, (state, action) => {
                state.loading = false;
                state.items = action.payload.items;
                state.total = action.payload.total;
            })
            .addCase(fetchFunds.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Connectivity error. Security protocol engaged.';
            });
    },
});

export const { setCurrentPage, setPageSize, setCategoryFilter, setAmcSearch, clearError } = fundsSlice.actions;
export default fundsSlice.reducer;
