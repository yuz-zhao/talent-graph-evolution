import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import UiIcon from './components/UiIcon.vue'
import { installAuthenticatedFetch } from './utils/authFetch'

import './css/style.css'
import './css/design-system.css'

const app = createApp(App)
app.component('UiIcon',UiIcon)

installAuthenticatedFetch()

// 全局错误捕获 — 帮助调试空白页问题
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err)
  console.error('[Vue Error Info]', info)
  const appEl = document.getElementById('app')
  if (appEl && !appEl.innerHTML.trim()) {
    appEl.innerHTML = '<div style="padding:40px;text-align:center;font-family:sans-serif"><h2 style="color:red">页面加载错误</h2><pre style="text-align:left;max-width:700px;margin:16px auto;background:#fee;padding:16px;border-radius:8px;overflow:auto;font-size:12px">' + (err.message || err) + '</pre></div>'
  }
}

app.use(createPinia())
app.use(router)
app.mount('#app')
