<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useSession } from '../composables/useSession';
import { api } from '../api/client';
import ChatLog from '../components/ChatLog.vue';
import Composer from '../components/Composer.vue';
import StateBadge from '../components/StateBadge.vue';
import OutlineEditor from '../components/OutlineEditor.vue';
import SlotKanban from '../components/SlotKanban.vue';

const props = defineProps<{ id: string }>();

const router = useRouter();
const {
  session,
  messages,
  slots,
  slotList,
  isLoading,
  isStreaming,
  error,
  state,
  mode,
  canSendMessage,
  loadSession,
  sendMessage,
  deleteThisSession,
  subscribeToEvents,
  unsubscribe,
  setSlots,
} = useSession(props.id);

const runId = ref<string | null>(null);
const showOutlineEditor = ref(false);

// ── slot progress simulation (backend does not emit slot_update today) ──
let simTimer: ReturnType<typeof setInterval> | null = null;
const slotsLoading = ref(false);

function parseSlotIds(md: string): string[] {
  const matches = [...md.matchAll(/第\s*(\d+)\s*题/g)];
  const nums = [...new Set(matches.map((m) => Number(m[1])))].sort((a, b) => a - b);
  return nums.length ? nums.map((n) => `Q${n}`) : [];
}

function stopSlotSim() {
  if (simTimer) { clearInterval(simTimer); simTimer = null; }
}

function startSlotSim(ids: string[]) {
  stopSlotSim();
  setSlots(ids);
  simTimer = setInterval(() => {
    const arr = Object.values(slots.value);
    const pending = arr.find((s) => s.status === 'pending');
    if (pending) {
      slots.value[pending.slot_id] = { ...slots.value[pending.slot_id], status: 'generating' };
      return;
    }
    const inFlight = arr.find((s) => s.status === 'generating' || s.status === 'review');
    if (inFlight) {
      const next = inFlight.status === 'generating' ? 'review' : 'complete';
      slots.value[inFlight.slot_id] = { ...slots.value[inFlight.slot_id], status: next };
    }
  }, 1100);
}

// ── artifact viewer (final only; review/solution unsupported by backend) ──
const viewer = ref<{ slotId: string; content: string; loading: boolean } | null>(null);
async function handleView(slotId: string, _outputFile: string) {
  viewer.value = { slotId, content: '', loading: true };
  try {
    const rid = runId.value || session.value?.blueprint_id || '';
    const content = await api.getArtifact(rid, 'final', slotId);
    viewer.value = { slotId, content, loading: false };
  } catch {
    viewer.value = { slotId, content: '加载失败（该题型可能暂不支持预览）', loading: false };
  }
}

// retry has no backend endpoint — documented no-op
const retryNotice = ref('');
function handleRetry(slotId: string) {
  retryNotice.value = `${slotId} 重试功能即将上线`;
  setTimeout(() => (retryNotice.value = ''), 2200);
}

const modeLabel = computed(() => (mode.value === 'compose' ? '组卷' : '知识点出题'));
const title = computed(() => session.value?.title || `${modeLabel.value}会话`);

async function handleSend(message: string) {
  try {
    const response = await sendMessage(message);
    if (response.blueprint_id) runId.value = response.blueprint_id;
    if (response.state === 'blueprint_ready') showOutlineEditor.value = true;
  } catch (err) {
    console.error('Failed to send message:', err);
  }
}

async function handleOutlineSaved(_outline: string) {
  messages.value.push({
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content: '大纲已保存。可继续修改或确认出题。',
    timestamp: new Date(),
  });
  showOutlineEditor.value = false;
}

async function handleOutlineConfirm() {
  try {
    await api.startGeneration(props.id);
    showOutlineEditor.value = false;
    messages.value.push({
      id: `msg-${Date.now()}`,
      role: 'assistant',
      content: '开始生成题目…',
      timestamp: new Date(),
    });
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

// Drive the slot sim from the session state machine.
watch(
  state,
  async (s) => {
    if (s === 'generating') {
      slotsLoading.value = true;
      try {
        const o = await api.getOutline(props.id);
        const ids = parseSlotIds(o.outline_md);
        if (ids.length) startSlotSim(ids);
      } catch {
        /* outline unavailable — kanban shows empty state */
      } finally {
        slotsLoading.value = false;
      }
    } else if (s === 'complete' || s === 'error') {
      stopSlotSim();
    }
  }
);

onMounted(async () => {
  await loadSession();
  subscribeToEvents();
});

onUnmounted(() => {
  stopSlotSim();
  unsubscribe();
});
</script>

<template>
  <div class="session-view">
    <header class="session-header">
      <div class="header-left">
        <button class="back-button" title="返回" @click="router.push('/')">
          <svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <h1>{{ title }}</h1>
        <StateBadge :state="state" />
        <span v-if="isStreaming" class="stream-pill">生成中…</span>
      </div>
      <div class="header-right">
        <button class="btn-icon" title="删除会话" @click="handleDeleteSession">
          <svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14" /></svg>
        </button>
      </div>
    </header>

    <main class="session-main">
      <ChatLog :messages="messages" />

      <div v-if="error" class="error-strip">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
        <span>{{ error }}</span>
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
        :slots="slotList"
        :loading="slotsLoading"
        @view="handleView"
        @retry="handleRetry"
      />

      <transition name="toast">
        <div v-if="retryNotice" class="toast">{{ retryNotice }}</div>
      </transition>

      <Composer
        v-if="canSendMessage"
        :disabled="isLoading"
        :placeholder="state === 'idle' ? '输入你的要求…' : '输入补充信息…'"
        @send="handleSend"
      />
    </main>

    <!-- artifact viewer modal -->
    <transition name="modal">
      <div v-if="viewer" class="modal-overlay" @click.self="viewer = null">
        <div class="modal-panel card">
          <header class="modal-head">
            <h3>{{ viewer.slotId }} · 题目预览</h3>
            <button class="btn-icon" title="关闭" @click="viewer = null">
              <svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </header>
          <div class="modal-body">
            <div v-if="viewer.loading" class="skeleton skeleton-line"></div>
            <div v-else class="markdown-body" v-html="viewer.content"></div>
          </div>
        </div>
      </div>
    </transition>
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
.header-left { display: flex; align-items: center; gap: var(--space-md); }
.back-button {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; color: var(--text-muted); border-radius: var(--radius-sm);
  transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out);
}
.back-button:hover { background: var(--bg-fill-tertiary); color: var(--text); }
.back-button svg { width: 18px; height: 18px; stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round; }

.session-header h1 { font-size: var(--text-lg); font-weight: 500; color: var(--text-strong); margin: 0; }

.stream-pill {
  font-size: var(--text-xs); font-weight: 500; color: var(--accent);
  background: var(--accent-tint); padding: 3px 9px; border-radius: var(--radius-pill);
}

.header-right { display: flex; gap: var(--space-sm); }
.header-right .btn-icon svg { width: 18px; height: 18px; }

.session-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  gap: var(--space-md);
  padding-bottom: var(--space-md);
}

.error-strip {
  display: flex; align-items: center; gap: var(--space-sm);
  margin: 0 var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: var(--red-bg); color: var(--red);
  border-radius: var(--radius); font-size: var(--text-sm);
}
.error-strip svg { width: 16px; height: 16px; stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; }

.toast {
  align-self: center;
  padding: var(--space-sm) var(--space-md);
  background: var(--text-strong); color: var(--accent-on);
  font-size: var(--text-sm); border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
}
.toast-enter-active, .toast-leave-active { transition: opacity var(--duration-base) var(--ease-out), transform var(--duration-base) var(--ease-out); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(6px); }

/* artifact modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: var(--z-overlay);
  background: rgba(58, 47, 30, 0.4);
  display: flex; align-items: center; justify-content: center;
  padding: var(--space-lg);
}
.modal-panel {
  width: min(720px, 100%); max-height: 80vh; display: flex; flex-direction: column;
  background: var(--bg-elevated); box-shadow: var(--shadow-lg);
}
.modal-head {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: var(--space-md); border-bottom: 1px solid var(--border);
}
.modal-head h3 { font-size: var(--text-md); font-weight: 500; color: var(--text-strong); }
.modal-body { padding-top: var(--space-md); overflow-y: auto; }
.skeleton-line { height: 120px; }
.modal-enter-active, .modal-leave-active { transition: opacity var(--duration-base) var(--ease-out); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
