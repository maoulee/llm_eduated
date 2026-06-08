<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api/client';

const router = useRouter();
const isCreating = ref(false);
const error = ref<string | null>(null);

async function createSession(mode: 'compose' | 'knowledge_point') {
  try {
    isCreating.value = true;
    error.value = null;
    const session = await api.createSession(mode);
    router.push(`/session/${session.id}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create session';
  } finally {
    isCreating.value = false;
  }
}
</script>

<template>
  <div class="home-view">
    <div class="container">
      <header class="home-header">
        <h1>EduTeacher Workbench</h1>
        <p class="subtitle">智能组卷与知识点出题系统</p>
      </header>

      <main class="home-main">
        <div class="entry-cards">
          <button
            class="entry-card"
            :disabled="isCreating"
            @click="() => createSession('compose')"
          >
            <div class="card-icon">📝</div>
            <h2>组卷</h2>
            <p>智能生成试卷</p>
          </button>

          <button
            class="entry-card"
            :disabled="isCreating"
            @click="() => createSession('knowledge_point')"
          >
            <div class="card-icon">🎯</div>
            <h2>知识点出题</h2>
            <p>针对知识点生成题目</p>
          </button>
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <div v-if="isCreating" class="loading-state">
          <div class="spinner"></div>
          <p>创建会话中...</p>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg-app);
}

.container {
  max-width: 1000px;
  margin: 0 auto;
  padding: var(--space-xl);
  width: 100%;
}

.home-header {
  text-align: center;
  margin-bottom: var(--space-xl);
}

.home-header h1 {
  font-size: 48px;
  font-weight: 600;
  color: var(--text-strong);
  margin-bottom: var(--space-sm);
  letter-spacing: -0.5px;
}

.subtitle {
  font-size: 18px;
  color: var(--text-muted);
}

.home-main {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.entry-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-lg);
  width: 100%;
  max-width: 700px;
}

.entry-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-xl);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: border-color 140ms var(--ease-out), box-shadow 140ms var(--ease-out), transform 140ms var(--ease-out);
}

.entry-card:hover:not(:disabled) {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.entry-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.card-icon {
  font-size: 48px;
  margin-bottom: var(--space-md);
}

.entry-card h2 {
  font-size: 24px;
  font-weight: 500;
  color: var(--text-strong);
  margin-bottom: var(--space-sm);
}

.entry-card p {
  font-size: 14.5px;
  color: var(--text-muted);
  text-align: center;
}

.error-message {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--red-bg);
  color: var(--red);
  border-radius: var(--radius);
  text-align: center;
}

.loading-state {
  margin-top: var(--space-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  color: var(--text-muted);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--bg-fill);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
