<script setup lang="ts">
import type { ClarificationQuestion, StructuredSummary } from '../types/workflow'

defineProps<{
  summary: StructuredSummary
  clarificationQuestions: ClarificationQuestion[]
  clarificationDraftAnswers: Record<string, string>
  loadingRefine: boolean
  loadingGenerate: boolean
}>()

const emit = defineEmits<{
  refine: []
  generateDesign: []
}>()

const listToText = (value: string[]) => value.join('\n')
const textToList = (value: string) =>
  value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">Step 2</div>
        <h2>摘要确认</h2>
      </div>
      <div class="action-group">
        <button class="btn btn-secondary" :disabled="loadingRefine" @click="emit('refine')">
          {{ loadingRefine ? '更新中...' : '结合回答重新整理摘要' }}
        </button>
        <button class="btn btn-primary" :disabled="loadingGenerate" @click="emit('generateDesign')">
          {{ loadingGenerate ? '生成中...' : '确认摘要并生成测试设计' }}
        </button>
      </div>
    </div>

    <div class="form-grid">
      <label class="field">
        <span>功能标题</span>
        <input v-model="summary.title" />
      </label>
      <label class="field">
        <span>业务目标</span>
        <input v-model="summary.business_goal" />
      </label>
    </div>

    <div class="form-grid form-grid-advanced">
      <label class="field">
        <span>角色</span>
        <textarea :value="listToText(summary.actors)" rows="5" @input="summary.actors = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
      <label class="field">
        <span>前置条件</span>
        <textarea :value="listToText(summary.preconditions)" rows="5" @input="summary.preconditions = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
    </div>

    <div class="form-grid form-grid-advanced">
      <label class="field">
        <span>主流程</span>
        <textarea :value="listToText(summary.main_flow)" rows="8" @input="summary.main_flow = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
      <label class="field">
        <span>异常流程</span>
        <textarea :value="listToText(summary.exception_flows)" rows="8" @input="summary.exception_flows = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
    </div>

    <div class="form-grid form-grid-advanced">
      <label class="field">
        <span>业务规则</span>
        <textarea :value="listToText(summary.business_rules)" rows="6" @input="summary.business_rules = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
      <label class="field">
        <span>平台专项关注点</span>
        <textarea :value="listToText(summary.platform_focus)" rows="6" @input="summary.platform_focus = textToList(($event.target as HTMLTextAreaElement).value)"></textarea>
      </label>
    </div>

    <div class="question-panel">
      <div class="sub-title">待确认问题</div>
      <div v-if="clarificationQuestions.length === 0" class="empty-state">当前没有额外澄清问题，可以直接进入测试设计。</div>
      <div v-for="question in clarificationQuestions" :key="question.id" class="question-item">
        <div class="question-title">
          <span>{{ question.question }}</span>
          <span class="pill" :class="question.blocking ? 'pill-danger' : 'pill-info'">
            {{ question.blocking ? '阻塞' : '建议' }}
          </span>
        </div>
        <div class="question-reason">{{ question.reason }}</div>
        <textarea v-model="clarificationDraftAnswers[question.id]" rows="3" placeholder="填写你的确认、假设或补充信息"></textarea>
      </div>
    </div>
  </section>
</template>
