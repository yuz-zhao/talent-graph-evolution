<template>
  <transition name="search-fade"><div v-show="modalOpen" class="fixed inset-0 bg-gray-900/30 z-50" aria-hidden="true" /></transition>
  <transition name="search-panel">
    <div v-show="modalOpen" :id="id" class="fixed inset-0 z-50 overflow-hidden flex items-start top-20 mb-4 justify-center px-4 sm:px-6" role="dialog" aria-modal="true">
      <div ref="modalContent" class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-auto max-w-2xl w-full max-h-full rounded-xl shadow-lg">
        <form class="border-b border-gray-200 dark:border-gray-700" @submit.prevent="submitSearch()">
          <div class="relative">
            <label :for="searchId" class="sr-only">搜索</label>
            <input :id="searchId" ref="searchInput" v-model="query" class="w-full dark:text-gray-300 bg-white dark:bg-gray-800 border-0 focus:ring-transparent placeholder-gray-400 appearance-none py-3 pl-10 pr-4" type="search" placeholder="搜索岗位、技能、简历或图谱节点..." />
            <button class="absolute inset-0 right-auto group" type="submit" aria-label="搜索">
              <svg class="fill-current text-gray-400 ml-4 mr-2" width="16" height="16" viewBox="0 0 16 16"><path d="M7 14c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7zm0-12a5 5 0 100 10A5 5 0 007 2z"/><path d="M15.707 14.293L13.314 11.9a8 8 0 01-1.414 1.414l2.393 2.393a1 1 0 001.414-1.414z"/></svg>
            </button>
          </div>
        </form>
        <div class="py-4 px-2">
          <section v-if="recentSearches.length" class="mb-3">
            <div class="text-xs font-semibold text-gray-400 px-2 mb-2">最近搜索</div>
            <button v-for="item in recentSearches" :key="item" type="button" class="w-full flex items-center p-2 text-sm text-gray-800 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg" @click="submitSearch(item)">
              <span class="text-gray-400 mr-3">↻</span><span>{{ item }}</span>
            </button>
          </section>
          <section>
            <div class="text-xs font-semibold text-gray-400 px-2 mb-2">常用页面</div>
            <router-link v-for="item in pages" :key="item.title" :to="item.to" class="flex items-center p-2 text-sm text-gray-800 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg" @click="$emit('close-modal')">
              <span class="text-gray-400 mr-3">▣</span><span><b>{{ item.title }}</b> - <span class="text-gray-500">{{ item.desc }}</span></span>
            </router-link>
          </section>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps(['id', 'searchId', 'modalOpen'])
const emit = defineEmits(['open-modal', 'close-modal'])
const route = useRoute(), router = useRouter()
const modalContent = ref(null), searchInput = ref(null), query = ref(''), recentSearches = ref([])
const isAdmin = computed(() => route.path.startsWith('/admin'))
const storageKey = computed(() => `talentgraph_recent_searches_${isAdmin.value ? 'admin' : 'user'}`)
const pages = computed(() => isAdmin.value ? [
  { title:'数据治理', desc:'查看数据源和采集状态', to:'/admin/data-sources' },
  { title:'岗位图谱', desc:'浏览岗位与技能关系', to:'/admin/knowledge-graph' },
  { title:'系统设置', desc:'管理用户和运行参数', to:'/admin/settings' },
] : [
  { title:'发现岗位', desc:'搜索和筛选岗位', to:'/user/jobs' },
  { title:'我的画像', desc:'查看简历解析结果', to:'/user/resume' },
  { title:'成长计划', desc:'查看学习路径和进度', to:'/user/learning' },
])
const loadRecent = () => { try { recentSearches.value = JSON.parse(localStorage.getItem(storageKey.value) || '[]').slice(0, 4) } catch { recentSearches.value = [] } }
const targetFor = text => {
  const rules = isAdmin.value
    ? [[/用户|账号/, '/admin/settings'], [/设置|配置/, '/admin/settings'], [/采集|数据源|治理/, '/admin/data-sources'], [/趋势|演化/, '/admin/skill-evolution'], [/评估|验证/, '/admin/evaluation'], [/问答|GraphRAG/i, '/admin/graphrag'], [/新岗位|发现/, '/admin/new-jobs']]
    : [[/简历|画像/, '/user/resume'], [/收藏/, '/user/match-favorites'], [/学习|课程|成长/, '/user/learning'], [/差距/, '/user/gap-analysis'], [/匹配|推荐/, '/user/job-recommend'], [/图谱/, '/user/graph']]
  return { path: rules.find(([pattern]) => pattern.test(text))?.[1] || (isAdmin.value ? '/admin/knowledge-graph' : '/user/jobs'), query:{ keyword:text } }
}
const submitSearch = value => {
  const text = String(value ?? query.value).trim()
  if (!text) return searchInput.value?.focus()
  recentSearches.value = [text, ...recentSearches.value.filter(item => item !== text)].slice(0, 4)
  localStorage.setItem(storageKey.value, JSON.stringify(recentSearches.value))
  router.push(targetFor(text)); query.value = ''; emit('close-modal')
}
const clickHandler = ({ target }) => { if (props.modalOpen && !modalContent.value?.contains(target)) emit('close-modal') }
const keyHandler = event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); emit('open-modal'); return }
  if (props.modalOpen && event.key === 'Escape') emit('close-modal')
}
onMounted(() => { document.addEventListener('click', clickHandler); document.addEventListener('keydown', keyHandler) })
onUnmounted(() => { document.removeEventListener('click', clickHandler); document.removeEventListener('keydown', keyHandler) })
watch(() => props.modalOpen, open => { if (open) { loadRecent(); nextTick(() => searchInput.value?.focus()) } })
</script>

<style scoped>
.search-fade-enter-active,.search-fade-leave-active,.search-panel-enter-active,.search-panel-leave-active{transition:all .18s ease}.search-fade-enter-from,.search-fade-leave-to{opacity:0}.search-panel-enter-from,.search-panel-leave-to{opacity:0;transform:translateY(12px)}
</style>
