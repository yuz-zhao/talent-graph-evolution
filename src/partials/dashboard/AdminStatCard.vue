<template>
  <div class="flex flex-col col-span-full sm:col-span-6 xl:col-span-3 bg-white dark:bg-gray-800 shadow-xs rounded-xl">
    <div class="px-5 pt-5">
      <header class="flex justify-between items-start mb-2">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">{{ title }}</h2>
        <AdminMetricActionMenu
          @view-detail="$emit('view-detail')"
          @export-metric="$emit('export-metric')"
          @refresh-metric="$emit('refresh-metric')"
        />
      </header>
      <div class="text-xs font-semibold text-gray-400 dark:text-gray-500 mb-1">{{ subtitle }}</div>
      <div class="flex items-start">
        <div class="text-3xl font-bold text-gray-800 dark:text-gray-100 mr-2">{{ formattedValue }}</div>
        <div class="text-sm font-medium px-1.5 rounded-full" :class="growthClass">{{ growthLabel }}</div>
      </div>
    </div>
    <div class="grow max-sm:max-h-[128px] xl:max-h-[128px]">
      <LineChart :data="chartData" width="389" height="128" />
    </div>
  </div>
</template>

<script>
import { computed } from 'vue'
import { chartAreaGradient } from '../../charts/ChartjsConfig'
import LineChart from '../../charts/LineChart01.vue'
import AdminMetricActionMenu from '../../components/admin/AdminMetricActionMenu.vue'

// 颜色常量 — 不使用 CSS 变量，避免 Tailwind v4 兼容问题
const COLOR_VIOLET = '#8470ff'
const COLOR_GRAY = '#6b7280'

const toNumber = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

const trendPointValue = (point) => {
  if (typeof point === 'number') return point
  return toNumber(point?.value ?? point?.count ?? point?.total ?? point?.rate)
}

const trendPointLabel = (point, index) => {
  if (point && typeof point === 'object') {
    return point.date || point.day || point.month || point.label || `M${index + 1}`
  }
  return `M${index + 1}`
}

export default {
  name: 'AdminStatCard',
  components: {
    LineChart,
    AdminMetricActionMenu,
  },
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, required: true },
    value: { type: [Number, String], default: 0 },
    growthRate: { type: [Number, String], default: 0 },
    trend: { type: Array, default: () => [] },
    detailPath: { type: String, default: '/' },
    isPercent: { type: Boolean, default: false },
  },
  setup(props) {
    const formattedValue = computed(() => {
      const value = toNumber(props.value)
      if (props.isPercent) return `${value.toFixed(1).replace('.0', '')}%`
      return Math.round(value).toLocaleString('zh-CN')
    })

    const growthLabel = computed(() => {
      const growth = toNumber(props.growthRate)
      const sign = growth > 0 ? '+' : ''
      return `较上月 ${sign}${growth}%`
    })

    const growthClass = computed(() => {
      const growth = toNumber(props.growthRate)
      if (growth > 0) return 'text-green-700 bg-green-500/20'
      if (growth < 0) return 'text-red-700 bg-red-500/20'
      return 'text-gray-600 dark:text-gray-300 bg-gray-500/10'
    })

    const chartData = computed(() => {
      const hasTrend = Array.isArray(props.trend) && props.trend.length > 0
      const source = hasTrend ? props.trend : [0, 0, 0, 0, 0, 0]
      const lineColor = hasTrend ? COLOR_VIOLET : `${COLOR_GRAY}59` /* #6b7280 at 35% opacity — 透明度硬编码避免 adjustColorOpacity 报错 */
      return {
        labels: source.map(trendPointLabel),
        datasets: [
          {
            data: source.map(trendPointValue),
            fill: true,
            backgroundColor: function(context) {
              const chart = context.chart
              const { ctx, chartArea } = chart
              const c = lineColor.replace('#', '')
              const r = parseInt(c.substring(0,2),16), g = parseInt(c.substring(2,4),16), b = parseInt(c.substring(4,6),16)
              return chartAreaGradient(ctx, chartArea, [
                { stop: 0, color: `rgba(${r},${g},${b},0)` },
                { stop: 1, color: `rgba(${r},${g},${b},${hasTrend ? 0.2 : 0.08})` },
              ])
            },
            borderColor: lineColor,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: hasTrend ? 3 : 0,
            pointBackgroundColor: lineColor,
            pointHoverBackgroundColor: lineColor,
            pointBorderWidth: 0,
            pointHoverBorderWidth: 0,
            clip: 20,
            tension: 0.2,
          },
        ],
      }
    })


    return {
      formattedValue,
      growthLabel,
      growthClass,
      chartData,
    }
  }
}
</script>
