import apiClient from '../apiClient';

const fundService = {
    // FUNDS
    getFunds: async (skip = 0, limit = 100) => {
        const response = await apiClient.get(`/funds/?skip=${skip}&limit=${limit}`);
        return response.data;
    },

    getFundDetail: async (schemeCode) => {
        const response = await apiClient.get(`/funds/${schemeCode}`);
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
    getBenchmarks: async (skip = 0, limit = 100) => {
        const response = await apiClient.get(`/benchmarks/?skip=${skip}&limit=${limit}`);
        return response.data;
    },

    getBenchmarkDetail: async (benchmarkCode) => {
        const response = await apiClient.get(`/benchmarks/${benchmarkCode}`);
        return response.data;
    },

    getBenchmarkNavHistory: async (benchmarkCode, limit = 100) => {
        const response = await apiClient.get(`/benchmark-navs/${benchmarkCode}?limit=${limit}`);
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
