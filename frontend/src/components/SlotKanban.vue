<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { api } from '../api/client';
import SlotCard from './SlotCard.vue';

const props = defineProps<{
  sessionId: string;
  runId?: string;
}>();

const emit = defineEmits<{
  complete: [];
}>();

interface SlotData {
  slot_id: string;
  status: 'pending' | 'generating' | 'review' | 'complete' | 'error';
  output_file?: string;
  error_message?: string;
}

const slots = ref<Record<string, SlotData>>({});
const eventSource = ref<EventSource | null>(null);

function subscribeToEvents() {
  if (eventSource.value) {
    eventSource.value.close();
  }

  eventSource.value = api.subscribeToEvents(props.sessionId, {
    onMessage: (event) => {
      if (event.type === 'slot_update') {
        const update = event.data as unknown as SlotData;
        slots.value[update.slot_id] = update;
      } else if (event.type === 'generation_complete') {
        emit('complete');
      }
    },
  });
}

onMounted(() => {
  subscribeToEvents();
});

onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close();
  }
});

function handleRetry(slotId: string) {
  // Retry logic would be handled by the backend
  console.log('Retry slot:', slotId);
}

function handleView(slotId: string, outputFile: string) {
  // View logic - could open a modal or navigate
  console.log('View slot:', slotId, outputFile);
}

const slotList = computed(() => {
  return Object.entries(slots.value).map(([id, data]) => ({
    id,
    ...data,
  }));
});
</script>

<template>
  <div class="slot-kanban">
    <h3>生成进度</h3>
    <div v-if="slotList.length === 0" class="empty-state">
      <p class="text-muted">等待开始生成...</p>
    </div>
    <div v-else class="slot-grid">
      <SlotCard
        v-for="slot in slotList"
        :key="slot.id"
        :slot-id="slot.slot_id"
        :status="slot.status"
        :output-file="slot.output_file"
        :error-message="slot.error_message"
        @retry="handleRetry"
        @view="handleView"
      />
    </div>
  </div>
</template>

<style scoped>
.slot-kanban {
  margin: var(--space-md) 0;
  padding: var(--space-lg);
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.slot-kanban h3 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: var(--space-md);
  color: var(--text-strong);
}

.empty-state {
  padding: var(--space-xl) 0;
  text-align: center;
}

.slot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-md);
}
</style>
