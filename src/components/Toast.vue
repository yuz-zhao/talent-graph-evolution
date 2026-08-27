<template>
  <Teleport to="body">
    <TransitionGroup name="toast" tag="div" class="toast-container">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type" @click="dismiss(t.id)">
        <div class="toast-icon">
          <CheckCircle v-if="t.type==='success'" :size="18"/>
          <AlertTriangle v-else-if="t.type==='warning'" :size="18"/>
          <XCircle v-else-if="t.type==='error'" :size="18"/>
          <Info v-else :size="18"/>
        </div>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import CheckCircle from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import AlertTriangle from '@lucide/vue/dist/esm/icons/triangle-alert.mjs'
import XCircle from '@lucide/vue/dist/esm/icons/circle-x.mjs'
import Info from '@lucide/vue/dist/esm/icons/info.mjs'

const toasts = ref([])
let id = 0

function show(message, type = 'success', duration = 3000) {
  const tid = ++id
  toasts.value.push({ id: tid, message, type })
  setTimeout(() => dismiss(tid), duration)
}

function dismiss(tid) {
  toasts.value = toasts.value.filter(t => t.id !== tid)
}

defineExpose({ show })
</script>

<style scoped>
.toast-container{position:fixed;top:22px;left:50%;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;transform:translateX(-50%)}
.toast{position:relative;display:flex;align-items:center;gap:10px;min-width:360px;max-width:520px;padding:15px 20px;overflow:hidden;border:1px solid var(--tg-border);border-radius:16px;color:var(--tg-text);background:rgba(255,255,255,.94);font-size:13px;font-weight:500;cursor:pointer;pointer-events:auto;box-shadow:0 12px 36px rgba(23,32,51,.10);backdrop-filter:blur(14px);transition:opacity var(--tg-motion-base) var(--tg-ease),transform var(--tg-motion-base) var(--tg-ease)}
.toast::before{display:none}
.toast.success{border-color:#badfce;background:rgba(235,248,241,.96);color:var(--tg-success)}
.toast.warning{border-color:#f0d8aa;background:rgba(255,248,233,.96);color:var(--tg-warning)}
.toast.error{border-color:#efc3c3;background:rgba(255,241,241,.96);color:var(--tg-danger)}
.toast.info{border-color:#c8ddf5;background:rgba(239,247,255,.96);color:var(--tg-info)}
.toast-icon{flex-shrink:0;color:currentColor}
.toast-msg{flex:1;line-height:1.4}
.toast-msg{color:var(--tg-text)}

.toast-enter-active{transition:opacity var(--tg-motion-base) var(--tg-ease-enter),transform var(--tg-motion-base) var(--tg-ease-enter)}
.toast-leave-active{transition:opacity var(--tg-motion-fast) var(--tg-ease-exit),transform var(--tg-motion-fast) var(--tg-ease-exit)}
.toast-enter-from{opacity:0;transform:translateY(-8px)}
.toast-leave-to{opacity:0;transform:translateY(-4px)}
@media(max-width:639px){.toast-container{top:12px;right:12px;left:12px;transform:none}.toast{width:100%;min-width:0;max-width:none}}
</style>
