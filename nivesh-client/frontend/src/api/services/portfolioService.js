import apiClient from '../apiClient';

const portfolioService = {
    getHoldings: async (assetType = null) => {
        const params = assetType ? { asset_type: assetType } : {};
        const response = await apiClient.get('/local/portfolio/holdings', { params });
        return response.data;
    },

    addHolding: async (data) => {
        const response = await apiClient.post('/local/portfolio/holdings', data);
        return response.data;
    },

    updateHolding: async (id, data) => {
        const response = await apiClient.put(`/local/portfolio/holdings/${id}`, data);
        return response.data;
    },

    deleteHolding: async (id) => {
        await apiClient.delete(`/local/portfolio/holdings/${id}`);
    },

    getTransactions: async (symbol = null) => {
        const params = symbol ? { symbol } : {};
        const response = await apiClient.get('/local/portfolio/transactions', { params });
        return response.data;
    },

    addTransaction: async (data) => {
        const response = await apiClient.post('/local/portfolio/transactions', data);
        return response.data;
    },
};

export default portfolioService;
