import apiClient from '../apiClient';

const authService = {
    /**
     * POST /auth/login — forwards to Render server, stores JWT in SQLite.
     * Returns { access_token, token_type, expires_in }.
     * React never sees the raw JWT after this point.
     */
    login: async (username, password) => {
        const response = await apiClient.post('/auth/login', { username, password });
        return response.data;
    },

    /**
     * POST /auth/logout — clears stored tokens from SQLite.
     * Best-effort: local logout always succeeds even if server unreachable.
     */
    logout: async () => {
        try {
            await apiClient.post('/auth/logout');
        } catch {
            // Ignore — local SQLite tokens are cleared regardless
        }
    },
};

export default authService;
