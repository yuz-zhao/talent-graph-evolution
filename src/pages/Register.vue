<template>
  <main class="h-screen overflow-hidden bg-slate-50 text-slate-900 relative">
    <div class="absolute inset-0 pointer-events-none">
      <div class="absolute -top-28 -left-20 w-96 h-96 rounded-full bg-blue-200/45 blur-3xl"></div>
      <div class="absolute top-20 right-10 w-[30rem] h-[30rem] rounded-full bg-violet-200/45 blur-3xl"></div>
      <div class="absolute bottom-0 left-1/3 w-[36rem] h-[22rem] rounded-full bg-sky-100/75 blur-3xl"></div>
    </div>

    <div class="relative h-full flex items-center justify-center px-6 py-5">
      <div class="w-full max-w-7xl h-full max-h-[880px] rounded-[2rem] border border-white/80 bg-white/70 shadow-[0_30px_90px_-48px_rgba(30,64,175,0.55)] backdrop-blur-xl overflow-hidden">
        <div class="grid h-full min-h-0 lg:grid-cols-[1fr_0.92fr]">
          <section class="relative min-h-0 p-6 lg:p-8 bg-linear-to-br from-white via-blue-50/70 to-violet-50/80 border-b lg:border-b-0 lg:border-r border-slate-200/70 overflow-hidden">
            <div class="absolute right-12 top-10 grid grid-cols-8 gap-3 opacity-30">
              <span v-for="index in 48" :key="index" class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            </div>

            <div class="relative">
              <img class="h-16 w-auto object-contain" :src="Logo" alt="TalentGraph Evolution" />

              <div class="mt-8 max-w-3xl">
                <h1 class="text-3xl xl:text-4xl font-bold tracking-tight text-slate-950 leading-tight">
                  创建 TalentGraph 账号
                </h1>
                <p class="mt-3 text-base text-slate-600 leading-7">
                  注册后即可进入岗位能力图谱动态演化系统，后续可接入简历解析、人岗匹配、GraphRAG 分析与知识图谱构建能力。
                </p>
              </div>

              <div class="mt-7 grid gap-3 max-w-2xl">
                <div v-for="item in steps" :key="item.title" class="flex items-start gap-3 rounded-2xl border border-white/80 bg-white/70 p-4 shadow-[0_18px_45px_-34px_rgba(37,99,235,0.75)]">
                  <div class="w-10 h-10 shrink-0 rounded-xl bg-linear-to-br from-blue-500 to-violet-500 text-white flex items-center justify-center text-sm font-bold">
                    {{ item.index }}
                  </div>
                  <div>
                    <h2 class="font-semibold text-slate-900">{{ item.title }}</h2>
                    <p class="mt-0.5 text-sm leading-5 text-slate-500">{{ item.description }}</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section class="min-h-0 flex items-center justify-center p-6 lg:p-8 bg-white/55 overflow-hidden">
            <div class="w-full max-w-md rounded-3xl border border-white/80 bg-white/75 backdrop-blur-xl shadow-[0_24px_70px_-44px_rgba(15,23,42,0.65)] p-6">
              <div>
                <h2 class="text-3xl font-bold text-slate-950">注册账号</h2>
                <p class="mt-2 text-sm text-slate-500">填写基础信息后写入系统用户数据库</p>
              </div>

              <form class="mt-5 space-y-3" @submit.prevent="handleRegister">
                <label class="block">
                  <span class="text-sm font-medium text-slate-700">真实姓名</span>
                  <input v-model.trim="form.real_name" class="form-input mt-1.5 w-full h-10 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" type="text" autocomplete="name" placeholder="请输入真实姓名" />
                </label>

                <label class="block">
                  <span class="text-sm font-medium text-slate-700">账号</span>
                  <input v-model.trim="form.username" class="form-input mt-1.5 w-full h-10 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" type="text" autocomplete="username" placeholder="请输入登录账号" />
                </label>

                <label class="block">
                  <span class="text-sm font-medium text-slate-700">密码</span>
                  <input v-model="form.password" class="form-input mt-1.5 w-full h-10 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" type="password" autocomplete="new-password" placeholder="请输入密码" />
                </label>

                <label class="block">
                  <span class="text-sm font-medium text-slate-700">确认密码</span>
                  <input v-model="form.confirm_password" class="form-input mt-1.5 w-full h-10 rounded-xl border-slate-200 bg-white/90 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500/20" type="password" autocomplete="new-password" placeholder="请再次输入密码" />
                </label>

                <div class="rounded-xl bg-blue-50/70 border border-blue-100 px-3 py-2 text-xs text-slate-600">
                  默认注册为普通用户，管理员权限请在用户管理中分配。
                </div>

                <div v-if="errorMessage" class="rounded-xl bg-red-50 border border-red-100 px-3 py-2 text-sm text-red-600">
                  {{ errorMessage }}
                </div>

                <button class="w-full h-11 rounded-xl bg-linear-to-r from-blue-600 to-violet-600 text-white font-semibold shadow-[0_16px_35px_-20px_rgba(37,99,235,0.9)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_45px_-22px_rgba(79,70,229,0.95)] disabled:opacity-60 disabled:hover:translate-y-0" type="submit" :disabled="loading">
                  {{ loading ? '注册中...' : '注册并进入系统' }}
                </button>

                <p class="pt-1 text-center text-sm text-slate-500">
                  已有账号？
                  <router-link class="font-semibold text-blue-600 hover:text-violet-600" to="/signin">
                    返回登录
                  </router-link>
                </p>
              </form>
            </div>
          </section>
        </div>
      </div>
    </div>
  </main>
</template>

<script>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Logo from '../images/talentgraph-logo-transparent.png'

const normalizeUser = (data) => data?.user ?? data?.data?.user ?? data

export default {
  name: 'Register',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const errorMessage = ref('')
    const form = reactive({
      real_name: '',
      username: '',
      password: '',
      confirm_password: '',
    })
    const steps = [
      {
        index: '01',
        title: '创建账号身份',
        description: '使用真实姓名展示系统身份，后台不再显示模板账号名称。',
      },
      {
        index: '02',
        title: '写入用户数据库',
        description: '注册表单提交到 /api/register，由后端完成用户入库。',
      },
      {
        index: '03',
        title: '进入系统工作台',
        description: '注册成功后根据角色进入管理员端或普通用户端。',
      },
    ]

    const handleRegister = async () => {
      errorMessage.value = ''
      if (!form.real_name || !form.username || !form.password) {
        errorMessage.value = '请完整填写真实姓名、账号和密码'
        return
      }
      if (form.password.length < 6) {
        errorMessage.value = '密码长度不能少于 6 位'
        return
      }
      if (form.password !== form.confirm_password) {
        errorMessage.value = '两次输入的密码不一致'
        return
      }

      loading.value = true
      try {
        const response = await fetch('/api/register', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            real_name: form.real_name,
            username: form.username,
            password: form.password,
            role: 'user',
          }),
        })

        if (!response.ok) throw new Error(`注册失败：${response.status}`)
        const payload = await response.json()
        const user = normalizeUser(payload)
        const safeUser = {
          ...user,
          real_name: user?.real_name || user?.realName || form.real_name,
          role: user?.role || 'user',
        }

        localStorage.setItem('user', JSON.stringify(safeUser))
        if (payload.token) localStorage.setItem('token', payload.token)
        localStorage.setItem('remember_login', 'true')

        if (safeUser.role === 'admin') {
          router.push('/admin/dashboard')
        } else {
          router.push('/user/dashboard')
        }
      } catch (error) {
        console.error(error)
        errorMessage.value = '注册失败，请检查后端注册接口或账号是否已存在'
      } finally {
        loading.value = false
      }
    }

    return {
      Logo,
      form,
      steps,
      loading,
      errorMessage,
      handleRegister,
    }
  },
}
</script>
