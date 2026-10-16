<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ThumbsUp, ThumbsDown, MessageSquare } from '@lucide/vue'
import { useTaskApi } from '@/composables/useTaskApi'

const props = defineProps<{ taskId: string }>()
const emit = defineEmits<{ 'feedback-submitted': [] }>()
const { submitFeedback } = useTaskApi()
const feedback = ref('')
const submitting = ref(false)

async function handleApprove() {
  submitting.value = true
  try {
    await submitFeedback(props.taskId, { feedback: feedback.value.trim(), approved: true })
    ElMessage.success('已批准')
    feedback.value = ''
    emit('feedback-submitted')
  } catch { ElMessage.error('操作失败') }
  finally { submitting.value = false }
}

async function handleReject() {
  if (!feedback.value.trim()) { ElMessage.warning('请填写驳回理由'); return }
  submitting.value = true
  try {
    await submitFeedback(props.taskId, { feedback: feedback.value.trim(), approved: false })
    ElMessage.success('已驳回')
    feedback.value = ''
    emit('feedback-submitted')
  } catch { ElMessage.error('操作失败') }
  finally { submitting.value = false }
}
</script>

<template>
  <div class="panel card" style="border-left: 3px solid var(--accent)">
    <div class="panel-head">
      <MessageSquare :size="16" style="color:var(--accent)" />
      <span>最终审批</span>
    </div>
    <p class="hint">请查看交付产物和评审结果，决定批准通过或驳回重做</p>

    <textarea v-model="feedback" class="text-input" placeholder="审批意见（可选，驳回时必填）..." rows="2" :disabled="submitting"></textarea>

    <div class="actions">
      <el-button class="btn-approve" :loading="submitting" @click="handleApprove">
        <ThumbsUp :size="14" style="margin-right:4px" /> 批准
      </el-button>
      <el-button class="btn-reject" :loading="submitting" @click="handleReject">
        <ThumbsDown :size="14" style="margin-right:4px" /> 驳回
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.panel { padding: 16px; margin-bottom: 16px; }
.panel-head { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.hint { font-size: 12px; color: var(--text-secondary); margin-bottom: 10px; }

.text-input {
  width: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 12px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  outline: none;
  resize: vertical;
  margin-bottom: 12px;
}
.text-input:focus { border-color: var(--accent); }
.text-input::placeholder { color: var(--text-placeholder); }

.actions { display: flex; gap: 8px; }

.btn-approve {
  height: 34px; font-weight: 600; font-size: 12px;
  border-radius: var(--radius-sm);
  background: var(--success); border: none; color: #fff;
}
.btn-approve:hover { opacity: 0.9; }

.btn-reject {
  height: 34px; font-weight: 600; font-size: 12px;
  border-radius: var(--radius-sm);
  background: transparent; border: 1px solid var(--danger); color: var(--danger);
}
.btn-reject:hover { background: var(--danger-subtle); }
</style>
