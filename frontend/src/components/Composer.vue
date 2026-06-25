<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = defineProps<{
  disabled?: boolean;
  placeholder?: string;
}>();

const emit = defineEmits<{
  send: [message: string];
}>();

const input = ref('');
const textareaRef = ref<HTMLTextAreaElement>();

async function send() {
  const trimmed = input.value.trim();
  if (!trimmed || props.disabled) return;

  emit('send', trimmed);
  input.value = '';
  await nextTick();
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto';
    textareaRef.value.focus();
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

function autoResize(e: Event) {
  const target = e.target as HTMLTextAreaElement;
  target.style.height = 'auto';
  target.style.height = Math.min(target.scrollHeight, 200) + 'px';
}

watch(() => props.disabled, (disabled) => {
  if (!disabled && textareaRef.value) {
    textareaRef.value.focus();
  }
});
</script>

<template>
  <div class="composer">
    <!-- Optional state hint, shown only when locked due to a non-input state -->
    <p v-if="disabled" class="composer-hint">助手正在处理中，请稍候…</p>

    <div class="composer-shell">
      <textarea
        ref="textareaRef"
        v-model="input"
        :disabled="disabled"
        :placeholder="placeholder || '输入你的要求...'"
        class="composer-input"
        @keydown="handleKeydown"
        @input="autoResize"
        rows="1"
      />

      <button
        type="button"
        :disabled="disabled || !input.trim()"
        class="send-btn"
        :aria-label="'发送'"
        title="发送 (Enter)"
        @click="send"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22l-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  padding: var(--space-md);
  background: var(--bg-app);
}

/* Optional disabled-state hint line above the shell */
.composer-hint {
  margin: 0 0 var(--space-sm) var(--space-sm);
  font-size: var(--text-sm);
  color: var(--text-soft);
  line-height: 1.4;
}

/* Shell: elevated warm surface + 1px hairline ring, accent ring on focus-within */
.composer-shell {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  transition: border-color var(--duration-exit) var(--ease-out),
              box-shadow var(--duration-exit) var(--ease-out);
}

.composer-shell:focus-within {
  border-color: var(--accent);
  box-shadow: var(--ring-accent);
}

/* Transparent textarea, warm text, soft placeholder */
.composer-input {
  flex: 1;
  min-height: 24px;
  max-height: 200px;
  padding: var(--space-sm);
  background: transparent;
  border: none;
  resize: none;
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--text);
  font-family: inherit;
}

.composer-input::placeholder {
  color: var(--text-soft);
}

.composer-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* Circular accent icon button — the single Terracotta accent in this view */
.send-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  background: var(--accent);
  color: var(--accent-on);
  border: none;
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out),
              opacity var(--duration-fast) var(--ease-out);
}

.send-btn svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  stroke-width: 1.75;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.send-btn:active:not(:disabled) {
  background: var(--accent-active);
  transform: scale(0.95);
}

.send-btn:focus-visible {
  outline: none;
  box-shadow: var(--ring-focus);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
