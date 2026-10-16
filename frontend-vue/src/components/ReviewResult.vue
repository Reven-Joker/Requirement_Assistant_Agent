<script setup lang="ts">
import { computed } from 'vue'
import { ShieldCheck, ShieldX, AlertTriangle, Lightbulb } from '@lucide/vue'
import type { ReviewResult as ReviewType } from '@/types'

const props = defineProps<{ review: ReviewType }>()

const scoreColor = computed(() => {
  const s = props.review.overall_score
  if (s >= 8) return 'var(--success)'
  if (s >= 6) return 'var(--warning)'
  return 'var(--danger)'
})
</script>

<template>
  <div class="panel card">
    <div class="panel-head">
      <ShieldCheck v-if="review.passed" :size="16" style="color:var(--success)" />
      <ShieldX v-else :size="16" style="color:var(--danger)" />
      <span>智能评审</span>
      <span :class="['badge', review.passed ? 'pass' : 'fail']">
        {{ review.passed ? '通过' : '未通过' }}
      </span>
    </div>

    <!-- Scores -->
    <div class="scores">
      <div class="score-box">
        <span class="score-num" :style="{ color: scoreColor }">{{ review.overall_score.toFixed(1) }}</span>
        <span class="score-label">综合评分</span>
      </div>
      <div class="score-box">
        <span class="score-num-sm">{{ review.prd_score.toFixed(1) }}</span>
        <span class="score-label">PRD 评分</span>
      </div>
      <div class="score-box">
        <span class="score-num-sm">{{ review.tech_score.toFixed(1) }}</span>
        <span class="score-label">技术评分</span>
      </div>
    </div>

    <p v-if="review.summary" class="summary">{{ review.summary }}</p>

    <!-- Issues -->
    <div v-if="review.issues.length" class="section">
      <div class="sect-title"><AlertTriangle :size="13" style="color:var(--warning)" /> 问题 ({{ review.issues.length }})</div>
      <div v-for="(issue, idx) in review.issues" :key="idx" class="issue-item">
        <div class="issue-head">
          <span :class="'sev sev-' + issue.severity">{{ issue.severity }}</span>
          <span class="issue-desc">{{ issue.description }}</span>
        </div>
        <div v-if="issue.suggestion" class="issue-sugg">
          <Lightbulb :size="11" /> {{ issue.suggestion }}
        </div>
      </div>
    </div>

    <!-- Suggestions -->
    <div v-if="review.suggestions.length" class="section">
      <div class="sect-title" style="color:var(--info)">建议</div>
      <ul class="sugg-list">
        <li v-for="(s, idx) in review.suggestions" :key="idx">{{ s }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.panel { padding: 18px; margin-bottom: 16px; }
.panel-head { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; margin-bottom: 14px; }
.badge { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; margin-left: auto; }
.badge.pass { background: var(--success-subtle); color: var(--success); }
.badge.fail { background: var(--danger-subtle); color: var(--danger); }

/* ── Scores ──────────────────────────────── */
.scores { display: flex; gap: 24px; margin-bottom: 14px; }
.score-box { display: flex; flex-direction: column; }
.score-num { font-size: 26px; font-weight: 800; line-height: 1; }
.score-num-sm { font-size: 18px; font-weight: 700; line-height: 1; color: var(--text-primary); }
.score-label { font-size: 10px; color: var(--text-muted); margin-top: 2px; }

.summary {
  font-size: 12px; color: var(--text-secondary); line-height: 1.6;
  padding: 8px 10px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
}

/* ── Issues ──────────────────────────────── */
.section { margin-top: 12px; }
.sect-title { display: flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; margin-bottom: 8px; }
.issue-item { margin-bottom: 6px; }
.issue-head { display: flex; gap: 6px; align-items: flex-start; }
.sev {
  font-size: 9px; font-weight: 700; text-transform: uppercase;
  padding: 1px 5px; border-radius: 3px; flex-shrink: 0; margin-top: 2px;
}
.sev-critical { background: var(--danger-subtle); color: var(--danger); }
.sev-high { background: var(--warning-subtle); color: var(--warning); }
.sev-medium { background: var(--info-subtle); color: var(--info); }
.sev-low { background: var(--bg-primary); color: var(--text-muted); }
.issue-desc { font-size: 12px; color: var(--text-primary); line-height: 1.5; }
.issue-sugg {
  font-size: 11px; color: var(--info);
  display: flex; align-items: center; gap: 3px;
  margin-top: 3px; padding-left: 54px;
}

.sugg-list { padding-left: 18px; }
.sugg-list li { font-size: 12px; color: var(--text-secondary); margin-bottom: 3px; }
</style>
