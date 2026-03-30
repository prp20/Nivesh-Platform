import { configureStore } from '@reduxjs/toolkit';
import syncReducer from './slices/syncSlice';
import compareReducer from './slices/compareSlice';
import fundsReducer from './slices/fundsSlice';
import indicesReducer from './slices/indicesSlice';

export const store = configureStore({
  reducer: {
    sync: syncReducer,
    compare: compareReducer,
    funds: fundsReducer,
    indices: indicesReducer,
  },
});
