/* 导出报告 / 指标操作通用工具 */
export const safeText = (val, fallback = '--') => {
  if (val === null || val === undefined) return fallback
  const s = String(val)
  return (s.trim() === '' || s === 'NaN' || s === 'undefined' || s === 'null') ? fallback : s
}

export const safeNumber = (val) => {
  const n = Number(val)
  return Number.isFinite(n) ? n : 0
}

export const safePercent = (val) => {
  const n = safeNumber(val)
  return `${Math.round(n * 10) / 10}%`
}

export const formatDateTime = (date) => {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) date = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export const formatDateFile = (date) => {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) date = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

export const readExportUser = () => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    return safeText(user.real_name, safeText(user.username, '--'))
  } catch {
    return '--'
  }
}

export const downloadHtmlFile = (html, filename) => {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export const buildMetricReportHtml = (metric) => {
  const now = new Date()
  const dateStr = formatDateTime(now)
  const user = readExportUser()
  const pageName = safeText(metric.pageName, '管理员端')
  const title = safeText(metric.title, '指标')
  const value = safeText(metric.value, '0')
  const change = safeText(metric.change, '0%')
  const range = safeText(metric.range, '全部数据')
  const source = safeText(metric.source, '--')
  const desc = safeText(metric.description, '--')
  const formula = safeText(metric.formula, '--')
  const emptyTip = safeText(metric.emptyTip, '当前暂无真实数据。')

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>${pageName}_${title}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #fff; color: #1e293b; margin: 0; padding: 32px; }
  h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px 0; }
  .subtitle { font-size: 14px; color: #64748b; margin-bottom: 20px; }
  h2 { font-size: 16px; font-weight: 600; color: #6366f1; border-bottom: 2px solid #e0e7ff; padding-bottom: 6px; margin: 24px 0 12px 0; }
  .grid-field { display: grid; grid-template-columns: 100px 1fr; gap: 6px 16px; font-size: 13px; margin-bottom: 4px; }
  .grid-field .label { color: #64748b; }
  .grid-field .value { color: #1e293b; font-weight: 500; }
  .footer { margin-top: 24px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 12px; color: #64748b; line-height: 1.6; border: 1px solid #e2e8f0; }
</style></head>
<body>
  <h1>${pageName} — ${title}</h1>
  <div class="subtitle">TalentGraph Evolution 指标导出</div>

  <h2>指标概览</h2>
  <div class="grid-field"><span class="label">系统名称</span><span class="value">TalentGraph Evolution</span></div>
  <div class="grid-field"><span class="label">中文名称</span><span class="value">基于多源异构数据的岗位能力图谱动态演化与智能分析系统</span></div>
  <div class="grid-field"><span class="label">所属页面</span><span class="value">${pageName}</span></div>
  <div class="grid-field"><span class="label">指标名称</span><span class="value">${title}</span></div>
  <div class="grid-field"><span class="label">当前数值</span><span class="value">${value}</span></div>
  <div class="grid-field"><span class="label">较上月变化</span><span class="value">${change}</span></div>
  <div class="grid-field"><span class="label">统计范围</span><span class="value">${range}</span></div>
  <div class="grid-field"><span class="label">数据来源</span><span class="value">${source}</span></div>
  <div class="grid-field"><span class="label">生成时间</span><span class="value">${dateStr}</span></div>
  <div class="grid-field"><span class="label">导出人</span><span class="value">${user}</span></div>

  <h2>指标说明</h2>
  <div style="font-size:13px;color:#334155;line-height:1.7;">${desc}</div>

  <h2>空系统说明</h2>
  <div style="font-size:13px;color:#94a3b8;">${emptyTip}</div>

  <div class="footer">当前暂无真实数据，已导出指标说明模板。</div>
</body></html>`
}
