import { ref, computed, shallowRef } from 'vue';
import { api, type Session } from '../api/client';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export function useSession(sessionId: string) {
  const session = shallowRef<Session | null>(null);
  const messages = ref<ChatMessage[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const eventSource = ref<EventSource | null>(null);

  const state = computed(() => session.value?.state ?? 'idle');
  const mode = computed(() => session.value?.mode ?? 'compose');
  const canSendMessage = computed(() => {
    const s = state.value;
    return s === 'idle' || s === 'collecting' || s === 'blueprint_ready' || s === 'error';
  });

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

  async function sendMessage(message: string) {
    try {
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

      const assistantMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      };
      messages.value.push(assistantMsg);

      if (response.state !== state.value) {
        session.value = { ...session.value!, state: response.state } as Session;
      }

      return response;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to send message';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function deleteThisSession() {
    await api.deleteSession(sessionId);
  }

  function subscribeToEvents() {
    if (eventSource.value) {
      eventSource.value.close();
    }

    eventSource.value = api.subscribeToEvents(sessionId, {
      onMessage: (event) => {
        if (event.type === 'state_change' && session.value) {
          session.value = { ...session.value, state: event.data.state as Session['state'] } as Session;
        } else if (event.type === 'generation_complete' && session.value) {
          session.value = { ...session.value, state: 'complete' } as Session;
        } else if (event.type === 'error' && session.value) {
          session.value = { ...session.value, state: 'error', error: event.data.error as string } as Session;
        }
      },
      onError: () => {
        error.value = 'Connection lost. Reconnecting...';
      },
    });
  }

  function unsubscribe() {
    if (eventSource.value) {
      eventSource.value.close();
      eventSource.value = null;
    }
  }

  return {
    session,
    messages,
    isLoading,
    error,
    state,
    mode,
    canSendMessage,
    loadSession,
    sendMessage,
    deleteThisSession,
    subscribeToEvents,
    unsubscribe,
  };
}
