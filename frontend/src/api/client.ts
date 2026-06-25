/**
 * API client — V2-interact adapter.
 *
 * The frontend speaks a compose-style contract (Session / MessageResponse / Outline /
 * SlotStatus / SSEEvent). The REAL backend is the V2 interact system at /api/v2/interact/*
 * (turn / draft / confirm_handoff / pipeline-progress / display-result / events), which
 * drives trigger_generation (the team pipeline). This client preserves the frontend's
 * method names/shapes and adapts V2 underneath, so useSession/SessionView/components
 * need minimal changes.
 */
const API_BASE = '/api';
const V2 = '/v2/interact';

// Provider used throughout this project (online GLM-5.2 via /api/anthropic).
const PROVIDER = 'glm5.2_anthropic';

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
  type: 'state_change' | 'slot_update' | 'generation_complete' | 'generation_error' | 'error';
  data: Record<string, unknown>;
}

// V2 backend shapes (subset we consume).
interface V2Session {
  session_id: string;
  state: string; // collecting | reviewing | confirmed | completed | ...
  scenario?: string;
  title?: string;
  created_at?: number;
  turn_count?: number;
}
interface V2TurnResponse {
  response_text: string;
  session_state: 'collecting' | 'reviewing' | 'confirmed';
  has_draft: boolean;
  has_result: boolean;
  files_written?: string[];
}
interface V2Draft {
  draft_id: string;
  title?: string;
  raw_md?: string;
}
interface PipelineProgress {
  status?: string;
  total_slots?: number;
  completed?: number;
  failed?: number;
  is_done?: boolean;
  slots?: Record<string, { status?: string; stage?: string; label?: string }>;
  error?: string | null;
}
interface DisplayResult {
  status?: string;
  questions?: Array<{ slot_id: string; title?: string; stem?: string; options?: string[]; answer?: string; explanation?: string }>;
  paper_markdown?: string;
}

/** Map V2 session_state → frontend Session.state. */
function mapState(s: string | undefined): Session['state'] {
  switch (s) {
    case 'collecting': return 'collecting';
    case 'reviewing': return 'blueprint_ready';
    case 'confirmed':
    case 'generating': return 'generating';
    case 'completed':
    case 'complete': return 'complete';
    case 'error': return 'error';
    default: return 'idle';
  }
}

/** Map V2 pipeline slot status → frontend SlotStatus.status. */
const SLOT_STATUS_MAP: Record<string, SlotStatus['status']> = {
  waiting: 'pending',
  generating: 'generating',
  completed: 'complete',
  failed: 'error',
};

class APIClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    });
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }
    return response.json();
  }

  private mapSession(s: V2Session, mode: Session['mode'] = 'compose'): Session {
    return {
      id: s.session_id,
      mode,
      state: mapState(s.state),
      created_at: s.created_at ? new Date(s.created_at * 1000).toISOString() : new Date().toISOString(),
      updated_at: new Date().toISOString(),
      title: s.title,
    };
  }

  // ── Session lifecycle ──

  async createSession(mode: 'compose' | 'knowledge_point'): Promise<Session> {
    const data = await this.request<V2Session>(`${V2}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ provider: PROVIDER, thinking: true, ui_mode: 'api', user_id: 'default' }),
    });
    return this.mapSession(data, mode);
  }

  async getSessions(): Promise<Session[]> {
    const data = await this.request<V2Session[]>(`${V2}/sessions`);
    return data.map((s) => this.mapSession(s));
  }

  async getSession(id: string): Promise<Session> {
    const data = await this.request<V2Session>(`${V2}/sessions/${id}`);
    return this.mapSession(data);
  }

  async deleteSession(id: string): Promise<void> {
    await this.request(`${V2}/sessions/${id}`, { method: 'DELETE' });
  }

  // ── Chat (turn-driven) ──

  /** Normal discussion turn. Maps V2 InteractTurnResponse → MessageResponse. */
  async sendMessage(sessionId: string, message: string): Promise<MessageResponse> {
    const data = await this.request<V2TurnResponse>(`${V2}/sessions/${sessionId}/turn`, {
      method: 'POST',
      body: JSON.stringify({ message, intent: 'discuss' }),
    });
    return {
      response: data.response_text,
      state: mapState(data.session_state),
      mode: 'compose',
      // session is the "run" in V2 — use it as blueprint_id for artifact fetches.
      blueprint_id: data.has_result ? sessionId : undefined,
      collected_params: { has_draft: data.has_draft, has_result: data.has_result },
    };
  }

  /** Confirm the handoff → triggers the real pipeline (fire-and-forget). */
  async startGeneration(sessionId: string): Promise<{ status: string }> {
    await this.request(`${V2}/sessions/${sessionId}/turn`, {
      method: 'POST',
      body: JSON.stringify({ message: '确认出题', intent: 'confirm_handoff' }),
    });
    return { status: 'started' };
  }

  // ── Draft / outline ──

  async getOutline(sessionId: string): Promise<Outline> {
    // V2 draft is structured; we surface its raw_md as the outline text.
    try {
      const data = await this.request<V2Draft>(`${V2}/sessions/${sessionId}/draft`);
      return { outline_md: data.raw_md || '' };
    } catch {
      return { outline_md: '' };
    }
  }

  async saveOutline(_sessionId: string, _outlineMd: string): Promise<void> {
    // V2 revision is turn-driven (chat), not a direct md write. No-op here;
    // teachers revise by discussing further before confirming.
    return;
  }

  // ── Progress + artifacts ──

  async getPipelineProgress(sessionId: string): Promise<PipelineProgress | null> {
    try {
      return await this.request<PipelineProgress>(`${V2}/sessions/${sessionId}/pipeline-progress`);
    } catch {
      return null;
    }
  }

  async getDisplayResult(sessionId: string): Promise<DisplayResult> {
    try {
      return await this.request<DisplayResult>(`${V2}/sessions/${sessionId}/display-result`);
    } catch {
      return { questions: [], paper_markdown: '' };
    }
  }

  async getArtifact(sessionId: string, _type: string, slotId?: string): Promise<string> {
    const data = await this.getDisplayResult(sessionId);
    if (slotId) {
      const q = (data.questions || []).find((x) => x.slot_id === slotId);
      if (q) {
        let md = `### ${q.title || q.slot_id}\n\n${q.stem || ''}\n`;
        if (q.options?.length) {
          md += `\n${q.options.map((o, i) => `${'ABCD'[i] || ''}. ${o}`).join('\n')}\n`;
        }
        if (q.answer) md += `\n**答案**：${q.answer}\n`;
        if (q.explanation) md += `\n**解析**：${q.explanation}\n`;
        return md;
      }
    }
    return data.paper_markdown || '（暂无产物）';
  }

  // ── SSE ──

  subscribeToEvents(
    sessionId: string,
    callbacks: { onMessage?: (event: SSEEvent) => void; onError?: (error: Error) => void; onClose?: () => void },
  ): EventSource {
    const url = `${this.baseUrl}${V2}/sessions/${sessionId}/events`;
    const eventSource = new EventSource(url);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        callbacks.onMessage?.(data);
      } catch (err) {
        callbacks.onError?.(err as Error);
      }
    };
    eventSource.onerror = () => callbacks.onError?.(new Error('SSE connection error'));
    return eventSource;
  }
}

export const api = new APIClient();
export { SLOT_STATUS_MAP };
