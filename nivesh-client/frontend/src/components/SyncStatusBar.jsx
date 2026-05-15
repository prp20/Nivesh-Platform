import { useState, useEffect } from 'react';
import statusService from '../api/services/statusService';

function formatRelativeTime(isoString) {
    if (!isoString) return 'never';
    const diff = Date.now() - new Date(isoString).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

const SyncStatusBar = () => {
    const [status, setStatus] = useState(null);
    const [clientError, setClientError] = useState(false);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const data = await statusService.get();
                setStatus(data);
                setClientError(false);
            } catch {
                setClientError(true);
            }
        };

        fetchStatus();
        const id = setInterval(fetchStatus, 60_000);
        return () => clearInterval(id);
    }, []);

    if (clientError) {
        return (
            <div className="w-full px-4 py-1.5 bg-red-900/30 border-b border-red-500/20 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                <span className="text-[10px] font-semibold text-red-400 uppercase tracking-widest">
                    Client not reachable on port 8001
                </span>
            </div>
        );
    }

    if (!status) return null;

    const lastSync = formatRelativeTime(status.last_connected_at);
    const isOnline = status.is_online;

    return (
        <div className={`w-full px-4 py-1.5 border-b flex items-center gap-2
            ${isOnline
                ? 'bg-emerald-900/20 border-emerald-500/20'
                : 'bg-amber-900/20 border-amber-500/20'
            }`}
        >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0
                ${isOnline ? 'bg-emerald-400' : 'bg-amber-400'}`}
            />
            <span className={`text-[10px] font-semibold uppercase tracking-widest
                ${isOnline ? 'text-emerald-400' : 'text-amber-400'}`}
            >
                {isOnline
                    ? `Connected · Last sync ${lastSync} · ${status.cached_resources} cached`
                    : `Offline — showing cached data · last sync ${lastSync}`
                }
            </span>
        </div>
    );
};

export default SyncStatusBar;
