import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

export const fetchFunds = createAsyncThunk(
    'funds/fetchFunds',
    async ({ skip, limit, category, subcategory, amc, plan_type, order_by }, { rejectWithValue }) => {
        try {
            const data = await fundService.getFunds(skip, limit, category, amc, subcategory, plan_type, order_by);
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
        currentPage: 1,
        pageSize: 10,
        categoryFilter: 'All',
        subcategoryFilter: '',
        amcSearch: '',
        planTypeFilter: '',
        sortBy: 'scheme_name',
        viewMode: 'card', // 'card' or 'table'
    },
    reducers: {
        setCurrentPage: (state, action) => { state.currentPage = action.payload; },
        setPageSize: (state, action) => { state.pageSize = action.payload; state.currentPage = 1; },
        setCategoryFilter: (state, action) => { state.categoryFilter = action.payload; state.currentPage = 1; },
        setSubcategoryFilter: (state, action) => { state.subcategoryFilter = action.payload; state.currentPage = 1; },
        setAmcSearch: (state, action) => { state.amcSearch = action.payload; state.currentPage = 1; },
        setPlanTypeFilter: (state, action) => { state.planTypeFilter = action.payload; state.currentPage = 1; },
        setSortBy: (state, action) => { state.sortBy = action.payload; state.currentPage = 1; },
        setViewMode: (state, action) => { state.viewMode = action.payload; },
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
                state.items = action.payload.items.map(fund => ({
                    ...fund,
                    displayMetrics: {
                        aum: fund.metrics?.aum_in_crores ? `${fund.metrics.aum_in_crores.toLocaleString()} Cr` : 'N/A',
                        nav: fund.metrics?.current_nav ? fund.metrics.current_nav.toFixed(2).toLocaleString() : '0.00',
                        change: fund.metrics?.absolute_return_1y ? `${fund.metrics.absolute_return_1y > 0 ? '+' : ''}${fund.metrics.absolute_return_1y}%` : '0.0%',
                        rating: fund.metrics?.fund_rating || 0
                    }
                }));
                state.total = action.payload.total;
            })
            .addCase(fetchFunds.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || 'Connectivity error. Security protocol engaged.';
            });
    },
});

export const { 
    setCurrentPage, 
    setPageSize, 
    setCategoryFilter, 
    setSubcategoryFilter,
    setAmcSearch, 
    setPlanTypeFilter,
    setSortBy,
    setViewMode,
    clearError 
} = fundsSlice.actions;
export default fundsSlice.reducer;
