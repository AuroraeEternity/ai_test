<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

type Platform = 'web' | 'app'

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

interface MetaResponse {
  platforms: PlatformOption[]
  workflow_steps: string[]
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const fallbackMeta: MetaResponse = {
  platforms: [
    {
      label: 'Web',
      value: 'web',
      description: '适合后台、官网、管理端、表单系统等页面型产品',
    },
    {
      label: 'App',
      value: 'app',
      description: '适合 iOS / Android 原生或混合应用场景',
    },
  ],
  workflow_steps: [
    '选择平台',
    '输入需求',
    'AI 解析需求',
    '确认歧义问题',
    '审核测试点',
    '生成测试用例',
  ],
}

const meta = ref<MetaResponse>(fallbackMeta)
const loadingMeta = ref(false)
const analyzing = ref(false)
const reviewing = ref(false)
const generating = ref(false)
const errorMessage = ref('')

const form = reactive({
  platform: 'web' as Platform,
  requirementText: '',
  actors: '',
  preconditions: '',
  businessRules: '',
})

const analysis = ref<AnalyzeResponse | null>(null)
const reviewResult = ref<ReviewTestPointsResponse | null>(null)
const generation = ref<GenerateCasesResponse | null>(null)
const selectedTestPointIds = ref<string[]>([])
const clarificationAnswers = reactive<Record<string, string>>({})

const currentStep = computed(() => {
  if (generation.value) return 6
  if (reviewResult.value) return 5
  if (analysis.value) return 4
  return 2
})

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
  reviewResult.value = null
  generation.value = null
  analyzing.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        requirement_text: form.requirementText,
        actors: formatLines(form.actors),
        preconditions: formatLines(form.preconditions),
        business_rules: formatLines(form.businessRules),
        clarification_answers: clarificationAnswerList.value,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '需求解析失败，请检查后端服务是否启动'))
    const data = (await response.json()) as AnalyzeResponse
    analysis.value = data
    selectedTestPointIds.value = data.test_points.map((item) => item.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '需求解析失败'
  } finally {
    analyzing.value = false
  }
}

const reviewTestPoints = async () => {
  if (!analysis.value) return
  errorMessage.value = ''
  generation.value = null
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
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试用例生成失败，请检查后端服务是否启动'))
    generation.value = (await response.json()) as GenerateCasesResponse
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试用例生成失败'
  } finally {
    generating.value = false
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
  <div class="page-shell">
    <header class="hero-card">
      <div>
        <p class="eyebrow">AI 测试平台</p>
        <h1>功能测试用例生成工作台</h1>
        <p class="hero-text">
          先选平台，再解析需求，确认测试点后输出结构化测试用例。当前版本聚焦 `Web` / `App`
          的功能测试场景。
        </p>
      </div>
      <div class="hero-side">
        <div class="metric-card">
          <span>当前流程</span>
          <strong>{{ meta.workflow_steps[currentStep - 1] || '输入需求' }}</strong>
        </div>
        <div class="metric-card">
          <span>平台数</span>
          <strong>{{ meta.platforms.length }}</strong>
        </div>
      </div>
    </header>

    <section class="step-strip">
      <div
        v-for="(step, index) in meta.workflow_steps"
        :key="step"
        class="step-item"
        :class="{ active: currentStep >= index + 1 }"
      >
        <span>{{ index + 1 }}</span>
        <strong>{{ step }}</strong>
      </div>
    </section>

    <section class="workspace-grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <p class="panel-title">1. 选择平台并输入需求</p>
            <p class="panel-subtitle">平台类型会决定平台专项测试点的生成策略。</p>
          </div>
          <span class="status-badge muted" v-if="loadingMeta">加载中</span>
        </div>

        <div class="platform-grid">
          <button
            v-for="platform in meta.platforms"
            :key="platform.value"
            class="platform-card"
            :class="{ selected: form.platform === platform.value }"
            @click="form.platform = platform.value"
          >
            <strong>{{ platform.label }}</strong>
            <span>{{ platform.description }}</span>
          </button>
        </div>

        <label class="field">
          <span>需求描述</span>
          <textarea
            v-model="form.requirementText"
            rows="7"
            placeholder="请输入 PRD、用户故事或场景描述"
          />
        </label>

        <div class="field-row">
          <label class="field">
            <span>角色信息</span>
            <input v-model="form.actors" placeholder="多个角色可用逗号分隔" />
          </label>
          <label class="field">
            <span>前置条件</span>
            <input v-model="form.preconditions" placeholder="多个条件可用逗号分隔" />
          </label>
        </div>

        <label class="field">
          <span>业务规则补充</span>
          <textarea
            v-model="form.businessRules"
            rows="4"
            placeholder="每行一条业务规则，例如：手机号必填且唯一"
          />
        </label>

        <div class="action-row">
          <button class="primary-button" :disabled="analyzing" @click="analyzeRequirement">
            {{ analyzing ? '正在解析需求...' : '开始解析需求' }}
          </button>
        </div>
      </div>

      <div class="panel panel-soft">
        <div class="panel-header">
          <div>
            <p class="panel-title">流程说明</p>
            <p class="panel-subtitle">先产出测试点，再生成用例，避免直接黑盒生成。</p>
          </div>
        </div>
        <ul class="timeline-list">
          <li v-for="step in meta.workflow_steps" :key="step">
            <span class="timeline-dot" />
            <div>
              <strong>{{ step }}</strong>
            </div>
          </li>
        </ul>
        <div class="tip-box">
          <p>建议输入内容：</p>
          <ul>
            <li>功能主流程和异常流程</li>
            <li>角色差异、状态流转、页面反馈</li>
            <li>与平台相关的重点关注点</li>
          </ul>
        </div>
      </div>
    </section>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

    <section v-if="analysis" class="result-section">
      <div class="section-header">
        <div>
          <h2>2. AI 解析结果与测试点确认</h2>
          <p>先确认 AI 对需求的理解，再决定哪些测试点进入生成阶段。</p>
        </div>
        <div class="section-actions">
          <button class="ghost-button" @click="selectAllTestPoints">全选</button>
          <button class="ghost-button" @click="clearSelection">清空</button>
        </div>
      </div>

      <div class="summary-grid">
        <article class="summary-card">
          <span>功能标题</span>
          <strong>{{ analysis.summary.title }}</strong>
          <p>{{ analysis.summary.business_goal }}</p>
        </article>
        <article class="summary-card">
          <span>角色</span>
          <strong>{{ analysis.summary.actors.join(' / ') }}</strong>
          <p>前置条件：{{ analysis.summary.preconditions.join('；') }}</p>
        </article>
        <article class="summary-card">
          <span>平台关注点</span>
          <strong>{{ form.platform.toUpperCase() }}</strong>
          <p>{{ analysis.summary.platform_focus.join('；') }}</p>
        </article>
      </div>

      <div class="result-grid">
        <div class="panel">
          <div class="panel-header">
            <div>
              <p class="panel-title">待确认问题</p>
              <p class="panel-subtitle">先补充这些答案，再进入测试点审核阶段。</p>
            </div>
          </div>
          <div v-if="analysis.clarification_questions.length" class="question-list">
            <article
              v-for="question in analysis.clarification_questions"
              :key="question.id"
              class="question-item"
            >
              <strong>{{ question.question }}</strong>
              <p>{{ question.reason }}</p>
              <textarea
                v-model="clarificationAnswers[question.id]"
                class="inline-textarea"
                rows="3"
                placeholder="请输入该问题的补充答案，补充后可重新解析需求"
              />
            </article>
          </div>
          <p v-else class="empty-state">当前需求信息较完整，没有识别到阻塞性问题。</p>
          <div class="action-row top-gap" v-if="analysis.clarification_questions.length">
            <button class="ghost-button" :disabled="analyzing" @click="analyzeRequirement">
              {{ analyzing ? '正在重新解析...' : '带着澄清答案重新解析' }}
            </button>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <p class="panel-title">{{ reviewResult ? '审核后测试点' : '原始测试点清单' }}</p>
              <p class="panel-subtitle">
                已选 {{ selectedCount }} 个测试点，{{ reviewResult ? '可直接进入用例生成' : '建议先审核后再生成用例' }}。
              </p>
            </div>
            <span class="status-badge">{{ analysis.coverage_dimensions.length }} 个覆盖维度</span>
          </div>

          <div v-if="reviewResult?.review_notes.length" class="review-note-box">
            <p class="list-title">审核说明</p>
            <div class="question-list compact-list">
              <article
                v-for="note in reviewResult.review_notes"
                :key="`${note.note_type}-${note.message}`"
                class="question-item compact-item"
              >
                <strong>{{ note.note_type }}</strong>
                <p>{{ note.message }}</p>
              </article>
            </div>
          </div>

          <div class="test-point-list">
            <label
              v-for="testPoint in displayedTestPoints"
              :key="testPoint.id"
              class="test-point-item"
              :class="{ checked: selectedTestPointIds.includes(testPoint.id) }"
            >
              <input
                :checked="selectedTestPointIds.includes(testPoint.id)"
                type="checkbox"
                @change="toggleTestPoint(testPoint.id)"
              />
              <div>
                <div class="test-point-header">
                  <strong>{{ testPoint.title }}</strong>
                  <span
                    class="status-badge"
                    :class="{ warning: testPoint.platform_specific }"
                  >
                    {{ testPoint.platform_specific ? '平台专项' : testPoint.source }}
                  </span>
                </div>
                <p>{{ testPoint.description }}</p>
              </div>
            </label>
          </div>

          <div class="action-row">
            <button class="ghost-button" :disabled="reviewing" @click="reviewTestPoints">
              {{ reviewing ? '正在审核测试点...' : reviewResult ? '重新审核测试点' : '审核测试点' }}
            </button>
            <button
              class="primary-button"
              :disabled="generating || selectedCount === 0 || !reviewResult"
              @click="generateCases"
            >
              {{ generating ? '正在生成测试用例...' : '基于审核后测试点生成用例' }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-if="generation" class="result-section">
      <div class="section-header">
        <div>
          <h2>3. 测试用例结果</h2>
          <p>当前结果为结构化功能测试用例，可继续扩展导出、编辑和审批能力。</p>
        </div>
        <span class="status-badge success">{{ generation.cases.length }} 条用例</span>
      </div>

      <div class="case-list">
        <article v-for="item in generation.cases" :key="item.id" class="case-card">
          <div class="case-card-header">
            <div>
              <span class="case-id">{{ item.id }}</span>
              <h3>{{ item.title }}</h3>
            </div>
            <div class="case-meta">
              <span class="status-badge">{{ item.priority }}</span>
              <span class="status-badge muted">置信度 {{ Math.round(item.confidence * 100) }}%</span>
            </div>
          </div>

          <div class="case-columns">
            <div>
              <p class="list-title">前置条件</p>
              <ul>
                <li v-for="condition in item.preconditions" :key="condition">{{ condition }}</li>
              </ul>
            </div>
            <div>
              <p class="list-title">测试步骤</p>
              <ol>
                <li v-for="step in item.steps" :key="step">{{ step }}</li>
              </ol>
            </div>
            <div>
              <p class="list-title">预期结果</p>
              <ul>
                <li v-for="result in item.expected_results" :key="result">{{ result }}</li>
              </ul>
            </div>
          </div>

          <div class="tag-row">
            <span v-for="tag in item.coverage_tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </article>
      </div>

      <div class="result-grid">
        <div class="panel">
          <div class="panel-header">
            <div>
              <p class="panel-title">自动校验结果</p>
              <p class="panel-subtitle">当前用于检查重复、可执行性和结构完整性。</p>
            </div>
          </div>
          <div v-if="generation.validation_issues.length" class="question-list">
            <article
              v-for="issue in generation.validation_issues"
              :key="issue.message"
              class="question-item"
            >
              <strong>{{ issue.issue_type }}</strong>
              <p>{{ issue.message }}</p>
            </article>
          </div>
          <p v-else class="empty-state">未发现明显重复或结构化问题。</p>
        </div>
      </div>
    </section>
  </div>
</template>
