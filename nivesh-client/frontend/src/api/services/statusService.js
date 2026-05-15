import apiClient from '../apiClient';

const statusService = {
    /**
     * GET /status — returns client connectivity summary.
     * { is_online, last_connected_at, server_url, cached_resources, db_path }
     */
    get: async () => {
        const response = await apiClient.get('/status');
        return response.data;
    },
};

export default statusService;
