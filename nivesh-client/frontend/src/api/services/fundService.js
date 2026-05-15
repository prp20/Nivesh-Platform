import apiClient from '../apiClient';

const fundService = {
    // ── Mutual Funds ──────────────────────────────────────────────────────────

    getFunds: async (skip = 0, limit = 10, category = null, amc = null,
                     subcategory = null, plan_type = null, order_by = null, search = null) => {
        const params = { skip, limit };
        if (category && category !== 'All') params.category = category;
        if (amc && amc !== 'All') params.amc = amc;
        if (subcategory) params.subcategory = subcategory;
        if (plan_type) params.plan_type = plan_type;
        if (order_by) params.order_by = order_by;
        if (search) params.q = search;
        const response = await apiClient.get('/proxy/funds', { params });
        return response.data;
    },

    getAmcs: async () => {
        const response = await apiClient.get('/proxy/funds/amcs');
        return response.data;
    },

    compareFunds: async (codes) => {
        const scheme_codes = Array.isArray(codes) ? codes.join(',') : codes;
        const response = await apiClient.get('/proxy/funds/compare', { params: { scheme_codes } });
        return response.data;
    },

    getCategories: async () => {
        const response = await apiClient.get('/proxy/funds/categories');
        return response.data;
    },

    getSubcategories: async (category) => {
        const response = await apiClient.get(
            `/proxy/funds/categories/${encodeURIComponent(category)}/subcategories`
        );
        return response.data;
    },

    getFundDetail: async (schemeCode) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}`);
        return response.data;
    },

    getSimilarFunds: async (schemeCode) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}/similar`);
        return response.data;
    },

    getFundNavHistory: async (schemeCode, limit = 100) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}/nav`, { params: { limit } });
        return response.data;
    },

    getFundMetrics: async (schemeCode) => {
        // Metrics are embedded in the fund detail response from the proxy
        const response = await apiClient.get(`/proxy/funds/${schemeCode}`);
        return response.data?.metrics ?? {};
    },

    // ── Benchmarks ────────────────────────────────────────────────────────────

    getBenchmarks: async (skip = 0, limit = 10, search = null) => {
        const params = { skip, limit };
        if (search) params.q = search;
        const response = await apiClient.get('/proxy/benchmarks', { params });
        return response.data;
    },

    getBenchmarkDetail: async (benchmarkCode) => {
        const response = await apiClient.get(`/proxy/benchmarks/${benchmarkCode}`);
        return response.data;
    },

    getBenchmarkNavHistory: async (benchmarkCode, limit = 100) => {
        const response = await apiClient.get(
            `/proxy/benchmarks/${benchmarkCode}/nav`, { params: { limit } }
        );
        return response.data;
    },

    // ── Sync status (pipeline) ────────────────────────────────────────────────

    getSyncStatus: async () => {
        const response = await apiClient.get('/proxy/sync/status');
        return response.data;
    },
};

export default fundService;
