import { ref, computed, shallowRef, onUnmounted } from 'vue';
import { api, type Session } from '../api/client';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  streaming?: boolean;
  error?: boolean;
}

export interface SlotData {
  slot_id: string;
  status: 'pending' | 'generating' | 'review' | 'complete' | 'error';
  output_file?: string;
  error_message?: string;
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Owns the SINGLE SSE EventSource for a session and all derived reactive state:
 * session, chat messages, slot map. Components (SlotKanban, ChatLog, …) consume
 * from here instead of opening their own EventSource.
 *
 * Backend realities (see DESIGN.md):
 *  - /message is synchronous (no token deltas) → assistant text is typewriter-streamed client-side.
 *  - `slot_update` is never emitted today → slots are seeded from the outline and may be driven
 *    by a simulator; real slot_update events override the simulation if/when emitted.
 *  - failure event is `generation_error` (handled here; `error` is a defensive alias).
 */
export function useSession(sessionId: string) {
  const session = shallowRef<Session | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const slots = ref<Record<string, SlotData>>({});
  const isLoading = ref(false);
  const isStreaming = ref(false);
  const error = ref<string | null>(null);
  let eventSource: EventSource | null = null;
  let streamTimer: ReturnType<typeof setInterval> | null = null;

  const state = computed(() => session.value?.state ?? 'idle');
  const mode = computed(() => session.value?.mode ?? 'compose');
  const canSendMessage = computed(() => {
    const s = state.value;
    return s === 'idle' || s === 'collecting' || s === 'blueprint_ready' || s === 'error';
  });
  const slotList = computed(() => Object.values(slots.value));

  /** Seed the slot map from outline-derived ids (e.g. 第N题) before generation runs. */
  function setSlots(ids: string[]) {
    const next: Record<string, SlotData> = {};
    for (const id of ids) next[id] = { slot_id: id, status: 'pending' };
    slots.value = next;
  }

  function stopStream() {
    if (streamTimer) { clearInterval(streamTimer); streamTimer = null; }
    isStreaming.value = false;
  }

  async function loadSession() {
    try {
      isLoading.value = true;
      error.value = null;
      session.value = await api.getSession(sessionId);
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load session';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  /** Typewriter-reveal the full assistant string (server does not stream tokens). */
  function streamInto(target: ChatMessage, full: string) {
    isStreaming.value = true;
    target.streaming = true;
    if (!full) { target.streaming = false; isStreaming.value = false; return; }
    if (prefersReducedMotion()) {
      target.content = full;
      target.streaming = false;
      isStreaming.value = false;
      return;
    }
    const chunk = Math.max(2, Math.round(full.length / 90)); // ~90 frames regardless of length
    let i = 0;
    streamTimer = setInterval(() => {
      i = Math.min(full.length, i + chunk);
      target.content = full.slice(0, i);
      if (i >= full.length) {
        target.content = full;
        target.streaming = false;
        stopStream();
      }
    }, 16);
  }

  async function sendMessage(message: string) {
    try {
      stopStream();
      isLoading.value = true;
      error.value = null;

      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: message,
        timestamp: new Date(),
      };
      messages.value.push(userMsg);

      const response = await api.sendMessage(sessionId, message);

      messages.value.push({
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      });
      // reference via the reactive array so streaming mutations trigger reactivity
      const target = messages.value[messages.value.length - 1];
      streamInto(target, response.response || '');

      if (response.state !== state.value) {
        session.value = { ...session.value!, state: response.state } as Session;
      }
      return response;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to send message';
      messages.value.push({
        id: `msg-err-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ ${error.value}`,
        timestamp: new Date(),
        error: true,
      });
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function deleteThisSession() {
    await api.deleteSession(sessionId);
  }

  function subscribeToEvents() {
    if (eventSource) eventSource.close();
    eventSource = api.subscribeToEvents(sessionId, {
      onMessage: (event) => {
        if (!session.value) return;
        switch (event.type) {
          case 'state_change':
            session.value = { ...session.value, state: event.data.state as Session['state'] };
            break;
          case 'slot_update': {
            const u = event.data as unknown as SlotData | null;
            if (u?.slot_id) {
              slots.value = {
                ...slots.value,
                [u.slot_id]: { ...slots.value[u.slot_id], ...u },
              };
            }
            break;
          }
          case 'generation_complete':
            session.value = { ...session.value, state: 'complete' };
            for (const s of Object.values(slots.value)) {
              if (s.status !== 'error') slots.value[s.slot_id] = { ...s, status: 'complete' };
            }
            break;
          case 'generation_error':
          case 'error':
            session.value = {
              ...session.value,
              state: 'error',
              error: (event.data.error as string) || '生成失败',
            };
            break;
        }
      },
      onError: () => {
        error.value = '连接已断开，正在重连…';
      },
    });
  }

  function unsubscribe() {
    stopStream();
    if (eventSource) { eventSource.close(); eventSource = null; }
  }

  onUnmounted(() => unsubscribe());

  return {
    session,
    messages,
    slots,
    slotList,
    isLoading,
    isStreaming,
    error,
    state,
    mode,
    canSendMessage,
    loadSession,
    sendMessage,
    deleteThisSession,
    subscribeToEvents,
    unsubscribe,
    setSlots,
    stopStream,
  };
}
