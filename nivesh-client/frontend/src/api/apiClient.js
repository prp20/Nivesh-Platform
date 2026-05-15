import axios from 'axios';

// All API calls go to the local client FastAPI on port 8001.
// The client backend injects the JWT for /proxy/* calls.
// React never handles JWT tokens directly.
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
    headers: { 'Content-Type': 'application/json' },
});

// No request interceptor — client backend handles auth headers server-side.

// Response interceptor: on 401, the client's refresh logic already tried and
// gave up. Signal auth expiry to AuthContext via a custom event.
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            window.dispatchEvent(new CustomEvent('auth:session-expired'));
        }
        return Promise.reject(error);
    }
);

export default apiClient;
