<template>
  <header
    class="sticky top-0 before:absolute before:inset-0 before:backdrop-blur-md max-lg:before:bg-white/90 dark:max-lg:before:bg-gray-800/90 before:-z-10 z-30"
    :class="[
      variant === 'v2' || variant === 'v3' ? 'before:bg-white after:absolute after:h-px after:inset-x-0 after:top-full after:bg-gray-200 dark:after:bg-gray-700/60 after:-z-10' : 'max-lg:shadow-xs lg:before:bg-gray-100/90 dark:lg:before:bg-gray-900/90',
      variant === 'v2' ? 'dark:before:bg-gray-800' : '',
      variant === 'v3' ? 'dark:before:bg-gray-900' : '',
    ]"
  >
    <div class="header-inner px-4 sm:px-6">
      <div
        class="flex items-center justify-between"
        :class="variant === 'v2' || variant === 'v3' ? '' : 'lg:border-b border-gray-200 dark:border-gray-700/60'"
      >

        <!-- 品牌与移动端菜单 -->
        <div class="header-brand flex items-center" :class="{ 'is-collapsed': sidebarCollapsed }">

          <!-- 汉堡菜单按钮 -->
          <button class="text-gray-500 hover:text-gray-600 dark:hover:text-gray-400 lg:hidden" @click.stop="$emit('toggle-sidebar')" aria-controls="sidebar" :aria-expanded="sidebarOpen">
            <span class="sr-only">打开侧边栏</span>
            <svg class="w-6 h-6 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <rect x="4" y="5" width="16" height="2" />
              <rect x="4" y="11" width="16" height="2" />
              <rect x="4" y="17" width="16" height="2" />
            </svg>
          </button>
          <button
            class="sidebar-collapse-btn hidden lg:grid"
            type="button"
            :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="$emit('toggle-collapse')"
          >
            <component :is="sidebarCollapsed ? PanelLeftOpen : PanelLeftClose" :size="19" :stroke-width="1.9" />
          </button>
          <router-link class="header-brand-link" :to="homePath">
            <img :src="TalentGraphLogo" alt="TalentGraph Evolution" />
          </router-link>
        </div>

        <!-- 右侧 -->
        <div class="header-actions flex items-center space-x-2">
          <div>
            <button
              class="header-search h-9 flex items-center justify-center rounded-full"
              :class="{ 'bg-gray-200 dark:bg-gray-800': searchModalOpen }"
              @click.stop="searchModalOpen = true"
              aria-controls="search-modal"
            >
              <span class="sr-only">搜索</span>
              <svg class="fill-current text-gray-500/80 dark:text-gray-400/80" width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7 14c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7ZM7 2C4.243 2 2 4.243 2 7s2.243 5 5 5 5-2.243 5-5-2.243-5-5-5Z" />
                  <path d="m13.314 11.9 2.393 2.393a.999.999 0 1 1-1.414 1.414L11.9 13.314a8.019 8.019 0 0 0 1.414-1.414Z" />
              </svg>
              <span class="header-search__label">搜索</span>
              <kbd class="header-search__key">Ctrl K</kbd>
            </button>          
            <SearchModal id="search-modal" searchId="search" :modalOpen="searchModalOpen" @open-modal="searchModalOpen = true" @close-modal="searchModalOpen = false" />
          </div>
          <Notifications align="right" />
          <Help align="right" />
          <!-- 分割线 -->
          <hr class="w-px h-6 bg-gray-200 dark:bg-gray-700/60 border-none" />
          <UserMenu align="right" />

        </div>

      </div>
    </div>
  </header>
</template>

<script>
import { ref } from 'vue'

import SearchModal from '../components/ModalSearch.vue'
import Notifications from '../components/DropdownNotifications.vue'
import Help from '../components/DropdownHelp.vue'

import UserMenu from '../components/DropdownProfile.vue'
import TalentGraphLogo from '../images/talentgraph-header-logo-v3.png'
import { useRoute } from 'vue-router'
import PanelLeftClose from '@lucide/vue/dist/esm/icons/panel-left-close.mjs'
import PanelLeftOpen from '@lucide/vue/dist/esm/icons/panel-left-open.mjs'

export default {
  name: 'Header',
  props: [
    'sidebarOpen',
    'variant',
    'sidebarCollapsed',
  ],
  components: {
    SearchModal,
    Notifications,
    Help,
    PanelLeftClose,
    PanelLeftOpen,

    UserMenu,
  },
  setup() {
    const searchModalOpen = ref(false)
    const route = useRoute()
    const isUser = () => route.path.startsWith('/user')
    return {
      searchModalOpen,
      TalentGraphLogo,
      homePath: isUser() ? '/user/dashboard' : '/admin/dashboard',
      PanelLeftClose,
      PanelLeftOpen,
    }
  }  
}
</script>

<style scoped>
header { position: relative !important; top: auto !important; height: 68px; flex: 0 0 68px; border: 0 !important; background: var(--tg-canvas) !important; backdrop-filter: none; box-shadow: none !important; }
header::before, header::after { display: none !important; }
header > div > div { height: 68px !important; border-bottom: 0 !important; }
.header-inner { height: 68px; }
.header-brand { width: 224px; flex: 0 0 224px; gap: 10px; }
/* 收起侧边栏时保留品牌 logo —— 仅收窄下方菜单栏，不隐藏 logo */
.header-brand.is-collapsed { width: 224px; flex-basis: 224px; gap: 10px; }
.header-brand-link { display: flex; align-items: center; height: 52px; transform: translateY(4px); }
.sidebar-collapse-btn { width: 40px; height: 40px; flex: 0 0 40px; place-items: center; border: 0 !important; border-radius: 10px; color: #111827; background: transparent; box-shadow: none !important; cursor: pointer; transition: background-color var(--tg-motion-fast) var(--tg-ease) !important; }
.sidebar-collapse-btn:hover { background: rgba(17, 24, 39, 0.06); color: #000; }
.header-brand-link img { display: block; width: 168px; max-height: 48px; object-fit: contain; object-position: left center; }
header button { transition: color var(--tg-motion-fast) var(--tg-ease), background-color var(--tg-motion-fast) var(--tg-ease) !important; }
.header-search { width: 224px; gap: 9px; padding: 0 8px 0 13px; border: 1px solid var(--tg-border); border-radius: 14px; color: var(--tg-text-secondary); background: #fff; }
.header-search:hover { border-color: var(--tg-border-strong); background: #fff; }
.header-search__label { flex: 1; text-align: left; font-size: 13px; }
.header-search__key { padding: 3px 7px; border: 1px solid var(--tg-border); border-radius: 7px; color: var(--tg-text-muted); background: var(--tg-surface-subtle); font-size: 10px; font-family: inherit; }
@media (max-width: 767px) { .header-search { width: 36px; padding: 0; } .header-search__label, .header-search__key { display: none; } }
@media (max-width: 1100px) { .header-brand { width: auto; flex: 0 1 auto; } }
</style>
