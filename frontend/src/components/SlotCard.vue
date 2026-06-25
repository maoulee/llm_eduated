<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  slotId: string;
  status: 'pending' | 'generating' | 'review' | 'complete' | 'error';
  outputFile?: string;
  errorMessage?: string;
}>();

const emit = defineEmits<{
  retry: [slotId: string];
  view: [slotId: string, outputFile: string];
}>();

const cfg = computed(() => {
  const map = {
    pending: { label: '排队中', color: 'var(--text-muted)', bg: 'var(--bg-subtle)', border: 'transparent' },
    generating: { label: '生成中', color: 'var(--accent)', bg: 'var(--accent-tint)', border: 'var(--accent)' },
    review: { label: '审核中', color: 'var(--blue)', bg: 'var(--blue-bg)', border: 'var(--blue)' },
    complete: { label: '已完成', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green)' },
    error: { label: '失败', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red)' },
  } as const;
  return map[props.status];
});

const isAnimating = computed(() => props.status === 'generating');

function handleView() {
  if (props.status === 'complete' && props.outputFile) {
    emit('view', props.slotId, props.outputFile);
  }
}
</script>

<template>
  <div
    class="slot-card"
    :class="{ clickable: status === 'complete' }"
    :style="{ '--status-border': cfg.border }"
  >
    <div class="tile-head">
      <span class="slot-id">{{ slotId }}</span>
      <span class="badge" :style="{ color: cfg.color, background: cfg.bg }">
        <!-- inline SVG status marks (no emoji) -->
        <svg v-if="status === 'pending'" class="mark" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" /></svg>
        <svg v-else-if="status === 'generating'" class="mark spin" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5" /></svg>
        <svg v-else-if="status === 'review'" class="mark" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
        <svg v-else-if="status === 'complete'" class="mark" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" /></svg>
        <svg v-else class="mark" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" /></svg>
        {{ cfg.label }}
      </span>
    </div>

    <!-- indeterminate progress rail while generating (no real % available) -->
    <div v-if="isAnimating" class="progress-rail" aria-hidden="true">
      <div class="progress-fill"></div>
    </div>

    <div v-if="status === 'error' && errorMessage" class="slot-error">{{ errorMessage }}</div>

    <div class="tile-actions">
      <button v-if="status === 'complete' && outputFile" class="btn btn-primary btn-sm" @click="handleView">
        查看题目
      </button>
      <button v-if="status === 'error'" class="btn btn-ghost btn-sm" @click="emit('retry', slotId)">
        重试
      </button>
    </div>
  </div>
</template>

<style scoped>
.slot-card {
  --status-border: transparent;
  padding: var(--space-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-left: 3px solid var(--status-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  min-height: 96px;
  transition: border-color var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out), transform var(--duration-fast) var(--ease-out);
}
.slot-card.clickable { cursor: pointer; }
.slot-card.clickable:hover {
  border-color: var(--accent-soft);
  box-shadow: var(--shadow-sm);
}

.tile-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
}
.slot-id {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.mark {
  width: 13px;
  height: 13px;
  stroke: currentColor;
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.mark.spin { transform-origin: 50% 50%; animation: spin 1.1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.progress-rail {
  height: 3px;
  border-radius: var(--radius-pill);
  background: var(--bg-fill-secondary);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  width: 40%;
  border-radius: inherit;
  background: var(--accent);
  animation: rail-indeterminate 1.4s var(--ease-in-out) infinite;
}
@keyframes rail-indeterminate {
  0% { margin-left: -40%; }
  100% { margin-left: 100%; }
}

.slot-error {
  padding: var(--space-sm);
  background: var(--red-bg);
  color: var(--red);
  font-size: var(--text-sm);
  border-radius: var(--radius-sm);
  line-height: 1.45;
}

.tile-actions {
  margin-top: auto;
  display: flex;
  gap: var(--space-sm);
  min-height: 28px;
}
</style>
