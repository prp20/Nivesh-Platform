import apiClient from '../apiClient';

const fundService = {
    // FUNDS
    getFunds: async (skip = 0, limit = 10, category = null, amc = null, subcategory = null, plan_type = null, order_by = null, search = null) => {
        let url = `/funds/?skip=${skip}&limit=${limit}`;
        if (category && category !== 'All') url += `&category=${encodeURIComponent(category)}`;
        if (amc && amc !== 'All') url += `&amc=${encodeURIComponent(amc)}`;
        if (subcategory) url += `&subcategory=${encodeURIComponent(subcategory)}`;
        if (plan_type) url += `&plan_type=${encodeURIComponent(plan_type)}`;
        if (order_by) url += `&order_by=${encodeURIComponent(order_by)}`;
        if (search) url += `&q=${encodeURIComponent(search)}`;
        
        const response = await apiClient.get(url);
        return response.data; // Now returns {total, skip, limit, items}
    },

    getAmcs: async () => {
        const response = await apiClient.get('/funds/amcs');
        return response.data;
    },

    compareFunds: async (codes) => {
        const codesStr = Array.isArray(codes) ? codes.join(',') : codes;
        const response = await apiClient.get(`/funds/compare?codes=${codesStr}`);
        return response.data;
    },

    getCategories: async () => {
        const response = await apiClient.get('/funds/categories');
        return response.data;
    },

    getSubcategories: async (category) => {
        const response = await apiClient.get(`/funds/categories/${encodeURIComponent(category)}/subcategories`);
        return response.data;
    },

    getFundDetail: async (schemeCode) => {
        const response = await apiClient.get(`/funds/${schemeCode}`);
        return response.data;
    },

    getSimilarFunds: async (schemeCode) => {
        const response = await apiClient.get(`/funds/${schemeCode}/similar`);
        return response.data;
    },

    createFund: async (data) => {
        const response = await apiClient.post(`/funds/`, data);
        return response.data;
    },

    updateFund: async (schemeCode, data) => {
        const response = await apiClient.put(`/funds/${schemeCode}`, data);
        return response.data;
    },

    deleteFund: async (schemeCode) => {
        const response = await apiClient.delete(`/funds/${schemeCode}`);
        return response.data;
    },

    // NAVs
    getFundNavHistory: async (schemeCode, limit = 100) => {
        const response = await apiClient.get(`/navs/${schemeCode}?limit=${limit}`);
        return response.data;
    },

    // METRICS
    getFundMetrics: async (schemeCode) => {
        const response = await apiClient.get(`/metrics/${schemeCode}`);
        return response.data;
    },

    computeMetrics: async (schemeCode) => {
        const response = await apiClient.post(`/metrics/${schemeCode}/compute`);
        return response.data;
    },

    getSyncStatus: async (schemeCode) => {
        const response = await apiClient.get(`/metrics/${schemeCode}/status`);
        return response.data;
    },

    // BENCHMARKS (INDICES)
    getBenchmarks: async (skip = 0, limit = 10, search = null) => {
        let url = `/benchmarks/?skip=${skip}&limit=${limit}`;
        if (search) url += `&q=${encodeURIComponent(search)}`;
        const response = await apiClient.get(url);
        return response.data;
    },

    getBenchmarkDetail: async (benchmarkCode) => {
        const response = await apiClient.get(`/benchmarks/${benchmarkCode}`);
        return response.data;
    },

    createBenchmark: async (data) => {
        const response = await apiClient.post(`/benchmarks/`, data);
        return response.data;
    },

    updateBenchmark: async (benchmarkCode, data) => {
        const response = await apiClient.put(`/benchmarks/${benchmarkCode}`, data);
        return response.data;
    },

    deleteBenchmark: async (benchmarkCode) => {
        const response = await apiClient.delete(`/benchmarks/${benchmarkCode}`);
        return response.data;
    },

    getBenchmarkNavHistory: async (benchmarkCode, limit = 100) => {
        const response = await apiClient.get(`/benchmark-navs/${benchmarkCode}?limit=${limit}`);
        return response.data;
    },

    uploadBenchmarkCsv: async (benchmarkCode, file) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post(`/benchmark-navs/${benchmarkCode}/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    },

    // SYNC
    syncAllFunds: async () => {
        const response = await apiClient.post('/sync/all');
        return response.data;
    },

    syncFund: async (schemeCode) => {
        const response = await apiClient.post(`/sync/${schemeCode}`);
        return response.data;
    }
};

export default fundService;
