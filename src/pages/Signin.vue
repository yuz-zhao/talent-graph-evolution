<template>
  <main class="h-screen overflow-hidden bg-[radial-gradient(circle_at_18%_18%,rgba(191,219,254,0.58),transparent_32%),radial-gradient(circle_at_78%_22%,rgba(221,214,254,0.42),transparent_30%),linear-gradient(135deg,#ffffff_0%,#eef2ff_46%,#f5f3ff_100%)] text-slate-900 relative">
    <div class="absolute inset-0 pointer-events-none">
      <div class="absolute -top-32 -left-24 w-96 h-96 rounded-full bg-blue-200/40 blur-3xl"></div>
      <div class="absolute top-16 right-20 w-[34rem] h-[34rem] rounded-full bg-violet-100/55 blur-3xl"></div>
      <div class="absolute bottom-0 left-1/2 w-[34rem] h-[20rem] rounded-full bg-sky-100/70 blur-3xl"></div>
      <div class="absolute bottom-12 right-12 w-[24rem] h-[16rem] rounded-full bg-blue-100/50 blur-3xl"></div>
    </div>

    <div class="relative h-full">
      <div class="grid h-full lg:grid-cols-[minmax(0,1.32fr)_minmax(500px,0.88fr)]">
        <section class="relative min-w-0 min-h-0 p-6 lg:px-14 lg:py-10 overflow-hidden">
            <div class="absolute right-10 top-8 grid grid-cols-8 gap-3 opacity-25">
              <span v-for="index in 48" :key="index" class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            </div>

          <div class="relative h-full flex flex-col max-w-[1120px]">
            <div class="self-start">
              <img class="h-24 w-auto object-contain" :src="Logo" alt="TalentGraph Evolution" />
              <p class="mt-4 text-lg font-semibold tracking-wide text-slate-700">
                基于多源异构数据的岗位能力图谱动态演化与智能分析系统
              </p>
            </div>

            <div class="relative mt-5 flex-1 min-h-0 flex items-center justify-center">
              <img
                class="block w-full max-w-[980px] max-h-[clamp(390px,54vh,590px)] rounded-[2rem] object-contain opacity-95"
                :src="LoginVisual"
                alt="岗位能力图谱动态演化分析"
              />
            </div>
          </div>
        </section>

        <section class="relative min-w-0 flex items-center justify-center p-6 lg:p-10 overflow-hidden">
          <div class="absolute right-24 top-16 h-40 w-40 rounded-full border border-blue-100/50"></div>
          <div class="absolute right-36 bottom-14 h-56 w-56 rounded-full bg-violet-100/28 blur-3xl"></div>
          <div class="absolute right-[18%] top-[12%] h-32 w-32 rounded-full bg-blue-100/25 blur-2xl"></div>
          <div class="relative w-full max-w-md rounded-3xl border border-white/80 bg-white/88 backdrop-blur-xl shadow-[0_30px_90px_-54px_rgba(15,23,42,0.78)] p-8">
              <div>
                <h2 class="text-3xl font-bold text-slate-950">欢迎登录</h2>
                <p class="mt-2 text-sm text-slate-500">请输入账号密码进入系统</p>
              </div>

              <form class="mt-8 space-y-5" @submit.prevent="handleLogin">
                <label class="block">
                  <span class="text-sm font-medium text-slate-700">账号</span>
                  <div class="mt-2 relative">
                    <input v-model.trim="form.username" class="form-input w-full h-12 pl-11 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" type="text" autocomplete="username" placeholder="请输入账号" />
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21a8 8 0 0 0-16 0" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  </div>
                </label>

                <label class="block">
                  <span class="text-sm font-medium text-slate-700">密码</span>
                  <div class="mt-2 relative">
                    <input v-model="form.password" class="form-input w-full h-12 pl-11 pr-11 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" />
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="4" y="10" width="16" height="10" rx="2" />
                      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                    </svg>
                    <button class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-blue-600" type="button" @click="showPassword = !showPassword">
                      <span class="sr-only">切换密码显示</span>
                      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    </button>
                  </div>
                </label>

                <div class="captcha-wrap">
                  <div class="captcha-card" @click="newCaptcha" title="点击换题">
                    <svg viewBox="0 0 120 44" class="captcha-svg">
                      <rect width="120" height="44" rx="6" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
                      <line v-for="i in 4" :key="'l'+i" :x1="i*25-10" :y1="8" :x2="i*25+15" :y2="36" stroke="#cbd5e1" stroke-width="0.6"/>
                      <text x="20" y="30" fill="#7c3aed" font-size="22" font-weight="700" font-family="Georgia,serif" transform="rotate(-8 20 30)">{{ captcha.a }}</text>
                      <text x="52" y="30" fill="#475569" font-size="16" font-weight="600">+</text>
                      <text x="72" y="30" fill="#6366f1" font-size="22" font-weight="700" font-family="Georgia,serif" transform="rotate(6 72 30)">{{ captcha.b }}</text>
                      <text x="100" y="30" fill="#64748b" font-size="14" font-weight="600">= ?</text>
                    </svg>
                  </div>
                  <input v-model="captcha.input" class="captcha-inp" placeholder="结果" maxlength="3" @keyup.enter="handleLogin"/>
                </div>

                <div class="flex items-center justify-between text-sm">
                  <label class="flex items-center gap-2 text-slate-600">
                    <input v-model="rememberMe" class="form-checkbox rounded border-slate-300 text-blue-600 focus:ring-blue-500/30" type="checkbox" />
                    记住我
                  </label>
                  <a class="font-medium text-blue-600 hover:text-violet-600" href="#0">忘记密码？</a>
                </div>

                <div v-if="errorMessage" class="rounded-xl bg-red-50 border border-red-100 px-3 py-2 text-sm text-red-600">
                  {{ errorMessage }}
                </div>

                <button class="w-full h-12 rounded-xl bg-linear-to-r from-blue-600 to-violet-600 text-white font-semibold shadow-[0_16px_35px_-20px_rgba(37,99,235,0.9)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_45px_-22px_rgba(79,70,229,0.95)] disabled:opacity-60 disabled:hover:translate-y-0" type="submit" :disabled="loading">
                  {{ loading ? '登录中...' : '登录系统' }}
                </button>

                <p class="pt-1 text-center text-sm text-slate-500">
                  还没有账号？
                  <router-link class="font-semibold text-blue-600 hover:text-violet-600" to="/register">
                    立即注册
                  </router-link>
                </p>
              </form>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>

<script>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Logo from '../images/talentgraph-logo-transparent.webp'
import LoginVisual from '../images/login-graph-visual.webp'

const normalizeUser = (data) => data?.user ?? data?.data?.user ?? data

export default {
  name: 'Signin',
  setup() {
    const router = useRouter()
    const form = reactive({
      username: '',
      password: '',
    })
    const rememberMe = ref(true)
    const showPassword = ref(false)
    const loading = ref(false)
    const errorMessage = ref('')
    const captcha = reactive({ a: 0, b: 0, input: '' })
    const newCaptcha = () => { captcha.a = Math.floor(Math.random() * 8) + 1; captcha.b = Math.floor(Math.random() * 8) + 1; captcha.input = '' }
    newCaptcha()

    const handleLogin = async () => {
      errorMessage.value = ''
      if (parseInt(captcha.input) !== captcha.a + captcha.b) { errorMessage.value = '验证码错误'; newCaptcha(); return }
      if (!form.username || !form.password) {
        errorMessage.value = '请输入账号和密码'
        return
      }

      loading.value = true
      try {
        const response = await fetch('/api/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            username: form.username,
            password: form.password,
          }),
        })

        const payload = await response.json()
        if (!response.ok) throw new Error(payload?.message || `登录失败：${response.status}`)
        const user = normalizeUser(payload)
        const safeUser = {
          ...user,
          real_name: user?.real_name || user?.realName || '用户',
          role: user?.role || 'user',
        }

        localStorage.setItem('user', JSON.stringify(safeUser))
        if (payload.token) localStorage.setItem('token', payload.token)
        if (rememberMe.value) localStorage.setItem('remember_login', 'true')
        else localStorage.removeItem('remember_login')

        if (safeUser.role === 'admin') {
          router.push('/admin/dashboard')
        } else {
          router.push('/user/dashboard')
        }
      } catch (error) {
        console.error(error)
        errorMessage.value = error.message || '登录失败，请检查账号密码或后端服务'
      } finally {
        loading.value = false
      }
    }

    return {
      Logo,
      newCaptcha,
      LoginVisual,
      form,
      rememberMe,
      showPassword,
      loading,
      errorMessage,
      captcha,
      handleLogin,
    }
  },
}
</script>

<style scoped>
.captcha-wrap{display:flex;align-items:center;gap:10px}
.captcha-card{cursor:pointer;flex-shrink:0;transition:opacity .15s}.captcha-card:hover{opacity:.85}
.captcha-svg{width:140px;height:44px;display:block}
.captcha-inp{width:72px;height:42px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;text-align:center;font-size:18px;font-weight:700;color:#1e293b}
</style>
