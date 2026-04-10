import React, { createContext, useState, useContext, useEffect } from 'react';
import authService from '../api/services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState({ username: 'admin', role: 'admin' });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // Authentication disabled - defaulting to mock user
        /*
        const initAuth = async () => {
            try {
                const token = localStorage.getItem('nivesh_token');
                if (token) {
                    try {
                        const userData = await authService.getMe();
                        setUser(userData);
                    } catch (error) {
                        console.error("Auth initialization failed", error);
                        localStorage.removeItem('nivesh_token');
                    }
                }
            } catch (storageError) {
                console.warn("localStorage access failed (possibly incognito mode)", storageError);
            }
            setLoading(false);
        };
        initAuth();
        */
    }, []);

    const login = async (username, password) => {
        try {
            const data = await authService.login(username, password);
            try {
                localStorage.setItem('nivesh_token', data.access_token);
            } catch (storageError) {
                console.warn("Failed to store token (possibly incognito mode)", storageError);
                throw storageError;
            }
            const userData = await authService.getMe();
            setUser(userData);
            return userData;
        } catch (error) {
            localStorage.removeItem('nivesh_token');
            setUser(null);
            throw error;
        }
    };

    const logout = () => {
        try {
            localStorage.removeItem('nivesh_token');
        } catch (storageError) {
            console.warn("Failed to remove token from storage", storageError);
        }
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
