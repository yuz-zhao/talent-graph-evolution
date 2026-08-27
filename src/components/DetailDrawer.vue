<template>
  <Teleport to="body">
    <transition name="dr-fade">
      <div v-if="open" class="dr-mask" @click.self="$emit('close')">
        <transition name="dr-slide"><div v-if="open" class="dr-panel"><div class="dr-inner">
          <div class="dr-hd">
            <h3>{{ title }}</h3>
            <button @click="$emit('close')"><X :size="18"/></button>
          </div>
          <div class="dr-bd">
            <div class="dr-val">{{ value }}</div>
            <p class="dr-sub">{{ subtitle }}</p>
            <div class="dr-meta">
              <span>数据来源：{{ source }}</span>
              <span>更新时间：{{ updatedAt }}</span>
            </div>
            <div class="dr-chart" v-if="chartData">
              <canvas :ref="el => chartRef=el"></canvas>
            </div>
            <div class="dr-list" v-if="list && list.length">
              <div v-for="item in list" :key="item.label" class="dr-li">
                <span class="dr-li-label">{{ item.label }}</span>
                <span class="dr-li-val">{{ item.value }}</span>
              </div>
            </div>
            <button v-if="link" class="dr-btn" @click="$router.push(link);$emit('close')">查看完整数据 →</button>
          </div>
        </div></div></transition>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import X from '@lucide/vue/dist/esm/icons/x.mjs'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip)

const props = defineProps({
  open: Boolean, title: String, value: String, subtitle: String,
  source: String, updatedAt: String, link: String,
  chartData: Object, list: Array,
})
defineEmits(['close'])

const chartRef = ref(null)
let instance = null

watch(() => props.open, async (v) => {
  if (v && props.chartData) {
    await nextTick()
    if (chartRef.value) {
      if (instance) instance.destroy()
      instance = new Chart(chartRef.value, {
        type: 'line',
        data: props.chartData,
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { display: false }, y: { display: false } },
          elements: { line: { tension: 0.4, borderColor: '#7c3aed', borderWidth: 2 },
            point: { radius: 0 }, area: { backgroundColor: 'rgba(124,58,237,0.08)' } },
        },
      })
    }
  }
})
</script>

<style scoped>
.dr-mask { position: fixed; inset: 0; z-index: 9998; background: rgba(15,23,42,.2); backdrop-filter: blur(3px); }
.dr-panel { position: absolute; right: 0; top: 0; bottom: 0; width: 38%; min-width: 380px; max-width: 520px; background: #fff; box-shadow: -8px 0 40px rgba(0,0,0,.06); }
.dr-inner { display: flex; flex-direction: column; height: 100%; }
.dr-hd { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid #f1f5f9; flex-shrink: 0; }
.dr-hd h3 { font-size: 16px; font-weight: 700; color: #1e293b; margin: 0; }
.dr-hd button { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px; border-radius: 6px; }
.dr-hd button:hover { background: #f1f5f9; color: #475569; }
.dr-bd { flex: 1; overflow-y: auto; padding: 22px; }
.dr-val { font-size: 38px; font-weight: 800; color: #7c3aed; margin-bottom: 6px; }
.dr-sub { font-size: 13px; color: #64748b; line-height: 1.6; margin: 0 0 16px; }
.dr-meta { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: #94a3b8; margin-bottom: 18px; }
.dr-chart { height: 120px; margin-bottom: 18px; border-radius: 12px; background: #f8fafc; padding: 10px; }
.dr-list { margin-bottom: 18px; }
.dr-li { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f8fafc; font-size: 13px; }
.dr-li-label { color: #64748b; } .dr-li-val { color: #1e293b; font-weight: 600; }
.dr-btn { display: inline-block; padding: 8px 18px; border-radius: 8px; background: #7c3aed; color: #fff; font-size: 13px; border: none; cursor: pointer; font-weight: 500; text-decoration: none; }
.dr-btn:hover { background: #6d28d9; }
.dr-fade-enter-active, .dr-fade-leave-active { transition: opacity .2s; }
.dr-fade-enter-from, .dr-fade-leave-to { opacity: 0; }
.dr-slide-enter-active { transition: transform .25s ease; }
.dr-slide-leave-active { transition: transform .2s ease; }
.dr-slide-enter-from, .dr-slide-leave-to { transform: translateX(100%); }
</style>
