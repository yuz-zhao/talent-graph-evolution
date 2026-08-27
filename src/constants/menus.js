import Activity from '@lucide/vue/dist/esm/icons/activity.mjs'
import Bookmark from '@lucide/vue/dist/esm/icons/bookmark.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import BrainCircuit from '@lucide/vue/dist/esm/icons/brain-circuit.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import FileText from '@lucide/vue/dist/esm/icons/file-text.mjs'
import House from '@lucide/vue/dist/esm/icons/house.mjs'
import LayoutDashboard from '@lucide/vue/dist/esm/icons/layout-dashboard.mjs'
import MessageSquareText from '@lucide/vue/dist/esm/icons/message-square-text.mjs'
import Network from '@lucide/vue/dist/esm/icons/network.mjs'
import Search from '@lucide/vue/dist/esm/icons/search.mjs'
import SearchCode from '@lucide/vue/dist/esm/icons/search-code.mjs'
import Settings2 from '@lucide/vue/dist/esm/icons/settings-2.mjs'
import ShieldCheck from '@lucide/vue/dist/esm/icons/shield-check.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import UserRound from '@lucide/vue/dist/esm/icons/user-round.mjs'
import UserRoundSearch from '@lucide/vue/dist/esm/icons/user-round-search.mjs'
import WandSparkles from '@lucide/vue/dist/esm/icons/wand-sparkles.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'

// 岗位能力研究中心：按赛题闭环组织，而不是按技术页面堆叠。
export const adminMenuItems = [
  { label: '数据总览', path: '/admin/dashboard', icon: LayoutDashboard },
  { label: '数据治理', path: '/admin/data-sources', icon: DatabaseZap },
  { label: '岗位发现', path: '/admin/new-jobs', icon: WandSparkles },
  { label: '能力趋势', path: '/admin/skill-evolution', icon: TrendingUp },
  { label: '岗位图谱', path: '/admin/knowledge-graph', icon: Network },
  { label: '人岗匹配', path: '/admin/evaluation', icon: UserRoundSearch },
  { label: '用户分析', path: '/admin/behavior', icon: Activity },
  { label: '能力证据', path: '/admin/graphrag', icon: BrainCircuit },
  { label: '可信度评估', path: '/admin/cross-validation', icon: ShieldCheck },
  { label: '系统设置', path: '/admin/settings', icon: Settings2 },
]

// 职业发展中心：按”画像-探索-匹配-成长”组织，不使用 group 以保持侧边栏扁平清晰（与管理员端一致）。
export const userMenuItems = [
  { label: '职业概览', path: '/user/dashboard', icon: House },
  { label: '我的画像', path: '/user/resume', aliases: ['/user/profile'], icon: FileScan },
  { label: '发现岗位', path: '/user/new-jobs', icon: WandSparkles },
  { label: '岗位洞察', path: '/user/jobs', icon: Network },
  { label: '能力图谱', path: '/user/graph', icon: BrainCircuit },
  { label: '岗位匹配', path: '/user/job-recommend', aliases: ['/user/matches', '/user/match/'], icon: Target },
  { label: '收藏岗位', path: '/user/match-favorites', aliases: ['/user/favorites'], icon: Bookmark },
  { label: '能力差距', path: '/user/gap-analysis', icon: TrendingUp },
  { label: '成长计划', path: '/user/learning', icon: BookOpen },
]
