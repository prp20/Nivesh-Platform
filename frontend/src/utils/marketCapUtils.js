/**
 * Unified mapping for Market Cap categories.
 * Maps various raw database strings to consistent, premium labels.
 */
const MARKET_CAP_MAP = {
    // Large Cap variations
    "NIFTY 100": "Large Cap",
    "largecap": "Large Cap",
    "LARGE CAP": "Large Cap",
    "LargeCap": "Large Cap",

    // Mid Cap variations
    "NIFTY MIDCAP 150": "Mid Cap",
    "midcap": "Mid Cap",
    "MID CAP": "Mid Cap",
    "MidCap": "Mid Cap",

    // Small Cap variations
    "NIFTY SMALLCAP 250": "Small Cap",
    "smallcap": "Small Cap",
    "SMALL CAP": "Small Cap",
    "SmallCap": "Small Cap"
};

/**
 * Normalizes a raw market cap string into a standard label.
 * @param {string} raw - The raw value from the API/Database.
 * @returns {string} - The unified label ("Large Cap", "Mid Cap", "Small Cap") or the original value.
 */
export const normalizeMarketCap = (raw) => {
    if (!raw) return "—";
    return MARKET_CAP_MAP[raw] || raw;
};

/**
 * Returns the relevant raw database keys for a unified label.
 * Used for backend filtering.
 */
export const getMarketCapRawValues = (label) => {
    return Object.keys(MARKET_CAP_MAP).filter(key => MARKET_CAP_MAP[key] === label);
};
