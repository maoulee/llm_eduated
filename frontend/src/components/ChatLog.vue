<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import ChatMessage from './ChatMessage.vue';

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const props = defineProps<{
  messages: ChatMessageData[];
}>();

const containerRef = ref<HTMLElement>();

async function scrollToBottom() {
  await nextTick();
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight;
  }
}

watch(() => props.messages.length, () => {
  scrollToBottom();
}, { flush: 'post' });
</script>

<template>
  <div ref="containerRef" class="chat-log">
    <div v-if="messages.length === 0" class="empty-state">
      <p class="text-muted">开始对话...</p>
    </div>
    <ChatMessage
      v-for="msg in messages"
      :key="msg.id"
      :role="msg.role"
      :content="msg.content"
    />
  </div>
</template>

<style scoped>
.chat-log {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg) var(--space-md);
  scroll-behavior: smooth;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.empty-state p {
  font-size: 14.5px;
}
</style>
