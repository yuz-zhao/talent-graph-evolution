<template>
  <router-view v-slot="{ Component, route }">
    <transition :name="route.meta.transition || 'page'" appear>
      <component :is="Component" :key="route.matched[0]?.path || route.path" />
    </transition>
  </router-view>
  <Toast ref="toastRef" />
</template>

<script>
import { ref, provide } from 'vue'
import Toast from './components/Toast.vue'

export default {
  components: { Toast },
  setup() {
    const toastRef = ref(null)
    const toast = {
      success: (msg) => toastRef.value?.show(msg, 'success'),
      warning: (msg) => toastRef.value?.show(msg, 'warning'),
      error: (msg) => toastRef.value?.show(msg, 'error'),
      info: (msg) => toastRef.value?.show(msg, 'info'),
    }
    provide('$toast', toast)
    return { toastRef }
  },
}
</script>

<style>
.page-enter-active { transition: opacity 340ms cubic-bezier(.16,1,.3,1), transform 340ms cubic-bezier(.16,1,.3,1); }
.page-enter-from { opacity: 0; transform: translateY(7px); }
.page-leave-active { display: none; }
</style>
