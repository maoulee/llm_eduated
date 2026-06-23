<script setup lang="ts">
import { computed } from 'vue';
import { marked } from 'marked';

const props = defineProps<{
  role: 'user' | 'assistant';
  content: string;
}>();

const isUser = computed(() => props.role === 'user');
const renderedContent = computed(() => {
  if (isUser.value) return props.content;
  return marked(props.content);
});
</script>

<template>
  <div :class="['chat-message', role]">
    <div class="message-content">
      <div v-if="isUser" class="user-text">{{ content }}</div>
      <div v-else class="markdown-body" v-html="renderedContent"></div>
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  display: flex;
  width: 100%;
  margin-bottom: var(--space-md);
  animation: fadeIn 200ms var(--ease-out);
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.message-content {
  max-width: min(78%, 560px);
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-elevated);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
}

.chat-message.user .message-content {
  background: var(--bg-fill-tertiary);
  border: none;
}

.user-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14.5px;
  line-height: 1.5;
}

.markdown-body {
  font-size: 14.5px;
  line-height: 1.5;
  color: var(--text);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: var(--space-md);
  margin-bottom: var(--space-sm);
  font-weight: 500;
  color: var(--text-strong);
}

.markdown-body :deep(h1) {
  font-size: 1.5em;
}

.markdown-body :deep(h2) {
  font-size: 1.25em;
}

.markdown-body :deep(h3) {
  font-size: 1.1em;
}

.markdown-body :deep(p) {
  margin-bottom: var(--space-sm);
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  background: var(--bg-subtle);
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 0.9em;
}

.markdown-body :deep(pre) {
  padding: var(--space-md);
  margin: var(--space-md) 0;
  background: var(--bg-subtle);
  border-radius: var(--radius);
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: var(--space-lg);
  margin-bottom: var(--space-sm);
}

.markdown-body :deep(li) {
  margin-bottom: var(--space-xs);
}

.markdown-body :deep(blockquote) {
  margin: var(--space-md) 0;
  padding-left: var(--space-md);
  border-left: 3px solid var(--accent);
  color: var(--text-muted);
}

.markdown-body :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: var(--space-md) 0;
  border-collapse: collapse;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: var(--space-sm);
  border: 1px solid var(--border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--bg-subtle);
  font-weight: 500;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
