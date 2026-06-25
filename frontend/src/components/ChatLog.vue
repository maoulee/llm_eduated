<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue';
import ChatMessage from './ChatMessage.vue';

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  streaming?: boolean;
  error?: boolean;
}

const props = defineProps<{
  messages: ChatMessageData[];
}>();

const containerRef = ref<HTMLElement>();
const stickyBottom = ref(true);

function isNearBottom() {
  const el = containerRef.value;
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
}

function onScroll() {
  stickyBottom.value = isNearBottom();
}

async function scrollToBottom(smooth = true) {
  await nextTick();
  if (containerRef.value) {
    containerRef.value.scrollTo({
      top: containerRef.value.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
  }
}

// Auto-scroll when new messages arrive OR streaming content grows — only if user is pinned to bottom.
watch(
  () => props.messages.map((m) => `${m.id}:${m.content.length}`).join('|'),
  () => {
    if (stickyBottom.value) scrollToBottom();
  }
);
watch(() => props.messages.length, () => {
  if (stickyBottom.value) scrollToBottom();
}, { flush: 'post' });

onMounted(() => scrollToBottom(false));
onUnmounted(() => {});

const showJump = computed(() => !stickyBottom.value && props.messages.length > 0);
</script>

<template>
  <div class="chat-log-wrap">
    <div ref="containerRef" class="chat-log" @scroll="onScroll">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-headline">开始出题对话</div>
        <div class="empty-body">告诉我科目、范围与难度，或直接描述你想要的试卷/题目。</div>
      </div>
      <template v-else>
        <ChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :role="msg.role"
          :content="msg.content"
          :streaming="msg.streaming"
          :timestamp="msg.timestamp"
          :error="msg.error"
        />
      </template>
    </div>

    <button v-if="showJump" class="jump-latest" @click="() => { stickyBottom = true; scrollToBottom(); }">
      回到最新
      <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7" transform="rotate(180 12 12)" /></svg>
    </button>
  </div>
</template>

<style scoped>
.chat-log-wrap {
  position: relative;
  flex: 1;
  display: flex;
  min-height: 0;
}
.chat-log {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg) var(--space-md);
  scroll-behavior: smooth;
  max-width: 820px;
  margin: 0 auto;
  width: 100%;
}
.jump-latest {
  position: absolute;
  left: 50%;
  bottom: var(--space-md);
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-xs) var(--space-md);
  background: var(--accent-tint);
  color: var(--accent);
  font-size: var(--text-sm);
  font-weight: 500;
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
  transition: background var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out);
  z-index: var(--z-raised);
}
.jump-latest:hover { background: var(--accent-soft); }
.jump-latest svg { width: 14px; height: 14px; stroke: currentColor; stroke-width: 1.75; fill: none; stroke-linecap: round; stroke-linejoin: round; }
</style>
