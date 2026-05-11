import apiClient from '../apiClient';

const agentService = {
  // Stock analysis
  triggerStockAnalysis: (symbol, force = false) =>
    apiClient.post(`/agents/stock/${symbol}/analyse`, null, { params: { force } }).then(r => r.data),

  getStockAnalysis: (symbol) =>
    apiClient.get(`/agents/stock/${symbol}/analysis`).then(r => r.data),

  // Stock recommendation
  triggerStockRecommendation: (symbol, force = false) =>
    apiClient.post(`/agents/stock/${symbol}/recommend`, null, { params: { force } }).then(r => r.data),

  getStockRecommendation: (symbol) =>
    apiClient.get(`/agents/stock/${symbol}/recommendation`).then(r => r.data),

  // Fund analysis
  triggerFundAnalysis: (schemeCode, force = false) =>
    apiClient.post(`/agents/fund/${schemeCode}/analyse`, null, { params: { force } }).then(r => r.data),

  getFundAnalysis: (schemeCode) =>
    apiClient.get(`/agents/fund/${schemeCode}/analysis`).then(r => r.data),

  // Fund comparison
  triggerFundComparison: (fundCodes) =>
    apiClient.post('/agents/fund/compare', { fund_codes: fundCodes }).then(r => r.data),

  getFundComparison: (comparisonId) =>
    apiClient.get(`/agents/fund/compare/${comparisonId}`).then(r => r.data),
};

export default agentService;
