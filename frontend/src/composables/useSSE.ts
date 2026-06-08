import { ref, onUnmounted } from 'vue';
import { api, type SSEEvent } from '../api/client';

export interface SlotUpdate {
  slot_id: string;
  status: 'pending' | 'generating' | 'review' | 'complete' | 'error';
  output_file?: string;
  error_message?: string;
}

export function useSSE(sessionId: string) {
  const isConnected = ref(false);
  const error = ref<string | null>(null);
  let eventSource: EventSource | null = null;

  function subscribe(callbacks: {
    onStateChange?: (state: string) => void;
    onSlotUpdate?: (update: SlotUpdate) => void;
    onGenerationComplete?: () => void;
    onError?: (errorMessage: string) => void;
  }) {
    eventSource = api.subscribeToEvents(sessionId, {
      onMessage: (event: SSEEvent) => {
        isConnected.value = true;
        error.value = null;

        switch (event.type) {
          case 'state_change':
            callbacks.onStateChange?.(event.data.state as string);
            break;
          case 'slot_update':
            callbacks.onSlotUpdate?.(event.data as unknown as SlotUpdate);
            break;
          case 'generation_complete':
            callbacks.onGenerationComplete?.();
            break;
          case 'error':
            callbacks.onError?.(event.data.error as string);
            break;
        }
      },
      onError: () => {
        isConnected.value = false;
        error.value = 'Connection lost';
      },
    });
  }

  function unsubscribe() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
      isConnected.value = false;
    }
  }

  onUnmounted(() => {
    unsubscribe();
  });

  return {
    isConnected,
    error,
    subscribe,
    unsubscribe,
  };
}
