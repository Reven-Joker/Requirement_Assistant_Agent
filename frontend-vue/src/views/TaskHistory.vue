<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Activity, CheckCircle2, ChevronRight, CircleAlert, Clock3, Inbox, Plus, RefreshCw, Search, Sparkles } from '@lucide/vue'
import { useTaskApi } from '@/composables/useTaskApi'
import { useTaskStore } from '@/stores/task'
import type { TaskListItem } from '@/types'

const router = useRouter()
const { listTasks } = useTaskApi()
const store = useTaskStore()

const tasks = ref<TaskListItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const statusFilter = ref('all')

const filters = ['all', 'queued', 'running', 'waiting_human', 'completed', 'error']
const filterLabels: Record<string, string> = {
  all: '全部', queued: '排队中', running: '执行中', waiting_human: '待处理', completed: '已完成', error: '失败',
}

const statusConfig: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'tag-info' },
  running: { label: '执行中', cls: 'tag-warning' },
  waiting_human: { label: '待处理', cls: 'tag-warning' },
  completed: { label: '已完成', cls: 'tag-success' },
  error: { label: '失败', cls: 'tag-danger' },
}

const filteredTasks = computed(() => {
  let result = tasks.value
  if (statusFilter.value !== 'all') result = result.filter(t => t.status === statusFilter.value)
  const q = searchQuery.value.trim().toLowerCase()
  if (q) result = result.filter(t => t.task_id.includes(q) || t.user_input.toLowerCase().includes(q))
  return result
})

const summaryCards = computed(() => [
  { label: '全部任务', value: tasks.value.length, icon: Activity, tone: 'blue' },
  { label: '执行中', value: tasks.value.filter(t => t.status === 'running').length, icon: Clock3, tone: 'amber' },
  { label: '已完成', value: tasks.value.filter(t => t.status === 'completed').length, icon: CheckCircle2, tone: 'green' },
  { label: '需要关注', value: tasks.value.filter(t => t.status === 'error' || t.status === 'waiting_human').length, icon: CircleAlert, tone: 'red' },
])

onMounted(refresh)

async function refresh() {
  loading.value = true
  try { tasks.value = await listTasks(50) } catch { tasks.value = [] }
  finally { loading.value = false }
}

function viewTask(id: string) {
  store.setTaskId(id)
  router.push({ name: 'detail', params: { id } })
}
</script>

<template>
  <div class="history-page animate-in">
    <div class="page-header">
      <div>
        <div class="eyebrow"><Sparkles :size="13" /> Agent Tasks</div>
        <h1>历史任务</h1>
        <p>浏览和管理所有需求交付任务</p>
      </div>
      <div class="header-actions">
        <el-button class="btn-secondary" :loading="loading" @click="refresh"><RefreshCw :size="14" /> 刷新</el-button>
        <el-button class="btn-primary" @click="router.push({ name: 'create' })"><Plus :size="14" /> 新建任务</el-button>
      </div>
    </div>

    <div class="summary-grid">
      <div v-for="item in summaryCards" :key="item.label" :class="['summary-card', 'card', `tone-${item.tone}`]">
        <span class="summary-icon"><component :is="item.icon" :size="17" /></span>
        <div><strong>{{ item.value }}</strong><span>{{ item.label }}</span></div>
      </div>
    </div>

    <div class="content-card card">
      <div class="toolbar">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="searchQuery" class="search-input" placeholder="搜索任务 ID 或需求描述..." />
        </div>
        <div class="result-count">共 {{ filteredTasks.length }} 条结果</div>
      </div>
      <div class="filter-row">
        <button
          v-for="f in filters" :key="f"
          :class="['filter-btn', { active: statusFilter === f }]"
          @click="statusFilter = f"
        >{{ filterLabels[f] }}</button>
      </div>

      <div v-if="filteredTasks.length" class="list">
        <div v-for="task in filteredTasks" :key="task.task_id" class="list-row" @click="viewTask(task.task_id)">
          <span class="task-icon"><Inbox :size="17" /></span>
          <div class="list-body">
            <span class="list-text">{{ task.user_input }}</span>
            <span class="list-id">ID · {{ task.task_id }}</span>
          </div>
          <span :class="['list-tag', statusConfig[task.status]?.cls || 'tag-info']">
            {{ statusConfig[task.status]?.label || task.status }}
          </span>
          <ChevronRight :size="17" class="row-arrow" />
        </div>
      </div>

      <div v-else-if="!loading" class="empty-center">
        <Inbox :size="34" />
        <h3>暂无匹配任务</h3>
        <p>调整筛选条件，或创建一个新的交付任务。</p>
        <el-button class="btn-primary" size="small" @click="router.push({ name: 'create' })">创建任务</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 26px;
}
.page-header h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 4px; }
.page-header p { font-size: 14px; color: var(--text-secondary); }
.eyebrow { display: flex; align-items: center; gap: 6px; margin-bottom: 7px; color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.header-actions { display: flex; gap: 8px; }

.btn-secondary {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 12px;
  gap: 6px; border-radius: 8px; height: 36px;
}
.btn-secondary:hover { border-color: var(--text-muted); color: var(--text-primary); }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
.summary-card { display: flex; align-items: center; gap: 12px; padding: 16px 18px; }
.summary-icon { display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 11px; color: var(--accent); background: var(--accent-subtle); }
.summary-card strong { display: block; font-size: 21px; line-height: 1.1; color: var(--text-primary); }
.summary-card span:last-child { font-size: 11px; color: var(--text-muted); }
.tone-green .summary-icon { color: var(--success); background: var(--success-subtle); }
.tone-amber .summary-icon { color: var(--warning); background: var(--warning-subtle); }
.tone-red .summary-icon { color: var(--danger); background: var(--danger-subtle); }
.content-card { overflow: hidden; }
.toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px 12px;
}
.search-box {
  display: flex; align-items: center;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 0 12px;
  flex: 1; max-width: 420px;
  color: var(--text-muted);
}
.search-input {
  width: 100%;
  height: 38px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
}
.search-input::placeholder { color: var(--text-placeholder); }
.result-count { font-size: 11px; color: var(--text-muted); }
.filter-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; padding: 0 20px 16px; border-bottom: 1px solid var(--border-light); }
.filter-btn {
  padding: 5px 10px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--text-secondary);
  font-size: 11px; font-weight: 500; font-family: var(--font-sans);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.filter-btn:hover { border-color: var(--text-muted); color: var(--text-primary); }
.filter-btn.active {
  background: var(--accent-subtle); border-color: var(--accent); color: var(--accent);
}

.list { display: flex; flex-direction: column; }
.list-row {
  display: flex; align-items: center; justify-content: space-between;
  min-height: 76px; padding: 13px 20px; border-bottom: 1px solid var(--border-light); cursor: pointer;
  transition: background var(--transition-fast);
}
.list-row:last-child { border-bottom: 0; }
.list-row:hover { background: var(--bg-card-hover); }
.task-icon { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; margin-right: 12px; flex-shrink: 0; border-radius: 10px; color: var(--text-muted); background: var(--bg-overlay); }
.list-body { flex: 1; overflow: hidden; }
.list-text {
  font-size: 13px; font-weight: 500;
  display: block;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 4px;
}
.list-id { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.list-tag {
  font-size: 11px; font-weight: 600; padding: 2px 8px;
  border-radius: 6px; flex-shrink: 0; margin-left: 12px;
}
.row-arrow { margin-left: 12px; color: var(--text-placeholder); }
.list-row:hover .row-arrow { color: var(--accent); transform: translateX(2px); }

/* ── Tags ─────────────────────────────────── */
.tag-info    { background: var(--info-subtle); color: var(--info); }
.tag-warning { background: var(--warning-subtle); color: var(--warning); }
.tag-success { background: var(--success-subtle); color: var(--success); }
.tag-danger  { background: var(--danger-subtle); color: var(--danger); }

.btn-primary {
  background: var(--accent-dark);
  border: 1px solid var(--accent-dark);
  color: #fff;
  font-weight: 600;
  font-size: 12px;
  display: inline-flex; gap: 6px; border-radius: 8px; height: 36px;
}
.empty-center { padding: 72px 0; text-align: center; color: var(--text-muted); }
.empty-center > svg { margin-bottom: 10px; color: var(--text-placeholder); }
.empty-center h3 { color: var(--text-primary); font-size: 15px; }
.empty-center p { margin: 4px 0 16px; font-size: 12px; }

@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px) { .page-header { gap: 14px; } .page-header h1 { font-size: 24px; } .summary-grid { grid-template-columns: 1fr 1fr; } .summary-card { padding: 13px; } .header-actions .btn-secondary { display: none; } .toolbar { align-items: stretch; flex-direction: column; } .search-box { max-width: none; } .result-count { display: none; } }
</style>
