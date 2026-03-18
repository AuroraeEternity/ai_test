<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

type Platform = 'web' | 'app' | 'plugin'

interface PlatformOption {
  label: string
  value: Platform
  description: string
}

interface StructuredSummary {
  title: string
  business_goal: string
  actors: string[]
  preconditions: string[]
  main_flow: string[]
  exception_flows: string[]
  business_rules: string[]
  platform_focus: string[]
}

interface ClarificationQuestion {
  id: string
  question: string
  reason: string
  blocking: boolean
}

interface ClarificationAnswer {
  question_id: string
  question: string
  answer: string
}

interface TestPoint {
  id: string
  title: string
  category: string
  description: string
  source: string
  risk_level: 'high' | 'medium' | 'low'
  platform_specific: boolean
}

interface AnalyzeResponse {
  platform: Platform
  summary: StructuredSummary
  functions: string[]
  flows: string[]
  module_segments: Record<string, string>
  clarification_questions: ClarificationQuestion[]
  coverage_dimensions: string[]
  test_points: TestPoint[]
  prompts: Record<string, string>
}

interface TestCase {
  id: string
  title: string
  case_type: string
  priority: 'P0' | 'P1' | 'P2'
  requirement_refs: string[]
  preconditions: string[]
  test_data: string[]
  steps: string[]
  expected_results: string[]
  coverage_tags: string[]
  platform: Platform
  source_test_point_id: string
  confidence: number
}

interface ValidationIssue {
  issue_type: string
  message: string
  severity: 'high' | 'medium' | 'low'
}

interface ReviewNote {
  note_type: string
  message: string
  severity: 'high' | 'medium' | 'low'
  target_test_point_id: string
}

interface GenerateCasesResponse {
  platform: Platform
  cases: TestCase[]
  validation_issues: ValidationIssue[]
  prompts: Record<string, string>
}

interface ReviewTestPointsResponse {
  platform: Platform
  reviewed_test_points: TestPoint[]
  review_notes: ReviewNote[]
  prompts: Record<string, string>
}

interface IntegrationTest {
  id: string
  title: string
  description: string
  flow: string
  preconditions: string[]
  steps: string[]
  expected_results: string[]
}

interface IntegrationTestsResponse {
  platform: Platform
  integration_tests: IntegrationTest[]
  prompts: Record<string, string>
}

interface ProjectOption {
  label: string
  value: string
}

interface MetaResponse {
  platforms: PlatformOption[]
  projects: ProjectOption[]
  workflow_steps: string[]
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const fallbackMeta: MetaResponse = {
  platforms: [
    { label: 'Web', value: 'web', description: '后台、官网、表单' },
    { label: 'App', value: 'app', description: 'iOS / Android 客户端' },
    { label: '插件', value: 'plugin', description: '浏览器插件、IDE 扩展等' },
  ],
  projects: [
    { label: 'Solvely', value: 'solvely' },
  ],
  workflow_steps: [
    '输入需求',
    'AI 结构分析',
    '缺失检查与澄清',
    '审核测试点',
    '生成功能用例',
    '流程联动测试',
    '结果校验',
  ],
}

const showAdvanced = ref(false)

const meta = ref<MetaResponse>(fallbackMeta)
const loadingMeta = ref(false)
const analyzing = ref(false)
const reviewing = ref(false)
const generating = ref(false)
const generatingIntegration = ref(false)
const errorMessage = ref('')

const form = reactive({
  platform: 'web' as Platform,
  project: '',
  requirementText: '',
  actors: '',
  preconditions: '',
  businessRules: '',
})

const analysis = ref<AnalyzeResponse | null>(null)
const reviewResult = ref<ReviewTestPointsResponse | null>(null)
const generation = ref<GenerateCasesResponse | null>(null)
const integrationResult = ref<IntegrationTestsResponse | null>(null)
const selectedTestPointIds = ref<string[]>([])
const clarificationAnswers = reactive<Record<string, string>>({})

const viewStep = ref(1)
const summaryFilter = ref<'all' | 'functional' | 'integration'>('all')

const maxReachedStep = computed(() => {
  if (integrationResult.value) return 6
  if (generation.value) return 4
  if (reviewResult.value || (analysis.value && analysis.value.clarification_questions.length === 0)) return 3
  if (analysis.value && analysis.value.clarification_questions.length > 0) return 2
  return 1
})

const stepLabels = ['需求输入', 'AI 澄清问题', '测试点审核', '功能用例', '流程联动测试', '用例汇总']

const goToStep = (step: number) => {
  if (step >= 1 && step <= maxReachedStep.value) {
    viewStep.value = step
  }
}

const goBack = () => {
  if (viewStep.value > 1) {
    let prev = viewStep.value - 1
    if (prev === 2 && analysis.value && analysis.value.clarification_questions.length === 0) {
      prev = 1
    }
    viewStep.value = prev
  }
}

const displayedTestPoints = computed(() => {
  if (reviewResult.value) return reviewResult.value.reviewed_test_points
  if (analysis.value) return analysis.value.test_points
  return []
})

const selectedTestPoints = computed(() =>
  displayedTestPoints.value.filter((item) => selectedTestPointIds.value.includes(item.id)),
)

const clarificationAnswerList = computed<ClarificationAnswer[]>(() => {
  if (!analysis.value) return []
  return analysis.value.clarification_questions
    .map((item) => ({
      question_id: item.id,
      question: item.question,
      answer: clarificationAnswers[item.id]?.trim() || '',
    }))
    .filter((item) => item.answer)
})

const blockingQuestions = computed(() => {
  if (!analysis.value) return []
  return analysis.value.clarification_questions.filter(q => q.blocking)
})

const hasUnansweredBlocking = computed(() => {
  return blockingQuestions.value.some(q => !(clarificationAnswers[q.id]?.trim()))
})

const selectedCount = computed(() => selectedTestPointIds.value.length)

const formatLines = (value: string) =>
  value
    .split(/\n|,|，/)
    .map((item) => item.trim())
    .filter(Boolean)

const loadMeta = async () => {
  loadingMeta.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/meta`)
    if (!response.ok) throw new Error('获取平台配置失败')
    meta.value = await response.json()
  } catch {
    meta.value = fallbackMeta
  } finally {
    loadingMeta.value = false
  }
}

const analyzeRequirement = async () => {
  errorMessage.value = ''
  analyzing.value = true
  reviewResult.value = null
  generation.value = null
  integrationResult.value = null
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        project: form.project,
        requirement_text: form.requirementText,
        actors: formatLines(form.actors),
        preconditions: formatLines(form.preconditions),
        business_rules: formatLines(form.businessRules),
        clarification_answers: clarificationAnswerList.value,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '需求解析失败，请检查后端服务'))
    const data = (await response.json()) as AnalyzeResponse
    analysis.value = data
    selectedTestPointIds.value = data.test_points.map((item) => item.id)
    viewStep.value = data.clarification_questions.length > 0 ? 2 : 3
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '需求解析失败'
  } finally {
    analyzing.value = false
  }
}

const reviewTestPoints = async () => {
  if (!analysis.value) return
  if (hasUnansweredBlocking.value) {
    errorMessage.value = '请先回答所有阻塞性问题'
    return
  }
  errorMessage.value = ''
  generation.value = null
  integrationResult.value = null
  reviewing.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/review-test-points`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: analysis.value.summary,
        clarification_answers: clarificationAnswerList.value,
        test_points: analysis.value.test_points,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试点审核失败'))
    const data = (await response.json()) as ReviewTestPointsResponse
    reviewResult.value = data
    selectedTestPointIds.value = data.reviewed_test_points.map((item) => item.id)
    viewStep.value = 3
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试点审核失败'
  } finally {
    reviewing.value = false
  }
}

const generateCases = async () => {
  if (!analysis.value || selectedTestPoints.value.length === 0) return
  errorMessage.value = ''
  generating.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/generate-cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: analysis.value.summary,
        selected_test_points: selectedTestPoints.value,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试用例生成失败'))
    generation.value = (await response.json()) as GenerateCasesResponse
    viewStep.value = 4
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试用例生成失败'
  } finally {
    generating.value = false
  }
}

const generateIntegrationTests = async () => {
  if (!analysis.value) return
  const points = reviewResult.value?.reviewed_test_points || analysis.value.test_points
  errorMessage.value = ''
  generatingIntegration.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/integration-tests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: analysis.value.summary,
        flows: analysis.value.flows,
        reviewed_test_points: points,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '流程联动测试生成失败'))
    integrationResult.value = (await response.json()) as IntegrationTestsResponse
    viewStep.value = 5
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流程联动测试生成失败'
  } finally {
    generatingIntegration.value = false
  }
}

const extractErrorMessage = async (response: Response, fallback: string) => {
  try {
    const payload = await response.json()
    return payload.detail || fallback
  } catch {
    return fallback
  }
}

const toggleTestPoint = (id: string) => {
  if (selectedTestPointIds.value.includes(id)) {
    selectedTestPointIds.value = selectedTestPointIds.value.filter((item) => item !== id)
    return
  }
  selectedTestPointIds.value = [...selectedTestPointIds.value, id]
}

const selectAllTestPoints = () => {
  selectedTestPointIds.value = displayedTestPoints.value.map((item) => item.id)
}

const clearSelection = () => {
  selectedTestPointIds.value = []
}

onMounted(loadMeta)
</script>

<template>
  <div class="app-wrapper">
    <!-- Sidebar -->
    <aside class="app-sidebar">
      <div class="sidebar-logo">
        <svg class="nav-icon" style="margin-right: 8px; color: var(--primary-color);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
        <span>AI Test</span>
        <span
          class="status-dot"
          :class="loadingMeta ? 'offline' : 'online'"
          :title="loadingMeta ? '服务连接中...' : '服务已就绪'"
        ></span>
      </div>
      <nav class="sidebar-nav">
        <a href="#" class="nav-item active">
          <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
          <span>生成测试用例</span>
        </a>
      </nav>
    </aside>

    <main class="app-main">

      <div class="workbench-layout">
        <!-- Step Progress Bar -->
        <div class="step-progress">
          <div
            v-for="(label, idx) in stepLabels"
            :key="idx"
            class="step-progress-item"
            :class="{
              active: viewStep === idx + 1,
              completed: maxReachedStep >= idx + 1 && viewStep !== idx + 1,
              disabled: maxReachedStep < idx + 1,
              skipped: idx === 1 && analysis && analysis.clarification_questions.length === 0
            }"
            @click="goToStep(idx + 1)"
          >
            <div class="step-circle">
              <svg v-if="maxReachedStep > idx + 1" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="step-label">{{ label }}</span>
            <div v-if="idx < stepLabels.length - 1" class="step-connector" :class="{ filled: maxReachedStep > idx + 1 }"></div>
          </div>
        </div>

        <!-- Error Banner -->
        <div v-if="errorMessage" class="error-banner">
          <strong>操作失败：</strong> {{ errorMessage }}
        </div>

        <div class="workbench-main" :class="{ 'has-sidebar': !!analysis }">
          <!-- LEFT COLUMN: Step Content (wizard style, only one step visible) -->
          <div class="workbench-left">

            <!-- Step 1: Input -->
            <div class="panel" v-if="viewStep === 1">
              <div class="panel-header">
                <h2 class="panel-title">需求输入</h2>
              </div>

              <div class="form-group">
                <label class="form-label">选择平台</label>
                <div class="platform-options">
                  <button
                    v-for="platform in meta.platforms"
                    :key="platform.value"
                    class="platform-btn"
                    :class="{ active: form.platform === platform.value }"
                    @click="form.platform = platform.value"
                  >
                    <strong>{{ platform.label }}</strong>
                    <span>{{ platform.description }}</span>
                  </button>
                </div>
              </div>

              <div class="form-group" v-if="meta.projects.length">
                <label class="form-label">
                  选择项目
                  <span class="badge badge-gray">可选</span>
                </label>
                <select v-model="form.project" class="form-select">
                  <option value="">不限项目</option>
                  <option v-for="proj in meta.projects" :key="proj.value" :value="proj.value">
                    {{ proj.label }}
                  </option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">
                  需求描述
                  <span class="badge badge-gray">必填</span>
                </label>
                <textarea
                  v-model="form.requirementText"
                  class="form-control"
                  rows="6"
                  placeholder="在此粘贴需求文档、用户故事或 PRD 内容..."
                />
              </div>

              <button class="advanced-toggle" @click="showAdvanced = !showAdvanced">
                <svg v-if="!showAdvanced" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                <svg v-else width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path></svg>
                补充高级信息（可选）
              </button>

              <div class="advanced-panel" v-if="showAdvanced">
                <div class="form-group">
                  <label class="form-label">角色信息</label>
                  <input v-model="form.actors" class="form-control" placeholder="如：普通用户, 管理员（逗号分隔）" />
                </div>
                <div class="form-group">
                  <label class="form-label">前置条件</label>
                  <input v-model="form.preconditions" class="form-control" placeholder="如：用户已登录, 账户余额大于0" />
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">业务规则</label>
                  <textarea v-model="form.businessRules" class="form-control" rows="3" placeholder="明确写出特定的校验规则，如：密码不能包含特殊字符"></textarea>
                </div>
              </div>

              <div class="step-actions">
                <div></div>
                <button
                  class="btn btn-primary"
                  :disabled="analyzing || !form.requirementText.trim()"
                  @click="analyzeRequirement"
                >
                  {{ analyzing ? '正在深度解析...' : (analysis ? '重新解析需求' : '开始智能解析') }}
                </button>
              </div>
            </div>

            <!-- Step 2: Clarification Questions -->
            <div class="panel" v-if="viewStep === 2 && analysis && analysis.clarification_questions.length > 0">
              <div class="panel-header">
                <h2 class="panel-title">AI 澄清问题</h2>
                <span class="badge badge-warning" v-if="hasUnansweredBlocking">存在待确认的阻塞问题</span>
                <span class="badge badge-success" v-else>问题已确认</span>
              </div>

              <div class="cq-list">
                <div
                  v-for="question in analysis.clarification_questions"
                  :key="question.id"
                  class="cq-card"
                  :class="{ blocking: question.blocking }"
                >
                  <div class="cq-header">
                    <span class="cq-title">{{ question.question }}</span>
                    <span class="badge badge-warning" v-if="question.blocking">阻塞</span>
                    <span class="badge badge-info" v-else>建议</span>
                  </div>
                  <p class="cq-reason">原因：{{ question.reason }}</p>
                  <textarea
                    v-model="clarificationAnswers[question.id]"
                    class="form-control"
                    rows="2"
                    placeholder="在此输入您的确认或补充..."
                  />
                </div>
              </div>

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <button
                  class="btn btn-primary"
                  :disabled="reviewing"
                  @click="reviewTestPoints"
                >
                  {{ reviewing ? '正在审核...' : '应用答案并进入审核' }}
                </button>
              </div>
            </div>

            <!-- Step 3: Test Points Review -->
            <div class="panel" v-if="viewStep === 3 && analysis">
              <div class="panel-header">
                <h2 class="panel-title">测试点审核</h2>
                <span class="badge badge-gray">{{ displayedTestPoints.length }} 项</span>
              </div>

              <div class="tp-toolbar">
                <div>
                  已选择 <strong>{{ selectedCount }}</strong> / {{ displayedTestPoints.length }} 项
                  <span style="color: var(--text-muted); font-size: 13px; margin-left: 12px;">（勾选需要生成用例的测试点）</span>
                </div>
                <div style="display: flex; gap: 12px;">
                  <button class="btn btn-default" @click="selectAllTestPoints">全选</button>
                  <button class="btn btn-default" @click="clearSelection">清空</button>
                </div>
              </div>

              <div v-if="reviewResult?.review_notes.length" class="review-notes-box">
                <div class="list-title">AI 审核意见 (基于您的澄清补充)</div>
                <div class="review-note-item" v-for="note in reviewResult.review_notes" :key="note.message">
                  <strong>[{{ note.note_type }}]</strong> {{ note.message }}
                </div>
              </div>

              <div class="tp-list">
                <label
                  v-for="tp in displayedTestPoints"
                  :key="tp.id"
                  class="tp-item"
                  :class="{ selected: selectedTestPointIds.includes(tp.id) }"
                >
                  <input
                    type="checkbox"
                    class="tp-checkbox"
                    :checked="selectedTestPointIds.includes(tp.id)"
                    @change="toggleTestPoint(tp.id)"
                  />
                  <div class="tp-main">
                    <div class="tp-title-row">
                      <span class="tp-title">{{ tp.title }}</span>
                      <span class="badge" :class="tp.risk_level === 'high' ? 'badge-danger' : (tp.risk_level === 'medium' ? 'badge-warning' : 'badge-info')">
                        {{ tp.risk_level === 'high' ? '高风险' : (tp.risk_level === 'medium' ? '中风险' : '低风险') }}
                      </span>
                    </div>
                    <div class="tp-desc">{{ tp.description }}</div>
                    <div class="tp-meta">
                      <span>来源: {{ tp.source }}</span>
                      <span>分类: {{ tp.category }}</span>
                      <span v-if="tp.platform_specific" style="color: var(--primary-color); font-weight: 600;">特定平台专项</span>
                    </div>
                  </div>
                </label>
              </div>

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <button
                  class="btn btn-primary"
                  :disabled="selectedCount === 0 || generating"
                  @click="generateCases"
                >
                  {{ generating ? '正在生成用例...' : '基于选中项生成用例' }}
                </button>
              </div>
            </div>

            <!-- Step 4: Generated Cases -->
            <div class="panel" v-if="viewStep === 4 && generation">
              <div class="panel-header">
                <h2 class="panel-title">功能用例</h2>
                <span class="badge badge-success">{{ generation.cases.length }} 条</span>
              </div>

              <div class="case-item" v-for="c in generation.cases" :key="c.id">
                <div class="case-header">
                  <div class="case-id-title">
                    <span class="case-id">{{ c.id }}</span>
                    <span class="case-title">{{ c.title }}</span>
                  </div>
                  <div>
                    <span class="badge" :class="c.priority === 'P0' ? 'badge-danger' : 'badge-info'">{{ c.priority }}</span>
                  </div>
                </div>
                <div class="case-body">
                  <div>
                    <div class="case-section-title">前置条件</div>
                    <ul v-if="c.preconditions.length">
                      <li v-for="pre in c.preconditions" :key="pre">{{ pre }}</li>
                    </ul>
                    <div v-else style="color: var(--text-muted); font-size: 13px;">无</div>
                  </div>
                  <div>
                    <div class="case-section-title">测试步骤</div>
                    <ol>
                      <li v-for="step in c.steps" :key="step">{{ step }}</li>
                    </ol>
                  </div>
                  <div>
                    <div class="case-section-title">预期结果</div>
                    <ul>
                      <li v-for="res in c.expected_results" :key="res">{{ res }}</li>
                    </ul>
                  </div>
                </div>
                <div class="case-footer">
                  <span class="tag-outline" v-for="tag in c.coverage_tags" :key="tag">{{ tag }}</span>
                  <span class="tag-outline" style="border-color: var(--primary-color); color: var(--primary-color);">来自: {{ c.source_test_point_id }}</span>
                </div>
              </div>

              <!-- Validation Issues inline -->
              <div v-if="generation.validation_issues.length > 0" style="margin-top: 24px;">
                <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 12px; color: var(--danger-color);">校验问题 ({{ generation.validation_issues.length }})</h3>
                <div class="issue-list">
                  <div class="issue-card" v-for="issue in generation.validation_issues" :key="issue.message">
                    <div class="cq-title">类型: {{ issue.issue_type }}</div>
                    <div style="margin-top: 8px; font-size: 14px;">{{ issue.message }}</div>
                  </div>
                </div>
              </div>

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <button
                  class="btn btn-primary"
                  :disabled="generatingIntegration"
                  @click="generateIntegrationTests"
                >
                  {{ generatingIntegration ? '正在生成...' : '生成流程联动测试' }}
                </button>
              </div>
            </div>

            <!-- Step 5: Integration Tests -->
            <div class="panel" v-if="viewStep === 5 && integrationResult">
              <div class="panel-header">
                <h2 class="panel-title">流程联动测试</h2>
                <span class="badge badge-info">{{ integrationResult.integration_tests.length }} 个场景</span>
              </div>

              <div class="integration-list">
                <div class="integration-item" v-for="it in integrationResult.integration_tests" :key="it.id">
                  <div class="integration-header">
                    <span class="case-id">{{ it.id }}</span>
                    <span class="case-title">{{ it.title }}</span>
                  </div>
                  <div class="integration-desc">{{ it.description }}</div>
                  <div class="integration-flow-tag">
                    <span class="tag-filled">{{ it.flow }}</span>
                  </div>
                  <div class="integration-body">
                    <div>
                      <div class="case-section-title">前置条件</div>
                      <ul v-if="it.preconditions.length">
                        <li v-for="pre in it.preconditions" :key="pre">{{ pre }}</li>
                      </ul>
                      <div v-else style="color: var(--text-muted); font-size: 13px;">无</div>
                    </div>
                    <div>
                      <div class="case-section-title">执行步骤</div>
                      <ol>
                        <li v-for="step in it.steps" :key="step">{{ step }}</li>
                      </ol>
                    </div>
                    <div>
                      <div class="case-section-title">预期结果</div>
                      <ul>
                        <li v-for="res in it.expected_results" :key="res">{{ res }}</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <button class="btn btn-primary" @click="viewStep = 6">
                  查看用例汇总
                </button>
              </div>
            </div>

            <!-- Step 6: Summary -->
            <div class="panel" v-if="viewStep === 6 && generation && integrationResult">
              <div class="panel-header">
                <h2 class="panel-title">用例汇总</h2>
                <span class="badge badge-success">共 {{ generation.cases.length + integrationResult.integration_tests.length }} 条</span>
              </div>

              <!-- Stats cards -->
              <div class="summary-stats">
                <div class="stat-card">
                  <div class="stat-number">{{ generation.cases.length + integrationResult.integration_tests.length }}</div>
                  <div class="stat-label">用例总数</div>
                </div>
                <div class="stat-card">
                  <div class="stat-number" style="color: var(--primary-color);">{{ generation.cases.length }}</div>
                  <div class="stat-label">功能用例</div>
                </div>
                <div class="stat-card">
                  <div class="stat-number" style="color: var(--info-color);">{{ integrationResult.integration_tests.length }}</div>
                  <div class="stat-label">流程联动</div>
                </div>
                <div class="stat-card" v-if="generation.validation_issues.length > 0">
                  <div class="stat-number" style="color: var(--danger-color);">{{ generation.validation_issues.length }}</div>
                  <div class="stat-label">校验问题</div>
                </div>
              </div>

              <!-- Filter tabs -->
              <div class="summary-filter">
                <button
                  class="filter-btn"
                  :class="{ active: summaryFilter === 'all' }"
                  @click="summaryFilter = 'all'"
                >
                  全部 ({{ generation.cases.length + integrationResult.integration_tests.length }})
                </button>
                <button
                  class="filter-btn"
                  :class="{ active: summaryFilter === 'functional' }"
                  @click="summaryFilter = 'functional'"
                >
                  功能用例 ({{ generation.cases.length }})
                </button>
                <button
                  class="filter-btn"
                  :class="{ active: summaryFilter === 'integration' }"
                  @click="summaryFilter = 'integration'"
                >
                  流程联动 ({{ integrationResult.integration_tests.length }})
                </button>
              </div>

              <!-- Functional Cases -->
              <div v-if="summaryFilter !== 'integration'">
                <div v-if="summaryFilter === 'all'" class="summary-section-title">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                  功能用例
                  <span class="badge badge-gray">{{ generation.cases.length }}</span>
                </div>
                <div class="case-item" v-for="c in generation.cases" :key="c.id">
                  <div class="case-header">
                    <div class="case-id-title">
                      <span class="case-id">{{ c.id }}</span>
                      <span class="case-title">{{ c.title }}</span>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: center;">
                      <span class="badge badge-gray">功能</span>
                      <span class="badge" :class="c.priority === 'P0' ? 'badge-danger' : 'badge-info'">{{ c.priority }}</span>
                    </div>
                  </div>
                  <div class="case-body">
                    <div>
                      <div class="case-section-title">前置条件</div>
                      <ul v-if="c.preconditions.length">
                        <li v-for="pre in c.preconditions" :key="pre">{{ pre }}</li>
                      </ul>
                      <div v-else style="color: var(--text-muted); font-size: 13px;">无</div>
                    </div>
                    <div>
                      <div class="case-section-title">测试步骤</div>
                      <ol>
                        <li v-for="step in c.steps" :key="step">{{ step }}</li>
                      </ol>
                    </div>
                    <div>
                      <div class="case-section-title">预期结果</div>
                      <ul>
                        <li v-for="res in c.expected_results" :key="res">{{ res }}</li>
                      </ul>
                    </div>
                  </div>
                  <div class="case-footer">
                    <span class="tag-outline" v-for="tag in c.coverage_tags" :key="tag">{{ tag }}</span>
                    <span class="tag-outline" style="border-color: var(--primary-color); color: var(--primary-color);">来自: {{ c.source_test_point_id }}</span>
                  </div>
                </div>
              </div>

              <!-- Integration Tests -->
              <div v-if="summaryFilter !== 'functional'">
                <div v-if="summaryFilter === 'all'" class="summary-section-title" style="margin-top: 32px;">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                  流程联动测试
                  <span class="badge badge-gray">{{ integrationResult.integration_tests.length }}</span>
                </div>
                <div class="integration-list">
                  <div class="integration-item" v-for="it in integrationResult.integration_tests" :key="it.id">
                    <div class="integration-header">
                      <span class="case-id">{{ it.id }}</span>
                      <span class="case-title">{{ it.title }}</span>
                    </div>
                    <div class="integration-desc">{{ it.description }}</div>
                    <div class="integration-flow-tag">
                      <span class="tag-filled">{{ it.flow }}</span>
                    </div>
                    <div class="integration-body">
                      <div>
                        <div class="case-section-title">前置条件</div>
                        <ul v-if="it.preconditions.length">
                          <li v-for="pre in it.preconditions" :key="pre">{{ pre }}</li>
                        </ul>
                        <div v-else style="color: var(--text-muted); font-size: 13px;">无</div>
                      </div>
                      <div>
                        <div class="case-section-title">执行步骤</div>
                        <ol>
                          <li v-for="step in it.steps" :key="step">{{ step }}</li>
                        </ol>
                      </div>
                      <div>
                        <div class="case-section-title">预期结果</div>
                        <ul>
                          <li v-for="res in it.expected_results" :key="res">{{ res }}</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Validation Issues -->
              <div v-if="generation.validation_issues.length > 0" style="margin-top: 32px;">
                <div class="summary-section-title" style="color: var(--danger-color);">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                  校验问题
                  <span class="badge badge-danger">{{ generation.validation_issues.length }}</span>
                </div>
                <div class="issue-list">
                  <div class="issue-card" v-for="issue in generation.validation_issues" :key="issue.message">
                    <div class="cq-title">类型: {{ issue.issue_type }}</div>
                    <div style="margin-top: 8px; font-size: 14px;">{{ issue.message }}</div>
                  </div>
                </div>
              </div>

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <span class="badge badge-success" style="font-size: 13px; padding: 6px 16px;">全部流程已完成</span>
              </div>
            </div>

          </div> <!-- End Left Column -->

          <!-- RIGHT COLUMN: AI Insights -->
          <div class="workbench-right" v-if="analysis">
            <div class="panel">
              <div class="panel-header" style="margin-bottom: 12px;">
                <h2 class="panel-title">AI 需求洞察</h2>
              </div>

              <div class="insight-group">
                <div class="insight-title">功能目标</div>
                <div class="insight-content">
                  <strong>{{ analysis.summary.title }}</strong>
                  <p style="margin-top: 4px; color: var(--text-muted);">{{ analysis.summary.business_goal }}</p>
                </div>
              </div>

              <div class="insight-group" v-if="analysis.functions.length">
                <div class="insight-title">功能模块</div>
                <div class="insight-tags">
                  <span class="tag-filled" v-for="fn in analysis.functions" :key="fn">{{ fn }}</span>
                </div>
              </div>

              <div class="insight-group" v-if="analysis.flows.length">
                <div class="insight-title">端到端业务流</div>
                <div class="flow-list">
                  <div class="flow-item" v-for="(flow, idx) in analysis.flows" :key="idx">
                    <span class="flow-index">{{ idx + 1 }}</span>
                    <span class="flow-text">{{ flow }}</span>
                  </div>
                </div>
              </div>

              <div class="insight-group" v-if="Object.keys(analysis.module_segments).length">
                <div class="insight-title">模块需求拆分</div>
                <div class="module-segments">
                  <div class="module-segment-item" v-for="(desc, mod) in analysis.module_segments" :key="mod">
                    <div class="module-name">{{ mod }}</div>
                    <div class="module-desc">{{ desc }}</div>
                  </div>
                </div>
              </div>

              <div class="insight-group">
                <div class="insight-title">覆盖维度</div>
                <div class="insight-tags">
                  <span class="tag-outline" v-for="dim in analysis.coverage_dimensions" :key="dim">{{ dim }}</span>
                </div>
              </div>

              <div class="insight-group">
                <div class="insight-title">平台专项关注 ({{ form.platform.toUpperCase() }})</div>
                <div class="insight-tags">
                  <span class="tag-outline" v-for="focus in analysis.summary.platform_focus" :key="focus">{{ focus }}</span>
                </div>
              </div>
            </div>
          </div> <!-- End Right Column -->
        </div> <!-- End Workbench Main -->

      </div>
    </main>
  </div>
</template>
