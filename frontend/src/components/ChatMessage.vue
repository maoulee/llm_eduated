<script setup lang="ts">
import { computed, ref } from 'vue';
import { marked } from 'marked';

const props = defineProps<{
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
  timestamp?: Date | string;
  error?: boolean;
}>();

const isUser = computed(() => props.role === 'user');
const isEmptyStreaming = computed(() => !isUser.value && props.streaming && !props.content);

const renderedContent = computed(() => {
  if (isUser.value) return props.content;
  // While streaming, render as plain text (layout-stable); markdown-render only once complete.
  if (props.streaming) return '';
  return marked(props.content);
});

const timeLabel = computed(() => {
  if (!props.timestamp) return '';
  const d = props.timestamp instanceof Date ? props.timestamp : new Date(props.timestamp);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
});

const copied = ref(false);
async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.content);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1600);
  } catch {
    /* clipboard unavailable */
  }
}
</script>

<template>
  <div :class="['chat-message', role, { error }]">
    <!-- assistant avatar dot -->
    <div v-if="!isUser" class="avatar" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path d="M12 3l2.09 4.26L19 8.27l-3.5 3.4.83 4.83L12 14.77l-4.33 1.73.83-4.83L5 8.27l4.91-1.01L12 3z" /></svg>
    </div>

    <div class="message-body">
      <div v-if="isUser" class="user-bubble">{{ content }}</div>
      <div v-else class="assistant-doc">
        <!-- pre-first-token: typing dots -->
        <div v-if="isEmptyStreaming" class="typing-dots" aria-label="正在思考">
          <span></span><span></span><span></span>
        </div>
        <!-- streaming plain text + cursor -->
        <div v-else-if="streaming" class="streaming-text">
          <span class="plain-text">{{ content }}</span><span class="stream-cursor"></span>
        </div>
        <!-- complete: rendered markdown -->
        <div v-else class="markdown-body" v-html="renderedContent"></div>

        <!-- copy action (assistant, complete, non-empty) -->
        <div v-if="!isUser && !streaming && content && !error" class="message-actions">
          <button class="btn-icon copy-btn" :title="copied ? '已复制' : '复制'" @click="copyContent">
            <svg v-if="!copied" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg>
            <svg v-else viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5" /></svg>
          </button>
        </div>
      </div>

      <div v-if="timeLabel" class="timestamp">{{ timeLabel }}</div>
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  display: flex;
  width: 100%;
  margin-bottom: var(--space-md);
  gap: var(--space-sm);
  animation: fadeIn var(--duration-enter) var(--ease-out);
}
.chat-message.user {
  justify-content: flex-end;
}

.avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  margin-top: 2px;
  border-radius: var(--radius-sm);
  background: var(--accent-tint);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar svg { width: 16px; height: 16px; fill: currentColor; stroke: none; }

.message-body {
  max-width: min(78%, 640px);
  display: flex;
  flex-direction: column;
}
.chat-message.user .message-body { align-items: flex-end; }

.user-bubble {
  background: var(--bg-warm-sand);
  color: var(--text);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-xs); /* square corner = "sent" */
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--text-base);
  line-height: 1.5;
}

.assistant-doc {
  max-width: 720px;
  color: var(--text);
}
.plain-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--text-base);
  line-height: 1.6;
}
.streaming-text { font-size: var(--text-base); line-height: 1.6; }

.message-actions {
  display: flex;
  gap: var(--space-xs);
  margin-top: var(--space-xs);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.chat-message.assistant:hover .message-actions { opacity: 1; }
.copy-btn { width: 26px; height: 26px; }
.copy-btn svg { width: 14px; height: 14px; }

.timestamp {
  margin-top: var(--space-xs);
  font-size: var(--text-xs);
  color: var(--text-faint);
}

.chat-message.error .assistant-doc {
  background: var(--red-bg);
  border-left: 3px solid var(--red);
  border-radius: var(--radius-sm);
  padding: var(--space-sm) var(--space-md);
  color: var(--red);
  font-size: var(--text-sm);
}
</style>
