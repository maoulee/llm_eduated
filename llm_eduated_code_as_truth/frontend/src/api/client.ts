const API_BASE = '/api';

export interface Session {
  id: string;
  mode: 'compose' | 'knowledge_point';
  state: 'idle' | 'collecting' | 'blueprint_ready' | 'annotating' | 'approved' | 'generating' | 'complete' | 'error';
  created_at: string;
  updated_at: string;
  title?: string;
  blueprint_id?: string;
  collected_params?: Record<string, unknown>;
  error?: string;
}

export interface MessageResponse {
  response: string;
  state: Session['state'];
  mode: Session['mode'];
  blueprint_id?: string;
  collected_params?: Record<string, unknown>;
  error?: string;
}

export interface Outline {
  outline_md: string;
}

export interface SlotStatus {
  slot_id: string;
  status: 'pending' | 'generating' | 'review' | 'complete' | 'error';
  output_file?: string;
  error_message?: string;
}

export interface SSEEvent {
  type: 'state_change' | 'slot_update' | 'generation_complete' | 'error';
  data: Record<string, unknown>;
}

class APIClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE;
  }

  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getSessions(): Promise<Session[]> {
    return this.request<Session[]>('/sessions');
  }

  async getSession(id: string): Promise<Session> {
    return this.request<Session>(`/sessions/${id}`);
  }

  async createSession(mode: 'compose' | 'knowledge_point'): Promise<Session> {
    return this.request('/sessions', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  }

  async deleteSession(id: string): Promise<void> {
    await this.request(`/sessions/${id}`, {
      method: 'DELETE',
    });
  }

  async sendMessage(sessionId: string, message: string): Promise<MessageResponse> {
    return this.request<MessageResponse>(`/sessions/${sessionId}/message`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  async getOutline(sessionId: string): Promise<Outline> {
    return this.request<Outline>(`/sessions/${sessionId}/outline`);
  }

  async saveOutline(sessionId: string, outlineMd: string): Promise<void> {
    await this.request(`/sessions/${sessionId}/outline`, {
      method: 'PUT',
      body: JSON.stringify({ outline_md: outlineMd }),
    });
  }

  async startGeneration(sessionId: string): Promise<void> {
    await this.request(`/sessions/${sessionId}/generate`, {
      method: 'POST',
    });
  }

  async getArtifact(runId: string, type: string, slotId?: string): Promise<string> {
    const params = new URLSearchParams();
    if (slotId) params.set('slot_id', slotId);
    const url = `/runs/${runId}/artifacts/${type}?${params.toString()}`;
    const response = await fetch(`${this.baseUrl}${url}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch artifact: ${response.statusText}`);
    }
    return response.text();
  }

  subscribeToEvents(sessionId: string, callbacks: {
    onMessage?: (event: SSEEvent) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
  }): EventSource {
    const url = `${this.baseUrl}/sessions/${sessionId}/events`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        callbacks.onMessage?.(data);
      } catch (err) {
        callbacks.onError?.(err as Error);
      }
    };

    eventSource.onerror = () => {
      callbacks.onError?.(new Error('SSE connection error'));
    };

    return eventSource;
  }
}

export const api = new APIClient();
