import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import stockService from '../../api/services/stockService';

export const fetchStockComparisonData = createAsyncThunk(
    'stockCompare/fetchStockComparisonData',
    async (symbols, { rejectWithValue }) => {
        try {
            const data = await stockService.getCompare(symbols);
            return data;
        } catch (err) {
            return rejectWithValue(err.response?.data || 'Failed to initialize stock comparison matrix.');
        }
    }
);

const stockCompareSlice = createSlice({
    name: 'stockCompare',
    initialState: {
        compareList: [],                // Selected stocks (max 4)
        comparisonResult: null,         // Full API response
        comparisonLoading: false,
        comparisonError: null,
    },
    reducers: {
        addStockToCompare: (state, action) => {
            const stock = action.payload;
            const alreadyAdded = state.compareList.find(s => s.symbol === stock.symbol);
            if (alreadyAdded) return;

            if (state.compareList.length >= 4) return;
            state.compareList.push(stock);
        },

        removeStockFromCompare: (state, action) => {
            const symbol = action.payload;
            state.compareList = state.compareList.filter(s => s.symbol !== symbol);
            if (state.compareList.length === 0) {
                state.comparisonResult = null;
            }
        },

        clearStockCompare: (state) => {
            state.compareList = [];
            state.comparisonResult = null;
            state.comparisonError = null;
        },

        clearStockComparisonResult: (state) => {
            state.comparisonResult = null;
            state.comparisonError = null;
        }
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchStockComparisonData.pending, (state) => {
                state.comparisonLoading = true;
                state.comparisonError = null;
            })
            .addCase(fetchStockComparisonData.fulfilled, (state, action) => {
                state.comparisonLoading = false;
                state.comparisonResult = action.payload;
            })
            .addCase(fetchStockComparisonData.rejected, (state, action) => {
                state.comparisonLoading = false;
                state.comparisonError = action.payload;
            });
    }
});

export const { 
    addStockToCompare, 
    removeStockFromCompare, 
    clearStockCompare, 
    clearStockComparisonResult
} = stockCompareSlice.actions;

export default stockCompareSlice.reducer;
