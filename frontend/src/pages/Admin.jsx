import React, { useState } from 'react';
import fundService from '../api/services/fundService';
import { motion } from 'framer-motion';

const Admin = () => {
    const [logs, setLogs] = useState([
        { id: 1, time: '2024-03-24 14:20', level: 'INFO', msg: 'System integrity check passed. Tier-1 security active.' },
        { id: 2, time: '2024-03-24 14:18', level: 'AUTH', msg: 'Admin session established via Sovereign Protocol.' },
    ]);
    const [syncing, setSyncing] = useState(false);
    const [actionMsg, setActionMsg] = useState(null);

    const addLog = (msg, level = 'INFO') => {
        setLogs(prev => [{ id: Date.now(), time: new Date().toISOString().replace('T', ' ').substring(0, 16), level, msg }, ...prev]);
    };

    const handleSyncAll = async () => {
        setSyncing(true);
        addLog('Initiating Global Wealth Synchronization...', 'SYSTEM');
        try {
            await fundService.syncAllFunds();
            addLog('Global Sync Job Dispatched to Background.', 'SUCCESS');
            setActionMsg({ type: 'success', text: 'Sovereign synchronization dispatched.' });
        } catch (err) {
            addLog(`Sync error: ${err.message}`, 'ERROR');
            setActionMsg({ type: 'error', text: 'Protocol Breach: Sync failed.' });
        } finally {
            setSyncing(false);
            setTimeout(() => setActionMsg(null), 5000);
        }
    };

    const handlePurgeCache = () => {
        addLog('Purging ephemeral wealth cache...', 'SECURITY');
        setActionMsg({ type: 'info', text: 'Cache artifacts decimated.' });
        setTimeout(() => setActionMsg(null), 3000);
    };

    return (
        <div className="p-6 md:p-12 lg:p-16 xl:p-24 2xl:p-32 w-full animate-fadeIn flex flex-col gap-16 transition-all duration-500">
            {/* Header - Ultra Scale */}
            <header className="flex flex-col 3xl:flex-row 3xl:items-end justify-between gap-12 mb-8">
                <div>
                    <span className="text-sm md:text-base text-primary font-black uppercase tracking-[0.5em] opacity-80 mb-4 block">Command & Control Interface</span>
                    <h1 className="text-5xl sm:text-7xl md:text-8xl lg:text-9xl 3xl:text-[11rem] font-headline font-bold tracking-tighter leading-none group uppercase">
                        Sovereign <span className="text-primary/10 group-hover:text-primary/20 transition-colors">Admin</span> <span className="text-slate-500 opacity-20 block 3xl:inline">Panel</span>
                    </h1>
                </div>

                <div className="flex gap-8">
                    <button 
                        onClick={handleSyncAll}
                        disabled={syncing}
                        className="px-12 py-6 gold-gradient rounded-3xl text-on-primary font-black text-sm uppercase tracking-[0.4em] shadow-2xl hover:brightness-110 active:scale-95 transition-all flex items-center gap-4"
                    >
                        <span className={`material-symbols-outlined text-2xl ${syncing ? 'animate-spin' : ''}`}>sync_alt</span>
                        {syncing ? 'Synchronizing...' : 'Global Sync All'}
                    </button>
                </div>
            </header>

            {actionMsg && (
                <motion.div 
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={`p-10 rounded-[2.5rem] border font-black uppercase tracking-[0.4em] text-center ${actionMsg.type === 'success' ? 'bg-secondary/10 border-secondary/20 text-secondary' : 'bg-primary/10 border-primary/20 text-primary'}`}
                >
                    {actionMsg.text}
                </motion.div>
            )}

            {/* Admin Grid - Ultra Scaling */}
            <div className="grid grid-cols-1 3xl:grid-cols-3 gap-16 mb-24">
                <div className="col-span-1 3xl:col-span-2 glass-panel p-16 rounded-[4rem] border border-white/5 shadow-2xl bg-white/[0.01] backdrop-blur-3xl min-h-[800px] flex flex-col shadow-[0_64px_128px_rgba(0,0,0,0.6)]">
                    <div className="flex justify-between items-center mb-16">
                        <h3 className="text-4xl font-headline font-bold tracking-tight uppercase tracking-widest">Protocol Intelligence Logs</h3>
                        <span className="px-6 py-2 rounded-xl bg-secondary/10 text-secondary text-[10px] font-black uppercase tracking-widest border border-secondary/20 animate-pulse">Live Surveillance</span>
                    </div>
                    
                    <div className="flex flex-col gap-8 flex-1 overflow-y-auto pr-8 custom-scrollbar">
                        {logs.map(log => (
                            <div key={log.id} className="p-8 hover:bg-white/5 rounded-3xl transition-all border border-transparent hover:border-white/5 group flex items-start gap-10">
                                <div className="text-slate-500 font-mono text-sm pt-1 opacity-60">{log.time}</div>
                                <div className="flex flex-col gap-2">
                                    <div className="flex items-center gap-4">
                                        <span className={`text-[10px] font-black tracking-widest uppercase px-3 py-1 rounded-lg ${log.level === 'INFO' ? 'bg-primary/20 text-primary' : log.level === 'SUCCESS' ? 'bg-secondary/20 text-secondary' : 'bg-slate-800 text-slate-400'}`}>
                                            {log.level}
                                        </span>
                                    </div>
                                    <div className="text-2xl text-white font-bold tracking-tight group-hover:text-primary transition-colors leading-relaxed uppercase opacity-80">{log.msg}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="flex flex-col gap-12">
                    <div className="bg-surface-container-high p-16 rounded-[4rem] border border-white/5 shadow-2xl flex flex-col gap-12 group">
                        <h4 className="text-3xl font-headline font-black mb-4 tracking-tight uppercase tracking-widest">Vault Decryption</h4>
                        <p className="text-slate-500 font-bold leading-relaxed uppercase tracking-[0.2em] italic opacity-60">
                            Perform deep-level metric re-calculation for all identified asset artifacts in the ledger.
                        </p>
                        <button className="w-full py-8 border border-white/10 rounded-3xl text-white font-black text-xs uppercase tracking-[0.5em] hover:bg-primary hover:text-on-primary hover:border-primary transition-all shadow-2xl shadow-primary/20">
                            Initiate Deep Compute
                        </button>
                    </div>

                    <div className="bg-surface-container-low p-16 rounded-[4rem] border border-white/10 border-dashed shadow-2xl flex flex-col gap-12 group hover:bg-error/[0.02] transition-colors">
                        <h4 className="text-3xl font-headline font-black mb-4 text-error tracking-tight uppercase tracking-widest">Danger Zone</h4>
                        <p className="text-slate-500 font-bold leading-relaxed uppercase tracking-[0.2em] italic opacity-60">
                            Irreversible decimation of ephemeral wealth cache and metadata fingerprints.
                        </p>
                        <button 
                            onClick={handlePurgeCache}
                            className="w-full py-8 bg-error/10 border border-error/20 rounded-3xl text-error font-black text-xs uppercase tracking-[0.5em] hover:bg-error hover:text-white transition-all shadow-2xl"
                        >
                            Purge Asset Cache
                        </button>
                    </div>
                </div>
            </div>

            <footer className="mt-20 py-16 border-t border-white/5 opacity-30 italic text-[11px] tracking-[0.6em] uppercase font-black text-center leading-relaxed">
                Autonomous Command Engine: Alpha V1.0 • Security Token Active • Zero-Trust Mode Enabled
            </footer>
        </div>
    );
};

export default Admin;
