import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

export const triggerSync = createAsyncThunk(
  'sync/triggerSync',
  async (schemeCode, { rejectWithValue }) => {
    try {
      const response = await fundService.computeMetrics(schemeCode);
      return { schemeCode, ...response };
    } catch (err) {
      return rejectWithValue(err.response?.data || 'Failed to trigger sync');
    }
  }
);

export const fetchSyncStatus = createAsyncThunk(
  'sync/fetchSyncStatus',
  async (schemeCode, { rejectWithValue }) => {
    try {
      const response = await fundService.getSyncStatus(schemeCode);
      return { schemeCode, ...response };
    } catch (err) {
      // If 404, might mean no job exists yet, which is fine
      if (err.response?.status === 404) {
        return { schemeCode, status: 'IDLE' };
      }
      return rejectWithValue(err.response?.data || 'Failed to fetch status');
    }
  }
);

export const triggerGlobalSync = createAsyncThunk(
  'sync/triggerGlobalSync',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fundService.syncAllFunds();
      return response;
    } catch (err) {
      return rejectWithValue(err.response?.data || 'Failed to trigger global sync');
    }
  }
);

const syncSlice = createSlice({
  name: 'sync',
  initialState: {
    jobs: {}, // schemeCode -> { status, message, job_id, error }
    globalSync: { status: 'IDLE', message: null }
  },
  reducers: {
    clearJob: (state, action) => {
      delete state.jobs[action.payload];
    },
    clearGlobalSync: (state) => {
      state.globalSync = { status: 'IDLE', message: null };
    }
  },
  extraReducers: (builder) => {
    builder
      // Trigger Sync
      .addCase(triggerSync.pending, (state, action) => {
        const schemeCode = action.meta.arg;
        state.jobs[schemeCode] = { 
          ...state.jobs[schemeCode], 
          status: 'RUNNING', 
          message: 'Initializing sync...' 
        };
      })
      .addCase(triggerSync.fulfilled, (state, action) => {
        const { schemeCode, job_id, sync_status, sync_message } = action.payload;
        state.jobs[schemeCode] = { 
          status: sync_status || 'RUNNING', 
          message: sync_message || 'Sync started...', 
          job_id 
        };
      })
      .addCase(triggerSync.rejected, (state, action) => {
        const schemeCode = action.meta.arg;
        state.jobs[schemeCode] = { 
          status: 'FAILED', 
          error: action.payload 
        };
      })
      // Fetch Status
      .addCase(fetchSyncStatus.fulfilled, (state, action) => {
        const { schemeCode, status, message, id } = action.payload;
        state.jobs[schemeCode] = { 
          status, 
          message, 
          job_id: id 
        };
      })
      // Global Sync
      .addCase(triggerGlobalSync.pending, (state) => {
        state.globalSync = { status: 'RUNNING', message: 'Initiating bulk synchronization...' };
      })
      .addCase(triggerGlobalSync.fulfilled, (state) => {
        state.globalSync = { status: 'COMPLETED', message: 'Bulk synchronization started successfully.' };
      })
      .addCase(triggerGlobalSync.rejected, (state, action) => {
        state.globalSync = { status: 'FAILED', message: action.payload };
      });
  }
});

export const { clearJob, clearGlobalSync } = syncSlice.actions;
export default syncSlice.reducer;
