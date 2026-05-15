import apiClient from '../apiClient';

const agentService = {
    createSession: async ({ context_type = 'general', context_id = null, title = null } = {}) => {
        const response = await apiClient.post('/agent/sessions', { context_type, context_id, title });
        return response.data;  // { session_id, title }
    },

    listSessions: async () => {
        const response = await apiClient.get('/agent/sessions');
        return response.data;  // AgentSession[]
    },

    getMessages: async (sessionId) => {
        const response = await apiClient.get(`/agent/sessions/${sessionId}/messages`);
        return response.data;  // AgentMessage[]
    },

    chat: async (sessionId, message) => {
        const response = await apiClient.post(`/agent/sessions/${sessionId}/chat`, { message });
        return response.data;  // { reply, session_id }
    },

    getMemory: async () => {
        const response = await apiClient.get('/agent/memory');
        return response.data;  // { key: { value, confidence } }
    },
};

export default agentService;
