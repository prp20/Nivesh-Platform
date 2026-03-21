import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('admin123');
    const [error, setError] = useState('');
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(username, password);
        } catch (err) {
            setError('Invalid credentials. Please try again.');
        }
    };

    return (
        <div className="login-container">
            <div className="login-card glass">
                <h1 className="font-accent">NIVESH ELITE</h1>
                <p className="subtitle">Sign in to your private portfolio</p>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    {error && <p className="error-msg">{error}</p>}
                    <button type="submit" className="login-btn">ENTER VAULT</button>
                </form>
            </div>
        </div>
    );
};

export default Login;
