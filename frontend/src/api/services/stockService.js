import apiClient from '../apiClient';

const stockService = {
  getStocks: async (params) => {
    const response = await apiClient.get('/stocks', { params });
    return response.data;
  },

  searchStocks: async (q) => {
    const response = await apiClient.get('/stocks/search', { params: { q } });
    return response.data;
  },

  getStockDetail: async (symbol) => {
    const response = await apiClient.get(`/stocks/${symbol}`);
    return response.data;
  },

  getPriceHistory: async (symbol, params) => {
    const response = await apiClient.get(`/stocks/${symbol}/price`, { params });
    return response.data;
  },

  getFundamentals: async (symbol, params) => {
    const response = await apiClient.get(`/stocks/${symbol}/fundamentals`, { params });
    return response.data;
  },

  getShareholding: async (symbol, params) => {
    const response = await apiClient.get(`/stocks/${symbol}/shareholding`, { params });
    return response.data;
  },

  getRatios: async (symbol) => {
    const response = await apiClient.get(`/stocks/${symbol}/ratios`);
    return response.data;
  },

  getTechnicals: async (symbol, timeframe = "1d") => {
    const response = await apiClient.get(`/stocks/${symbol}/technicals`, { params: { timeframe } });
    return response.data;
  },

  getPatterns: async (symbol) => {
    const response = await apiClient.get(`/stocks/${symbol}/patterns`);
    return response.data;
  },

  getRating: async (symbol) => {
    const response = await apiClient.get(`/stocks/${symbol}/rating`);
    return response.data;
  },

  getScreener: async (filters) => {
    const response = await apiClient.get('/screener', { params: filters });
    return response.data;
  },

  getCompare: async (symbols) => {
    const response = await apiClient.get('/compare', { params: { symbols: symbols.join(',') } });
    return response.data;
  },
};

export default stockService;
