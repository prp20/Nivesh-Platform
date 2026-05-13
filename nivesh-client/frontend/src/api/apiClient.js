import axios from 'axios';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add JWT token
apiClient.interceptors.request.use(
    (config) => {
        try {
            const token = localStorage.getItem('nivesh_token');
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        } catch (storageError) {
            console.warn("Failed to set authentication header", storageError);
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for global error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            try {
                localStorage.removeItem('nivesh_token');
            } catch (storageError) {
                console.warn("Failed to clear token on 401", storageError);
            }
            // Force reload to login to ensure clean state
            if (!window.location.pathname.includes('/login')) {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

export default apiClient;
