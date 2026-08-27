<template>
  <div class="dash">
    <!-- 页面内标签切换 -->
    <div class="tab-bar">
      <button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" @click="tab = item.key">{{ item.label }}</button>
    </div>

    <!-- Tab1: 用户管理 -->
    <div v-if="tab==='users'">
      <!-- 搜索过滤面板 -->
      <div class="panel panel-lift um-filter-panel">
        <div class="um-toolbar">
          <div class="um-filters">
            <input v-model="keyword" @keyup.enter="page=1;loadUsers()" placeholder="搜索账号或姓名" class="um-inp"/>
            <select v-model="roleFilter" @change="page=1;loadUsers()" class="um-sel">
              <option value="">全部角色</option>
              <option value="admin">管理员</option>
              <option value="user">学生</option>
            </select>
            <select v-model="statusFilter" @change="page=1;loadUsers()" class="um-sel">
              <option value="">全部状态</option>
              <option value="normal">正常</option>
              <option value="disabled">禁用</option>
            </select>
          </div>
          <div class="um-actions">
            <button class="um-reset" @click="resetFilters">重置</button>
            <button class="um-search-btn" @click="page=1;loadUsers()">搜索</button>
            <button class="um-add" @click="openEdit()">+ 添加用户</button>
          </div>
        </div>
      </div>

      <!-- 用户列表表格面板 -->
      <div class="tbl-wrap"><table class="um-tbl">
        <thead><tr><th class="um-seq">#</th><th>账号</th><th>姓名</th><th>角色</th><th>状态</th><th>最后登录</th><th class="um-op">操作</th></tr></thead>
        <tbody>
          <tr v-for="(u,i) in users" :key="u.id" class="um-row">
            <td class="um-seq">{{ (page-1)*pageSize + i + 1 }}</td>
            <td class="fw">{{ u.username }}</td>
            <td>{{ u.real_name||'—' }}</td>
            <td><span class="tag" :class="u.role==='admin'?'t-a':'t-u'">{{ u.role==='admin'?'管理员':'学生' }}</span></td>
            <td><span class="tag" :class="u.status==='normal'?'s-ok':'s-no'">{{ u.status==='normal'?'正常':'禁用' }}</span></td>
            <td class="um-time">{{ u.last_login_at||'—' }}</td>
            <td class="um-op">
              <button class="op-link" @click="openEdit(u)">编辑</button>
              <button class="op-link" @click="resetPwd(u)">重置密码</button>
              <button class="op-link del" @click="toggleStatus(u)">{{ u.status==='normal'?'禁用':'启用' }}</button>
              <button class="op-link danger" :disabled="deletingUserId===u.id" @click="deleteUser(u)">{{ deletingUserId===u.id?'删除中…':'删除' }}</button>
            </td>
          </tr>
        </tbody>
      </table></div>
      <div class="um-pager">
        <div class="um-pager-meta">
          <span class="um-pager-total">共 <strong>{{ total }}</strong> 条</span>
          <label class="um-pager-size">
            <span>每页</span>
            <select v-model="pageSize" @change="page=1;loadUsers()" aria-label="每页行数">
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>
        </div>
        <div class="um-pager-nav" aria-label="分页导航">
          <button class="um-page-icon" :disabled="page<=1" title="首页" aria-label="首页" @click="page=1;loadUsers()"><ChevronsLeft :size="16"/></button>
          <button class="um-page-icon" :disabled="page<=1" title="上一页" aria-label="上一页" @click="page--;loadUsers()"><ChevronLeft :size="16"/></button>
          <span class="um-page-current" aria-current="page">{{ page }}</span>
          <button class="um-page-icon" :disabled="page>=totalPages" title="下一页" aria-label="下一页" @click="page++;loadUsers()"><ChevronRight :size="16"/></button>
          <button class="um-page-icon" :disabled="page>=totalPages" title="末页" aria-label="末页" @click="page=totalPages;loadUsers()"><ChevronsRight :size="16"/></button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <Teleport to="body">
      <div v-if="showEdit" class="modal-mask" @click.self="showEdit=false">
        <div class="modal-box-sm">
          <div class="modal-hd"><h3>{{ editForm.id?'编辑用户':'添加用户' }}</h3><button @click="showEdit=false"><X :size="18"/></button></div>
          <div class="modal-bd">
            <div class="fm-item"><label>账号</label><input v-model="editForm.username" :disabled="!!editForm.id" class="fm-inp"/></div>
            <div class="fm-item"><label>密码</label><input v-model="editForm.password" :placeholder="editForm.id?'留空不修改':'请输入密码'" class="fm-inp" type="password"/></div>
            <div class="fm-item"><label>姓名</label><input v-model="editForm.real_name" class="fm-inp"/></div>
            <div class="fm-item"><label>邮箱</label><input v-model="editForm.email" class="fm-inp"/></div>
            <div class="fm-item"><label>手机</label><input v-model="editForm.phone" class="fm-inp"/></div>
            <div class="fm-item"><label>角色</label><select v-model="editForm.role" class="fm-inp"><option value="user">学生</option><option value="admin">管理员</option></select></div>
            <div v-if="editForm.id" class="fm-item"><label>状态</label><select v-model="editForm.status" class="fm-inp"><option value="normal">正常</option><option value="disabled">禁用</option></select></div>
            <div class="fm-btns"><button class="btn-cancel" @click="showEdit=false">取消</button><button class="btn-save" @click="saveUser" :disabled="saving">{{ saving?'保存中':'保存' }}</button></div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 临时密码仅保存在当前弹窗内，关闭后立即清空 -->
    <Teleport to="body">
      <div v-if="temporaryPassword" class="modal-mask" @click.self="closeTemporaryPassword">
        <div class="modal-box-sm temporary-password-modal" role="dialog" aria-modal="true" aria-labelledby="temporary-password-title">
          <div class="modal-hd">
            <h3 id="temporary-password-title">密码重置成功</h3>
            <button aria-label="关闭" @click="closeTemporaryPassword"><X :size="18"/></button>
          </div>
          <div class="modal-bd">
            <p class="tp-warning">临时密码只显示一次，请复制后通过安全渠道交给用户。</p>
            <div class="tp-user">账号：<strong>{{ temporaryUsername }}</strong></div>
            <div class="tp-copy-row">
              <input ref="temporaryPasswordInput" class="tp-password" :value="temporaryPassword" readonly aria-label="临时密码" @focus="$event.target.select()"/>
              <button class="tp-copy-btn" @click="copyTemporaryPassword">{{ copyStatus || '复制密码' }}</button>
            </div>
            <p class="tp-hint">也可以点击密码框后按 Ctrl+C 复制。</p>
            <div class="fm-btns"><button class="btn-save" @click="closeTemporaryPassword">我已保存，关闭</button></div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Tab2: 系统状态 -->
    <div v-if="tab==='status'">
      <div class="cards4">
        <div class="sc" v-for="s in services" :key="s.name">
          <div class="sc-top"><span class="sc-dot" :class="s.online?'on':'off'"></span><span class="sc-name">{{ s.name }}</span></div>
          <div class="sc-desc">{{ s.desc }}</div>
          <div class="sc-info"><span>{{ s.online?'运行中':s.error||'检测中...' }}</span><span v-if="s.latency">{{ s.latency }}ms</span></div>
        </div>
      </div>
      <div class="panel panel-lift"><div class="ph">资源配置</div><div class="pb">
        <div class="res-grid">
          <div v-for="r in resources" :key="r.label" class="res-item"><span class="res-label">{{ r.label }}</span><div class="res-bar"><div class="res-fill" :style="{width:r.pct+'%',background:r.color}"></div></div><span class="res-val">{{ r.value }}</span></div>
        </div>
      </div></div>
      <div class="panel panel-lift"><div class="ph">最近日志</div><div class="pb p0"><div class="log-list"><div v-for="l in logs" :key="l.time" class="log-item"><span class="log-tag" :class="'lt-'+l.level">{{ l.level }}</span><span class="log-time">{{ l.time }}</span><span class="log-msg">{{ l.msg }}</span></div></div></div></div>
      <button class="refresh-btn" @click="checkHealth" :disabled="healthLoading">{{ healthLoading?'检测中...':'刷新状态' }}</button>
    </div>

    <!-- Tab3: 系统设置 -->
    <div v-if="tab==='settings'">
      <div v-for="g in settingGroups" :key="g.title" class="panel set-panel panel-lift">
        <div class="ph">{{ g.title }}<span class="ph-cnt">{{ g.items.length }}项</span></div>
        <div class="pb">
          <div v-for="item in g.items" :key="item.label" class="set-row">
            <div class="set-info"><div class="set-label">{{ item.label }}</div><div class="set-desc">{{ item.desc }}</div></div>
            <div class="set-input-wrap"><input v-model="item.value" class="set-inp" :type="item.type||'text'" :placeholder="item.placeholder"/></div>
          </div>
          <div class="set-btns"><button class="btn-cancel" @click="loadConfig">重置</button><button class="btn-save" @click="saveConfig">保存配置</button></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref,reactive,onMounted,computed,watch } from 'vue'
import X from '@lucide/vue/dist/esm/icons/x.mjs'
import ChevronLeft from '@lucide/vue/dist/esm/icons/chevron-left.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import ChevronsLeft from '@lucide/vue/dist/esm/icons/chevrons-left.mjs'
import ChevronsRight from '@lucide/vue/dist/esm/icons/chevrons-right.mjs'
import { useRoute } from 'vue-router'

const tab=ref('users'),keyword=ref(''),roleFilter=ref(''),statusFilter=ref(''),users=ref([]),total=ref(0),page=ref(1),pageSize=ref(10),showEdit=ref(false),saving=ref(false)
const deletingUserId=ref(null)
const temporaryPassword=ref(''),temporaryUsername=ref(''),temporaryPasswordInput=ref(null),copyStatus=ref('')
const route=useRoute()
const loading=ref(false),updateTime=ref('--')
const totalPages=computed(()=>Math.ceil(total.value/pageSize.value)||1)
const editForm=reactive({id:null,username:'',password:'',real_name:'',email:'',phone:'',role:'user',status:'normal'})
const tabs=[{key:'users',label:'用户管理'},{key:'status',label:'系统状态'},{key:'settings',label:'系统设置'}]
const services=ref([{name:'PostgreSQL',desc:'业务数据库',online:false,latency:null,error:null},{name:'Neo4j',desc:'知识图谱',online:false,latency:null,error:null},{name:'Qdrant',desc:'向量检索',online:false,latency:null,error:null},{name:'GNN模型',desc:'图嵌入服务',online:false,latency:null,error:null},{name:'DeepSeek',desc:'大模型API',online:false,latency:null,error:null}])
const resources=ref([{label:'CPU',value:'—',pct:0,color:'#7c3aed'},{label:'内存',value:'—',pct:0,color:'#6366f1'},{label:'运行时间',value:'—',pct:0,color:'#10b981'},{label:'Node.js',value:'—',pct:0,color:'#f59e0b'}])
const logs=ref([{time:'—',level:'INFO',msg:'系统启动中...'}])
const healthLoading=ref(false)
const settingGroups=reactive([{title:'AI模型配置',items:[{key:'graphrag_model',label:'模型名称',desc:'DeepSeek API模型ID',value:'deepseek-chat',placeholder:'deepseek-chat'},{key:'temperature',label:'温度参数',desc:'生成随机性(0-1)',value:'0.3',placeholder:'0.3'},{key:'max_tokens',label:'最大Token',desc:'单次回复长度上限',value:'2048',placeholder:'2048'},{key:'retrieval_topk',label:'检索TopK',desc:'向量检索返回数量',value:'5',placeholder:'5'}]},{title:'图谱配置',items:[{key:'neo4j_uri',label:'Neo4j连接',desc:'数据库连接URI',value:'bolt://localhost:7687',placeholder:'bolt://localhost:7687'},{key:'import_batch_size',label:'导入批次大小',desc:'批量导入节点数',value:'1000',placeholder:'1000'},{key:'relation_default_weight',label:'关系默认权重',desc:'新建关系权重',value:'0.7',placeholder:'0.7'}]},{title:'采集调度',items:[{key:'crawl_frequency',label:'采集频率',desc:'自动采集时间间隔',value:'weekly',placeholder:'weekly'},{key:'max_concurrency',label:'并发数',desc:'同时采集任务数',value:'3',placeholder:'3'},{key:'scheduler_enabled',label:'调度开关',desc:'启用定时采集',value:'false',placeholder:'false'}]},{title:'通知设置',items:[{key:'new_job_alert',label:'新岗位告警',desc:'发现新岗位时通知',value:'true',placeholder:'true'},{key:'skill_change_alert',label:'技能变更告警',desc:'技能趋势变化时通知',value:'true',placeholder:'true'}]}])

const checkHealth=async()=>{
  healthLoading.value=true
  try{
    const r=await fetch('/api/admin/system/health')
    if(r.ok){
      const d=await r.json()
      if(d.services) services.value=d.services
      if(d.resources) resources.value=d.resources
      logs.value.unshift({time:new Date().toLocaleTimeString(),level:'INFO',msg:`健康检查完成: ${d.services.filter(s=>s.online).length}/${d.services.length} 服务正常`})
    }else{
      logs.value.unshift({time:new Date().toLocaleTimeString(),level:'ERROR',msg:'健康检查失败: '+r.status})
    }
  }catch(e){
    logs.value.unshift({time:new Date().toLocaleTimeString(),level:'ERROR',msg:'健康检查请求失败: '+(e.message||'')})
  }
  healthLoading.value=false
  if(logs.value.length>20)logs.value=logs.value.slice(0,20)
}
const loadConfig=async()=>{
  try{
    const r=await fetch('/api/admin/config')
    if(!r.ok) return
    const rows=await r.json()
    if(!rows||!rows.length) return
    for(const g of settingGroups){
      for(const item of g.items){
        const row=rows.find(r=>r.config_key===item.key)
        if(row) item.value=row.config_value
      }
    }
  }catch{}
}
const saveConfig=async()=>{
  let saved=0,failed=[]
  for(const g of settingGroups){
    for(const item of g.items){
      try{
        const r=await fetch(`/api/admin/config/${item.key}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:item.value})})
        if(r.ok)saved++;else failed.push(`${item.label}：${(await r.json().catch(()=>({}))).message||r.status}`)
      }catch(e){failed.push(`${item.label}：${e.message||'请求失败'}`)}
    }
  }
  alert(failed.length?`已应用 ${saved} 项，失败 ${failed.length} 项\n${failed.join('\n')}`:`已保存并即时应用 ${saved} 项配置`)
}

const api=async(u,o)=>{try{const opts={...o};const token=localStorage.getItem('token');if(token){opts.headers={...opts.headers||{},'Authorization':'Bearer '+token}}const r=await fetch(u,opts);if(!r.ok)throw Error();return await r.json()}catch(e){return null}}
const loadUsers=async()=>{const params=new URLSearchParams({page:String(page.value),page_size:String(pageSize.value)});if(keyword.value)params.set('keyword',keyword.value);if(roleFilter.value)params.set('role',roleFilter.value);if(statusFilter.value)params.set('status',statusFilter.value);const d=await api(`/api/admin/users?${params.toString()}`);if(d){users.value=d.list;total.value=d.total}}
const resetFilters=()=>{keyword.value='';roleFilter.value='';statusFilter.value='';page.value=1;loadUsers()}
const openEdit=(u)=>{if(u){Object.assign(editForm,{id:u.id,username:u.username,password:'',real_name:u.real_name||'',email:u.email||'',phone:u.phone||'',role:u.role,status:u.status})}else{Object.assign(editForm,{id:null,username:'',password:'',real_name:'',email:'',phone:'',role:'user',status:'normal'})};showEdit.value=true}
const saveUser=async()=>{if(!editForm.username)return alert('请输入账号');saving.value=true;const method=editForm.id?'PUT':'POST';const url=editForm.id?`/api/admin/users/${editForm.id}`:'/api/admin/users';const d=await api(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(editForm)});if(d){showEdit.value=false;loadUsers()}else{alert('保存失败')};saving.value=false}
const resetPwd=async(u)=>{if(!confirm(`为 ${u.username} 生成一次性临时密码？`))return;const d=await api(`/api/admin/users/${u.id}/reset-password`,{method:'PUT'});if(d?.temporary_password){temporaryUsername.value=u.username;temporaryPassword.value=d.temporary_password;copyStatus.value=''}else alert('密码重置失败')}
const copyTemporaryPassword=async()=>{
  if(!temporaryPassword.value)return
  try{
    if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(temporaryPassword.value)
    else throw new Error('Clipboard API unavailable')
    copyStatus.value='已复制 ✓'
  }catch{
    const input=temporaryPasswordInput.value
    if(input){input.focus();input.select();copyStatus.value=document.execCommand('copy')?'已复制 ✓':'请按 Ctrl+C'}
    else copyStatus.value='请按 Ctrl+C'
  }
  setTimeout(()=>{if(temporaryPassword.value)copyStatus.value=''},2000)
}
const closeTemporaryPassword=()=>{temporaryPassword.value='';temporaryUsername.value='';copyStatus.value=''}
const toggleStatus=async(u)=>{const newStatus=u.status==='normal'?'disabled':'normal';if(!confirm(`${newStatus==='disabled'?'禁用':'启用'}用户 ${u.username}？`))return;const d=await api(`/api/admin/users/${u.id}/status`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:newStatus})});if(d){loadUsers()}}
const deleteUser=async(u)=>{
  if(!confirm(`确定永久删除用户“${u.username}”吗？\n\n该用户的画像、简历、岗位操作和学习计划等关联数据也会一并删除，此操作无法撤销。`))return
  const confirmation=prompt(`为避免误删，请输入账号 ${u.username} 进行确认：`)
  if(confirmation===null)return
  if(confirmation.trim()!==u.username)return alert('输入的账号不一致，已取消删除')
  deletingUserId.value=u.id
  try{
    const token=localStorage.getItem('token')
    const r=await fetch(`/api/admin/users/${u.id}`,{method:'DELETE',headers:{'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})},body:JSON.stringify({confirmation:u.username})})
    const d=await r.json().catch(()=>({}))
    if(!r.ok)throw new Error(d.message||`删除失败（${r.status}）`)
    alert(d.message||'用户已删除')
    if(users.value.length===1&&page.value>1)page.value--
    await loadUsers()
  }catch(e){alert(e.message||'删除失败，请稍后重试')}
  finally{deletingUserId.value=null}
}

const loadAll=async()=>{
  loading.value=true
  if(tab.value==='users'){loadUsers()}
  else if(tab.value==='status'){await checkHealth()}
  else if(tab.value==='settings'){loadConfig()}
  updateTime.value=new Date().toLocaleString('zh-CN')
  loading.value=false
}
onMounted(async()=>{keyword.value=String(route.query.keyword||'');tab.value=route.query.tab==='users'?'users':tab.value;loadUsers();updateTime.value=new Date().toLocaleString('zh-CN');checkHealth()})
watch(tab,(v)=>{if(v==='status'&&!services.value[0].online)checkHealth();if(v==='settings')loadConfig()})
</script>

<style scoped>
/* 吸顶标题 + 胶囊导航 */

.dash{padding:0 24px 20px;max-width:1500px;margin:0 auto}
.hd{margin-bottom:16px}.hd h1{font-size:20px;font-weight:700;color:#1e293b;margin:0}.hd p{font-size:13px;color:#64748b;margin:3px 0 0}

.tab-bar{display:flex;gap:4px;margin-bottom:16px;background:#f1f5f9;padding:4px;border-radius:10px;width:fit-content}
.tab-bar button{padding:7px 18px;border:none;background:transparent;border-radius:8px;font-size:13px;font-weight:500;color:#64748b;cursor:pointer;transition:all .15s}
.tab-bar button.active{background:#fff;color:#1e293b;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tab-bar button:hover:not(.active){color:#334155}

.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

.cards4{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:16px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 20px;position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;opacity:0;transition:opacity .25s;background:#7c3aed}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}.sc:hover::before{opacity:1}.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}.sc-v{font-size:20px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;color:#64748b;margin-top:2px}

.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}.ph{padding:12px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:600;color:#334155;display:flex;align-items:center;gap:8px}.ph-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400}.pb{padding:16px 18px}.p0{padding:0}


.um-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px}
.um-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.um-inp{padding:7px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;width:180px;color:#475569;background:#fff;outline:none}
.um-inp:focus{border-color:#c4b5fd}
.um-sel{padding:7px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff;outline:none;cursor:pointer}
.um-sel:focus{border-color:#c4b5fd}
.um-actions{display:flex;align-items:center;gap:8px}
.um-reset{padding:7px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}.um-reset:hover{background:#f8fafc;color:#475569}
.um-search-btn{padding:7px 16px;border-radius:8px;border:none;background:#6366f1;color:#fff;font-size:12px;cursor:pointer;font-weight:500}.um-search-btn:hover{background:#4f46e5}
.um-add{padding:7px 16px;border-radius:8px;border:1px solid #6366f1;background:#fff;color:#6366f1;font-size:12px;cursor:pointer;font-weight:500}.um-add:hover{background:#eef2ff}

.um-row{transition:background .15s}.um-row:hover{background:#f5f3ff}
.um-seq{width:44px;text-align:center;font-size:11px;color:#94a3b8;font-weight:500}
.um-time{font-size:11px;color:#94a3b8}
.um-tbl{width:100%;font-size:13px;border-collapse:collapse}
.um-tbl thead th{position:sticky;top:0;text-align:left;padding:10px 14px;font-size:11px;font-weight:600;color:#64748b;background:#f8fafc;border-bottom:1px solid #f1f5f9;z-index:1}
.um-tbl tbody td{padding:12px 14px;border-bottom:1px solid #f8fafc;color:#475569}
.um-tbl .fw{font-weight:600;color:#1e293b}
.um-op{white-space:nowrap}

.tbl-wrap{margin-top:20px;background:#fff;border:1px solid #f1f5f9;border-radius:12px;max-height:460px;overflow-y:auto;overflow-x:hidden}

.tag{font-size:10px;padding:2px 8px;border-radius:5px;font-weight:600}.t-a{background:#f5f3ff;color:#7c3aed}.t-u{background:#f1f5f9;color:#64748b}.s-ok{background:#ecfdf5;color:#059669}.s-no{background:#fef2f2;color:#dc2626}
.op-link{font-size:12px;padding:0 6px;color:#6366f1;background:transparent;border:none;cursor:pointer}.op-link:hover{text-decoration:underline;color:#4f46e5}.op-link.del{color:#94a3b8}.op-link.del:hover{color:#64748b}.op-link.danger{color:#ef4444}.op-link.danger:hover{color:#dc2626}.op-link:disabled{cursor:not-allowed;opacity:.5;text-decoration:none}

.um-pager{display:flex;align-items:center;justify-content:flex-end;gap:18px;min-height:54px;padding:10px 16px;margin-top:0;background:#fff;border-top:1px solid #eef1f5;border-radius:0 0 12px 12px;box-shadow:0 6px 14px rgba(15,23,42,.04)}
.um-pager-meta{display:flex;align-items:center;gap:16px;min-width:0}
.um-pager-total{font-size:13px;color:#707782;white-space:nowrap}.um-pager-total strong{margin:0 3px;color:#20242a;font-size:13px;font-weight:700}
.um-pager-size{display:flex;align-items:center;gap:7px;color:#707782;font-size:13px;font-weight:400;white-space:nowrap}
.um-pager-size select{width:68px;height:32px;padding:0 9px;border-radius:6px;border:1px solid #dfe3e8;background:#fff;color:#252a31;font-size:13px;font-weight:500;outline:none;cursor:pointer}.um-pager-size select:focus{border-color:#8bb9ef;box-shadow:0 0 0 2px rgba(104,164,232,.12)}
.um-pager-nav{display:flex;align-items:center;gap:7px;flex-shrink:0}
.um-page-icon,.um-page-current{width:32px;height:32px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;flex:0 0 32px}
.um-page-icon{border:1px solid #e7e9ed;background:#fff;color:#aeb3ba;cursor:pointer;transition:background .16s,border-color .16s,color .16s}.um-page-icon:hover:not(:disabled){background:#f5f8fc;border-color:#cbd7e4;color:#6686aa}
.um-page-icon:disabled{color:#d9dde2;background:#fbfbfc;border-color:#eff0f2;cursor:not-allowed}
.um-page-current{border:1px solid #68a4e8;background:#68a4e8;color:#fff;font-size:13px;font-weight:700}
@media (max-width:720px){.um-pager{flex-wrap:wrap;gap:10px;padding:10px 12px}.um-pager-meta{gap:10px}.um-pager-nav{gap:5px}.um-page-icon,.um-page-current{width:30px;height:30px;flex-basis:30px}.um-pager-size,.um-pager-total{font-size:12px}.um-pager-total strong{font-size:12px}.um-pager-size select{width:62px;height:30px;font-size:12px}}

.sc-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}.sc-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}.sc-dot.on{background:#10b981}.sc-dot.off{background:#ef4444}.sc-name{font-size:13px;font-weight:600;color:#1e293b}.sc-desc{font-size:11px;color:#94a3b8;margin-bottom:4px}.sc-info{display:flex;justify-content:space-between;font-size:11px;color:#64748b}

.res-grid{display:flex;flex-direction:column;gap:12px}.res-item{display:flex;align-items:center;gap:10px}.res-label{font-size:12px;color:#64748b;width:40px}.res-bar{flex:1;height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden}.res-fill{height:100%;border-radius:3px}.res-val{font-size:11px;color:#94a3b8;width:30px;text-align:right}

.log-list{max-height:200px;overflow-y:auto}.log-item{display:flex;align-items:center;gap:10px;padding:8px 18px;border-bottom:1px solid #f8fafc;font-size:11px}.log-tag{font-size:9px;padding:1px 6px;border-radius:3px;font-weight:600;color:#fff;flex-shrink:0}.lt-INFO{background:#6366f1}.lt-WARN{background:#f59e0b}.lt-ERROR{background:#ef4444}.log-time{color:#94a3b8;flex-shrink:0}.log-msg{color:#475569;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.refresh-btn{padding:6px 16px;border-radius:8px;border:1px solid #7c3aed;background:#f5f3ff;color:#7c3aed;font-size:12px;cursor:pointer;margin-top:12px}.refresh-btn:hover{background:#ede9fe}.refresh-btn:disabled{opacity:.5}

.set-panel{margin-bottom:16px}.set-row{display:flex;align-items:center;gap:20px;padding:12px 0;border-bottom:1px solid #f8fafc}.set-row:last-child{border-bottom:none}.set-info{flex:1}.set-label{font-size:13px;font-weight:600;color:#334155}.set-desc{font-size:11px;color:#94a3b8;margin-top:2px}.set-inp{padding:6px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#1e293b;width:220px}.set-btns{display:flex;justify-content:flex-end;gap:8px;margin-top:14px;padding-top:14px;border-top:1px solid #f1f5f9}

.modal-mask{position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.3);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center}
.modal-box-sm{background:#fff;border-radius:12px;width:420px;max-width:90vw;box-shadow:0 20px 60px rgba(0,0,0,.1)}
.modal-hd{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #f1f5f9}.modal-hd h3{font-size:15px;font-weight:700;color:#1e293b;margin:0}.modal-hd button{background:none;border:none;color:#94a3b8;cursor:pointer;padding:4px;border-radius:6px}.modal-hd button:hover{background:#f1f5f9;color:#475569}
.modal-bd{padding:18px 20px}
.fm-item{display:flex;align-items:center;margin-bottom:12px}.fm-item label{font-size:12px;color:#64748b;width:60px;flex-shrink:0}.fm-item .fm-inp{flex:1;text-align:left}
.fm-btns{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.btn-cancel{padding:6px 18px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}.btn-save{padding:6px 18px;border-radius:8px;border:none;background:#7c3aed;color:#fff;font-size:12px;cursor:pointer}.btn-save:disabled{opacity:.5}
.tp-warning{margin:0 0 14px;padding:10px 12px;border:1px solid #fde68a;border-radius:9px;background:#fffbeb;color:#92400e;font-size:12px;line-height:1.6}
.tp-user{margin-bottom:8px;color:#64748b;font-size:12px}.tp-user strong{color:#1e293b}
.tp-copy-row{display:flex;gap:8px}.tp-password{flex:1;min-width:0;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#f8fafc;color:#0f172a;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:15px;letter-spacing:.4px;outline:none}.tp-password:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.1)}
.tp-copy-btn{min-width:92px;padding:8px 12px;border:0;border-radius:8px;background:#4f46e5;color:#fff;font-size:12px;font-weight:600;cursor:pointer}.tp-copy-btn:hover{background:#4338ca}
.tp-hint{margin:7px 0 0;color:#94a3b8;font-size:11px}

/* animation utilities */
.panel-lift{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}

.icon-hover-rotate{transition:transform 0.25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}

/* modal scaleIn entrance */
.modal-box-sm{animation:scaleIn 0.25s cubic-bezier(0.4,0,0.2,1)}
@keyframes scaleIn{from{opacity:0;transform:scale(0.92)}to{opacity:1;transform:scale(1)}}

/* enhanced table row hover */
.um-row{transition:all 0.18s ease}
.um-row:hover{background:#fafaff;transform:translateX(2px)}

/* resource bar shimmer */
.res-fill{position:relative;overflow:hidden}
.res-fill::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.4) 50%,transparent 100%);animation:barShimmer 2s ease-in-out infinite}
@keyframes barShimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

</style>
