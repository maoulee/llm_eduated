<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  state: string;
}>();

const stateConfig = computed(() => {
  const configs: Record<string, { label: string; color: string; bg: string }> = {
    idle: { label: '空闲', color: 'var(--text-muted)', bg: 'var(--bg-subtle)' },
    collecting: { label: '收集中', color: 'var(--blue)', bg: 'var(--blue-bg)' },
    blueprint_ready: { label: '大纲就绪', color: 'var(--green)', bg: 'var(--green-bg)' },
    annotating: { label: '标注中', color: 'var(--amber)', bg: 'var(--amber-bg)' },
    approved: { label: '已确认', color: 'var(--green)', bg: 'var(--green-bg)' },
    generating: { label: '生成中', color: 'var(--accent)', bg: 'var(--accent-soft)' },
    complete: { label: '完成', color: 'var(--green)', bg: 'var(--green-bg)' },
    error: { label: '错误', color: 'var(--red)', bg: 'var(--red-bg)' },
  };
  return configs[props.state] || { label: props.state, color: 'var(--text-muted)', bg: 'var(--bg-subtle)' };
});
</script>

<template>
  <span class="state-badge" :style="{ color: stateConfig.color, background: stateConfig.bg }">
    {{ stateConfig.label }}
  </span>
</template>

<style scoped>
.state-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-pill);
  white-space: nowrap;
}
</style>
