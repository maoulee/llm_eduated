<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { marked } from 'marked';
import { api } from '../api/client';

const props = defineProps<{
  sessionId: string;
  readonly?: boolean;
}>();

const emit = defineEmits<{
  saved: [outline: string];
  confirmed: [];
  edit: [];
  cancel: [];
}>();

const outlineMd = ref('');
const isEditing = ref(!props.readonly);
const isSaving = ref(false);

const renderedMarkdown = computed(() => marked(outlineMd.value));

async function loadOutline() {
  try {
    const data = await api.getOutline(props.sessionId);
    outlineMd.value = data.outline_md;
  } catch (err) {
    console.error('Failed to load outline:', err);
  }
}

async function save() {
  try {
    isSaving.value = true;
    await api.saveOutline(props.sessionId, outlineMd.value);
    emit('saved', outlineMd.value);
  } catch (err) {
    console.error('Failed to save outline:', err);
  } finally {
    isSaving.value = false;
  }
}

function handleEdit() {
  isEditing.value = true;
  emit('edit');
}

function handleConfirm() {
  emit('confirmed');
}

onMounted(() => {
  loadOutline();
});
</script>

<template>
  <div class="outline-editor">
    <div v-if="isEditing" class="editor-mode">
      <div class="editor-container">
        <div class="preview-pane">
          <h3>预览</h3>
          <div class="markdown-body" v-html="renderedMarkdown"></div>
        </div>
        <div class="editor-pane">
          <h3>编辑</h3>
          <textarea
            v-model="outlineMd"
            class="outline-textarea"
            spellcheck="false"
          />
        </div>
      </div>
      <div class="editor-actions">
        <button class="btn btn-secondary" @click="$emit('cancel')">
          取消
        </button>
        <button class="btn btn-primary" :disabled="isSaving" @click="save">
          {{ isSaving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
    <div v-else class="view-mode">
      <div class="markdown-body" v-html="renderedMarkdown"></div>
      <div class="view-actions">
        <button class="btn btn-secondary" @click="handleEdit">
          修改意见
        </button>
        <button class="btn btn-primary" @click="handleConfirm">
          确认出题
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.outline-editor {
  margin: var(--space-md) 0;
  padding: var(--space-lg);
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.editor-mode h3,
.view-mode h3 {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: var(--space-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.editor-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-lg);
  margin-bottom: var(--space-lg);
  min-height: 400px;
}

.preview-pane,
.editor-pane {
  display: flex;
  flex-direction: column;
}

.markdown-body {
  font-size: 14.5px;
  line-height: 1.6;
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
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--space-sm);
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

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: var(--space-lg);
  margin-bottom: var(--space-sm);
}

.outline-textarea {
  flex: 1;
  width: 100%;
  min-height: 400px;
  padding: var(--space-md);
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

.outline-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-tint);
}

.editor-actions,
.view-actions {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
  margin-top: var(--space-md);
}

.btn {
  height: 36px;
  padding: 0 var(--space-md);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 140ms var(--ease-out), opacity 140ms var(--ease-out);
}

.btn-primary {
  background: var(--accent);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-subtle);
  color: var(--text);
}

.btn-secondary:hover {
  background: var(--bg-muted);
}
</style>
