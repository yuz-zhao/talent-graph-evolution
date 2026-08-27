<template>
  <div class="sidebar-rail w-[224px] min-w-[224px]" :class="{ 'is-collapsed': collapsed }">
    <div class="fixed inset-0 bg-gray-900/30 z-40 lg:hidden lg:z-auto transition-opacity duration-200" :class="sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'" aria-hidden="true"></div>

    <div
      id="sidebar"
      ref="sidebar"
      class="flex lg:flex! flex-col absolute z-40 left-0 top-0 lg:static lg:left-auto lg:top-auto lg:translate-x-0 h-screen w-[280px] min-w-[280px] shrink-0 bg-white dark:bg-gray-800 transition-all duration-300 ease-in-out"
      :class="[variant === 'v2' ? 'border-r border-gray-200 dark:border-gray-700/60' : 'rounded-r-2xl shadow-xs', sidebarOpen ? 'translate-x-0' : '-translate-x-[280px] lg:translate-x-0', { 'is-collapsed': collapsed }]"
    >
      <!-- Logo 区域 — 固定顶部不滚动 -->
      <div class="sidebar-brand shrink-0 px-4 pt-3 pb-0">
        <button
          ref="trigger"
          class="lg:hidden text-gray-500 hover:text-gray-400 mb-4"
          @click.stop="$emit('close-sidebar')"
          aria-controls="sidebar"
          :aria-expanded="sidebarOpen"
        >
          <span class="sr-only">关闭侧边栏</span>
          <svg class="w-6 h-6 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M10.7 18.7l1.4-1.4L7.8 13H20v-2H7.8l4.3-4.3-1.4-1.4L4 12z" />
          </svg>
        </button>

        <router-link
          class="sidebar-brand-link group"
          :to="route.path.startsWith('/user') ? '/user/dashboard' : '/admin/dashboard'"
        >
          <img class="sidebar-brand-logo" :src="TalentGraphLogo" alt="TalentGraph Evolution 岗位能力图谱动态演化系统" />
        </router-link>
      </div>

      <!-- 菜单区域 — 可独立滚动 -->
      <div ref="menuScroll" class="flex-1 overflow-y-auto overflow-x-hidden px-4 pb-4 sidebar-scroll" @scroll="onMenuScroll">
        <div class="pt-2">
          <section v-for="group in menuGroups" :key="group.name" class="sidebar-menu-group">
            <h3 v-if="group.name" class="sidebar-section-title text-xs font-semibold pl-3 tracking-wide"><span>{{ group.name }}</span></h3>
            <ul>
            <li v-for="item in group.items" :key="item.label">
              <router-link :to="item.path" custom v-slot="{ href, navigate }">
                <a
                  class="sidebar-menu-link group relative flex items-center rounded-xl px-3 py-2.5 text-sm font-medium truncate"
                  :class="{ 'is-active': isActive(item) }"
                  :href="href"
                  :title="collapsed ? item.label : undefined"
                  @click="navigate"
                >
                  <span class="absolute left-0 top-2 bottom-2 w-1 rounded-r-full transition-opacity duration-200" :class="isActive(item) ? 'opacity-100' : 'opacity-0'"></span>
                  <span class="shrink-0 grid place-items-center w-8 h-8 rounded-lg transition-all duration-200" :class="{ 'is-active': isActive(item) }">
                    <component :is="item.icon" :size="18" :stroke-width="2.15" />
                  </span>
                  <span class="ml-4 whitespace-nowrap">{{ item.label }}</span>
                </a>
              </router-link>
            </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import TalentGraphLogo from '../images/talentgraph-header-logo-v3.png'

export default {
  name: 'Sidebar',
  props: [
    'sidebarOpen',
    'variant',
    'menuItems',
    'collapsed',
  ],
  setup(props, { emit }) {
    const route = useRoute()
    const trigger = ref(null)
    const sidebar = ref(null)
    const menuScroll = ref(null)

    // 根据路由前缀区分管理员端 / 普通用户端，用不同的 sessionStorage key
    const storageKey = route.path.startsWith('/user/') ? 'userSidebarScrollTop' : 'adminSidebarScrollTop'

    const onMenuScroll = () => {
      if (menuScroll.value) {
        sessionStorage.setItem(storageKey, String(menuScroll.value.scrollTop))
      }
    }

    const restoreScroll = () => {
      nextTick(() => {
        const saved = sessionStorage.getItem(storageKey)
        if (menuScroll.value && saved !== null) {
          menuScroll.value.scrollTop = Number(saved) || 0
        }
      })
    }

    const menuItems = props.menuItems || []
    const menuGroups = computed(() => {
      const groups = []
      menuItems.forEach(item => {
        const name = item.group || ''
        let group = groups.find(g => g.name === name)
        if (!group) { group = { name, items: [] }; groups.push(group) }
        group.items.push(item)
      })
      return groups
    })
    const isActive = (item) => route.path === item.path || item.aliases?.some(path => route.path === path || (path.endsWith('/') && route.path.startsWith(path)))

    const clickHandler = ({ target }) => {
      if (!sidebar.value || !trigger.value) return
      if (
        !props.sidebarOpen ||
        sidebar.value.contains(target) ||
        trigger.value.contains(target)
      ) return
      emit('close-sidebar')
    }

    const keyHandler = ({ keyCode }) => {
      if (!props.sidebarOpen || keyCode !== 27) return
      emit('close-sidebar')
    }

    onMounted(() => {
      document.querySelector('body').classList.remove('sidebar-expanded')
      localStorage.removeItem('sidebar-expanded')
      document.addEventListener('click', clickHandler)
      document.addEventListener('keydown', keyHandler)
      restoreScroll()
    })

    watch(() => route.path, () => {
      restoreScroll()
    })

    onUnmounted(() => {
      document.removeEventListener('click', clickHandler)
      document.removeEventListener('keydown', keyHandler)
    })

    return {
      route,
      trigger,
      sidebar,
      menuScroll,
      menuItems,
      menuGroups,
      isActive,
      onMenuScroll,
      TalentGraphLogo,
    }
  },
}
</script>

<style>
.sidebar-scroll::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}
.sidebar-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar-scroll::-webkit-scrollbar-thumb {
  background: rgba(120, 120, 160, 0.25);
  border-radius: 999px;
}
.sidebar-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(120, 120, 160, 0.45);
}
.sidebar-scroll {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
#sidebar,
#sidebar * {
  -ms-overflow-style: none !important;
  scrollbar-width: none !important;
}
#sidebar::-webkit-scrollbar,
#sidebar *::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
  background: transparent !important;
}
</style>

<style scoped>
#sidebar {
  width: 224px !important;
  min-width: 224px !important;
  height: 100% !important;
  font-family: "Public Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  border-right: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  transition: transform var(--tg-motion-slow) var(--tg-ease-enter) !important;
}
.sidebar-rail,
#sidebar { transition: width 520ms cubic-bezier(.4,0,.2,1), min-width 520ms cubic-bezier(.4,0,.2,1), padding 520ms cubic-bezier(.4,0,.2,1), transform var(--tg-motion-slow) var(--tg-ease-enter) !important; }
.sidebar-rail { flex-shrink: 0; }
#sidebar { overflow-x: hidden; }
.sidebar-rail.is-collapsed,
#sidebar.is-collapsed { width: 72px !important; min-width: 72px !important; }
.sidebar-brand { display: none; }
.sidebar-brand-link {
  display: flex;
  min-height: 70px;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  padding: 7px 9px;
  border-radius: 10px;
  color: var(--tg-text);
  text-decoration: none;
  transition: background-color var(--tg-motion-fast) var(--tg-ease);
}
.sidebar-brand-link:hover { background: var(--tg-surface-subtle); }
.sidebar-brand-logo { display: block; width: 184px; max-width: 100%; height: 52px; object-fit: contain; object-position: left center; }
.sidebar-section-title { margin: 0 0 6px; padding-left: 12px; color: #858585 !important; font-size: 13px !important; font-weight: 500; line-height: 20px; letter-spacing: 0; }
.sidebar-menu-group { margin-bottom: 18px; }
.sidebar-menu-group:last-child { margin-bottom: 4px; }
.sidebar-scroll { padding: 26px 14px 20px !important; }
.sidebar-scroll ul { display: flex; flex-direction: column; gap: 3px; }
.sidebar-scroll li a {
  min-height: 48px;
  padding: 8px 12px !important;
  border-radius: 15px !important;
  color: #0a0a0a !important;
  font-size: 15px;
  font-weight: 400;
  line-height: 20px;
  box-shadow: none !important;
  transform: none !important;
  transition: color var(--tg-motion-fast) var(--tg-ease), background-color var(--tg-motion-fast) var(--tg-ease), width 520ms cubic-bezier(.4,0,.2,1), padding 520ms cubic-bezier(.4,0,.2,1) !important;
}
.sidebar-scroll li a:hover { color: #0a0a0a !important; background: #e9ebef !important; transform: none !important; }
.sidebar-scroll li a.is-active {
  color: #4f46e5 !important;
  background: #eef2ff !important;
  box-shadow: none !important;
  font-weight: 600;
}
.sidebar-scroll li a > span:first-child { display: none; }
.sidebar-scroll li a > span:nth-child(2) {
  width: 30px !important;
  height: 30px !important;
  border-radius: 0 !important;
  color: inherit !important;
  background: transparent !important;
  box-shadow: none !important;
  transition: color var(--tg-motion-fast) var(--tg-ease), background-color var(--tg-motion-fast) var(--tg-ease) !important;
}
.sidebar-scroll li a > span:last-child { min-width: 0; flex: 1; margin-left: 10px !important; font-size: 15px; font-weight: inherit; line-height: 21px; opacity: 1; max-width: 160px; overflow: hidden; transition: opacity 360ms ease, max-width 520ms cubic-bezier(.4,0,.2,1), margin-left 520ms cubic-bezier(.4,0,.2,1); }
@media (min-width: 1024px) {
  #sidebar.is-collapsed .sidebar-scroll { padding: 26px 12px 20px !important; }
  #sidebar.is-collapsed .sidebar-section-title { height: 1px; margin: 8px 0; padding: 0; overflow: hidden; color: transparent !important; background: #e5e7eb; }
  #sidebar.is-collapsed .sidebar-menu-group { margin-bottom: 8px; }
  #sidebar.is-collapsed .sidebar-scroll li a { width: 48px; min-height: 48px; justify-content: center; padding: 8px !important; }
  #sidebar.is-collapsed .sidebar-scroll li a > span:last-child { opacity: 0; max-width: 0; margin-left: 0 !important; }
  #sidebar.is-collapsed .sidebar-scroll li a > span:nth-child(2) { width: 30px !important; height: 30px !important; }
}
@media (max-width: 1023px) {
  .sidebar-rail { width: 0 !important; min-width: 0 !important; }
  #sidebar { width: 224px !important; min-width: 224px !important; background: var(--tg-canvas) !important; }
  .sidebar-brand { display: block; }
}
</style>
