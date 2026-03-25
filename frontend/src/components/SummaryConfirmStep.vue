<script setup lang="ts">
import { computed } from 'vue'
import type { ClarificationGap, ClarificationQuestion, StructuredSummary } from '../types/workflow'

const props = defineProps<{
  summary: StructuredSummary
  clarificationQuestions: ClarificationQuestion[]
  clarificationDraftAnswers: Record<string, string>
  missingFields: ClarificationGap[]
  resolvedFields: string[]
  remainingRisks: string[]
  isComplete: boolean
  hasUnansweredBlocking: boolean
  loadingRefine: boolean
  loadingGenerate: boolean
}>()

const emit = defineEmits<{
  refine: []
  generateDesign: []
}>()

const hasAnyAnswer = computed(() =>
  props.clarificationQuestions.some(q => (props.clarificationDraftAnswers[q.id] || '').trim())
)

const listToText = (value: string[]) => value.join('\n')
const textToList = (value: string) =>
  value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
</script>

<template>
  <div class="sc-layout">

    <!-- ── Left: Summary Editor ── -->
    <div class="sc-main">
      <div class="sc-main-header">
        <div class="sc-eyebrow">Step 2 · 摘要确认</div>
        <h2 class="sc-title">核对并补充 AI 解析的需求摘要</h2>
        <p class="sc-subtitle">所有字段均可直接编辑。修改后点击右侧「确认生成」进入测试设计阶段。</p>
      </div>

      <!-- 基本信息 -->
      <div class="sc-section">
        <div class="sc-section-label">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          基本信息
        </div>
        <div class="sc-row-2">
          <label class="sc-field">
            <span class="sc-field-label">功能标题</span>
            <input class="sc-input" v-model="summary.title" placeholder="例：用户登录功能" />
          </label>
          <label class="sc-field">
            <span class="sc-field-label">业务目标</span>
            <input class="sc-input" v-model="summary.business_goal" placeholder="描述核心业务目的" />
          </label>
        </div>
      </div>

      <!-- 参与者 & 前置条件 -->
      <div class="sc-section">
        <div class="sc-section-label">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          参与者 & 前置条件
        </div>
        <div class="sc-row-2">
          <label class="sc-field">
            <span class="sc-field-label">参与角色 <span class="sc-field-hint">每行一个</span></span>
            <textarea
              class="sc-textarea"
              rows="4"
              placeholder="例：注册用户&#10;管理员"
              :value="listToText(summary.actors)"
              @input="summary.actors = textToList(($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </label>
          <label class="sc-field">
            <span class="sc-field-label">前置条件 <span class="sc-field-hint">每行一个</span></span>
            <textarea
              class="sc-textarea"
              rows="4"
              placeholder="例：用户已注册账号&#10;网络连接正常"
              :value="listToText(summary.preconditions)"
              @input="summary.preconditions = textToList(($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </label>
        </div>
      </div>

      <!-- 主流程 -->
      <div class="sc-section">
        <div class="sc-section-label">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          主流程
        </div>
        <label class="sc-field">
          <span class="sc-field-label">按步骤描述正向操作路径 <span class="sc-field-hint">每行一步</span></span>
          <textarea
            class="sc-textarea sc-textarea--flow"
            rows="7"
            placeholder="1. 用户进入登录页&#10;2. 输入账号密码&#10;3. 点击登录按钮&#10;4. 系统校验成功，跳转首页"
            :value="listToText(summary.main_flow)"
            @input="summary.main_flow = textToList(($event.target as HTMLTextAreaElement).value)"
          ></textarea>
        </label>
      </div>

      <!-- 异常流程 -->
      <div class="sc-section">
        <div class="sc-section-label">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          异常流程
        </div>
        <label class="sc-field">
          <span class="sc-field-label">描述各类错误情况及系统响应 <span class="sc-field-hint">每行一个场景</span></span>
          <textarea
            class="sc-textarea sc-textarea--flow"
            rows="6"
            placeholder="密码错误超过 5 次，账号锁定 30 分钟&#10;网络超时，提示重试"
            :value="listToText(summary.exception_flows)"
            @input="summary.exception_flows = textToList(($event.target as HTMLTextAreaElement).value)"
          ></textarea>
        </label>
      </div>

      <!-- 规则 & 平台关注 -->
      <div class="sc-section">
        <div class="sc-section-label">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          规则 & 平台专项
        </div>
        <div class="sc-row-2">
          <label class="sc-field">
            <span class="sc-field-label">业务规则 <span class="sc-field-hint">每行一条</span></span>
            <textarea
              class="sc-textarea"
              rows="5"
              placeholder="例：密码至少 8 位，包含数字和字母"
              :value="listToText(summary.business_rules)"
              @input="summary.business_rules = textToList(($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </label>
          <label class="sc-field">
            <span class="sc-field-label">平台专项关注 <span class="sc-field-hint">每行一条</span></span>
            <textarea
              class="sc-textarea"
              rows="5"
              placeholder="例：iOS / Android 差异&#10;弱网场景"
              :value="listToText(summary.platform_focus)"
              @input="summary.platform_focus = textToList(($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </label>
        </div>
      </div>
    </div>

    <!-- ── Right: AI Analysis Panel ── -->
    <div class="sc-side">

      <!-- Status Banner -->
      <div class="sc-status" :class="isComplete ? 'sc-status--ok' : hasUnansweredBlocking ? 'sc-status--block' : 'sc-status--ok'">
        <div class="sc-status-icon">
          <svg v-if="isComplete" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <svg v-else-if="hasUnansweredBlocking" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <div>
          <div class="sc-status-title">{{ isComplete ? '需求信息已就绪' : hasUnansweredBlocking ? '有阻塞问题待确认' : '可以进入测试设计' }}</div>
          <div class="sc-status-sub">{{ isComplete ? 'AI 判定信息已足够支撑测试设计' : hasUnansweredBlocking ? '建议回答下方标红问题以提高覆盖质量' : '所有关键信息已齐备' }}</div>
        </div>
      </div>

      <!-- Clarification Questions -->
      <div v-if="clarificationQuestions.length > 0" class="sc-side-section">
        <div class="sc-side-label">AI 澄清问题</div>
        <div class="sc-questions">
          <div
            v-for="q in clarificationQuestions"
            :key="q.id"
            class="sc-question"
            :class="{ 'sc-question--blocking': q.blocking }"
          >
            <div class="sc-question-top">
              <span class="sc-question-text">{{ q.question }}</span>
              <span class="sc-q-badge" :class="q.blocking ? 'sc-q-badge--block' : 'sc-q-badge--suggest'">
                {{ q.blocking ? '阻塞' : '建议' }}
              </span>
            </div>
            <div class="sc-question-reason">{{ q.reason }}</div>
            <textarea
              class="sc-textarea sc-q-answer"
              rows="2"
              placeholder="填写确认、假设或补充信息…"
              v-model="clarificationDraftAnswers[q.id]"
            ></textarea>
          </div>
        </div>
      </div>
      <div v-else class="sc-side-section">
        <div class="sc-side-label">AI 澄清问题</div>
        <div class="sc-empty-hint">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          没有额外澄清问题
        </div>
      </div>

      <!-- Gaps & Risks -->
      <div class="sc-side-section">
        <div class="sc-side-label">需求缺口 & 风险</div>

        <div v-if="missingFields.length" class="sc-gap-list">
          <div v-for="item in missingFields" :key="`${item.field}-${item.detail}`" class="sc-gap-item">
            <span class="sc-gap-badge" :class="item.severity === 'high' ? 'sc-gap-badge--high' : 'sc-gap-badge--mid'">
              {{ item.field }}
            </span>
            <span class="sc-gap-text">{{ item.detail }}</span>
          </div>
        </div>
        <div v-else class="sc-empty-hint">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          未发现明显缺失字段
        </div>

        <div v-if="resolvedFields.length" class="sc-resolved">
          <div class="sc-resolved-label">已明确维度</div>
          <div class="sc-resolved-tags">
            <span v-for="item in resolvedFields" :key="item" class="sc-resolved-tag">{{ item }}</span>
          </div>
        </div>

        <div v-if="remainingRisks.length" class="sc-risks">
          <div class="sc-risks-label">剩余风险</div>
          <div v-for="item in remainingRisks" :key="item" class="sc-risk-item">
            <span class="sc-risk-dot"></span>{{ item }}
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="sc-actions">
        <button
          class="btn btn-primary sc-btn-generate"
          :disabled="loadingGenerate"
          @click="emit('generateDesign')"
        >
          <svg v-if="!loadingGenerate" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
          </svg>
          {{ loadingGenerate ? '生成中…' : '确认生成测试设计' }}
        </button>
        <button
          v-if="clarificationQuestions.length > 0"
          class="btn btn-default sc-btn-refine"
          :disabled="loadingRefine || !hasAnyAnswer"
          :title="!hasAnyAnswer ? '请先回答至少一个问题' : undefined"
          @click="emit('refine')"
        >
          {{ loadingRefine ? '更新中…' : '结合回答重新整理摘要' }}
        </button>
        <p v-if="!hasAnyAnswer && clarificationQuestions.length > 0" class="sc-refine-hint">
          回答至少一个问题后可触发重新整理
        </p>
      </div>

    </div>
  </div>
</template>
