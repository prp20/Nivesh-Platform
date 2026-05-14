import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import fundService from '../../api/services/fundService';

// ─── Fund-level sync ────────────────────────────────────────────────────────

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

// ─── Index-level sync ───────────────────────────────────────────────────────

export const triggerIndexSync = createAsyncThunk(
  'sync/triggerIndexSync',
  async (benchmarkCode, { rejectWithValue }) => {
    try {
      const response = await fundService.syncFund(benchmarkCode); // reuse the generic sync endpoint
      return { benchmarkCode, ...response };
    } catch (err) {
      return rejectWithValue(err.response?.data || 'Failed to trigger index sync');
    }
  }
);

export const fetchIndexSyncStatus = createAsyncThunk(
  'sync/fetchIndexSyncStatus',
  async (benchmarkCode, { rejectWithValue }) => {
    try {
      const response = await fundService.getSyncStatus(benchmarkCode);
      return { benchmarkCode, ...response };
    } catch (err) {
      if (err.response?.status === 404) {
        return { benchmarkCode, status: 'IDLE' };
      }
      return rejectWithValue(err.response?.data || 'Failed to fetch index sync status');
    }
  }
);

// ─── Slice ──────────────────────────────────────────────────────────────────

const syncSlice = createSlice({
  name: 'sync',
  initialState: {
    jobs: {},       // schemeCode   -> { status, message, job_id, error }
    indexJobs: {},  // benchmarkCode -> { status, message, job_id, error }
    globalSync: { status: 'IDLE', message: null }
  },
  reducers: {
    clearJob: (state, action) => {
      delete state.jobs[action.payload];
    },
    clearIndexJob: (state, action) => {
      delete state.indexJobs[action.payload];
    },
    clearGlobalSync: (state) => {
      state.globalSync = { status: 'IDLE', message: null };
    }
  },
  extraReducers: (builder) => {
    builder
      // ── Fund sync ──
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
        state.jobs[schemeCode] = { status: 'FAILED', error: action.payload };
      })
      .addCase(fetchSyncStatus.fulfilled, (state, action) => {
        const { schemeCode, status, message, id } = action.payload;
        state.jobs[schemeCode] = { status, message, job_id: id };
      })

      // ── Index sync ──
      .addCase(triggerIndexSync.pending, (state, action) => {
        const benchmarkCode = action.meta.arg;
        state.indexJobs[benchmarkCode] = {
          ...state.indexJobs[benchmarkCode],
          status: 'RUNNING',
          message: 'Initializing index sync...'
        };
      })
      .addCase(triggerIndexSync.fulfilled, (state, action) => {
        const { benchmarkCode, job_id, sync_status, sync_message } = action.payload;
        state.indexJobs[benchmarkCode] = {
          status: sync_status || 'RUNNING',
          message: sync_message || 'Index sync started...',
          job_id
        };
      })
      .addCase(triggerIndexSync.rejected, (state, action) => {
        const benchmarkCode = action.meta.arg;
        state.indexJobs[benchmarkCode] = { status: 'FAILED', error: action.payload };
      })
      .addCase(fetchIndexSyncStatus.fulfilled, (state, action) => {
        const { benchmarkCode, status, message, id } = action.payload;
        state.indexJobs[benchmarkCode] = { status, message, job_id: id };
      })

      // ── Global sync ──
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

export const { clearJob, clearIndexJob, clearGlobalSync } = syncSlice.actions;
export default syncSlice.reducer;
