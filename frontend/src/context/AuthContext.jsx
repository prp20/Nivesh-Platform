import React, { createContext, useState, useContext, useEffect } from 'react';
import authService from '../api/services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const initAuth = async () => {
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
            setLoading(false);
        };
        initAuth();
    }, []);

    const login = async (username, password) => {
        const data = await authService.login(username, password);
        localStorage.setItem('nivesh_token', data.access_token);
        const userData = await authService.getMe();
        setUser(userData);
        return userData;
    };

    const logout = () => {
        localStorage.removeItem('nivesh_token');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
