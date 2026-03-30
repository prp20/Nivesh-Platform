import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(username, password);
        } catch (err) {
            setError('ACCESS DENIED: INVALID CREDENTIALS');
        }
    };

    return (
        <div className="login-page">
            <div className="glass-panel login-card-elite reveal active">
                <header>
                    <h1 className="login-logo font-heading">NIVESH ELITE</h1>
                    <p className="login-subtitle">PRIVATE ASSET NETWORK</p>
                </header>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="input-box">
                        <label>Identity / Alias</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </div>
                    <div className="input-box">
                        <label>Access Key</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    
                    {error && <p className="login-error uppercase tracking-widest">{error}</p>}
                    
                    <button type="submit" className="login-btn-elite btn-premium btn-premium-primary">
                        INITIALIZE CONNECTION
                    </button>
                    
                    <p className="text-muted text-xs uppercase tracking-widest mt-10 opacity-30">
                        Encrypted Ledger Protocol v4.0.2
                    </p>
                </form>
            </div>
        </div>
    );
};

export default Login;
