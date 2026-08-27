import { inject } from 'vue'

export function useToast() {
  const toast = inject('$toast', null)
  if (!toast) {
    // fallback: when toast provider not mounted, use console
    return {
      success: (msg) => console.log('[Toast]', msg),
      warning: (msg) => console.warn('[Toast]', msg),
      error: (msg) => console.error('[Toast]', msg),
      info: (msg) => console.info('[Toast]', msg),
    }
  }
  return toast
}
