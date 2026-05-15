import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import authService from '../api/services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    // user: null = not authenticated, { username } = authenticated
    // Kept as 'user' (not 'isAuthenticated') for backward compat with existing route guards.
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Detect existing session on mount.
    // Strategy: GET /status — if last_connected_at is set, the user logged in before.
    // We don't check is_online because user can be authenticated while server is offline.
    useEffect(() => {
        const initAuth = async () => {
            try {
                const resp = await fetch('http://localhost:8001/status');
                if (resp.ok) {
                    const status = await resp.json();
                    // last_connected_at is set by the login endpoint and cleared on logout
                    if (status.last_connected_at) {
                        // Read stored username from preferences
                        const prefsResp = await fetch('http://localhost:8001/local/preferences');
                        const prefs = prefsResp.ok ? await prefsResp.json() : {};
                        setUser({ username: prefs.last_login_username ?? 'user' });
                    }
                }
            } catch {
                // Client not running — will show login screen
            } finally {
                setLoading(false);
            }
        };
        initAuth();
    }, []);

    // Listen for session expiry events dispatched by apiClient on 401
    useEffect(() => {
        const handleExpiry = () => {
            setUser(null);
        };
        window.addEventListener('auth:session-expired', handleExpiry);
        return () => window.removeEventListener('auth:session-expired', handleExpiry);
    }, []);

    const login = useCallback(async (username, password) => {
        setError(null);
        try {
            await authService.login(username, password);
            // Store username in local preferences for session persistence across page refreshes
            await fetch(
                `http://localhost:8001/local/preferences/last_login_username?value=${encodeURIComponent(username)}`,
                { method: 'PUT' }
            );
            setUser({ username });
        } catch (err) {
            const status = err.response?.status;
            if (status === 401) {
                setError('Incorrect username or password');
            } else if (status === 503) {
                setError('Cannot reach server — check NIVESH_SERVER_URL in ~/.nivesh/.env');
            } else {
                setError('Login failed — is the Nivesh Client running on port 8001?');
            }
            throw err;
        }
    }, []);

    const logout = useCallback(async () => {
        await authService.logout();
        // Clear stored username from preferences
        try {
            await fetch(
                'http://localhost:8001/local/preferences/last_login_username?value=',
                { method: 'PUT' }
            );
        } catch {
            // Best-effort
        }
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, error }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
