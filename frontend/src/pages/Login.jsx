import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';

const Login = () => {
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('admin123');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            await login(username, password);
            navigate('/dashboard');
        } catch (err) {
            setError(err.response?.data?.detail || 'Protocol Breach: Identity Verification Failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center bg-[#0a0f12] p-6 relative overflow-hidden transition-all duration-700">
            {/* Background Aesthetic */}
            <div className="absolute top-0 left-0 w-full h-full gold-gradient opacity-[0.02] -skew-y-12 translate-y-[-50%] transform-gpu"></div>
            <div className="absolute bottom-0 right-0 w-full h-full gold-gradient opacity-[0.01] skew-y-12 translate-y-[50%] transform-gpu"></div>

            <motion.div 
                initial={{ opacity: 0, y: 40, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className="w-full max-w-[600px] z-10"
            >
                <div className="bg-surface-container-high/60 backdrop-blur-3xl p-16 md:p-24 rounded-[4rem] border border-white/5 shadow-[0_128px_256px_rgba(0,0,0,0.8)] relative overflow-hidden group transition-all duration-700 hover:border-primary/20">
                    <div className="absolute top-0 right-0 p-16 opacity-0 group-hover:opacity-10 transition-all duration-1000 scale-150 group-hover:scale-100 pointer-events-none">
                         <span className="material-symbols-outlined text-[150px] text-primary">security</span>
                    </div>

                    <header className="text-center mb-16 relative z-10">
                        <div className="inline-block px-6 py-2 rounded-xl bg-primary/10 border border-primary/20 text-primary text-[10px] font-black uppercase tracking-[0.6em] mb-10 leading-none">Identity Verification Protocol</div>
                        <h1 className="text-5xl sm:text-6xl font-headline font-bold text-white tracking-tighter leading-none mb-6 group-hover:text-primary transition-colors">Nivesh <span className="text-slate-500">Elite</span></h1>
                        <p className="text-base text-slate-500 font-bold uppercase tracking-[0.3em] opacity-60">Sovereign Wealth Portal Access</p>
                    </header>

                    <form onSubmit={handleSubmit} className="space-y-10 relative z-10">
                        <div className="space-y-4">
                            <label className="block text-[11px] font-black uppercase tracking-[0.5em] text-slate-500 pl-4 mb-2">Primary Identifier</label>
                            <input 
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full bg-white/[0.03] border border-white/5 rounded-3xl p-8 text-white font-bold text-xl focus:outline-none focus:border-primary/40 focus:bg-white/[0.05] transition-all placeholder:text-slate-800 shadow-inner group-hover:bg-white/[0.05]"
                                placeholder="USERNAME"
                                required
                            />
                        </div>

                        <div className="space-y-4">
                            <label className="block text-[11px] font-black uppercase tracking-[0.5em] text-slate-500 pl-4 mb-2">Access Key Override</label>
                            <input 
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-white/[0.03] border border-white/5 rounded-3xl p-8 text-white font-bold text-xl focus:outline-none focus:border-primary/40 focus:bg-white/[0.05] transition-all placeholder:text-slate-800 shadow-inner group-hover:bg-white/[0.05]"
                                placeholder="PASSWORD"
                                required
                            />
                        </div>

                        <AnimatePresence>
                            {error && (
                                <motion.div 
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="p-8 bg-error/10 border border-error/20 rounded-3xl text-error text-center font-black uppercase tracking-widest text-sm"
                                >
                                    {error}
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <button 
                            type="submit"
                            disabled={loading}
                            className="w-full gold-gradient py-8 rounded-[2.5rem] text-on-primary font-black text-sm uppercase tracking-[0.6em] shadow-[0_32px_64px_rgba(233,195,73,0.3)] hover:shadow-[0_48px_96px_rgba(233,195,73,0.4)] hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-50 disabled:grayscale relative overflow-hidden"
                        >
                            <span className="relative z-10">{loading ? 'Verifying Integrity...' : 'Decrypt Access Port'}</span>
                        </button>
                    </form>

                    <footer className="mt-16 text-center">
                        <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] opacity-40 leading-relaxed italic">
                            Secured by Zero-Trust Architecture • Alpha V1.0 <br/>
                            Session fingerprinting active.
                        </p>
                    </footer>
                </div>
            </motion.div>
        </div>
    );
};

export default Login;
