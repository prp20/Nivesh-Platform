import { useState } from 'react';

/**
 * Shows when a proxy response has `_offline: true`.
 * Usage:
 *   const [data, setData] = useState(null);
 *   <OfflineBanner isOffline={data?._offline === true} />
 */
const OfflineBanner = ({ isOffline }) => {
    const [dismissed, setDismissed] = useState(false);

    if (!isOffline || dismissed) return null;

    return (
        <div className="w-full px-4 py-2 bg-amber-900/30 border border-amber-500/20 rounded-xl flex items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-400 text-[16px]">wifi_off</span>
                <span className="text-[11px] font-semibold text-amber-300">
                    Server offline — showing cached data. Connect to refresh.
                </span>
            </div>
            <button
                onClick={() => setDismissed(true)}
                className="text-amber-500 hover:text-amber-300 transition-colors shrink-0"
            >
                <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
        </div>
    );
};

export default OfflineBanner;
