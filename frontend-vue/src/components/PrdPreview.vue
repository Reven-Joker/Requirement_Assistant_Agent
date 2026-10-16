<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'
import { FileText, ChevronDown, ChevronRight } from '@lucide/vue'
import type { PRDDocument } from '@/types'

const props = defineProps<{ prd: PRDDocument }>()
const expanded = ref(true)

function renderMarkdown(text: string): string { return marked(text) as string }

function buildPRDMarkdown(prd: PRDDocument): string {
  let md = `# ${prd.product_name}\n\n`
  md += `## 产品定位\n${prd.positioning}\n\n`
  if (prd.user_stories?.length) {
    md += '## 用户故事\n'
    for (const s of prd.user_stories) md += `- **作为** ${s.role}，**我希望** ${s.action}，**从而** ${s.benefit}\n`
    md += '\n'
  }
  md += '## 功能模块\n'
  for (const m of prd.feature_modules || []) {
    md += `### ${m.name} (${m.priority})\n${m.description}\n`
    if (m.sub_features?.length) { for (const sf of m.sub_features) md += `- ${sf}\n`; md += '\n' }
    else md += '\n'
  }
  if (prd.user_flows?.length) {
    md += '## 用户流程\n'
    for (const f of prd.user_flows) {
      md += `### ${f.name}\n`
      for (let i = 0; i < (f.steps || []).length; i++) md += `${i + 1}. ${f.steps[i]}\n`
      md += '\n'
    }
  }
  if (prd.non_functional_requirements?.length) {
    md += '## 非功能性需求\n'
    for (const n of prd.non_functional_requirements) md += `- **${n.category}**: ${n.description}${n.metric ? ' (' + n.metric + ')' : ''}\n`
    md += '\n'
  }
  if (prd.success_metrics?.length) { md += '## 成功指标\n'; for (const m of prd.success_metrics) md += `- ${m}\n`; md += '\n' }
  if (prd.out_of_scope?.length) { md += '## 不在范围内\n'; for (const o of prd.out_of_scope) md += `- ${o}\n` }
  return md
}
</script>

<template>
  <div class="panel card">
    <div class="panel-head" @click="expanded = !expanded" style="cursor:pointer; user-select:none">
      <FileText :size="15" style="color:var(--accent)" />
      <span>PRD 产品方案</span>
      <span class="chip">{{ prd.product_name }}</span>
      <component :is="expanded ? ChevronDown : ChevronRight" :size="15" style="color:var(--text-muted); margin-left:auto" />
    </div>
    <div v-if="expanded" class="md-body" v-html="renderMarkdown(buildPRDMarkdown(prd))" />
  </div>
</template>

<style scoped>
.panel { padding: 16px; margin-bottom: 12px; }
.panel-head { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.chip {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
  background: var(--accent-subtle); color: var(--accent);
}

.md-body { font-size: 13px; line-height: 1.7; color: var(--text-primary); }
.md-body :deep(h1) { font-size: 18px; margin: 13px 0 10px; }
.md-body :deep(h2) { font-size: 15px; margin: 12px 0 8px; padding-bottom: 5px; border-bottom: 1px solid var(--border); }
.md-body :deep(h3) { font-size: 13px; margin: 8px 0 6px; color: var(--accent); }
.md-body :deep(p), .md-body :deep(li) { font-size: 13px; color: var(--text-secondary); margin-bottom: 3px; }
.md-body :deep(ul), .md-body :deep(ol) { padding-left: 22px; }
.md-body :deep(strong) { font-weight: 600; color: var(--text-primary); }
.md-body :deep(table) { border-collapse: collapse; width: 100%; margin: 10px 0; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid var(--border); padding: 6px 10px; font-size: 12px; text-align: left; }
.md-body :deep(th) { background: var(--bg-primary); font-weight: 600; }
</style>
