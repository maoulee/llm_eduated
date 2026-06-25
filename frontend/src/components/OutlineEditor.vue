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
  <div class="card outline-editor fade-in">
    <!-- Two-pane editor: preview | edit -->
    <div v-if="isEditing" class="editor-mode">
      <div class="editor-grid">
        <section class="pane preview-pane">
          <h3 class="pane-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            预览
          </h3>
          <div class="pane-scroll markdown-body" v-html="renderedMarkdown"></div>
        </section>
        <section class="pane editor-pane">
          <h3 class="pane-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
            </svg>
            编辑
          </h3>
          <textarea
            v-model="outlineMd"
            class="outline-textarea"
            spellcheck="false"
            placeholder="# 大纲标题&#10;## 一、知识点&#10;- …"
          />
        </section>
      </div>
      <div class="actions-row">
        <button class="btn btn-ghost" @click="$emit('cancel')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          取消
        </button>
        <button class="btn btn-primary" :disabled="isSaving" @click="save">
          <svg v-if="isSaving" class="spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" opacity="0.35" />
            <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
          {{ isSaving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>

    <!-- Read-only view -->
    <div v-else class="view-mode">
      <div class="view-scroll markdown-body" v-html="renderedMarkdown"></div>
      <div class="actions-row">
        <button class="btn btn-ghost" @click="handleEdit">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
          </svg>
          修改意见
        </button>
        <button class="btn btn-primary" @click="handleConfirm">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
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
}

/* ── Two-pane grid: preview | edit ── */
.editor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-lg);
  min-height: 400px;
}

.pane {
  display: flex;
  flex-direction: column;
  min-width: 0; /* prevent grid blowout */
}

/* Section subheads: small, uppercase, muted */
.pane-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-3);
}
.pane-title svg {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

/* Scroll regions for the markdown panes */
.pane-scroll,
.view-scroll {
  flex: 1;
  overflow: auto;
  padding: var(--space-md);
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  min-height: 0;
}
.view-scroll {
  min-height: 360px;
}

/* ── Edit textarea ── */
.outline-textarea {
  flex: 1;
  width: 100%;
  min-height: 400px;
  padding: var(--space-md);
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.5;
  color: var(--text);
  resize: vertical;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.outline-textarea::placeholder {
  color: var(--text-faint);
}
.outline-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--ring-accent);
}

/* ── Actions row: right-aligned, gap sm ── */
.actions-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-lg);
}

/* Reuse the global spinner sizing for inline use */
.btn-primary .spinner {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Buttons reuse global .btn / .btn-primary / .btn-ghost — svg sizing */
.btn svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

@media (max-width: 720px) {
  .editor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
