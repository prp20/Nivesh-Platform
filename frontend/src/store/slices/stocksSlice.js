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
      .addCase(fetchStocks.pending,   (s)    => { s.status = "loading"; })
      .addCase(fetchStocks.fulfilled, (s, a) => { s.status = "succeeded"; s.list = a.payload.results; s.pagination.total = a.payload.total; })
      .addCase(fetchStocks.rejected,  (s, a) => { s.status = "failed"; s.error = a.error.message; })
      .addCase(fetchStockDetail.fulfilled, (s, a) => { s.detail = a.payload; })
      .addCase(fetchScreener.fulfilled,    (s, a) => { s.screenerResult = a.payload.results; });
  },
});

export const { setFilter, resetFilters, setPage } = stocksSlice.actions;
export default stocksSlice.reducer;
