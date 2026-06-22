import { createApp } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import './style.css';
import App from './App.vue';
import HomeView from './views/HomeView.vue';
import SessionView from './views/SessionView.vue';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/session/:id', component: SessionView, props: true },
  ],
});

const app = createApp(App);
app.use(router);
app.mount('#app');
