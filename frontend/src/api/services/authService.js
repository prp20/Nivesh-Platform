import apiClient from '../apiClient';

const authService = {
    login: async (username, password) => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await apiClient.post('/auth/login', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    getMe: async (token) => {
        const config = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
        const response = await apiClient.get('/auth/me', config);
        return response.data;
    },
};

export default authService;
