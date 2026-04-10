import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";
import stockService from "../../api/services/stockService";

export const fetchStocks      = createAsyncThunk("stocks/fetchAll",    (p) => stockService.getStocks(p));
export const searchStocks     = createAsyncThunk("stocks/search",      (q) => stockService.searchStocks(q));
export const fetchStockDetail = createAsyncThunk("stocks/fetchDetail", (s) => stockService.getStockDetail(s));
export const fetchScreener    = createAsyncThunk("stocks/screener",    (f) => stockService.getScreener(f));

export const triggerFullStockSync = createAsyncThunk(
  "stocks/triggerSync",
  async (symbol, { dispatch, rejectWithValue }) => {
    try {
      await stockService.triggerScreenerScrape(symbol, true);
      await stockService.triggerDeepPriceSync(symbol, "1y");
      await stockService.triggerTechnicalAnalysis(symbol);
      await stockService.triggerRatingCompute(symbol);
      dispatch(fetchStockDetail(symbol));
      return true;
    } catch (err) {
      return rejectWithValue(err.response?.data || "Sync failed");
    }
  }
);

const stocksSlice = createSlice({
  name: "stocks",
  initialState: {
    list:           [],
    detail:         null,
    screenerResult: [],
    filters:        { sector: "", market_cap_cat: "", rating_label: "", min_roe: "", max_pe: "", max_debt_equity: "" },
    pagination:     { page: 1, limit: 25, total: 0 },
    status:         "idle",
    error:          null,
  },
  reducers: {
    setFilter:    (state, { payload: { key, val } }) => { state.filters[key] = val; state.pagination.page = 1; },
    resetFilters: (state) => { state.filters = {}; state.pagination.page = 1; },
    setPage:      (state, { payload }) => { state.pagination.page = payload; },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStocks.pending,   (s)    => { s.status = "loading"; s.error = null; })
      .addCase(fetchStocks.fulfilled, (s, a) => { s.status = "succeeded"; s.list = a.payload.results; s.pagination.total = a.payload.total; s.error = null; })
      .addCase(fetchStocks.rejected,  (s, a) => { s.status = "failed"; s.error = a.payload || a.error.message; })
      .addCase(searchStocks.pending,  (s)    => { s.status = "loading"; s.error = null; })
      .addCase(searchStocks.fulfilled, (s, a) => { s.status = "succeeded"; s.list = a.payload.results; s.error = null; })
      .addCase(searchStocks.rejected, (s, a) => { s.status = "failed"; s.error = a.payload || a.error.message; })
      .addCase(fetchStockDetail.pending, (s) => { s.status = "loading"; s.error = null; })
      .addCase(fetchStockDetail.fulfilled, (s, a) => { s.detail = a.payload; s.status = "succeeded"; s.error = null; })
      .addCase(fetchStockDetail.rejected, (s, a) => { s.status = "failed"; s.error = a.payload || a.error.message; })
      .addCase(fetchScreener.pending, (s)    => { s.status = "loading"; s.error = null; })
      .addCase(fetchScreener.fulfilled,    (s, a) => { s.screenerResult = a.payload.results; s.status = "succeeded"; s.error = null; })
      .addCase(fetchScreener.rejected, (s, a) => { s.status = "failed"; s.error = a.payload || a.error.message; })
      .addCase(triggerFullStockSync.pending, (s) => { s.status = "loading"; s.error = null; })
      .addCase(triggerFullStockSync.fulfilled, (s) => { s.status = "succeeded"; s.error = null; })
      .addCase(triggerFullStockSync.rejected, (s, a) => { s.status = "failed"; s.error = a.payload || a.error.message; });
  },
});

export const { setFilter, resetFilters, setPage } = stocksSlice.actions;
export default stocksSlice.reducer;
