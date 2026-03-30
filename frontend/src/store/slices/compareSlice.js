import { createSlice } from '@reduxjs/toolkit';

/**
 * compareSlice — Global compare dock state.
 *
 * Holds the list of funds selected for comparison.
 * Lifting this from MFListing local state into Redux means:
 * - The dock persists across hash-based navigation.
 * - MFCompare can read the selections without relying solely on URL params.
 * - Clear / add / remove actions are dispatched from anywhere.
 */
const compareSlice = createSlice({
    name: 'compare',
    initialState: {
        compareList: [], // Array of { scheme_code, scheme_name, scheme_category, amc_name }
    },
    reducers: {
        addToCompare: (state, action) => {
            const fund = action.payload;
            const alreadyAdded = state.compareList.find(f => f.scheme_code === fund.scheme_code);
            if (alreadyAdded) return; // no-op: already in dock

            if (state.compareList.length >= 4) return; // max 4 funds

            // Enforce same-category rule
            if (
                state.compareList.length > 0 &&
                (state.compareList[0].scheme_category !== fund.scheme_category ||
                 state.compareList[0].scheme_subcategory !== fund.scheme_subcategory)
            ) {
                return; // silently reject — caller should show alert before dispatching
            }

            state.compareList.push(fund);
        },

        removeFromCompare: (state, action) => {
            const schemeCode = action.payload;
            state.compareList = state.compareList.filter(f => f.scheme_code !== schemeCode);
        },

        clearCompare: (state) => {
            state.compareList = [];
        },
    },
});

export const { addToCompare, removeFromCompare, clearCompare } = compareSlice.actions;
export default compareSlice.reducer;
