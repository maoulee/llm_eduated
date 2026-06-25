<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api/client';

const router = useRouter();
const isCreating = ref(false);
const error = ref<string | null>(null);
// Tracks which mode is currently creating, so only the clicked card shows its
// loading state while the other stays interactive. Minimal addition to support
// the per-card loading affordance required by the design contract.
const creatingMode = ref<'compose' | 'knowledge_point' | null>(null);

async function createSession(mode: 'compose' | 'knowledge_point') {
  try {
    isCreating.value = true;
    creatingMode.value = mode;
    error.value = null;
    const session = await api.createSession(mode);
    router.push(`/session/${session.id}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create session';
  } finally {
    isCreating.value = false;
    creatingMode.value = null;
  }
}
</script>

<template>
  <div class="home-view">
    <div class="container">
      <header class="home-header fade-in">
        <h1 class="home-title">EduTeacher Workbench</h1>
        <p class="subtitle">智能组卷与知识点出题系统</p>
      </header>

      <main class="home-main">
        <div class="entry-cards">
          <!-- 组卷 (compose) -->
          <button
            class="entry-card fade-in"
            :class="{ 'is-creating': creatingMode === 'compose' }"
            :disabled="isCreating"
            @click="() => createSession('compose')"
          >
            <span class="card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path d="M14 3v5h5" />
                <path d="M9 13h6" />
                <path d="M9 17h4" />
              </svg>
            </span>

            <span class="card-body">
              <h2>组卷</h2>
              <p class="card-desc">智能生成试卷</p>
            </span>

            <span class="card-afford">
              <template v-if="creatingMode === 'compose'">
                <span class="skeleton skeleton-afford" aria-label="创建中"></span>
              </template>
              <template v-else>开始 →</template>
            </span>
          </button>

          <!-- 知识点出题 (knowledge_point) -->
          <button
            class="entry-card fade-in"
            :class="{ 'is-creating': creatingMode === 'knowledge_point' }"
            :disabled="isCreating"
            @click="() => createSession('knowledge_point')"
          >
            <span class="card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="5" />
                <circle cx="12" cy="12" r="1" />
              </svg>
            </span>

            <span class="card-body">
              <h2>知识点出题</h2>
              <p class="card-desc">针对知识点生成题目</p>
            </span>

            <span class="card-afford">
              <template v-if="creatingMode === 'knowledge_point'">
                <span class="skeleton skeleton-afford" aria-label="创建中"></span>
              </template>
              <template v-else>开始 →</template>
            </span>
          </button>
        </div>

        <div v-if="error" class="error-strip fade-in" role="alert">
          创建会话失败：{{ error }}
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-app);
}

/* Centered container, max-width 880px, vertical padding space-16 */
.container {
  max-width: 880px;
  margin: 0 auto;
  padding: var(--space-16) var(--space-lg);
  width: 100%;
}

/* Hero */
.home-header {
  text-align: center;
  margin-bottom: var(--space-12);
}

.home-title {
  font-family: var(--font-serif);
  font-size: var(--text-4xl);
  font-weight: 600;
  letter-spacing: -0.5px;
  color: var(--text-strong);
  margin-bottom: var(--space-sm);
}

.subtitle {
  font-size: var(--text-lg);
  color: var(--text-muted);
}

/* Main */
.home-main {
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Entry-card grid: 2 cols >=640px, else 1; gap space-lg; max-width 680px */
.entry-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-lg);
  width: 100%;
  max-width: 680px;
}

@media (min-width: 640px) {
  .entry-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Each card = a button. Left-aligned, flex column space-between. */
.entry-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-md);
  min-height: 200px;
  padding: var(--space-12) var(--space-lg);
  text-align: left;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  transition: border-color var(--duration-enter) var(--ease-out),
              box-shadow var(--duration-enter) var(--ease-out),
              transform var(--duration-enter) var(--ease-out),
              opacity var(--duration-fast) var(--ease-out);
}

.entry-card:hover:not(:disabled) {
  border-color: var(--accent-soft);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.entry-card:focus-visible {
  outline: none;
  box-shadow: var(--ring-accent);
  border-color: var(--accent-soft);
}

.entry-card:active:not(:disabled) {
  transform: scale(0.985);
}

.entry-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* The clicked (creating) card: title dims to .7, no lift */
.entry-card.is-creating {
  opacity: 0.6;
  cursor: progress;
  transform: none;
}
.entry-card.is-creating:hover {
  transform: none;
}
.entry-card.is-creating .card-body {
  opacity: 0.7;
}

/* 56px icon chip: accent-tint bg, radius-md, centered 28px SVG in accent */
.card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: var(--accent-tint);
  border-radius: var(--radius-md);
  color: var(--accent);
  transition: background var(--duration-enter) var(--ease-out);
  flex-shrink: 0;
}

.card-icon svg {
  width: 28px;
  height: 28px;
}

.entry-card:hover:not(:disabled) .card-icon {
  background: var(--accent-tint-strong);
}

/* Mid: title + one-line desc */
.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  transition: opacity var(--duration-fast) var(--ease-out);
}

.card-body h2 {
  font-size: var(--text-2xl);
  font-weight: 500;
  color: var(--text-strong);
  line-height: 1.2;
}

.card-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
}

/* Bottom ghost affordance: text-sm accent, bottom-aligned */
.card-afford {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--accent);
  display: inline-flex;
  align-items: center;
  min-height: 18px;
}

/* Skeleton bar replacing the affordance text while creating */
.skeleton-afford {
  display: inline-block;
  width: 64px;
  height: 12px;
}

/* Error strip: red bg, 3px left red border, radius, padding-md, red text */
.error-strip {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--red-bg);
  border-left: 3px solid var(--red);
  border-radius: var(--radius);
  color: var(--red);
  font-size: var(--text-sm);
  max-width: 680px;
  width: 100%;
}

@media (prefers-reduced-motion: reduce) {
  .entry-card,
  .card-icon,
  .card-body {
    transition: none;
  }
  .entry-card:hover:not(:disabled) {
    transform: none;
  }
  .entry-card:active:not(:disabled) {
    transform: none;
  }
}
</style>
