import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import fundService from '../api/services/fundService';
import stockService from '../api/services/stockService';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend
} from 'recharts';

const Admin = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const activeTab = searchParams.get('tab') || 'dashboard';

    const setActiveTab = (tab) => {
      setSearchParams({ tab });
    };

    const [logs, setLogs] = useState([
        { id: 1, time: '2024-03-24 14:20', level: 'INFO', msg: 'System integrity check passed. Tier-1 security active.' },
        { id: 2, time: '2024-03-24 14:18', level: 'AUTH', msg: 'Admin session established via Sovereign Protocol.' },
    ]);
    const [pipelineJobs, setPipelineJobs] = useState([]);
    const [syncing, setSyncing] = useState(false);
    const [actionMsg, setActionMsg] = useState(null);

    const addLog = (msg, level = 'INFO') => {
        setLogs(prev => [{ id: Date.now(), time: new Date().toISOString().replace('T', ' ').substring(0, 16), level, msg }, ...prev]);
    };

    const fetchPipelineStatus = async () => {
      try {
        const res = await stockService.getPipelineStatus();
        setPipelineJobs(res.jobs || []);
      } catch (err) {
        console.error("Failed to fetch pipeline status:", err);
      }
    };

    useEffect(() => {
      fetchPipelineStatus();
      const interval = setInterval(fetchPipelineStatus, 5000);
      return () => clearInterval(interval);
    }, []);

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

    const [assetType, setAssetType] = useState('stocks'); // 'stocks' or 'mf'
    const [assetsData, setAssetsData] = useState([]);
    const [loadingAssets, setLoadingAssets] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [assetModal, setAssetModal] = useState({ isOpen: false, data: null, mode: 'create' });

    const fetchAssets = async () => {
      setLoadingAssets(true);
      try {
        if (assetType === 'stocks') {
          const res = await stockService.getStocks({ limit: 50, q: searchQuery });
          setAssetsData(res.results || []);
        } else {
          const res = await fundService.getFunds(0, 50, null, null, null, null, null, searchQuery);
          setAssetsData(res.items || []);
        }
      } catch (err) {
        console.error("Failed to fetch assets:", err);
      } finally {
        setLoadingAssets(false);
      }
    };

    useEffect(() => {
      if (activeTab === 'assets') {
        fetchAssets();
      }
    }, [activeTab, searchQuery, assetType]);

    const handleSaveAsset = async (formData) => {
        try {
            addLog(`Saving ${assetType}...`, 'SYSTEM');
            if (assetType === 'stocks') {
                if (assetModal.mode === 'create') await stockService.createStock(formData);
                else await stockService.updateStock(assetModal.data.symbol, formData);
            } else {
                if (assetModal.mode === 'create') await fundService.createFund(formData);
                else await fundService.updateFund(assetModal.data.scheme_code, formData);
            }
            setAssetModal({ isOpen: false, data: null, mode: 'create' });
            fetchAssets();
        } catch(err) {
            addLog(`Error saving: ${err.message}`, 'ERROR');
        }
    };

    const handleDeleteAsset = async (id) => {
        try {
            addLog(`Deleting asset ${id}...`, 'SYSTEM');
            if (assetType === 'stocks') await stockService.deleteStock(id);
            else await fundService.deleteFund(id);
            fetchAssets();
        } catch(err) {
            addLog(`Error deleting: ${err.message}`, 'ERROR');
        }
    };

    const handleBulkAction = async (actionFn, label) => {
      try {
        addLog(`Initiating ${label}...`, 'SYSTEM');
        await actionFn();
        addLog(`${label} dispatched successfully.`, 'SUCCESS');
        setActionMsg({ type: 'success', text: `${label} cycle established.` });
      } catch (err) {
        addLog(`Error in ${label}: ${err.message}`, 'ERROR');
        setActionMsg({ type: 'error', text: `${label} failed.` });
      } finally {
        setTimeout(() => setActionMsg(null), 3000);
      }
    };

    const handleSingleStockSync = async (symbol, actionFn, label) => {
      try {
        addLog(`Syncing ${label} for ${symbol}...`, 'SYSTEM');
        await actionFn(symbol);
        addLog(`${label} updated for ${symbol}.`, 'SUCCESS');
      } catch (err) {
        addLog(`Failed to sync ${symbol}: ${err.message}`, 'ERROR');
      }
    };

    const sidebarItems = [
      { id: 'dashboard', label: 'Command Center', icon: 'dashboard' },
      { id: 'health', label: 'System Health', icon: 'monitor_heart' },
      { id: 'pipeline', label: 'Pipeline Hub', icon: 'cyclone' },
      { id: 'assets', label: 'Asset Ledger', icon: 'account_balance_wallet' },
      { id: 'logs', label: 'Security Logs', icon: 'security' },
    ];

    return (
        <div className="flex flex-col bg-[#0f1419] text-white min-h-screen font-inter w-full">
            {/* Main Content Area */}
            <main className="flex-1 flex flex-col relative">
              <header className="sticky top-0 z-30 bg-[#0f1419]/80 backdrop-blur-xl border-b border-white/5 px-16 py-8 flex justify-between items-center">
                <div className="flex items-center gap-8">
                  {activeTab !== 'dashboard' && (
                    <button onClick={() => setActiveTab('dashboard')} className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors">
                      <span className="material-symbols-outlined text-sm">arrow_back</span>
                    </button>
                  )}
                  <div>
                    <span className="text-[10px] text-slate-500 font-black tracking-[0.5em] uppercase mb-1 block">
                      {sidebarItems.find(i => i.id === activeTab)?.label} Control Panel
                    </span>
                    <h3 className="text-2xl font-headline font-black uppercase tracking-tighter">
                      {activeTab === 'dashboard' ? 'Overview Node' : 
                       activeTab === 'health' ? 'Infrastructure Health' : 
                       activeTab === 'pipeline' ? 'Job Scheduler' : 
                       activeTab === 'assets' ? 'Asset Ledger' :
                       'Security Archive'}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-8">
                  {actionMsg && (
                    <motion.div 
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={`px-6 py-3 rounded-xl border text-[10px] font-black uppercase tracking-widest ${actionMsg.type === 'success' ? 'bg-secondary/10 border-secondary/20 text-secondary' : 'bg-red-500/10 border-red-500/20 text-red-500'}`}
                    >
                      {actionMsg.text}
                    </motion.div>
                  )}
                  {activeTab === 'dashboard' && (
                    <button 
                      onClick={handleSyncAll}
                      disabled={syncing}
                      className="px-8 py-4 gold-gradient rounded-2xl text-on-primary font-black text-[10px] uppercase tracking-[0.3em] flex items-center gap-3 active:scale-95 transition-all shadow-xl shadow-primary/10"
                    >
                      <span className={`material-symbols-outlined text-xl ${syncing ? 'animate-spin' : ''}`}>sync</span>
                      {syncing ? 'Syncing...' : 'Global Force Sync'}
                    </button>
                  )}
                  <div className="flex items-center gap-4 bg-white/5 px-6 py-3 rounded-2xl border border-white/5">
                    <span className="material-symbols-outlined text-secondary text-lg">verified_user</span>
                    <span className="text-[10px] font-black tracking-widest uppercase">Admin_Root</span>
                  </div>
                </div>
              </header>

              <div className="p-16 flex-1 flex flex-col gap-12">
                <AnimatePresence mode="wait">
                  {activeTab === 'dashboard' && (
                    <motion.div 
                      key="dashboard"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      className="flex flex-col gap-12"
                    >
                      {/* Dashboard Metrics */}
                      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-8">
                        {[
                          { label: 'Total Assets', value: '43,950', sub: '+124 this week', icon: 'show_chart', color: 'primary' },
                          { label: 'Ingestion Delta', value: '1.2s', sub: '99.8% precision', icon: 'cyclone', color: 'secondary' },
                          { label: 'Active Pipeline', value: pipelineJobs.filter(j => j.status === 'RUNNING').length || 'Idle', sub: 'Global Sync Ready', icon: 'cloud_sync', color: 'secondary' },
                          { label: 'Vault Security', value: 'Level 9', sub: 'Zero Trust Active', icon: 'lock', color: 'primary' },
                        ].map((card, i) => (
                          <div key={i} className="glass-panel p-8 rounded-[2.5rem] border border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-all group overflow-hidden relative">
                            <div className={`absolute top-0 right-0 w-32 h-32 bg-${card.color}/5 blur-3xl -mr-16 -mt-16 group-hover:bg-${card.color}/10 transition-all`}></div>
                            <div className="flex justify-between items-start mb-6">
                              <span className={`material-symbols-outlined text-${card.color} text-3xl font-light`}>{card.icon}</span>
                              <span className="text-[10px] text-slate-500 font-bold tracking-widest uppercase italic">Node {i+1}</span>
                            </div>
                            <h4 className="text-4xl font-headline font-black tracking-tighter mb-1">{card.value}</h4>
                            <p className="text-[10px] text-slate-400 font-bold tracking-[0.2em] uppercase mb-4">{card.label}</p>
                            <div className="text-[10px] font-black text-secondary tracking-widest uppercase flex items-center gap-2">
                              {card.sub}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Recent Activity Mini-Feed */}
                      <div className="glass-panel p-12 rounded-[3.5rem] border border-white/5 bg-white/[0.01] flex flex-col gap-8">
                        <div className="flex justify-between items-center">
                          <h4 className="text-2xl font-headline font-black uppercase tracking-tighter">Sovereign Audit Feed</h4>
                          <button onClick={() => setActiveTab('logs')} className="text-[10px] font-black text-primary tracking-widest uppercase hover:underline">View All Intelligence</button>
                        </div>
                        <div className="flex flex-col gap-4">
                          {logs.slice(0, 5).map(log => (
                            <div key={log.id} className="flex items-center gap-8 py-4 border-b border-white/5 last:border-0 opacity-80 hover:opacity-100 transition-opacity">
                              <span className="text-[10px] font-mono text-slate-500 w-32">{log.time}</span>
                              <span className={`text-[9px] font-black px-3 py-1 rounded-lg uppercase tracking-tighter ${log.level === 'SUCCESS' ? 'bg-secondary/10 text-secondary' : log.level === 'ERROR' ? 'bg-red-500/10 text-red-500' : 'bg-primary/10 text-primary'}`}>{log.level}</span>
                              <span className="text-sm font-bold uppercase tracking-tight flex-1 truncate">{log.msg}</span>
                              <span className="material-symbols-outlined text-slate-600 text-lg cursor-pointer hover:text-white">chevron_right</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {activeTab === 'health' && (
                    <motion.div 
                      key="health"
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                    >
                      <header className="mb-12 flex items-center justify-between">
                        <div className="space-y-1">
                          <p className="font-label text-xs font-semibold uppercase tracking-[0.3em] text-primary">Sovereign Performance</p>
                          <h2 className="font-headline text-4xl font-light tracking-tight">System <span className="font-extrabold italic text-primary">Health</span> Dashboard</h2>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="bg-surface-container-low border border-outline-variant/20 px-4 py-2 rounded-lg flex items-center gap-3">
                            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                            <span className="text-xs font-bold uppercase tracking-widest text-secondary">All Systems Nominal</span>
                          </div>
                          <button className="bg-primary/10 border border-primary/20 text-primary p-2 rounded-lg hover:bg-primary/20 transition-all">
                            <span className="material-symbols-outlined">refresh</span>
                          </button>
                        </div>
                      </header>

                      {/* High-Density Status Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                        {/* Network Latency Card */}
                        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
                          <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-outline">Network Latency</p>
                            <span className="material-symbols-outlined text-primary text-lg">router</span>
                          </div>
                          <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-secondary">42<span className="text-xl font-light opacity-60 ml-1">ms</span></p>
                            <div className="flex flex-col mb-1">
                              <span className="text-[9px] text-secondary font-bold">OPTIMAL</span>
                              <span className="text-[8px] text-outline">12 Nodes Sync</span>
                            </div>
                          </div>
                          <div className="absolute bottom-0 left-0 w-full h-1 bg-secondary/20">
                            <div className="h-full bg-secondary w-full"></div>
                          </div>
                        </div>

                        {/* API Status Card */}
                        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
                          <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-outline">System API</p>
                            <span className="material-symbols-outlined text-primary text-lg">api</span>
                          </div>
                          <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white">100<span className="text-xl font-light opacity-60 ml-1">%</span></p>
                            <div className="flex flex-col mb-1">
                              <span className="text-[9px] text-secondary font-bold">OPERATIONAL</span>
                              <span className="text-[8px] text-outline">v2.4.1 Production</span>
                            </div>
                          </div>
                          <div className="absolute bottom-0 left-0 w-full h-1 bg-secondary/20">
                            <div className="h-full bg-secondary w-full"></div>
                          </div>
                        </div>

                        {/* Ledger Status Card */}
                        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
                          <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-outline">Main Ledger</p>
                            <span className="material-symbols-outlined text-primary text-lg">database</span>
                          </div>
                          <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white">Active</p>
                            <div className="flex flex-col mb-1">
                              <span className="text-[9px] text-secondary font-bold">SYNCHRONIZED</span>
                              <span className="text-[8px] text-outline">PG Master Instance</span>
                            </div>
                          </div>
                          <div className="absolute bottom-0 left-0 w-full h-1 bg-secondary/20">
                            <div className="h-full bg-secondary w-full"></div>
                          </div>
                        </div>

                        {/* Security Card */}
                        <div className="glass-panel p-6 rounded-xl relative overflow-hidden border-l-4 border-l-secondary">
                          <div className="flex justify-between items-start mb-4">
                            <p className="font-label text-[10px] uppercase tracking-widest text-outline">Security Core</p>
                            <span className="material-symbols-outlined text-secondary text-lg" style={{fontVariationSettings: "'FILL' 1"}}>verified_user</span>
                          </div>
                          <div className="flex items-end gap-2">
                            <p className="font-headline text-4xl font-extrabold text-white">AES</p>
                            <div className="flex flex-col mb-1">
                              <span className="text-[9px] text-secondary font-bold">LOCKED</span>
                              <span className="text-[8px] text-outline">Zero Breaches</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Metrics Visualizer (Side-by-Side Large Charts) */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8 h-[250px]">
                        {/* CPU Utilization Chart */}
                        <div className="glass-panel p-8 rounded-2xl flex flex-col">
                          <div className="flex justify-between items-center mb-6">
                            <div>
                              <h3 className="font-label text-xs font-bold uppercase tracking-widest text-outline">CPU Utilization</h3>
                              <p className="font-headline text-3xl font-extrabold mt-1 text-primary">24.8<span className="text-sm font-light opacity-50 ml-1">%</span></p>
                            </div>
                            <div className="flex items-center gap-4 text-xs font-bold uppercase tracking-tighter">
                              <span className="text-secondary flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-secondary"></span> User</span>
                              <span className="text-primary flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary"></span> Kernel</span>
                            </div>
                          </div>
                          <div className="flex-1 w-full -mx-4 -mb-4">
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={[
                                { t: '00:00', v: 20 }, { t: '04:00', v: 45 }, { t: '08:00', v: 30 }, 
                                { t: '12:00', v: 70 }, { t: '16:00', v: 40 }, { t: '20:00', v: 55 }, { t: '23:59', v: 25 }
                              ]}>
                                <defs>
                                  <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#e9c349" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#e9c349" stopOpacity={0}/>
                                  </linearGradient>
                                </defs>
                                <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{fill: '#45464c', fontSize: 10}} />
                                <Tooltip contentStyle={{backgroundColor: '#1b2025', border: '1px solid rgba(233, 195, 73, 0.2)', borderRadius: '0.5rem', fontSize: '10px'}} />
                                <Area type="monotone" dataKey="v" stroke="#e9c349" fillOpacity={1} fill="url(#colorCpu)" strokeWidth={2} />
                              </AreaChart>
                            </ResponsiveContainer>
                          </div>
                        </div>

                        {/* Memory Usage Chart */}
                        <div className="glass-panel p-8 rounded-2xl flex flex-col">
                          <div className="flex justify-between items-center mb-6">
                            <div>
                              <h3 className="font-label text-xs font-bold uppercase tracking-widest text-outline">Memory Consumption</h3>
                              <p className="font-headline text-3xl font-extrabold mt-1 text-secondary">12.2<span className="text-sm font-light opacity-50 ml-1">GB</span></p>
                            </div>
                            <div className="flex items-center gap-4 text-xs font-bold uppercase tracking-tighter">
                              <span className="text-secondary">Used: 12.2 GB</span>
                              <span className="text-outline">Total: 64.0 GB</span>
                            </div>
                          </div>
                          <div className="flex-1 w-full -mx-4 -mb-4">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={[
                                { t: 'Mon', v: 8 }, { t: 'Tue', v: 10 }, { t: 'Wed', v: 12 }, 
                                { t: 'Thu', v: 9 }, { t: 'Fri', v: 14 }, { t: 'Sat', v: 7 }, { t: 'Sun', v: 6 }
                              ]}>
                                <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{fill: '#45464c', fontSize: 10}} />
                                <Tooltip contentStyle={{backgroundColor: '#1b2025', border: '1px solid rgba(102, 221, 139, 0.2)', borderRadius: '0.5rem', fontSize: '10px'}} />
                                <Bar dataKey="v" fill="#66dd8b" radius={[4, 4, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {activeTab === 'pipeline' && (
                    <motion.div 
                      key="pipeline"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="flex flex-col gap-8"
                    >
                      <div className="grid grid-cols-1 2xl:grid-cols-3 gap-12">
                        <div className="2xl:col-span-2 flex flex-col gap-8">
                          <div className="flex justify-between items-center mb-4">
                            <h4 className="text-3xl font-headline font-black tracking-tighter uppercase">Live Scheduling Engine</h4>
                            <div className="flex gap-4">
                              <span className="px-5 py-2 rounded-xl bg-white/5 text-slate-400 text-[10px] font-black uppercase tracking-widest border border-white/5 hover:bg-white/10 transition-colors cursor-pointer">Export Ledger</span>
                              <span className="px-5 py-2 rounded-xl bg-primary/20 text-primary text-[10px] font-black uppercase tracking-widest border border-primary/30 hover:bg-primary/30 transition-colors cursor-pointer">Emergency Halt</span>
                            </div>
                          </div>
                          <div className="flex flex-col gap-6">
                            {pipelineJobs.length > 0 ? pipelineJobs.map((job, idx) => (
                              <div key={idx} className="glass-panel p-10 rounded-[3rem] border border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-all flex flex-col gap-6 shadow-[0_32px_64px_rgba(0,0,0,0.3)]">
                                <div className="flex justify-between items-center">
                                  <div className="flex items-center gap-6">
                                    <div className={`w-4 h-4 rounded-full ${job.status === 'RUNNING' ? 'bg-primary animate-pulse shadow-[0_0_20px_#e9c349]' : job.status === 'COMPLETED' ? 'bg-secondary shadow-[0_0_15px_#66dd8b]' : 'bg-red-500'}`}></div>
                                    <div>
                                      <h5 className="text-xl font-black uppercase tracking-tighter italic">{job.job_name.replace(/_/g, ' ')}</h5>
                                      <span className="text-[9px] text-slate-500 font-black tracking-widest uppercase">Node_Protocol_{idx + 1}</span>
                                    </div>
                                  </div>
                                  <div className="text-right flex flex-col gap-1">
                                    <span className="text-[10px] font-black text-slate-400">STARTED: {new Date(job.started_at).toLocaleTimeString()}</span>
                                    {job.ended_at && <span className="text-[10px] font-black text-slate-500 self-end">FINISHED: {new Date(job.ended_at).toLocaleTimeString()}</span>}
                                  </div>
                                </div>
                                
                                <div className="flex flex-col gap-2">
                                  <div className="flex justify-between text-[10px] font-black uppercase tracking-[0.2em] mb-1">
                                    <span className="text-primary">{job.status}</span>
                                    <span className="text-slate-500">{job.progress_pct || 0}% Compute Path</span>
                                  </div>
                                  <div className="w-full bg-white/5 h-3 rounded-full overflow-hidden border border-white/5 p-[2px]">
                                    <motion.div 
                                      initial={{ width: 0 }}
                                      animate={{ width: `${job.progress_pct || 0}%` }}
                                      className={`h-full rounded-full ${job.status === 'RUNNING' ? 'gold-gradient' : 'bg-secondary'}`}
                                    ></motion.div>
                                  </div>
                                </div>

                                <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-500 mt-2">
                                  <div className="flex gap-8">
                                    <span className="flex items-center gap-2"><span className="material-symbols-outlined text-sm">cloud_upload</span> Records: {job.records_out} / {job.records_in || '?'}</span>
                                    <span className="flex items-center gap-2"><span className="material-symbols-outlined text-sm">timer</span> Duration: {job.duration_sec}s</span>
                                  </div>
                                  {job.status === 'RUNNING' && <span className="text-primary animate-pulse">Syncing from Sovereign API...</span>}
                                </div>
                                {job.error_msg && (
                                  <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-[9px] text-red-400 font-mono tracking-wider break-all">
                                    FATAL_ERROR: {job.error_msg}
                                  </div>
                                )}
                              </div>
                            )) : (
                              <div className="p-32 glass-panel rounded-[3rem] border border-dashed border-white/10 flex flex-col items-center gap-6 opacity-40">
                                <span className="material-symbols-outlined text-6xl">cloud_off</span>
                                <span className="uppercase tracking-[0.4em] font-black text-xs text-center">No Active Job Cycles Detected<br/><span className="text-[10px] mt-2 block opacity-60 italic">System Idle • Monitoring Continuous</span></span>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-col gap-8">
                          <h4 className="text-3xl font-headline font-black tracking-tighter uppercase">Direct Ingress</h4>
                          <div className="flex flex-col gap-4">
                            {[
                              { label: 'Weekly Price Backfill', endpoint: stockService.triggerBulkPriceSync },
                              { label: 'Global Screener Scrape', endpoint: stockService.triggerBulkScreenerScrape },
                              { label: 'Rating Engine Re-Compute', endpoint: stockService.triggerBulkRatingCompute },
                              { label: 'Indices Weightage Update', endpoint: () => handleBulkAction(() => Promise.resolve(), 'Indices Update') },
                              { label: 'Purge Transient Cache', endpoint: () => handleBulkAction(() => Promise.resolve(), 'Cache Purge') },
                            ].map((ctrl, i) => (
                              <button 
                                key={i} 
                                onClick={() => handleBulkAction(ctrl.endpoint, ctrl.label)}
                                className="w-full py-8 glass-panel border border-white/5 rounded-[2.5rem] text-[10px] font-black uppercase tracking-[0.4em] hover:bg-white/5 hover:border-primary/30 transition-all flex justify-between px-10 items-center group relative overflow-hidden"
                              >
                                <div className="absolute inset-0 bg-primary/5 translate-y-full group-hover:translate-y-0 transition-transform"></div>
                                <span className="relative z-10">{ctrl.label}</span>
                                <span className="material-symbols-outlined text-primary group-hover:translate-x-2 transition-transform relative z-10">bolt</span>
                              </button>
                            ))}
                          </div>

                          <div className="bg-primary/5 p-10 rounded-[3rem] border border-primary/20 mt-8 flex flex-col gap-6">
                            <h5 className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">Admin Advisory</h5>
                            <p className="text-xs text-slate-400 leading-relaxed uppercase tracking-wider font-bold italic">
                              \"Bulk operations consume high database transactional throughput. Initiate only during low-traffic maintenance windows.\"
                            </p>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {activeTab === 'assets' && (
                    <motion.div 
                      key="assets"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      className="flex flex-col gap-8"
                    >
                      <div className="flex justify-between items-center gap-12">
                         <div className="flex-1 max-w-2xl relative group">
                            <span className="material-symbols-outlined absolute left-6 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-primary transition-colors">search</span>
                            <input 
                              type="text"
                              value={searchQuery}
                              onChange={(e) => setSearchQuery(e.target.value)}
                              placeholder="SEARCH GLOBAL ASSET LEDGER..."
                              className="w-full pl-16 pr-8 py-5 bg-white/5 border border-white/5 rounded-2xl text-xs font-black uppercase tracking-widest focus:outline-none focus:border-primary focus:bg-white/10 transition-all"
                            />
                         </div>
                         <div className="flex gap-4">
                            <div className="bg-white/5 p-1 flex rounded-xl border border-white/5">
                                <button onClick={() => setAssetType('stocks')} className={`px-6 py-3 rounded-lg text-[10px] uppercase font-black tracking-widest transition-all ${assetType === 'stocks' ? 'bg-primary text-black shadow-[0_0_15px_rgba(233,195,73,0.3)]' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}>Stocks</button>
                                <button onClick={() => setAssetType('mf')} className={`px-6 py-3 rounded-lg text-[10px] uppercase font-black tracking-widest transition-all ${assetType === 'mf' ? 'bg-primary text-black shadow-[0_0_15px_rgba(233,195,73,0.3)]' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}>Mutual Funds</button>
                            </div>
                            <button onClick={() => setAssetModal({ isOpen: true, data: null, mode: 'create' })} className="px-8 py-4 bg-primary text-black rounded-xl text-[10px] font-black uppercase tracking-widest hover:brightness-110 active:scale-95 transition-all flex items-center gap-3 shadow-[0_0_20px_rgba(233,195,73,0.2)]">
                              <span className="material-symbols-outlined text-lg">add</span>
                              Add Asset
                            </button>
                         </div>
                      </div>

                      <div className="glass-panel overflow-hidden border border-white/5 rounded-[3rem] bg-white/[0.01]">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="bg-white/5">
                              <th className="px-10 py-6 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">Asset</th>
                              <th className="px-10 py-6 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 text-right">Identifier</th>
                              <th className="px-10 py-6 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 text-right">Status</th>
                              <th className="px-10 py-6 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 text-center">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {loadingAssets ? (
                              <tr>
                                <td colSpan="4" className="px-10 py-20 text-center opacity-40 italic uppercase tracking-widest font-black animate-pulse">Accessing Encrypted Database...</td>
                              </tr>
                            ) : assetsData.length > 0 ? assetsData.map((asset, i) => {
                              const isStock = assetType === 'stocks';
                              const id = isStock ? asset.symbol : asset.scheme_code;
                              const name = isStock ? asset.name : asset.scheme_name;
                              return (
                              <tr key={i} className="hover:bg-white/5 transition-all group">
                                <td className="px-10 py-6">
                                  <div className="flex items-center gap-6">
                                    <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center text-primary font-black group-hover:bg-primary group-hover:text-black transition-all">
                                      {id.toString().substring(0, 1)}
                                    </div>
                                    <div>
                                      <h6 className="text-sm font-black uppercase tracking-tighter">{id}</h6>
                                      <p className="text-[10px] text-slate-500 font-bold uppercase truncate max-w-[200px]">{name}</p>
                                    </div>
                                  </div>
                                </td>
                                <td className="px-10 py-6 text-right font-mono text-xs text-secondary">
                                  {isStock ? 'EQ' : 'MF'}
                                </td>
                                <td className="px-10 py-6 text-right">
                                  <span className="px-4 py-1 rounded-lg bg-secondary/10 text-secondary text-[9px] font-black uppercase tracking-widest border border-secondary/20">Synced</span>
                                </td>
                                <td className="px-10 py-6">
                                  <div className="flex justify-center gap-4">
                                    {isStock && (
                                     <>
                                      <button 
                                        onClick={() => handleSingleStockSync(id, stockService.triggerDeepPriceSync, 'Price history')}
                                        className="p-3 bg-white/5 rounded-xl hover:bg-primary hover:text-black transition-all group/btn flex items-center gap-2"
                                        title="Sync Prices"
                                      >
                                        <span className="material-symbols-outlined text-lg">trending_up</span>
                                      </button>
                                      <button 
                                        onClick={() => handleSingleStockSync(id, stockService.triggerScreenerScrape, 'Fundamentals')}
                                        className="p-3 bg-white/5 rounded-xl hover:bg-primary hover:text-black transition-all group/btn"
                                        title="Sync Fundamentals"
                                      >
                                        <span className="material-symbols-outlined text-lg">analytics</span>
                                      </button>
                                     </>
                                    )}
                                    <button 
                                      onClick={() => setAssetModal({ isOpen: true, data: asset, mode: 'edit' })} 
                                      className="p-3 bg-white/5 rounded-xl hover:bg-primary hover:text-black transition-all"
                                      title="Edit Record"
                                    >
                                      <span className="material-symbols-outlined text-lg">edit</span>
                                    </button>
                                    <button 
                                      onClick={() => handleDeleteAsset(id)}
                                      className="p-3 bg-white/5 rounded-xl hover:bg-red-500 hover:text-white transition-all"
                                      title="Purge Record"
                                    >
                                      <span className="material-symbols-outlined text-lg">delete</span>
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )}) : (
                              <tr>
                                <td colSpan="4" className="px-10 py-20 text-center opacity-40 italic uppercase tracking-widest font-black italic">No Matching Artifacts in the Ledger</td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </motion.div>
                  )}

                  {activeTab === 'logs' && (
                    <motion.div 
                      key="logs"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex flex-col gap-8"
                    >
                      <div className="flex justify-between items-center mb-4">
                        <h4 className="text-3xl font-headline font-black tracking-tighter uppercase">Audit Archive</h4>
                        <button onClick={() => setLogs([])} className="px-6 py-2 rounded-xl bg-red-500/10 text-red-500 text-[10px] font-black uppercase tracking-widest border border-red-500/20 hover:bg-red-500 hover:text-white transition-all">Clear Session History</button>
                      </div>
                      
                      <div className="glass-panel p-12 rounded-[3.5rem] border border-white/5 bg-white/[0.01] min-h-[700px] flex flex-col gap-4 font-mono">
                        {logs.map(log => (
                          <div key={log.id} className="flex gap-10 items-start p-6 hover:bg-white/5 rounded-2xl transition-all border border-transparent hover:border-white/5 group">
                             <div className="flex flex-col gap-2 w-48 shrink-0">
                               <span className="text-[10px] text-slate-500 font-bold tracking-widest uppercase italic group-hover:text-primary transition-colors">{log.level}</span>
                               <span className="text-[10px] text-slate-600 italic">[{log.time}]</span>
                             </div>
                             <div className="flex-1 text-sm font-bold uppercase tracking-tight text-slate-300 group-hover:text-white transition-colors leading-relaxed">
                                {'>'} {log.msg}
                                {log.level === 'ERROR' && <span className="ml-4 px-2 py-0.5 bg-red-500/20 text-red-400 text-[9px] rounded">SECURITY_INTERRUPT</span>}
                             </div>
                             <span className="material-symbols-outlined text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity">terminal</span>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Asset CRUD Modal */}
              <AnimatePresence>
                {assetModal.isOpen && (
                  <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#0a0f12]/90 backdrop-blur-md">
                    <motion.div 
                      initial={{ opacity: 0, scale: 0.9, y: 20 }} 
                      animate={{ opacity: 1, scale: 1, y: 0 }} 
                      exit={{ opacity: 0, scale: 0.9, y: 20 }}
                      className="w-full max-w-lg glass-panel rounded-[2rem] border border-white/10 p-10 relative overflow-hidden bg-white/[0.02]"
                    >
                      <button onClick={() => setAssetModal({ isOpen: false, data: null, mode: 'create' })} className="absolute top-8 right-8 text-slate-500 hover:text-white transition-colors">
                        <span className="material-symbols-outlined text-3xl font-thin">close</span>
                      </button>
                      <div className="mb-10">
                        <h2 className="text-2xl font-headline font-black uppercase tracking-tighter mb-2">
                          {assetModal.mode === 'create' ? 'Provision' : 'Mutate'} {assetType === 'stocks' ? 'Equity Node' : 'Vault Protocol'}
                        </h2>
                        <p className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.3em]">
                          Enter required cryptographic identifiers
                        </p>
                      </div>
                      <form onSubmit={(e) => {
                        e.preventDefault();
                        const target = e.target;
                        let formData = {};
                        if (assetType === 'stocks') {
                          formData = { symbol: target.symbol.value, name: target.name.value };
                        } else {
                          formData = { scheme_code: target.scheme_code.value, scheme_name: target.name.value };
                        }
                        handleSaveAsset(formData);
                      }} className="flex flex-col gap-6">
                        <div className="flex flex-col gap-2">
                          <label className="text-[9px] font-black uppercase tracking-[0.4em] text-slate-500">
                            {assetType === 'stocks' ? 'Ticker Symbol' : 'Scheme Code'}
                          </label>
                          <input 
                            name={assetType === 'stocks' ? 'symbol' : 'scheme_code'} 
                            defaultValue={assetModal.data ? (assetType === 'stocks' ? assetModal.data.symbol : assetModal.data.scheme_code) : ''} 
                            required 
                            disabled={assetModal.mode === 'edit'}
                            className="w-full px-6 py-4 bg-white/5 border border-white/5 rounded-2xl text-sm font-black uppercase tracking-widest focus:outline-none focus:border-primary focus:bg-white/10 transition-all font-mono disabled:opacity-50"
                          />
                        </div>
                        <div className="flex flex-col gap-2">
                          <label className="text-[9px] font-black uppercase tracking-[0.4em] text-slate-500">
                            {assetType === 'stocks' ? 'Corporation Name' : 'Fund Designation'}
                          </label>
                          <input 
                            name="name" 
                            defaultValue={assetModal.data ? (assetType === 'stocks' ? assetModal.data.name : assetModal.data.scheme_name) : ''} 
                            required 
                            className="w-full px-6 py-4 bg-white/5 border border-white/5 rounded-2xl text-sm font-black uppercase tracking-widest focus:outline-none focus:border-primary focus:bg-white/10 transition-all"
                          />
                        </div>
                        <button type="submit" className="mt-6 px-8 py-5 bg-primary text-black rounded-2xl text-xs font-black uppercase tracking-[0.3em] hover:brightness-110 active:scale-95 transition-all shadow-[0_0_30px_rgba(233,195,73,0.3)]">
                          {assetModal.mode === 'create' ? 'Initialize' : 'Commit Overlay'}
                        </button>
                      </form>
                    </motion.div>
                  </div>
                )}
              </AnimatePresence>

              <footer className="px-16 py-12 border-t border-white/5 bg-black/20 flex justify-between items-center">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.4em]">
                  Sovereign Core Control • Layer 9 Verified
                </div>
                <div className="flex items-center gap-8 opacity-40">
                  <span className="text-[10px] font-black tracking-widest uppercase">System Stability: 99.98%</span>
                  <span className="material-symbols-outlined text-sm">settings_input_hdmi</span>
                </div>
              </footer>
            </main>
        </div>
    );
};

export default Admin;
