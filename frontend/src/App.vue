<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import MindMapView from './components/MindMapView.vue'

type Platform = 'web' | 'app' | 'plugin'

interface HistoryRecord {
  id: string
  title: string
  platform: Platform
  project: string
  cases_count: number
  integration_count: number
  timestamp: string
  data: {
    analysis?: AnalyzeResponse
    reviewResult?: ReviewTestPointsResponse
    generation?: GenerateCasesResponse
    integrationResult?: IntegrationTestsResponse
  }
}

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

interface ClarifyResponse {
  platform: Platform
  summary: StructuredSummary
  clarification_questions: ClarificationQuestion[]
  has_blocking_questions: boolean
  round: number
  prompts: Record<string, string>
}

interface GenerateTestPointsResponse {
  platform: Platform
  functions: string[]
  flows: string[]
  module_segments: Record<string, string>
  coverage_dimensions: string[]
  test_points: TestPoint[]
  prompts: Record<string, string>
}

interface TestCase {
  id: string
  title: string
  function_module: string
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
    'AI 澄清问题',
    '测试点审核',
    '用例生成',
  ],
}

const showAdvanced = ref(false)

const meta = ref<MetaResponse>(fallbackMeta)
const loadingMeta = ref(false)
const analyzing = ref(false)
const reviewing = ref(false)
const generating = ref(false)
const generatingIntegration = ref(false)
const generatingTestPoints = ref(false)
const errorMessage = ref('')
const clarifyRound = ref(0)
const accumulatedAnswers = ref<ClarificationAnswer[]>([])
const MAX_CLARIFY_ROUNDS = 3
const uploadingPdf = ref(false)
const pdfFileName = ref('')

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
const summaryViewMode = ref<'list' | 'mindmap'>('list')

const historyExpanded = ref(false)
const historyRecords = ref<HistoryRecord[]>([])
const activeHistoryId = ref<string | null>(null)
const taskActive = ref(false)

const maxReachedStep = computed(() => {
  if (generation.value) return 4
  if (analysis.value?.test_points.length) return 3
  if (generatingTestPoints.value) return 3
  if (analysis.value?.clarification_questions.length) return 2
  if (analyzing.value) return 2
  return 1
})

const stepLabels = ['需求输入', 'AI 澄清问题', '测试点审核', '用例生成']

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

const notesByTestPoint = computed(() => {
  const map: Record<string, ReviewNote[]> = {}
  if (!reviewResult.value) return map
  for (const note of reviewResult.value.review_notes) {
    const tpId = note.target_test_point_id || '__global__'
    if (!map[tpId]) map[tpId] = []
    map[tpId].push(note)
  }
  return map
})

const reviewStats = computed(() => {
  if (!reviewResult.value || !analysis.value) return null
  const origIds = new Set(analysis.value.test_points.map(t => t.id))
  const reviewedIds = new Set(reviewResult.value.reviewed_test_points.map(t => t.id))
  const addedItems = reviewResult.value.reviewed_test_points.filter(t => !origIds.has(t.id))
  const removedItems = analysis.value.test_points.filter(t => !reviewedIds.has(t.id))
  return {
    added: addedItems.length,
    removed: removedItems.length,
    notesCount: reviewResult.value.review_notes.length,
    addedItems,
    removedItems,
    notes: reviewResult.value.review_notes,
  }
})

const addedTestPointIds = computed(() => {
  if (!reviewStats.value) return new Set<string>()
  return new Set(reviewStats.value.addedItems.map(t => t.id))
})

const reviewDetailExpanded = ref(false)

const issuesByCase = computed(() => {
  const map: Record<string, ValidationIssue[]> = {}
  if (!generation.value) return map
  for (const issue of generation.value.validation_issues) {
    const match = issue.message.match(/^(TC[-\d]+\w*)/)
    const caseId = match ? match[1] : '__global__'
    if (!map[caseId]) map[caseId] = []
    map[caseId].push(issue)
  }
  return map
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

const MAX_PDF_SIZE_MB = 20
const handlePdfUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    errorMessage.value = '仅支持 PDF 文件'
    return
  }
  const sizeMB = file.size / 1024 / 1024
  if (sizeMB > MAX_PDF_SIZE_MB) {
    errorMessage.value = `文件过大（${sizeMB.toFixed(1)} MB），最大支持 ${MAX_PDF_SIZE_MB} MB`
    return
  }
  errorMessage.value = ''
  uploadingPdf.value = true
  pdfFileName.value = file.name
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 200000)
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${apiBaseUrl}/api/upload-pdf`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
    clearTimeout(timer)
    if (!response.ok) throw new Error(await extractErrorMessage(response, 'PDF 解析失败'))
    const data = await response.json()
    form.requirementText = data.text
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      errorMessage.value = 'PDF 解析超时，请尝试减少页数后重试'
    } else {
      errorMessage.value = error instanceof Error ? error.message : 'PDF 解析失败'
    }
    pdfFileName.value = ''
  } finally {
    uploadingPdf.value = false
    input.value = ''
  }
}

const startClarify = async () => {
  errorMessage.value = ''
  analyzing.value = true
  clarifyRound.value = 0
  accumulatedAnswers.value = []
  reviewResult.value = null
  generation.value = null
  integrationResult.value = null
  Object.keys(clarificationAnswers).forEach(k => delete clarificationAnswers[k])

  try {
    const result = await callClarifyApi([])
    clarifyRound.value = 1
    analysis.value = {
      platform: result.platform,
      summary: result.summary,
      functions: [],
      flows: [],
      module_segments: {},
      coverage_dimensions: [],
      clarification_questions: result.clarification_questions,
      test_points: [],
      prompts: result.prompts,
    }
    if (result.clarification_questions.length > 0) {
      viewStep.value = 2
    } else {
      await doGenerateTestPoints(result.summary, [])
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '需求解析失败'
  } finally {
    analyzing.value = false
  }
}

const callClarifyApi = async (answers: ClarificationAnswer[]): Promise<ClarifyResponse> => {
  const response = await fetch(`${apiBaseUrl}/api/workflow/clarify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      platform: form.platform,
      project: form.project,
      requirement_text: form.requirementText,
      actors: formatLines(form.actors),
      preconditions: formatLines(form.preconditions),
      business_rules: formatLines(form.businessRules),
      clarification_answers: answers,
    }),
  })
  if (!response.ok) throw new Error(await extractErrorMessage(response, '需求解析失败，请检查后端服务'))
  return (await response.json()) as ClarifyResponse
}

const submitClarifyAnswers = async () => {
  if (!analysis.value) return
  errorMessage.value = ''
  analyzing.value = true

  // 合并本轮答案到累积列表
  const existingIds = new Set(accumulatedAnswers.value.map(a => a.question_id))
  const newAnswers: ClarificationAnswer[] = analysis.value.clarification_questions
    .filter(q => clarificationAnswers[q.id]?.trim())
    .map(q => ({ question_id: q.id, question: q.question, answer: clarificationAnswers[q.id].trim() }))
    .filter(a => !existingIds.has(a.question_id))
  const merged = [...accumulatedAnswers.value, ...newAnswers]
  accumulatedAnswers.value = merged

  try {
    if (clarifyRound.value >= MAX_CLARIFY_ROUNDS) {
      await doGenerateTestPoints(analysis.value.summary, merged)
      return
    }
    const result = await callClarifyApi(merged)
    clarifyRound.value++
    analysis.value = { ...analysis.value, summary: result.summary, clarification_questions: result.clarification_questions }

    if (result.clarification_questions.length > 0 && clarifyRound.value < MAX_CLARIFY_ROUNDS) {
      Object.keys(clarificationAnswers).forEach(k => delete clarificationAnswers[k])
      viewStep.value = 2
    } else {
      await doGenerateTestPoints(result.summary, merged)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '需求澄清失败'
  } finally {
    analyzing.value = false
  }
}

const skipClarification = async () => {
  if (!analysis.value) return
  errorMessage.value = ''
  try {
    await doGenerateTestPoints(analysis.value.summary, accumulatedAnswers.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试点生成失败'
  }
}

const doGenerateTestPoints = async (summary: StructuredSummary, answers: ClarificationAnswer[]) => {
  generatingTestPoints.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/generate-test-points`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: form.platform, summary, clarification_answers: answers }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试点生成失败'))
    const data = (await response.json()) as GenerateTestPointsResponse
    analysis.value = {
      ...analysis.value!,
      functions: data.functions,
      flows: data.flows,
      module_segments: data.module_segments,
      coverage_dimensions: data.coverage_dimensions,
      test_points: data.test_points,
    }
    selectedTestPointIds.value = data.test_points.map(t => t.id)
    viewStep.value = 3
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试点生成失败'
  } finally {
    generatingTestPoints.value = false
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
        clarification_answers: accumulatedAnswers.value,
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

const generateAllCases = async () => {
  if (!analysis.value || selectedTestPoints.value.length === 0) return
  errorMessage.value = ''
  generating.value = true
  integrationResult.value = null
  generation.value = null

  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/generate-cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: analysis.value.summary,
        functions: analysis.value.functions,
        module_segments: analysis.value.module_segments,
        selected_test_points: selectedTestPoints.value,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试用例生成失败'))
    generation.value = (await response.json()) as GenerateCasesResponse
    viewStep.value = 4
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试用例生成失败'
    generating.value = false
    return
  }
  generating.value = false

  const points = reviewResult.value?.reviewed_test_points || analysis.value.test_points
  if (analysis.value.flows.length === 0) {
    await saveCurrentToHistory()
    return
  }

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
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '流程联动测试生成失败'
  } finally {
    generatingIntegration.value = false
    await saveCurrentToHistory()
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

const loadHistory = async () => {
  try {
    const res = await fetch(`${apiBaseUrl}/api/history`)
    if (res.ok) historyRecords.value = await res.json()
  } catch { /* ignore */ }
}

const saveCurrentToHistory = async () => {
  if (!analysis.value || !generation.value) return
  const id = `hist_${Date.now()}`
  const record: HistoryRecord = {
    id,
    title: analysis.value.summary.title,
    platform: form.platform,
    project: form.project,
    cases_count: generation.value.cases.length,
    integration_count: integrationResult.value?.integration_tests.length || 0,
    timestamp: new Date().toISOString(),
    data: {
      analysis: analysis.value,
      reviewResult: reviewResult.value || undefined,
      generation: generation.value,
      integrationResult: integrationResult.value || undefined,
    },
  }
  try {
    const res = await fetch(`${apiBaseUrl}/api/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record),
    })
    if (res.ok) {
      activeHistoryId.value = id
      await loadHistory()
    }
  } catch { /* ignore */ }
}

const loadHistoryRecord = (record: HistoryRecord) => {
  taskActive.value = true
  activeHistoryId.value = record.id
  form.platform = record.platform
  form.project = record.project
  analysis.value = record.data.analysis || null
  reviewResult.value = record.data.reviewResult || null
  generation.value = record.data.generation || null
  integrationResult.value = record.data.integrationResult || null
  if (record.data.analysis) {
    selectedTestPointIds.value = (
      record.data.reviewResult?.reviewed_test_points ||
      record.data.analysis.test_points
    ).map((t) => t.id)
  }
  if (generation.value) viewStep.value = 4
  else viewStep.value = 1
}

const deleteHistoryRecord = async (id: string) => {
  try {
    await fetch(`${apiBaseUrl}/api/history/${id}`, { method: 'DELETE' })
    if (activeHistoryId.value === id) {
      activeHistoryId.value = null
      taskActive.value = false
    }
    await loadHistory()
  } catch { /* ignore */ }
}

const formatHistoryTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => { loadMeta(); loadHistory() })
</script>

<template>
  <div class="app-wrapper">
    <!-- Sidebar -->
    <aside class="app-sidebar">
      <div class="sidebar-logo" @click="taskActive = false" style="cursor:pointer;" title="返回首页">
        <svg class="nav-icon" style="margin-right: 8px; color: var(--primary-color);" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
        <span>AI Test</span>
        <span
          class="status-dot"
          :class="loadingMeta ? 'offline' : 'online'"
          :title="loadingMeta ? '服务连接中...' : '服务已就绪'"
        ></span>
      </div>
      <nav class="sidebar-nav">
        <button class="nav-item active" @click="historyExpanded = !historyExpanded">
          <svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
          <span>生成测试用例</span>
          <svg
            class="nav-arrow"
            :class="{ expanded: historyExpanded }"
            width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"
          ><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        </button>

        <div class="nav-dropdown" v-if="historyExpanded">
          <a href="#" class="dropdown-new" @click.prevent="taskActive = true; activeHistoryId = null; viewStep = 1; analysis = null; reviewResult = null; generation = null; integrationResult = null; form.requirementText = ''">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            新建任务
          </a>

          <div v-if="historyRecords.length" class="dropdown-divider"></div>
          <div v-if="historyRecords.length" class="dropdown-label">历史记录</div>

          <div v-if="historyRecords.length === 0" class="dropdown-empty">暂无记录</div>

          <div
            v-for="record in historyRecords"
            :key="record.id"
            class="dropdown-history-item"
            :class="{ active: activeHistoryId === record.id }"
            @click="loadHistoryRecord(record)"
          >
            <div class="dropdown-history-content">
              <div class="dropdown-history-title">{{ record.title }}</div>
              <div class="dropdown-history-meta">
                <span>{{ record.platform.toUpperCase() }}</span>
                <span>{{ record.cases_count }}条</span>
                <span>{{ formatHistoryTime(record.timestamp) }}</span>
              </div>
            </div>
            <button class="dropdown-history-delete" @click.stop="deleteHistoryRecord(record.id)" title="删除">&times;</button>
          </div>
        </div>
      </nav>
    </aside>

    <main class="app-main">

      <!-- Welcome Page -->
      <div v-if="!taskActive" class="welcome-page">
        <div class="welcome-content">
          <!-- Hero Section -->
          <div class="welcome-hero">
            <div class="welcome-hero-badge">Powered by LLM</div>
            <h1 class="welcome-title">AI 智能测试用例工作台</h1>
            <p class="welcome-desc">从需求文档到结构化测试用例，AI 全程辅助：多轮澄清消除歧义、智能提取测试点、自动生成功能用例与集成测试。</p>
            <button class="btn btn-primary welcome-start" @click="taskActive = true; historyExpanded = true; viewStep = 1">
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
              新建测试任务
            </button>
          </div>

          <!-- Workflow Steps -->
          <div class="welcome-workflow">
            <div class="welcome-section-label">工作流程</div>
            <div class="welcome-steps">
              <div class="welcome-step" v-for="(s, i) in [
                { title: '需求输入', desc: '粘贴 PRD 或需求描述，选择平台类型' },
                { title: 'AI 多轮澄清', desc: '识别歧义与缺失，多轮问答消除盲区' },
                { title: '测试点审核', desc: 'AI 提取测试点，人工勾选确认' },
                { title: '用例生成', desc: '功能用例 + 集成测试 + 思维导图' },
              ]" :key="i">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">{{ i + 1 }}</div>
                  <div class="welcome-step-line" v-if="i < 3"></div>
                </div>
                <div class="welcome-step-title">{{ s.title }}</div>
                <div class="welcome-step-desc">{{ s.desc }}</div>
              </div>
            </div>
          </div>

          <!-- Capability Cards -->
          <div class="welcome-capabilities">
            <div class="welcome-section-label">核心能力</div>
            <div class="welcome-cap-grid">
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background:#EEF2FF;color:#6366F1;">
                  <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                </div>
                <div class="welcome-cap-title">多轮需求澄清</div>
                <div class="welcome-cap-desc">最多 3 轮 AI 追问，自动识别阻塞性问题，确保需求理解完整再生成测试点</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background:#FEF3C7;color:#D97706;">
                  <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
                </div>
                <div class="welcome-cap-title">测试点人工审核</div>
                <div class="welcome-cap-desc">AI 辅助审核标注新增/移除/意见，支持勾选过滤，人工掌控最终测试范围</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background:#ECFDF5;color:#059669;">
                  <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                </div>
                <div class="welcome-cap-title">集成测试自动生成</div>
                <div class="welcome-cap-desc">识别端到端业务流，自动生成跨模块流程联动测试场景</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background:#FDF2F8;color:#DB2777;">
                  <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                </div>
                <div class="welcome-cap-title">质量校验 + 思维导图</div>
                <div class="welcome-cap-desc">自动检测覆盖遗漏与重复，生成测试设计思维导图可一键复制到飞书</div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div v-else class="workbench-layout">
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
                <div class="form-label-row">
                  <label class="form-label" style="margin-bottom:0;">
                    需求描述
                    <span class="badge badge-gray">必填</span>
                  </label>
                  <label class="pdf-upload-btn" :class="{ uploading: uploadingPdf }">
                    <input type="file" accept=".pdf" hidden @change="handlePdfUpload" :disabled="uploadingPdf" />
                    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                    {{ uploadingPdf ? '解析中...' : '上传 PDF' }}
                  </label>
                </div>
                <div v-if="pdfFileName && !uploadingPdf" class="pdf-file-tag">
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                  {{ pdfFileName }}
                  <button class="pdf-file-remove" @click="pdfFileName = ''" title="清除">&times;</button>
                </div>
                <textarea
                  v-model="form.requirementText"
                  class="form-control"
                  rows="6"
                  placeholder="在此粘贴需求文档、用户故事或 PRD 内容，或上传 PDF 自动提取..."
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
                  :disabled="analyzing || generatingTestPoints || !form.requirementText.trim()"
                  @click="startClarify"
                >
                  {{ (analyzing || generatingTestPoints) ? '正在深度解析...' : (analysis ? '重新解析需求' : '开始智能解析') }}
                </button>
              </div>
            </div>

            <!-- Step 2: Clarification Questions -->
            <div class="panel" v-if="viewStep === 2 && analysis && analysis.clarification_questions.length > 0">
              <div class="panel-header">
                <h2 class="panel-title">AI 澄清问题</h2>
                <span class="badge badge-info" style="font-size:12px;">第 {{ clarifyRound }} 轮 / 最多 {{ MAX_CLARIFY_ROUNDS }} 轮</span>
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
                <div style="display:flex;gap:8px;">
                  <button
                    class="btn btn-back"
                    :disabled="analyzing || generatingTestPoints"
                    @click="skipClarification"
                  >
                    {{ generatingTestPoints ? '生成中...' : '跳过，直接生成测试点' }}
                  </button>
                  <button
                    class="btn btn-primary"
                    :disabled="analyzing || generatingTestPoints || hasUnansweredBlocking"
                    @click="submitClarifyAnswers"
                  >
                    {{ analyzing ? '处理中...' : (clarifyRound >= MAX_CLARIFY_ROUNDS ? '提交并生成测试点' : '提交答案') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Step 3: Test Points Review -->
            <div class="panel" v-if="viewStep === 3 && analysis">
              <div class="panel-header">
                <h2 class="panel-title">测试点审核</h2>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span class="badge badge-gray">{{ displayedTestPoints.length }} 项</span>
                  <button
                    class="btn btn-outline-primary btn-sm"
                    :disabled="reviewing"
                    @click="reviewTestPoints"
                  >
                    {{ reviewing ? 'AI 审核中...' : (reviewResult ? '重新 AI 审核' : 'AI 辅助审核') }}
                  </button>
                </div>
              </div>

              <!-- 审核结果摘要 -->
              <div v-if="reviewResult && reviewStats" class="review-summary-panel">
                <div class="review-summary-bar" @click="reviewDetailExpanded = !reviewDetailExpanded" style="cursor:pointer;">
                  <span class="review-summary-label">AI 审核完成</span>
                  <span v-if="reviewStats.added" class="badge badge-success">新增 {{ reviewStats.added }} 项</span>
                  <span v-if="reviewStats.removed" class="badge badge-danger">移除 {{ reviewStats.removed }} 项</span>
                  <span v-if="reviewStats.notesCount" class="badge badge-warning">{{ reviewStats.notesCount }} 条审核意见</span>
                  <span v-if="!reviewStats.added && !reviewStats.removed && !reviewStats.notesCount" class="badge badge-info">无调整</span>
                  <span class="review-expand-icon" :class="{ expanded: reviewDetailExpanded }">▶</span>
                </div>

                <div v-if="reviewDetailExpanded" class="review-detail-section">
                  <!-- 新增的测试点 -->
                  <div v-if="reviewStats.addedItems.length" class="review-detail-group">
                    <div class="review-detail-group-title review-added-title">新增的测试点</div>
                    <div v-for="tp in reviewStats.addedItems" :key="tp.id" class="review-detail-item review-added-item">
                      <span class="review-detail-item-title">{{ tp.title }}</span>
                      <span class="review-detail-item-desc">{{ tp.description }}</span>
                      <span class="review-detail-item-meta">分类: {{ tp.category }} · 来源: {{ tp.source }}</span>
                    </div>
                  </div>

                  <!-- 移除的测试点 -->
                  <div v-if="reviewStats.removedItems.length" class="review-detail-group">
                    <div class="review-detail-group-title review-removed-title">移除的测试点</div>
                    <div v-for="tp in reviewStats.removedItems" :key="tp.id" class="review-detail-item review-removed-item">
                      <span class="review-detail-item-title">{{ tp.title }}</span>
                      <span class="review-detail-item-desc">{{ tp.description }}</span>
                      <span class="review-detail-item-meta">分类: {{ tp.category }} · 来源: {{ tp.source }}</span>
                    </div>
                  </div>

                  <!-- 全部审核意见 -->
                  <div v-if="reviewStats.notes.length" class="review-detail-group">
                    <div class="review-detail-group-title review-notes-title">审核意见</div>
                    <div v-for="note in reviewStats.notes" :key="note.message" class="review-detail-note-item" :class="'severity-' + note.severity">
                      <span class="review-detail-note-type">[{{ note.note_type }}]</span>
                      <span class="review-detail-note-msg">{{ note.message }}</span>
                      <span v-if="note.target_test_point_id" class="review-detail-note-target">关联: {{ note.target_test_point_id }}</span>
                    </div>
                  </div>
                </div>
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
                      <span v-if="addedTestPointIds.has(tp.id)" class="badge badge-success">新增</span>
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
                    <!-- 关联到该测试点的审核意见 -->
                    <div v-if="notesByTestPoint[tp.id]?.length" class="tp-review-notes">
                      <div v-for="note in notesByTestPoint[tp.id]" :key="note.message" class="tp-review-note-tag" :class="'severity-' + note.severity">
                        <span class="tp-review-note-type">[{{ note.note_type }}]</span>
                        {{ note.message }}
                      </div>
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
                  @click="generateAllCases"
                >
                  {{ generating ? '正在生成用例...' : '基于选中项生成用例' }}
                </button>
              </div>
            </div>

            <!-- Step 4: Results (functional + integration in one view) -->
            <div class="panel" v-if="viewStep === 4 && generation">
              <div class="panel-header">
                <h2 class="panel-title">用例生成</h2>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span class="badge badge-success">
                    {{ generation.cases.length + (integrationResult?.integration_tests.length || 0) }} 条
                    <template v-if="generatingIntegration"> (联动生成中...)</template>
                  </span>
                  <div class="view-toggle" v-if="!generatingIntegration">
                    <button class="view-toggle-btn" :class="{ active: summaryViewMode === 'list' }" @click="summaryViewMode = 'list'" title="列表视图">
                      <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                    </button>
                    <button class="view-toggle-btn" :class="{ active: summaryViewMode === 'mindmap' }" @click="summaryViewMode = 'mindmap'" title="思维导图">
                      <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path></svg>
                    </button>
                  </div>
                </div>
              </div>

              <!-- MindMap View (only when integration is done or no flows) -->
              <MindMapView
                v-if="summaryViewMode === 'mindmap' && !generatingIntegration"
                :api-base-url="apiBaseUrl"
                :platform="form.platform"
                :summary="analysis?.summary || {}"
                :functions="analysis?.functions || []"
                :test-points="displayedTestPoints"
                :cases="generation.cases"
                :integration-tests="integrationResult?.integration_tests || []"
              />

              <!-- List View -->
              <template v-if="summaryViewMode === 'list'">

              <!-- Stats cards -->
              <div class="summary-stats">
                <div class="stat-card">
                  <div class="stat-number">{{ generation.cases.length + (integrationResult?.integration_tests.length || 0) }}</div>
                  <div class="stat-label">用例总数</div>
                </div>
                <div class="stat-card">
                  <div class="stat-number" style="color: var(--primary-color);">{{ generation.cases.length }}</div>
                  <div class="stat-label">功能用例</div>
                </div>
                <div class="stat-card">
                  <div class="stat-number" style="color: var(--info-color);">{{ integrationResult?.integration_tests.length || 0 }}</div>
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
                  全部 ({{ generation.cases.length + (integrationResult?.integration_tests.length || 0) }})
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
                  :disabled="generatingIntegration"
                >
                  流程联动 ({{ integrationResult?.integration_tests.length || 0 }})
                  <template v-if="generatingIntegration"> ...</template>
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
                      <span class="tag-filled" v-if="c.function_module">{{ c.function_module }}</span>
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
                  <div v-if="issuesByCase[c.id]?.length" class="case-issues">
                    <span
                      v-for="(issue, idx) in issuesByCase[c.id]"
                      :key="idx"
                      class="case-issue-tag"
                      :class="issue.severity === 'high' ? 'issue-high' : 'issue-medium'"
                      :title="issue.message"
                    >
                      <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                      {{ issue.issue_type }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Integration Tests -->
              <div v-if="summaryFilter !== 'functional'">
                <!-- Loading state -->
                <div v-if="generatingIntegration" class="integration-loading-banner">
                  <div class="mindmap-spinner" style="width: 20px; height: 20px; border-width: 2px;"></div>
                  <span>正在生成流程联动测试用例...</span>
                </div>

                <template v-else-if="integrationResult && integrationResult.integration_tests.length > 0">
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
                </template>

                <div v-else-if="!generatingIntegration && analysis && analysis.flows.length === 0" class="integration-loading-banner" style="color: var(--text-muted);">
                  未识别到端到端业务流，无流程联动测试
                </div>
              </div>

              </template><!-- End List View -->

              <div class="step-actions">
                <button class="btn btn-back" @click="goBack">
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  返回上一步
                </button>
                <span v-if="generatingIntegration" class="badge badge-info" style="font-size: 13px; padding: 6px 16px;">流程联动测试生成中...</span>
                <span v-else class="badge badge-success" style="font-size: 13px; padding: 6px 16px;">全部流程已完成</span>
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
