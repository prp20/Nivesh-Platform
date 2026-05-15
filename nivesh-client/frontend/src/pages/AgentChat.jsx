import { useState, useEffect, useRef } from 'react';
import agentService from '../api/services/agentService';

const SUGGESTIONS = [
    'Analyse RELIANCE',
    'Compare top large cap funds',
    'How is my portfolio doing?',
    'Show me oversold Nifty50 stocks',
];

const AgentChat = () => {
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [initError, setInitError] = useState(null);
    const bottomRef = useRef(null);

    // Create or resume the most recent session on mount
    useEffect(() => {
        const init = async () => {
            try {
                const sessions = await agentService.listSessions();
                if (sessions.length > 0) {
                    const s = sessions[0];
                    setSessionId(s.id);
                    const msgs = await agentService.getMessages(s.id);
                    setMessages(msgs);
                } else {
                    const s = await agentService.createSession({ context_type: 'general' });
                    setSessionId(s.session_id);
                }
            } catch (err) {
                setInitError('Could not connect to the agent. Is the client running on port 8001?');
                console.error('[AgentChat] Init failed:', err);
            }
        };
        init();
    }, []);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const handleSend = async (text) => {
        const msg = (text ?? input).trim();
        if (!msg || !sessionId || loading) return;
        setInput('');
        setLoading(true);

        // Optimistic user message
        const optimistic = {
            id: `opt-${Date.now()}`,
            role: 'user',
            content_text: msg,
            created_at: new Date().toISOString(),
        };
        setMessages(m => [...m, optimistic]);

        try {
            const resp = await agentService.chat(sessionId, msg);
            const assistantMsg = {
                id: `resp-${Date.now()}`,
                role: 'assistant',
                content_text: resp.reply,
                created_at: new Date().toISOString(),
            };
            setMessages(m => [...m, assistantMsg]);
        } catch {
            setMessages(m => [...m, {
                id: `err-${Date.now()}`,
                role: 'assistant',
                content_text: 'Something went wrong. Please try again.',
                created_at: new Date().toISOString(),
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleNewSession = async () => {
        try {
            const s = await agentService.createSession({ context_type: 'general' });
            setSessionId(s.session_id);
            setMessages([]);
        } catch (err) {
            console.error('[AgentChat] New session failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0f12] flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#e9c349] to-[#b8942e] flex items-center justify-center">
                        <span className="material-symbols-outlined text-[#0f1419] text-[16px]">smart_toy</span>
                    </div>
                    <div>
                        <h1 className="text-base font-bold text-white">Nivesh Agent</h1>
                        <span className="text-[9px] font-black uppercase tracking-widest text-amber-500/70">
                            Phase 6 — LLM not yet connected
                        </span>
                    </div>
                </div>
                <button
                    onClick={handleNewSession}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:border-white/20 transition-colors"
                >
                    <span className="material-symbols-outlined text-[14px]">add</span>
                    New
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4 max-w-3xl w-full mx-auto">
                {initError ? (
                    <div className="text-center py-8">
                        <span className="material-symbols-outlined text-4xl text-red-700 font-thin">error</span>
                        <p className="text-red-400 text-sm mt-3">{initError}</p>
                    </div>
                ) : messages.length === 0 && !loading ? (
                    <div className="flex flex-col items-center gap-6 py-12">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#e9c349]/20 to-[#b8942e]/20 flex items-center justify-center">
                            <span className="material-symbols-outlined text-[#e9c349] text-3xl font-thin">smart_toy</span>
                        </div>
                        <p className="text-slate-400 text-sm text-center max-w-sm">
                            Ask about a stock, mutual fund, or your portfolio.
                        </p>
                        <div className="flex flex-wrap gap-2 justify-center">
                            {SUGGESTIONS.map(s => (
                                <button
                                    key={s}
                                    onClick={() => handleSend(s)}
                                    className="px-3 py-1.5 rounded-full border border-white/10 text-[11px] text-slate-400 hover:text-white hover:border-white/20 transition-all"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map(msg => (
                        <div key={msg.id}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm
                                ${msg.role === 'user'
                                    ? 'bg-[#D4AF37]/15 border border-[#D4AF37]/20 text-white rounded-br-sm'
                                    : 'bg-[#161c22] border border-white/8 text-slate-200 rounded-bl-sm'
                                }`}>
                                {msg.content_text}
                            </div>
                        </div>
                    ))
                )}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-[#161c22] border border-white/8 rounded-2xl rounded-bl-sm px-4 py-3">
                            <div className="flex gap-1.5 items-center">
                                {[0, 1, 2].map(i => (
                                    <span key={i}
                                        className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                                        style={{ animationDelay: `${i * 0.15}s` }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div className="border-t border-white/5 px-4 py-4">
                <form
                    onSubmit={e => { e.preventDefault(); handleSend(); }}
                    className="max-w-3xl mx-auto flex gap-3"
                >
                    <input
                        type="text"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        placeholder="Ask about stocks, funds, or your portfolio..."
                        disabled={loading || !sessionId}
                        className="flex-1 bg-[#161c22] border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#D4AF37]/40 transition-colors disabled:opacity-50"
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim() || !sessionId}
                        className="px-5 py-3 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest disabled:opacity-40"
                    >
                        Send
                    </button>
                </form>
            </div>
        </div>
    );
};

export default AgentChat;
