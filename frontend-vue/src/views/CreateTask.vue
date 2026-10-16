<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, BookOpen, Check, FileText, GraduationCap, LayoutDashboard, Receipt, Send, ShieldCheck, ShoppingBag, Sparkles, Stethoscope, Users } from '@lucide/vue'
import { useTaskApi } from '@/composables/useTaskApi'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
const { createTask } = useTaskApi()
const store = useTaskStore()

const userInput = ref('')
const submitting = ref(false)

const templates = [
  { label: '用户登录系统', category: '认证与安全', icon: ShieldCheck, tone: 'blue', text: '设计一个用户认证系统，支持邮箱注册登录、JWT 令牌认证、密码加密存储、密码重置功能，需要提供完整的 RESTful API，高并发支持。' },
  { label: '电商平台', category: '交易平台', icon: ShoppingBag, tone: 'orange', text: '设计一个 B2C 电商平台，包括商品管理（CRUD）、购物车模块、订单管理、支付对接（支付宝/微信）、用户评价系统、后台管理面板。' },
  { label: '在线教育', category: '内容与学习', icon: GraduationCap, tone: 'green', text: '设计一个在线教育平台，支持视频课程发布和播放、作业提交与批改、学习进度跟踪、在线考试系统、师生互动讨论区。' },
  { label: '项目管理工具', category: '团队协作', icon: LayoutDashboard, tone: 'violet', text: '设计一个团队项目管理工具，支持看板视图、任务分配与跟踪、甘特图时间线、团队协作讨论、文件共享和版本管理。' },
  { label: '医疗问诊系统', category: '医疗健康', icon: Stethoscope, tone: 'rose', text: '设计一个在线医疗问诊系统，支持患者预约挂号、图文与视频问诊、电子病历、处方开具、医生排班，以及问诊记录查询。' },
  { label: '财税系统', category: '财务税务', icon: Receipt, tone: 'teal', text: '设计一个中小企业财税系统，支持发票识别入账、收支流水、增值税测算、三大报表、报税清单整理，并在人工确认后提交申报。' },
]

const workflowSteps = ['需求澄清', '方案设计', '工程实现', '智能评审', '交付打包']

function useTemplate(text: string) { userInput.value = text }

async function handleSubmit() {
  if (!userInput.value.trim()) return
  submitting.value = true
  try {
    const resp = await createTask(userInput.value.trim())
    store.setTaskId(resp.task_id)
    store.setTaskStatus('queued')
    ElMessage.success('任务已创建，正在启动协作流程')
    router.push({ name: 'detail', params: { id: resp.task_id } })
  } catch {
    ElMessage.error('创建失败，请检查后端服务是否运行')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="create-page animate-in">
    <div class="page-header">
      <div>
        <div class="eyebrow"><Sparkles :size="13" /> Agent Studio</div>
        <h1>创建任务</h1>
        <p>描述你的业务需求，AI 智能体团队将自动完成全流程交付</p>
      </div>
    </div>

    <div class="composer-grid">
      <div class="input-card card">
        <div class="card-heading">
          <span class="heading-icon"><FileText :size="18" /></span>
          <div>
            <h2>描述你的需求</h2>
            <p>写清楚目标、核心功能和约束，交付结果会更准确</p>
          </div>
        </div>
        <el-input
          v-model="userInput"
          type="textarea"
          :rows="9"
          placeholder="例如：我想开发一个在线教育平台，支持视频课程、直播教学、作业提交和成绩管理..."
          class="custom-textarea"
          :disabled="submitting"
        />
        <div class="input-footer">
          <span class="char-count">{{ userInput.length }} 字 · 建议 50 字以上</span>
          <el-button class="submit-btn" :loading="submitting" :disabled="!userInput.trim()" @click="handleSubmit">
            <Send :size="15" /> 提交需求
          </el-button>
        </div>
      </div>

      <aside class="workflow-card card">
        <div class="workflow-title"><Users :size="18" /> 智能体协作流程</div>
        <p class="workflow-desc">提交后，系统会自动组织多角色智能体完成以下步骤。</p>
        <div class="workflow-list">
          <div v-for="(step, index) in workflowSteps" :key="step" class="workflow-step">
            <span class="step-index">{{ index + 1 }}</span>
            <span>{{ step }}</span>
            <Check :size="14" />
          </div>
        </div>
        <div class="workflow-tip"><BookOpen :size="15" /> 可在任务详情中实时查看过程并参与审批</div>
      </aside>
    </div>

    <div class="section-head">
      <div><h3 class="section-title">从模板快速开始</h3><p>选择常见场景后仍可继续编辑需求</p></div>
    </div>
    <div class="template-grid">
      <div
        v-for="tpl in templates" :key="tpl.label"
        :class="['tpl-card', 'card', `tpl-${tpl.tone}`]"
        @click="useTemplate(tpl.text)"
      >
        <span class="tpl-icon"><component :is="tpl.icon" :size="20" /></span>
        <div class="tpl-copy">
          <span class="tpl-category">{{ tpl.category }}</span>
          <span class="tpl-name">{{ tpl.label }}</span>
          <span class="tpl-preview">{{ tpl.text.substring(0, 48) }}...</span>
        </div>
        <ArrowRight :size="17" class="tpl-arrow" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 26px; }
.page-header h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 4px; }
.page-header p { font-size: 14px; color: var(--text-secondary); }
.eyebrow { display: flex; align-items: center; gap: 6px; margin-bottom: 7px; color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.composer-grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 18px; margin-bottom: 34px; }
.input-card { padding: 24px; }
.card-heading { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.card-heading h2 { font-size: 16px; font-weight: 650; }
.card-heading p { margin-top: 2px; font-size: 12px; color: var(--text-muted); }
.heading-icon { display: flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 12px; color: var(--accent); background: var(--accent-subtle); }

.input-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.custom-textarea :deep(.el-textarea__inner) {
  background: #fafbfc;
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.7;
  border-radius: 12px;
  padding: 15px 16px;
  resize: vertical;
  transition: border-color var(--transition-fast);
}
.custom-textarea :deep(.el-textarea__inner):focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-subtle);
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}
.char-count { font-size: 11px; color: var(--text-muted); }

.submit-btn {
  height: 36px;
  padding: 0 18px;
  font-weight: 600;
  font-size: 13px;
  gap: 6px;
  border-radius: 8px;
  background: var(--accent-dark);
  border: 1px solid var(--accent-dark);
  color: #fff;
}
.submit-btn:hover { background: var(--accent); border-color: var(--accent); }
.submit-btn:disabled { opacity: 0.4; }
.workflow-card { padding: 22px; background: linear-gradient(160deg, #fff 45%, #f3f7ff 100%); }
.workflow-title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 650; }
.workflow-title svg { color: var(--accent); }
.workflow-desc { margin: 8px 0 18px; font-size: 12px; line-height: 1.7; color: var(--text-secondary); }
.workflow-list { display: flex; flex-direction: column; }
.workflow-step { position: relative; display: grid; grid-template-columns: 28px 1fr 16px; align-items: center; gap: 9px; min-height: 42px; font-size: 13px; color: var(--text-secondary); }
.workflow-step:not(:last-child)::after { position: absolute; top: 34px; bottom: -8px; left: 13px; width: 1px; content: ''; background: #dce6fb; }
.step-index { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; color: var(--accent); background: var(--accent-subtle); font-size: 11px; font-weight: 700; }
.workflow-step > svg { color: var(--success); }
.workflow-tip { display: flex; gap: 7px; margin-top: 17px; padding: 11px; border-radius: 10px; background: rgba(255,255,255,.72); color: var(--text-muted); font-size: 11px; line-height: 1.55; }

/* ── Templates ───────────────────────────── */
.section-head { margin-bottom: 12px; }
.section-title { font-size: 16px; font-weight: 650; }
.section-head p { margin-top: 2px; font-size: 12px; color: var(--text-muted); }
.template-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.tpl-card {
  display: flex; align-items: center; gap: 13px;
  min-width: 0;
  padding: 16px;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.tpl-card:hover { border-color: #bdcdf3; transform: translateY(-2px); }
.tpl-icon { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex-shrink: 0; border-radius: 13px; background: var(--accent-subtle); color: var(--accent); }
.tpl-orange .tpl-icon { color: #d97706; background: #fff4e5; }
.tpl-green .tpl-icon { color: var(--success); background: var(--success-subtle); }
.tpl-violet .tpl-icon { color: #7955d9; background: #f2efff; }
.tpl-rose .tpl-icon { color: #d9486b; background: #fff0f4; }
.tpl-teal .tpl-icon { color: #0f8f86; background: #e7f8f6; }
.tpl-copy { display: flex; flex: 1; min-width: 0; flex-direction: column; }
.tpl-category { font-size: 10px; color: var(--text-muted); }
.tpl-name { font-size: 13px; font-weight: 600; }
.tpl-preview {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tpl-arrow { flex-shrink: 0; color: var(--text-muted); }
.tpl-card:hover .tpl-arrow { color: var(--accent); transform: translateX(2px); }

@media (max-width: 900px) { .composer-grid { grid-template-columns: 1fr; } .workflow-card { display: none; } }
@media (max-width: 620px) { .page-header h1 { font-size: 24px; } .template-grid { grid-template-columns: 1fr; } .input-card { padding: 18px; } }
</style>
