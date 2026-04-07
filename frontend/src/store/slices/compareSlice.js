import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

/**
 * Async Thunks
 */
export const fetchComparisonData = createAsyncThunk(
    'compare/fetchComparisonData',
    async (codes, { rejectWithValue }) => {
        try {
            const data = await fundService.compareFunds(codes);
            return data;
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to initialize comparison matrix.');
        }
    }
);

export const fetchCategories = createAsyncThunk(
    'compare/fetchCategories',
    async (_, { rejectWithValue }) => {
        try {
            const data = await fundService.getCategories();
            return data;
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to fetch asset categories.');
        }
    }
);

export const fetchFundsByCategory = createAsyncThunk(
    'compare/fetchFundsByCategory',
    async ({ category, limit = 100 }, { rejectWithValue }) => {
        try {
            const data = await fundService.getFunds(0, limit, category);
            return data.items || [];
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to fetch funds for picker.');
        }
    }
);

/**
 * compareSlice — Global compare dock state.
 */
const compareSlice = createSlice({
    name: 'compare',
    initialState: {
        compareList: [],                // Selected funds (max 4)
        selectedCategory: null,         // Category lock
        selectedSubcategory: null,      // Subcategory lock
        comparisonResult: null,         // Full API response { funds, ranking, warning }
        categories: [],                 // All available categories
        categoriesLoading: false,
        categoryFunds: [],              // Funds in selected category (for picker)
        categoryFundsLoading: false,
        comparisonLoading: false,
        comparisonError: null,
    },
    reducers: {
        addToCompare: (state, action) => {
            const fund = action.payload;
            const alreadyAdded = state.compareList.find(f => f.scheme_code === fund.scheme_code);
            if (alreadyAdded) return;

            if (state.compareList.length >= 4) return;

            // Enforce same-category + same-subcategory rule
            if (state.compareList.length > 0) {
                if (
                    state.compareList[0].scheme_category !== fund.scheme_category ||
                    state.compareList[0].scheme_subcategory !== fund.scheme_subcategory
                ) {
                    return; // Rejected
                }
            } else {
                // Set locks on first addition
                state.selectedCategory = fund.scheme_category;
                state.selectedSubcategory = fund.scheme_subcategory;
            }

            state.compareList.push(fund);
        },

        removeFromCompare: (state, action) => {
            const schemeCode = action.payload;
            state.compareList = state.compareList.filter(f => f.scheme_code !== schemeCode);
            if (state.compareList.length === 0) {
                state.selectedCategory = null;
                state.selectedSubcategory = null;
                state.comparisonResult = null;
            }
        },

        clearCompare: (state) => {
            state.compareList = [];
            state.selectedCategory = null;
            state.selectedSubcategory = null;
            state.comparisonResult = null;
            state.comparisonError = null;
        },

        setSelectedCategory: (state, action) => {
            state.selectedCategory = action.payload;
        },

        clearComparisonResult: (state) => {
            state.comparisonResult = null;
            state.comparisonError = null;
        }
    },
    extraReducers: (builder) => {
        builder
            // Fetch Comparison Data
            .addCase(fetchComparisonData.pending, (state) => {
                state.comparisonLoading = true;
                state.comparisonError = null;
            })
            .addCase(fetchComparisonData.fulfilled, (state, action) => {
                state.comparisonLoading = false;
                state.comparisonResult = action.payload;
            })
            .addCase(fetchComparisonData.rejected, (state, action) => {
                state.comparisonLoading = false;
                state.comparisonError = action.payload;
            })
            // Fetch Categories
            .addCase(fetchCategories.pending, (state) => {
                state.categoriesLoading = true;
            })
            .addCase(fetchCategories.fulfilled, (state, action) => {
                state.categoriesLoading = false;
                state.categories = action.payload;
            })
            .addCase(fetchCategories.rejected, (state) => {
                state.categoriesLoading = false;
            })
            // Fetch Funds By Category
            .addCase(fetchFundsByCategory.pending, (state) => {
                state.categoryFundsLoading = true;
            })
            .addCase(fetchFundsByCategory.fulfilled, (state, action) => {
                state.categoryFundsLoading = false;
                state.categoryFunds = action.payload;
            })
            .addCase(fetchFundsByCategory.rejected, (state) => {
                state.categoryFundsLoading = false;
            });
    }
});

export const { 
    addToCompare, 
    removeFromCompare, 
    clearCompare, 
    setSelectedCategory,
    clearComparisonResult
} = compareSlice.actions;
export default compareSlice.reducer;
