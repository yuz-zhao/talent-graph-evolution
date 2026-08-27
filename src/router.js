import { createRouter, createWebHistory } from 'vue-router'

const pages = import.meta.glob('./pages/*.vue')
const page = (path) => pages[path]

const AdminLayout = () => import('./layouts/AdminLayout.vue')
const UserLayout = () => import('./layouts/UserLayout.vue')

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0, left: 0 }
  },
  routes: [
    { path: '/', redirect: '/signin' },
    { path: '/signin', name: 'Signin', component: page('./pages/Signin.vue') },
    { path: '/register', name: 'Register', component: page('./pages/Register.vue') },
    { path: '/flow', name: 'Flow', component: page('./pages/FlowView.vue') },

    // 管理员端 (8页)
    {
      path: '/admin', component: AdminLayout,
      children: [
        { path: 'dashboard', name: 'Dashboard', component: page('./pages/Dashboard.vue') },
        { path: 'data-sources', name: 'DataSources', component: page('./pages/AdminDataSources.vue') },
        { path: 'new-jobs', name: 'NewJobs', component: page('./pages/AdminNewJobs.vue') },
        { path: 'knowledge-graph', name: 'KnowledgeGraph', component: page('./pages/AdminKnowledgeGraph.vue') },
        { path: 'skill-evolution', name: 'SkillEvolution', component: page('./pages/AdminSkillEvolution.vue') },
        { path: 'evaluation', name: 'Evaluation', component: page('./pages/AdminEvaluation.vue') },
        { path: 'behavior', name: 'BehaviorAnalytics', component: page('./pages/AdminBehaviorAnalytics.vue') },
        { path: 'graphrag', name: 'GraphRAG', component: page('./pages/AdminGraphRAG.vue') },
        { path: 'cross-validation', name: 'CrossValidation', component: page('./pages/AdminCrossValidation.vue') },
        { path: 'settings', name: 'Settings', component: page('./pages/AdminSettings.vue') },
      ],
    },

    // 学生端 (8页)
    {
      path: '/user', component: UserLayout,
      children: [
        { path: 'dashboard', name: 'UserDashboard', component: page('./pages/UserDashboard.vue') },
        { path: 'profile', name: 'UserProfile', component: page('./pages/UserProfile.vue') },
        { path: 'resume', name: 'UserResume', component: page('./pages/UserResume.vue') },
        { path: 'new-jobs', name: 'UserNewJobs', component: page('./pages/UserNewJobs.vue') },
        { path: 'jobs', name: 'UserJobExplorer', component: page('./pages/UserJobExplorer.vue') },
        { path: 'graph', name: 'UserGraphView', component: page('./pages/UserGraphView.vue') },
        { path: 'job-recommend', name: 'UserJobRecommend', component: page('./pages/UserJobRecommend.vue') },
        { path: 'match-favorites', name: 'UserFavorites', component: page('./pages/UserFavorites.vue') },
        { path: 'matches', redirect: '/user/job-recommend' },
        { path: 'favorites', redirect: '/user/match-favorites' },
        { path: 'match/:id', name: 'UserMatchDetail', component: page('./pages/UserMatchDetail.vue') },
        { path: 'gap-analysis', name: 'UserGapAnalysis', component: page('./pages/UserGapAnalysis.vue') },
        { path: 'learning', name: 'UserLearning', component: page('./pages/UserLearning.vue') },
      ],
    },
  ],
})

router.afterEach((to, from) => {
  if (to.path === from.path) return
  // Admin/User layouts scroll inside .app-main rather than the browser window.
  // Wait until the new route has rendered, then reset both possible scrollers.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.querySelector('.app-main')?.scrollTo({ top: 0, left: 0, behavior: 'auto' })
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    })
  })
})

router.beforeEach((to, from, next) => {
  if (to.path === '/' || to.path === '/signin' || to.path === '/register' || to.path === '/flow') return next()
  let user = null
  try { user = JSON.parse(localStorage.getItem('user') || 'null') } catch { /* ignore */ }
  const token = localStorage.getItem('token')
  if (!user || !user.username || !token) return next('/signin')
  // 角色校验：学生不能访问管理员页面
  if (to.path.startsWith('/admin') && user.role !== 'admin') return next('/user/dashboard')
  next()
})

export default router
