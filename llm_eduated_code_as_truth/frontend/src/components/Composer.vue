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
        :disabled="disabled || !input.trim()"
        class="send-button"
        @click="send"
      >
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  padding: var(--space-md);
  background: var(--bg-app);
}

.composer-shell {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background: var(--bg-fill-tertiary);
  border: 1px solid var(--bg-fill-secondary);
  border-radius: var(--radius-lg);
  transition: border-color 140ms var(--ease-out), box-shadow 140ms var(--ease-out);
}

.composer-shell:focus-within {
  border-color: var(--accent-soft);
  box-shadow: 0 0 0 3px var(--accent-tint);
}

.composer-input {
  flex: 1;
  min-height: 24px;
  max-height: 200px;
  padding: var(--space-sm);
  background: transparent;
  border: none;
  resize: none;
  font-size: 14.5px;
  line-height: 1.5;
  color: var(--text);
}

.composer-input::placeholder {
  color: var(--text-soft);
}

.composer-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-button {
  height: 36px;
  padding: 0 var(--space-md);
  background: var(--accent);
  color: white;
  font-weight: 650;
  border-radius: var(--radius-sm);
  transition: background 140ms var(--ease-out), opacity 140ms var(--ease-out);
  white-space: nowrap;
}

.send-button:hover:not(:disabled) {
  background: var(--accent-hover);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
