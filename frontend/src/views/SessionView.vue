<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSession } from '../composables/useSession';
import { api } from '../api/client';
import ChatLog from '../components/ChatLog.vue';
import Composer from '../components/Composer.vue';
import StateBadge from '../components/StateBadge.vue';
import OutlineEditor from '../components/OutlineEditor.vue';
import SlotKanban from '../components/SlotKanban.vue';

const props = defineProps<{
  id: string;
}>();

const router = useRouter();
const {
  session,
  messages,
  isLoading,
  error,
  state,
  mode,
  canSendMessage,
  loadSession,
  sendMessage,
  deleteThisSession,
  subscribeToEvents,
  unsubscribe,
} = useSession(props.id);

const showOutlineEditor = ref(false);
const runId = ref<string | null>(null);

const modeLabel = computed(() => {
  return mode.value === 'compose' ? '组卷' : '知识点出题';
});

const title = computed(() => {
  return session.value?.title || `${modeLabel.value}会话`;
});

async function handleSend(message: string) {
  try {
    const response = await sendMessage(message);
    if (response.blueprint_id) {
      runId.value = response.blueprint_id;
    }

    if (response.state === 'blueprint_ready') {
      showOutlineEditor.value = true;
    }
  } catch (err) {
    console.error('Failed to send message:', err);
  }
}

async function handleOutlineSaved(_outline: string) {
  const assistantMsg = {
    id: `msg-${Date.now()}`,
    role: 'assistant' as const,
    content: `大纲已保存。可以继续修改或确认出题。`,
    timestamp: new Date(),
  };
  messages.value.push(assistantMsg);
  showOutlineEditor.value = false;
}

async function handleOutlineConfirm() {
  try {
    await api.startGeneration(props.id);
    showOutlineEditor.value = false;
    const assistantMsg = {
      id: `msg-${Date.now()}`,
      role: 'assistant' as const,
      content: `开始生成题目...`,
      timestamp: new Date(),
    };
    messages.value.push(assistantMsg);
  } catch (err) {
    console.error('Failed to start generation:', err);
  }
}

async function handleDeleteSession() {
  if (confirm('确定要删除这个会话吗？')) {
    await deleteThisSession();
    router.push('/');
  }
}

onMounted(async () => {
  await loadSession();
  subscribeToEvents();
});

onUnmounted(() => {
  unsubscribe();
});
</script>

<template>
  <div class="session-view">
    <header class="session-header">
      <div class="header-left">
        <button class="back-button" @click="router.push('/')">
          ← 返回
        </button>
        <h1>{{ title }}</h1>
        <StateBadge :state="state" />
      </div>
      <div class="header-right">
        <button class="icon-button" @click="handleDeleteSession" title="删除会话">
          🗑️
        </button>
      </div>
    </header>

    <main class="session-main">
      <ChatLog :messages="messages" />

      <div v-if="error" class="error-card">
        {{ error }}
      </div>

      <OutlineEditor
        v-if="state === 'blueprint_ready' || state === 'annotating'"
        :session-id="id"
        :readonly="state !== 'annotating'"
        @saved="handleOutlineSaved"
        @confirmed="handleOutlineConfirm"
      />

      <SlotKanban
        v-if="state === 'generating' || state === 'complete'"
        :session-id="id"
        :run-id="runId || undefined"
      />

      <Composer
        v-if="canSendMessage"
        :disabled="isLoading"
        :placeholder="state === 'idle' ? '输入你的要求...' : '输入补充信息...'"
        @send="handleSend"
      />
    </main>
  </div>
</template>

<style scoped>
.session-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-app);
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.back-button {
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-subtle);
  color: var(--text);
  border-radius: var(--radius-sm);
  font-size: 14px;
  transition: background 140ms var(--ease-out);
}

.back-button:hover {
  background: var(--bg-muted);
}

.session-header h1 {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
}

.header-right {
  display: flex;
  gap: var(--space-sm);
}

.icon-button {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  font-size: 16px;
  transition: background 140ms var(--ease-out);
}

.icon-button:hover {
  background: var(--bg-muted);
}

.session-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.error-card {
  margin: var(--space-md);
  padding: var(--space-md);
  background: var(--red-bg);
  color: var(--red);
  border-radius: var(--radius);
  text-align: center;
}
</style>
