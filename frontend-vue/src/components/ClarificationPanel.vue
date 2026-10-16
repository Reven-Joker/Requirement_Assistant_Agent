<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Send, HelpCircle, Lightbulb } from '@lucide/vue'
import { useTaskApi } from '@/composables/useTaskApi'
import type { ClarifiedRequirement } from '@/types'

const props = defineProps<{ taskId: string; clarifiedRequirement: ClarifiedRequirement | null }>()
const emit = defineEmits<{ 'feedback-submitted': [] }>()
const { submitFeedback } = useTaskApi()
const feedback = ref('')
const submitting = ref(false)

async function handleSubmit() {
  if (!feedback.value.trim()) return
  submitting.value = true
  try {
    await submitFeedback(props.taskId, { feedback: feedback.value.trim() })
    ElMessage.success('反馈已提交')
    feedback.value = ''
    emit('feedback-submitted')
  } catch { ElMessage.error('提交失败') }
  finally { submitting.value = false }
}
</script>

<template>
  <div class="panel card" style="border-left: 3px solid var(--warning)">
    <div class="panel-head">
      <HelpCircle :size="16" style="color:var(--warning)" />
      <span>需求澄清</span>
    </div>

    <div v-if="clarifiedRequirement?.open_questions?.length" class="box">
      <div class="box-title"><Lightbulb :size="13" /> 待澄清问题</div>
      <ul>
        <li v-for="(q, idx) in clarifiedRequirement.open_questions" :key="idx">
          {{ idx + 1 }}. {{ q }}
        </li>
      </ul>
    </div>

    <div class="row">
      <textarea v-model="feedback" class="text-input" placeholder="补充信息..." rows="2" :disabled="submitting"></textarea>
      <el-button class="btn-submit" :loading="submitting" :disabled="!feedback.trim()" @click="handleSubmit">
        <Send :size="13" style="margin-right:4px" /> 提交
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.panel { padding: 16px; margin-bottom: 16px; }
.panel-head { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; margin-bottom: 12px; }

.box {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 12px;
}
.box-title {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 600; color: var(--text-muted);
  margin-bottom: 8px;
}
.box ul { list-style: none; padding: 0; }
.box li { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; line-height: 1.5; }

.row { display: flex; gap: 8px; align-items: flex-end; }
.text-input {
  flex: 1;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 12px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  outline: none;
  resize: vertical;
}
.text-input:focus { border-color: var(--accent); }
.text-input::placeholder { color: var(--text-placeholder); }

.btn-submit {
  height: 34px; font-weight: 600; font-size: 12px;
  border-radius: var(--radius-sm);
  background: var(--accent-dark); border: none; color: #fff;
  white-space: nowrap;
}
.btn-submit:hover { background: var(--accent); }
</style>
