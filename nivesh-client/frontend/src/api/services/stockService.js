import apiClient from '../apiClient';

const stockService = {
    getStocks: async (params) => {
        const response = await apiClient.get('/proxy/stocks', { params });
        return response.data;
    },

    searchStocks: async (q) => {
        const response = await apiClient.get('/proxy/stocks/search', { params: { q } });
        return response.data;
    },

    getStockDetail: async (symbol) => {
        const response = await apiClient.get(`/proxy/stocks/${symbol.toUpperCase()}`);
        return response.data;
    },

    getScreener: async (filters) => {
        const response = await apiClient.get('/proxy/stocks/screener', { params: filters });
        return response.data;
    },

    // Stub: no /proxy/stocks/compare endpoint yet — Phase 6 will add it
    getCompare: async (_symbols) => ({ data: [] }),

    // Pipeline status (read-only — ingestion runs server-side)
    getPipelineStatus: async () => {
        const response = await apiClient.get('/proxy/sync/status');
        return response.data;
    },

    getPriceHistory: async (symbol, params) => {
        const response = await apiClient.get(`/proxy/stocks/${symbol.toUpperCase()}/price`, { params });
        return response.data;
    },

    getFundamentals: async (symbol, params) => {
        const response = await apiClient.get(`/proxy/stocks/${symbol.toUpperCase()}/fundamentals`, { params });
        return response.data;
    },

    // Financial ratios come from the stock detail endpoint as flat fields.
    // Returns { records: [detail] } so legacy callers still work.
    getRatios: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return { records: [detail] };
    },

    getShareholding: async (_symbol, _params) => ({ records: [] }),

    getAgentInsights: async (symbol) => {
        // Calls the direct analysis endpoint — no tool calling, no agent graph.
        // Pre-fetches stock data server-side and runs a single LLM inference.
        const response = await apiClient.post(`/agent/analyze/${symbol.toUpperCase()}`);
        return { reasoning_text: response.data.analysis };
    },

    getTechnicals: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },

    // ── Pipeline triggers ──────────────────────────────────────────────────────
    triggerDeepPriceSync: async (symbol, _period) => {
        const response = await apiClient.post(`/proxy/pipeline/prices/refresh/${symbol.toUpperCase()}`);
        return response.data;
    },

    triggerPriceRefresh: async (symbol) => {
        const response = await apiClient.post(`/proxy/pipeline/metrics/price-refresh/${symbol.toUpperCase()}`);
        return response.data;
    },

    triggerTechnicalAnalysis: async (symbol) => {
        const response = await apiClient.post(`/proxy/pipeline/technical/${symbol.toUpperCase()}`);
        return response.data;
    },

    triggerScreenerScrape: async (symbol, _background) => {
        const response = await apiClient.post(`/proxy/pipeline/screener/${symbol.toUpperCase()}`);
        return response.data;
    },

    triggerRatingCompute: async (symbol) => {
        const response = await apiClient.post(`/proxy/pipeline/ratings/${symbol.toUpperCase()}`);
        return response.data;
    },
};

export default stockService;
