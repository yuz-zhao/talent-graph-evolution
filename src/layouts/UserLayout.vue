<template>
  <div class="app-shell app-shell--user flex h-screen flex-col overflow-hidden" data-role="user">
    <Header :sidebarOpen="sidebarOpen" :sidebarCollapsed="sidebarCollapsed" @toggle-sidebar="sidebarOpen = !sidebarOpen" @toggle-collapse="toggleSidebarCollapse" />
    <div class="app-workspace flex min-h-0 flex-1 overflow-hidden">
      <Sidebar :sidebarOpen="sidebarOpen" :collapsed="sidebarCollapsed" :menuItems="userMenuItems" @close-sidebar="sidebarOpen = false" />
      <div class="app-shell__content relative flex min-w-0 flex-1 flex-col overflow-y-auto overflow-x-hidden">
        <main class="app-main grow">
          <ModuleTabs showActions @refresh="refreshKey++" />
          <router-view v-slot="{ Component, route }">
            <transition name="workspace" mode="out-in">
              <component :is="Component" :key="`${route.path}-${refreshKey}`" />
            </transition>
          </router-view>
        </main>
      </div>
    </div>
    <TalentGraphAI />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Sidebar from '../partials/Sidebar.vue'
import Header from '../partials/Header.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import TalentGraphAI from '../components/TalentGraphAI/TalentGraphAI.vue'
import { userMenuItems } from '../constants/menus.js'

const sidebarOpen = ref(false)
const refreshKey = ref(0)
const sidebarCollapsed = ref(localStorage.getItem('userSidebarCollapsed') === 'true')
const toggleSidebarCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('userSidebarCollapsed', String(sidebarCollapsed.value))
}
</script>
