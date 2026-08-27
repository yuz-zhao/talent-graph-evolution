<template>
  <div class="relative inline-flex">
    <button ref="trigger" class="inline-flex justify-center items-center group" aria-haspopup="true"
      @click.prevent="dropdownOpen = !dropdownOpen" :aria-expanded="dropdownOpen">
      <img class="w-8 h-8 rounded-full" :src="UserAvatar" width="32" height="32" alt="用户头像" />
      <div class="flex items-center truncate">
        <span class="truncate ml-2 text-sm font-medium text-gray-600 dark:text-gray-100 group-hover:text-gray-800 dark:group-hover:text-white">{{ displayName }}</span>
        <svg class="w-3 h-3 shrink-0 ml-1 fill-current text-gray-400 dark:text-gray-500" viewBox="0 0 12 12">
          <path d="M5.9 11.4L.5 6l1.4-1.4 4 4 4-4L11.3 6z" />
        </svg>
      </div>
    </button>

    <!-- 下拉菜单 -->
    <transition enter-active-class="transition ease-out duration-200 transform" enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-out duration-200"
      leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-show="dropdownOpen"
        class="origin-top-right z-10 absolute top-full min-w-44 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700/60 py-1.5 rounded-lg shadow-lg overflow-hidden mt-1"
        :class="align === 'right' ? 'right-0' : 'left-0'">
        <div class="pt-0.5 pb-2 px-3 mb-1 border-b border-gray-200 dark:border-gray-700/60">
          <div class="font-medium text-gray-800 dark:text-gray-100">{{ displayName }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">{{ roleName }}</div>
        </div>
        <ul ref="dropdown" @focusin="dropdownOpen = true" @focusout="dropdownOpen = false">
          <li v-if="isAdmin">
            <button class="font-medium text-sm text-violet-500 hover:text-violet-600 dark:hover:text-violet-400 flex items-center py-1 px-3 w-full text-left"
              @click="openModal">账户设置</button>
          </li>
          <li v-else>
            <router-link class="font-medium text-sm text-violet-500 hover:text-violet-600 dark:hover:text-violet-400 flex items-center py-1 px-3"
              :to="'/user/profile'" @click="dropdownOpen = false">账户设置</router-link>
          </li>
          <li>
            <button class="font-medium text-sm text-violet-500 hover:text-violet-600 dark:hover:text-violet-400 flex items-center py-1 px-3 w-full text-left"
              @click="logout">退出登录</button>
          </li>
        </ul>
      </div>
    </transition>

    <!-- 管理员账户弹窗 -->
    <Teleport to="body">
      <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0"
        enter-to-class="opacity-100" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100"
        leave-to-class="opacity-0">
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4"
          @click.self="closeModal">
          <div class="fixed inset-0 bg-gray-900/50 backdrop-blur-sm"></div>
          <div class="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md p-6 z-10">
            <div class="flex items-center justify-between mb-5">
              <h2 class="text-lg font-bold text-gray-800 dark:text-gray-100">我的账户</h2>
              <button @click="closeModal"
                class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>

            <!-- 账户信息 -->
            <div class="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 mb-5 space-y-2">
              <div class="flex justify-between"><span class="text-sm text-gray-500">账号</span><span class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ user.username }}</span></div>
              <div class="flex justify-between"><span class="text-sm text-gray-500">姓名</span><span class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ user.real_name }}</span></div>
              <div class="flex justify-between"><span class="text-sm text-gray-500">角色</span><span class="text-sm font-medium text-violet-600">系统管理员</span></div>
              <div class="flex justify-between"><span class="text-sm text-gray-500">最后登录</span><span class="text-sm text-gray-500">{{ user.last_login_at || '—' }}</span></div>
            </div>

            <!-- 修改密码 -->
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">修改密码</h3>
            <div class="space-y-3">
              <input v-model="pwd.old" type="password"
                class="form-input w-full text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2"
                placeholder="当前密码" />
              <input v-model="pwd.new1" type="password"
                class="form-input w-full text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2"
                placeholder="新密码" />
              <input v-model="pwd.new2" type="password"
                class="form-input w-full text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2"
                placeholder="确认新密码" />
              <button @click="changePwd"
                class="btn bg-violet-600 text-white hover:bg-violet-700 text-sm w-full">修改密码</button>
            </div>
            <p class="text-xs text-gray-400 mt-2 text-center">此功能需后端接口支持，当前为界面展示</p>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script>
import { computed, ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import UserAvatar from '../images/user-avatar-32.png'

const readUser = () => {
  try { return JSON.parse(localStorage.getItem('user') || '{}') }
  catch { return {} }
}

export default {
  name: 'DropdownProfile',
  props: ['align'],
  setup() {
    const router = useRouter()
    const dropdownOpen = ref(false)
    const trigger = ref(null)
    const dropdown = ref(null)
    const user = ref(readUser())
    const showModal = ref(false)
    const pwd = reactive({ old: '', new1: '', new2: '' })
    const displayName = computed(() => user.value.real_name || user.value.realName || '用户')
    const roleName = computed(() => user.value.role === 'user' ? '普通用户' : '系统管理员')
    const isAdmin = computed(() => user.value.role === 'admin')

    const openModal = () => {
      dropdownOpen.value = false
      showModal.value = true
    }
    const closeModal = () => {
      showModal.value = false
      pwd.old = ''; pwd.new1 = ''; pwd.new2 = ''
    }
    const changePwd = () => {
      if (!pwd.old || !pwd.new1) return alert('请填写密码')
      if (pwd.new1 !== pwd.new2) return alert('两次新密码不一致')
      if (pwd.new1.length < 6) return alert('密码长度不能少于6位')
      alert('密码修改功能需后端接口支持，此处为界面展示')
      closeModal()
    }

    const logout = () => {
      localStorage.removeItem('user')
      localStorage.removeItem('token')
      dropdownOpen.value = false
      router.push('/signin')
    }

    const clickHandler = ({ target }) => {
      if (!dropdownOpen.value || dropdown.value.contains(target) || trigger.value.contains(target)) return
      dropdownOpen.value = false
    }
    const keyHandler = ({ keyCode }) => {
      if (!dropdownOpen.value || keyCode !== 27) return
      dropdownOpen.value = false
    }

    onMounted(() => {
      document.addEventListener('click', clickHandler)
      document.addEventListener('keydown', keyHandler)
      user.value = readUser()
    })
    onUnmounted(() => {
      document.removeEventListener('click', clickHandler)
      document.removeEventListener('keydown', keyHandler)
    })

    return { UserAvatar, dropdownOpen, trigger, dropdown, user, displayName, roleName, isAdmin, showModal, pwd, openModal, closeModal, changePwd, logout }
  },
}
</script>
