<script setup lang="ts">
import { computed } from 'vue';
import SlotCard from './SlotCard.vue';
import type { SlotData } from '../composables/useSession';

const props = defineProps<{
  slots: SlotData[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  view: [slotId: string, outputFile: string];
  retry: [slotId: string];
  complete: [];
}>();

const summary = computed(() => {
  const total = props.slots.length;
  const count = (s: SlotData['status']) => props.slots.filter((x) => x.status === s).length;
  return {
    total,
    complete: count('complete'),
    failed: count('error'),
    active: count('generating') + count('review'),
    pending: count('pending'),
  };
});

const allDone = computed(() => summary.value.total > 0 && summary.value.complete + summary.value.failed === summary.value.total);
const pct = computed(() => (summary.value.total ? Math.round((summary.value.complete / summary.value.total) * 100) : 0));
</script>

<template>
  <section class="slot-kanban card">
    <header class="kanban-head">
      <div class="head-title">
        <h3>生成进度</h3>
        <span v-if="summary.total" class="progress-text">{{ summary.complete }} / {{ summary.total }} · {{ pct }}%</span>
      </div>
      <div v-if="summary.total" class="summary-chips">
        <span v-if="summary.active" class="chip chip-active">{{ summary.active }} 进行中</span>
        <span v-if="summary.failed" class="chip chip-failed">{{ summary.failed }} 失败</span>
        <span v-if="allDone && !summary.failed" class="chip chip-done">全部完成</span>
      </div>
    </header>

    <!-- overall progress bar -->
    <div v-if="summary.total" class="overall-rail" aria-hidden="true">
      <div class="overall-fill" :style="{ width: pct + '%' }"></div>
    </div>

    <!-- loading skeleton -->
    <div v-if="loading && !slots.length" class="slot-grid">
      <div v-for="n in 4" :key="n" class="skeleton-tile skeleton"></div>
    </div>

    <!-- empty state -->
    <div v-else-if="!slots.length" class="empty-state">
      <div class="empty-headline">还没有生成任务</div>
      <div class="empty-body">在对话里确认大纲后，题目会在这里逐题生成。</div>
    </div>

    <!-- slot grid -->
    <div v-else class="slot-grid">
      <SlotCard
        v-for="slot in slots"
        :key="slot.slot_id"
        :slot-id="slot.slot_id"
        :status="slot.status"
        :output-file="slot.output_file"
        :error-message="slot.error_message"
        @view="(id, f) => emit('view', id, f)"
        @retry="(id) => emit('retry', id)"
      />
    </div>
  </section>
</template>

<style scoped>
.slot-kanban {
  background: var(--bg-panel);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.kanban-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-md);
}
.head-title { display: flex; align-items: baseline; gap: var(--space-sm); }
.kanban-head h3 {
  font-size: var(--text-xl);
  font-weight: 500;
  color: var(--text-strong);
  margin: 0;
}
.progress-text {
  font-size: var(--text-sm);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.summary-chips { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
.chip {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 3px 9px;
  border-radius: var(--radius-pill);
}
.chip-active { background: var(--accent-tint); color: var(--accent); }
.chip-failed { background: var(--red-bg); color: var(--red); }
.chip-done { background: var(--green-bg); color: var(--green); }

.overall-rail {
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--bg-fill-secondary);
  overflow: hidden;
}
.overall-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width 400ms var(--ease-out);
}

.slot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-md);
}
.skeleton-tile { min-height: 96px; border-radius: var(--radius); }
</style>
