<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>

<template>
  <div class="app">
    <RouterView v-slot="{ Component }">
      <component :is="Component" class="app__view" />
    </RouterView>
  </div>
</template>

<style scoped>
/* App shell — intentionally thin. Views own their layout, width, and chrome.
 * No accent, no max-width container, no new surfaces. Just a flex column on the
 * warm app background so every route fills the viewport height. */
.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100%;
  background: var(--bg-app);
  color: var(--text);
  font-family: var(--font-sans);
}

/* Route fills the shell vertically; each view manages its own scrolling/width. */
.app__view {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
