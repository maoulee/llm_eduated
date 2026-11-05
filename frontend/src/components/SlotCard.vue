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

const config = computed(() => {
  const configs = {
    pending: { icon: '⏳', label: '排队中', color: 'var(--text-muted)', bg: 'var(--bg-subtle)' },
    generating: { icon: '🔄', label: '生成中', color: 'var(--accent)', bg: 'var(--accent-soft)' },
    review: { icon: '🔍', label: '审核中', color: 'var(--blue)', bg: 'var(--blue-bg)' },
    complete: { icon: '✅', label: '已完成', color: 'var(--green)', bg: 'var(--green-bg)' },
    error: { icon: '❌', label: '失败', color: 'var(--red)', bg: 'var(--red-bg)' },
  };
  return configs[props.status];
});

function handleView() {
  if (props.status === 'complete' && props.outputFile) {
    emit('view', props.slotId, props.outputFile);
  }
}

function handleRetry() {
  emit('retry', props.slotId);
}
</script>

<template>
  <div class="slot-card" :class="{ 'clickable': status === 'complete' }">
    <div class="slot-header">
      <span class="slot-id">{{ slotId }}</span>
      <span class="slot-status" :style="{ color: config.color, background: config.bg }">
        <span class="status-icon">{{ config.icon }}</span>
        {{ config.label }}
      </span>
    </div>
    <div v-if="status === 'complete' && outputFile" class="slot-actions">
      <button class="btn btn-sm" @click="handleView">
        查看题目
      </button>
    </div>
    <div v-if="status === 'error' && errorMessage" class="slot-error">
      {{ errorMessage }}
    </div>
    <div v-if="status === 'error'" class="slot-actions">
      <button class="btn btn-sm btn-secondary" @click="handleRetry">
        重试
      </button>
    </div>
  </div>
</template>

<style scoped>
.slot-card {
  padding: var(--space-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color 140ms var(--ease-out), box-shadow 140ms var(--ease-out);
}

.slot-card.clickable {
  cursor: pointer;
}

.slot-card.clickable:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
}

.slot-id {
  font-weight: 500;
  color: var(--text);
}

.slot-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-pill);
}

.status-icon {
  font-size: 14px;
}

.slot-error {
  margin-top: var(--space-sm);
  padding: var(--space-sm);
  background: var(--red-bg);
  color: var(--red);
  font-size: 13px;
  border-radius: var(--radius-sm);
}

.slot-actions {
  margin-top: var(--space-md);
  display: flex;
  gap: var(--space-sm);
}

.btn {
  height: 28px;
  padding: 0 var(--space-sm);
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 140ms var(--ease-out);
  background: var(--accent);
  color: white;
  border: none;
}

.btn:hover {
  background: var(--accent-hover);
}

.btn-secondary {
  background: var(--bg-subtle);
  color: var(--text);
}

.btn-secondary:hover {
  background: var(--bg-muted);
}
</style>
