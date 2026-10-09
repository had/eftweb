import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useSettingsStore } from './stores/settings'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)

useSettingsStore(pinia).loadSettings().finally(() => {
  app.mount('#app')
  document.documentElement.classList.remove('theme-loading')
})
