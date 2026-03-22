import { configureStore } from '@reduxjs/toolkit';
import syncReducer from './slices/syncSlice';

export const store = configureStore({
  reducer: {
    sync: syncReducer,
  },
});
