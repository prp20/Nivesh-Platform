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

    // Price history — not yet in proxy; return empty for now
    getPriceHistory: async (_symbol) => ({ data: [] }),

    // Stub read-only equivalents for removed pipeline triggers
    getFundamentals: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },

    getRatios: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },

    getTechnicals: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },
};

export default stockService;
