import apiClient from '../apiClient';

const watchlistService = {
    get: async (assetType = null) => {
        const params = assetType ? { asset_type: assetType } : {};
        const response = await apiClient.get('/local/watchlist', { params });
        return response.data;
    },

    add: async (data) => {
        // data: { symbol, asset_type, display_name?, notes?, alert_above?, alert_below? }
        const response = await apiClient.post('/local/watchlist', data);
        return response.data;
    },

    remove: async (id) => {
        await apiClient.delete(`/local/watchlist/${id}`);
    },
};

export default watchlistService;
