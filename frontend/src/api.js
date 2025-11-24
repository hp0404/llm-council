/**
 * API client for the LLM Council backend.
 */

// Dynamically determine API base URL
// If accessing via remote IP, use that IP for the backend too
// If accessing via localhost, use localhost for the backend
const getApiBase = () => {
  if (import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }
  
  // Use the same hostname as the frontend, but port 5174 for backend
  const hostname = window.location.hostname;
  const protocol = window.location.protocol;
  return `${protocol}//${hostname}:5174`;
};

const API_BASE = getApiBase();

// Auth token management - uses environment variable for localStorage key
const AUTH_TOKEN_KEY = import.meta.env.VITE_AUTH_TOKEN_KEY || 'llm_council_auth_token';

export const auth = {
  getToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  },
  
  setToken(token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  },
  
  clearToken() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  },
  
  /**
   * Verify token by attempting to use it with a real API call.
   * This is more secure than having a dedicated verify endpoint which
   * could be abused for brute-force attacks.
   */
  async verifyToken(token) {
    try {
      const response = await fetch(`${API_BASE}/api/conversations`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Auth-Token': token,
        },
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  },
};

function getAuthHeaders() {
  const token = auth.getToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { 'X-Auth-Token': token }),
  };
}

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        headers: getAuthHeaders(),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * Get list of available models from OpenRouter.
   */
  async getAvailableModels() {
    const response = await fetch(`${API_BASE}/api/models`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to fetch models');
    }
    return response.json();
  },

  /**
   * Get the model configuration for a conversation.
   */
  async getConversationModels(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/models`,
      {
        headers: getAuthHeaders(),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to get conversation models');
    }
    return response.json();
  },

  /**
   * Update the model configuration for a conversation.
   */
  async updateConversationModels(conversationId, councilModels, chairmanModel) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/models`,
      {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          council_models: councilModels,
          chairman_model: chairmanModel,
        }),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        auth.clearToken();
        throw new Error('Authentication failed');
      }
      throw new Error('Failed to update conversation models');
    }
    return response.json();
  },
};
