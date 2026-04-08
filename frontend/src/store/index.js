import { configureStore } from '@reduxjs/toolkit';
import syncReducer from './slices/syncSlice';
import compareReducer from './slices/compareSlice';
import fundsReducer from './slices/fundsSlice';
import indicesReducer from './slices/indicesSlice';
import fundDetailReducer from './slices/fundDetailSlice';
import dashboardReducer from './slices/dashboardSlice';
import stocksReducer from './slices/stocksSlice';
import stockCompareReducer from './slices/stockCompareSlice';

export const store = configureStore({
  reducer: {
    sync: syncReducer,
    compare: compareReducer,
    funds: fundsReducer,
    indices: indicesReducer,
    fundDetail: fundDetailReducer,
    dashboard: dashboardReducer,
    stocks: stocksReducer,
    stockCompare: stockCompareReducer,
  },
});
