<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import CaseSuiteStep from './components/CaseSuiteStep.vue'
import HistorySidebar from './components/HistorySidebar.vue'
import RequirementInputStep from './components/RequirementInputStep.vue'
import SummaryConfirmStep from './components/SummaryConfirmStep.vue'
import TestDesignStep from './components/TestDesignStep.vue'
import type {
  ClarificationAnswer,
  ClarifyResponse,
  GenerateCasesResponse,
  GenerateTestPointsResponse,
  HistoryRecord,
  HistoryStage,
  MetaResponse,
  ReviewTestPointsResponse,
  StructuredSummary,
  TaskFormState,
  TestPoint,
} from './types/workflow'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const fallbackMeta: MetaResponse = {
  platforms: [
    { label: 'Web', value: 'web', description: '后台、官网、表单' },
    { label: 'App', value: 'app', description: 'iOS / Android 客户端' },
    { label: '插件', value: 'plugin', description: '浏览器插件、IDE 扩展等' },
  ],
  projects: [{ label: 'Solvely', value: 'solvely' }],
  workflow_steps: ['需求输入', '摘要确认', '测试设计', '用例与回归资产'],
}

const meta = ref<MetaResponse>(fallbackMeta)
const loadingMeta = ref(false)
const clarifying = ref(false)
const refiningSummary = ref(false)
const generatingDesign = ref(false)
const reviewing = ref(false)
const generatingCases = ref(false)
const uploadingPdf = ref(false)
const pdfFileName = ref('')
const errorMessage = ref('')
const currentStep = ref(1)
const historyRecords = ref<HistoryRecord[]>([])
const activeHistoryId = ref<string | null>(null)
const taskActive = ref(false)
const moduleView = ref<string | null>(null)

const form = reactive<TaskFormState>({
  platform: 'web',
  project: '',
  requirementText: '',
  actors: '',
  preconditions: '',
  businessRules: '',
})

const summaryDraft = ref<StructuredSummary | null>(null)
const clarifyResult = ref<ClarifyResponse | null>(null)
const designResult = ref<GenerateTestPointsResponse | null>(null)
const reviewResult = ref<ReviewTestPointsResponse | null>(null)
const caseSuite = ref<GenerateCasesResponse | null>(null)
const selectedIds = ref<string[]>([])
const clarificationDraftAnswers = reactive<Record<string, string>>({})

const stepLabels = ['需求输入', '摘要确认', '测试设计', '用例与回归资产']

const maxReachedStep = computed(() => {
  if (caseSuite.value) return 4
  if (designResult.value) return 3
  if (summaryDraft.value) return 2
  return 1
})

const displayedPoints = computed(() =>
  reviewResult.value?.reviewed_test_points.length
    ? reviewResult.value.reviewed_test_points
    : designResult.value?.test_points || [],
)

const selectedPoints = computed(() =>
  displayedPoints.value.filter(point => selectedIds.value.includes(point.id)),
)

const hasUnansweredBlocking = computed(() =>
  (clarifyResult.value?.clarification_questions || [])
    .filter(item => item.blocking)
    .some(item => !(clarificationDraftAnswers[item.id] || '').trim()),
)

const serialize = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

const formatLines = (value: string) =>
  value
    .split(/\n|,|，/)
    .map(item => item.trim())
    .filter(Boolean)

const extractErrorMessage = async (response: Response, fallback: string) => {
  try {
    const payload = await response.json()
    return payload.detail || fallback
  } catch {
    return fallback
  }
}

const resetWorkflowState = () => {
  summaryDraft.value = null
  clarifyResult.value = null
  designResult.value = null
  reviewResult.value = null
  caseSuite.value = null
  selectedIds.value = []
  Object.keys(clarificationDraftAnswers).forEach(key => delete clarificationDraftAnswers[key])
  errorMessage.value = ''
  currentStep.value = 1
}

const startNewTask = () => {
  taskActive.value = true
  moduleView.value = null
  activeHistoryId.value = null
  form.requirementText = ''
  form.actors = ''
  form.preconditions = ''
  form.businessRules = ''
  pdfFileName.value = ''
  resetWorkflowState()
}

const goHome = () => {
  taskActive.value = false
  moduleView.value = null
  errorMessage.value = ''
}

const enterWorkflow = () => {
  if (taskActive.value) return
  moduleView.value = 'ai-gen-cases'
}

const startWorkflowFromIntro = () => {
  startNewTask()
  moduleView.value = null
}

const collectClarificationAnswers = (): ClarificationAnswer[] =>
  (clarifyResult.value?.clarification_questions || [])
    .filter(item => (clarificationDraftAnswers[item.id] || '').trim())
    .map(item => ({
      question_id: item.id,
      question: item.question,
      answer: clarificationDraftAnswers[item.id].trim(),
    }))

const callClarifyApi = async (answers: ClarificationAnswer[]) => {
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
  if (!response.ok) throw new Error(await extractErrorMessage(response, '需求解析失败'))
  return (await response.json()) as ClarifyResponse
}

const startClarify = async () => {
  clarifying.value = true
  errorMessage.value = ''
  resetWorkflowState()
  try {
    const result = await callClarifyApi([])
    clarifyResult.value = result
    summaryDraft.value = serialize(result.summary)
    currentStep.value = 2
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '需求解析失败'
  } finally {
    clarifying.value = false
  }
}

const refineSummary = async () => {
  if (!summaryDraft.value) return
  refiningSummary.value = true
  errorMessage.value = ''
  try {
    const result = await callClarifyApi(collectClarificationAnswers())
    clarifyResult.value = result
    summaryDraft.value = serialize(result.summary)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '摘要更新失败'
  } finally {
    refiningSummary.value = false
  }
}

const saveCurrentHistory = async (stage: HistoryStage) => {
  if (!summaryDraft.value || !clarifyResult.value) return
  const recordId = activeHistoryId.value || `hist_${Date.now()}`
  const record: HistoryRecord = {
    id: recordId,
    title: summaryDraft.value.title || '未命名任务',
    platform: form.platform,
    project: form.project,
    stage,
    cases_count: caseSuite.value?.cases.length || 0,
    integration_count: caseSuite.value?.integration_tests.length || 0,
    timestamp: new Date().toISOString(),
    data: {
      task_input: {
        requirement_text: form.requirementText,
        actors: formatLines(form.actors),
        preconditions: formatLines(form.preconditions),
        business_rules: formatLines(form.businessRules),
      },
      test_design: {
        summary: serialize(summaryDraft.value),
        clarification_questions: clarifyResult.value.clarification_questions,
        clarification_answers: collectClarificationAnswers(),
        missing_fields: clarifyResult.value.missing_fields,
        resolved_fields: clarifyResult.value.resolved_fields,
        remaining_risks: clarifyResult.value.remaining_risks,
        functions: designResult.value?.functions || [],
        flows: designResult.value?.flows || [],
        module_segments: designResult.value?.module_segments || {},
        coverage_dimensions: designResult.value?.coverage_dimensions || [],
        test_points: designResult.value?.test_points || [],
        reviewed_test_points: reviewResult.value?.reviewed_test_points || [],
        review_notes: reviewResult.value?.review_notes || [],
      },
      case_suite: caseSuite.value
        ? {
            cases: caseSuite.value.cases,
            integration_tests: caseSuite.value.integration_tests,
            regression_suites: caseSuite.value.regression_suites,
            validation_issues: caseSuite.value.validation_issues,
          }
        : null,
    },
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record),
    })
    if (response.ok) {
      activeHistoryId.value = recordId
      await loadHistory()
    }
  } catch {
    // ignore history errors to avoid blocking the main workflow
  }
}

const generateDesign = async () => {
  if (!summaryDraft.value || !clarifyResult.value) return
  generatingDesign.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/generate-test-points`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: summaryDraft.value,
        clarification_answers: collectClarificationAnswers(),
        clarification_questions: clarifyResult.value.clarification_questions,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试设计生成失败'))
    designResult.value = (await response.json()) as GenerateTestPointsResponse
    reviewResult.value = null
    caseSuite.value = null
    selectedIds.value = designResult.value.test_points.map(point => point.id)
    currentStep.value = 3
    await saveCurrentHistory('test_design')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试设计生成失败'
  } finally {
    generatingDesign.value = false
  }
}

const reviewDesign = async () => {
  if (!designResult.value || !summaryDraft.value) return
  reviewing.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/review-test-points`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: summaryDraft.value,
        clarification_answers: collectClarificationAnswers(),
        test_points: designResult.value.test_points,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试点评审失败'))
    reviewResult.value = (await response.json()) as ReviewTestPointsResponse
    selectedIds.value = reviewResult.value.reviewed_test_points.map(point => point.id)
    await saveCurrentHistory('test_design')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试点评审失败'
  } finally {
    reviewing.value = false
  }
}

const togglePoint = (id: string) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(item => item !== id)
    : [...selectedIds.value, id]
}

const selectAllPoints = () => {
  selectedIds.value = displayedPoints.value.map(point => point.id)
}

const clearSelection = () => {
  selectedIds.value = []
}

const replaceDisplayedPoints = (nextPoints: TestPoint[]) => {
  if (reviewResult.value) {
    reviewResult.value = {
      ...reviewResult.value,
      reviewed_test_points: nextPoints,
    }
  } else if (designResult.value) {
    designResult.value = {
      ...designResult.value,
      test_points: nextPoints,
    }
  }
}

const addPoint = (point: TestPoint) => {
  replaceDisplayedPoints([...displayedPoints.value, point])
  selectedIds.value = [...selectedIds.value, point.id]
}

const removePoint = (id: string) => {
  replaceDisplayedPoints(displayedPoints.value.filter(point => point.id !== id))
  selectedIds.value = selectedIds.value.filter(item => item !== id)
}

const generateCases = async () => {
  if (!designResult.value || !summaryDraft.value || selectedPoints.value.length === 0) return
  generatingCases.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/api/workflow/generate-cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: form.platform,
        summary: summaryDraft.value,
        functions: designResult.value.functions,
        flows: designResult.value.flows,
        module_segments: designResult.value.module_segments,
        selected_test_points: selectedPoints.value,
      }),
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, '测试用例生成失败'))
    caseSuite.value = (await response.json()) as GenerateCasesResponse
    currentStep.value = 4
    await saveCurrentHistory('case_suite')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试用例生成失败'
  } finally {
    generatingCases.value = false
  }
}

const handlePdfUpload = async (file: File) => {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    errorMessage.value = '仅支持 PDF 文件'
    return
  }
  uploadingPdf.value = true
  pdfFileName.value = file.name
  errorMessage.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${apiBaseUrl}/api/upload-pdf`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) throw new Error(await extractErrorMessage(response, 'PDF 解析失败'))
    const data = await response.json()
    form.requirementText = data.text
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'PDF 解析失败'
    pdfFileName.value = ''
  } finally {
    uploadingPdf.value = false
  }
}

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

const loadHistory = async () => {
  try {
    const response = await fetch(`${apiBaseUrl}/api/history`)
    if (response.ok) {
      historyRecords.value = await response.json()
    }
  } catch {
    historyRecords.value = []
  }
}

const loadHistoryRecord = (record: HistoryRecord) => {
  taskActive.value = true
  moduleView.value = null
  activeHistoryId.value = record.id
  form.platform = record.platform
  form.project = record.project
  form.requirementText = record.data.task_input.requirement_text
  form.actors = record.data.task_input.actors.join('\n')
  form.preconditions = record.data.task_input.preconditions.join('\n')
  form.businessRules = record.data.task_input.business_rules.join('\n')
  summaryDraft.value = serialize(record.data.test_design.summary)
  clarifyResult.value = {
    platform: record.platform,
    summary: serialize(record.data.test_design.summary),
    clarification_questions: record.data.test_design.clarification_questions,
    missing_fields: record.data.test_design.missing_fields,
    resolved_fields: record.data.test_design.resolved_fields,
    remaining_risks: record.data.test_design.remaining_risks,
    round: 1,
    prompts: {},
  }
  designResult.value = record.data.test_design.functions.length || record.data.test_design.test_points.length
    ? {
        platform: record.platform,
        functions: record.data.test_design.functions,
        flows: record.data.test_design.flows,
        module_segments: record.data.test_design.module_segments,
        coverage_dimensions: record.data.test_design.coverage_dimensions,
        test_points: record.data.test_design.test_points,
        prompts: {},
      }
    : null
  reviewResult.value = record.data.test_design.reviewed_test_points.length || record.data.test_design.review_notes.length
    ? {
        platform: record.platform,
        reviewed_test_points: record.data.test_design.reviewed_test_points,
        review_notes: record.data.test_design.review_notes,
        validation_issues: [],
        prompts: {},
      }
    : null
  caseSuite.value = record.data.case_suite
    ? {
        platform: record.platform,
        cases: record.data.case_suite.cases,
        integration_tests: record.data.case_suite.integration_tests,
        regression_suites: record.data.case_suite.regression_suites,
        validation_issues: record.data.case_suite.validation_issues,
        prompts: {},
      }
    : null
  selectedIds.value = (reviewResult.value?.reviewed_test_points || designResult.value?.test_points || []).map(point => point.id)
  currentStep.value = record.stage === 'case_suite' ? 4 : record.stage === 'test_design' ? 3 : 2
  Object.keys(clarificationDraftAnswers).forEach(key => delete clarificationDraftAnswers[key])
  for (const item of record.data.test_design.clarification_answers) {
    clarificationDraftAnswers[item.question_id] = item.answer
  }
  errorMessage.value = ''
}

const deleteHistoryRecord = async (id: string) => {
  try {
    await fetch(`${apiBaseUrl}/api/history/${id}`, { method: 'DELETE' })
    if (activeHistoryId.value === id) {
      activeHistoryId.value = null
      goHome()
    }
    await loadHistory()
  } catch {
    // ignore delete failure
  }
}

onMounted(async () => {
  await Promise.all([loadMeta(), loadHistory()])
})
</script>

<template>
  <div class="app-wrapper">
    <HistorySidebar
      :records="historyRecords"
      :active-id="activeHistoryId"
      :task-active="taskActive"
      @go-home="goHome"
      @new-task="startNewTask"
      @enter-workflow="enterWorkflow"
      @select-record="loadHistoryRecord"
      @delete-record="deleteHistoryRecord"
    />

    <main class="app-main">
      <div v-if="!taskActive && !moduleView" class="welcome-page">
        <div class="welcome-content">

          <!-- Hero -->
          <div class="welcome-hero">
            <div class="welcome-hero-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
              AI Test Platform · Beta
            </div>
            <h1 class="welcome-title">AI Test</h1>
            <p class="welcome-desc">
              面向测试工程师的 AI 原生工具平台。<br>
              覆盖测试设计、自动化执行、数据校验，让 AI 参与测试全链路。
            </p>
          </div>

          <!-- Module Cards -->
          <div class="welcome-modules">
            <div class="welcome-section-label">功能模块</div>
            <div class="welcome-module-grid">

              <!-- Active: AI 生成测试用例 -->
              <div class="module-card module-card--active" @click="enterWorkflow">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #EEF2FF;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                      <polyline points="10 9 9 9 8 9"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--live">已上线</span>
                </div>
                <div class="module-card-title">AI 生成测试用例</div>
                <div class="module-card-desc">
                  从需求文本一键生成结构化测试用例。覆盖需求澄清、摘要确认、测试点设计、用例套件全流程。
                </div>
                <div class="module-card-tags">
                  <span>需求澄清</span>
                  <span>测试设计</span>
                  <span>用例生成</span>
                  <span>回归套件</span>
                </div>
                <div class="module-card-action">
                  开始使用
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                  </svg>
                </div>
              </div>

              <!-- Coming soon: Android 埋点测试 -->
              <div class="module-card module-card--soon">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #F0FDF4;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
                      <line x1="12" y1="18" x2="12.01" y2="18"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--soon">规划中</span>
                </div>
                <div class="module-card-title">Android 埋点测试</div>
                <div class="module-card-desc">
                  接入 ADB 常用命令，结合 AI 自动验证 Android 埋点数据上报是否符合预期，降低手动验证成本。
                </div>
                <div class="module-card-tags">
                  <span>ADB 命令</span>
                  <span>埋点验证</span>
                  <span>自动化</span>
                </div>
              </div>

              <!-- Coming soon: BQ 数据校验 -->
              <div class="module-card module-card--soon">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #FFF7ED;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <ellipse cx="12" cy="5" rx="9" ry="3"/>
                      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--soon">规划中</span>
                </div>
                <div class="module-card-title">BigQuery 数据校验</div>
                <div class="module-card-desc">
                  接入 BigQuery 查询能力，自动比对测试前后数据变化，AI 驱动的数据层验证，无需手写 SQL。
                </div>
                <div class="module-card-tags">
                  <span>BQ 查询</span>
                  <span>数据比对</span>
                  <span>自动断言</span>
                </div>
              </div>

              <!-- Future: 测试执行闭环 -->
              <div class="module-card module-card--future">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #F8FAFC;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="23 4 23 10 17 10"/>
                      <polyline points="1 20 1 14 7 14"/>
                      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--future">远期</span>
                </div>
                <div class="module-card-title">测试执行闭环</div>
                <div class="module-card-desc">
                  Agent 化多轮自主测试设计，从用例生成到执行再到结果分析，打通测试全链路闭环。
                </div>
                <div class="module-card-tags">
                  <span>Agent</span>
                  <span>自动执行</span>
                  <span>结果分析</span>
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>

      <!-- Module intro: AI 生成测试用例 -->
      <div v-else-if="!taskActive && moduleView === 'ai-gen-cases'" class="module-intro-page">
        <div class="module-intro-content">

          <div class="module-intro-header">
            <button class="btn-back" @click="goHome">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="15 18 9 12 15 6"/>
              </svg>
              返回首页
            </button>
          </div>

          <div class="module-intro-hero">
            <div class="module-intro-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <div class="welcome-hero-badge" style="margin-bottom: 0;">
              <span class="module-status module-status--live" style="font-size:11px">已上线</span>
            </div>
            <h1 class="module-intro-title">AI 生成测试用例</h1>
            <p class="module-intro-desc">
              输入需求文本，AI 自动完成澄清、摘要、测试点设计、用例生成全流程。<br>
              从需求到可交付的测试资产，最快几分钟完成。
            </p>
            <button class="btn btn-primary module-intro-cta" @click="startWorkflowFromIntro">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              新建测试任务
            </button>
          </div>

          <!-- 4-step flow -->
          <div class="module-intro-section">
            <div class="welcome-section-label">工作流程</div>
            <div class="welcome-steps">
              <div class="welcome-step">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">1</div>
                  <div class="welcome-step-line"></div>
                </div>
                <div class="welcome-step-title">需求输入</div>
                <div class="welcome-step-desc">粘贴需求文本或上传 PDF，补充角色、前置条件与业务规则</div>
              </div>
              <div class="welcome-step">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">2</div>
                  <div class="welcome-step-line"></div>
                </div>
                <div class="welcome-step-title">摘要确认</div>
                <div class="welcome-step-desc">AI 提取结构化摘要，识别澄清问题和缺失信息，补充后进入设计</div>
              </div>
              <div class="welcome-step">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">3</div>
                  <div class="welcome-step-line"></div>
                </div>
                <div class="welcome-step-title">测试设计</div>
                <div class="welcome-step-desc">按功能模块生成测试点，支持 AI 评审、手动增删，选择进入用例</div>
              </div>
              <div class="welcome-step">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">4</div>
                </div>
                <div class="welcome-step-title">用例与资产</div>
                <div class="welcome-step-desc">生成功能用例、集成测试与回归套件，导出可直接使用的测试资产</div>
              </div>
            </div>
          </div>

          <!-- Capabilities -->
          <div class="module-intro-section">
            <div class="welcome-section-label">核心能力</div>
            <div class="welcome-cap-grid">
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background: #EEF2FF;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                </div>
                <div class="welcome-cap-title">需求澄清 · 结构化</div>
                <div class="welcome-cap-desc">识别缺失字段、阻塞问题，输出结构化摘要，确保测试设计有充足信息基础</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background: #F0FDF4;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                  </svg>
                </div>
                <div class="welcome-cap-title">测试点生成 · 模块化</div>
                <div class="welcome-cap-desc">按功能模块分组，支持 AI 二次评审、手动增删，精准覆盖业务场景</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background: #FFF7ED;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                  </svg>
                </div>
                <div class="welcome-cap-title">用例套件 · 全覆盖</div>
                <div class="welcome-cap-desc">同时生成功能用例、集成测试，自动去重，配套回归套件，可直接交付</div>
              </div>
              <div class="welcome-cap-card">
                <div class="welcome-cap-icon" style="background: #EFF6FF;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                  </svg>
                </div>
                <div class="welcome-cap-title">历史记录 · 可追溯</div>
                <div class="welcome-cap-desc">每次任务自动快照保存，支持随时回溯历史版本，保留完整设计上下文</div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div v-else class="workbench-layout">
        <div class="step-progress">
          <div
            v-for="(label, idx) in stepLabels"
            :key="label"
            class="step-progress-item"
            :class="{ active: currentStep === idx + 1, completed: maxReachedStep > idx + 1 }"
            @click="idx + 1 <= maxReachedStep ? (currentStep = idx + 1) : null"
          >
            <div class="step-circle">
              <svg v-if="maxReachedStep > idx + 1" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
              </svg>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="step-label">{{ label }}</span>
            <div v-if="idx < stepLabels.length - 1" class="step-connector" :class="{ filled: maxReachedStep > idx + 1 }"></div>
          </div>
        </div>

        <div v-if="errorMessage" class="error-banner">
          <strong>操作失败：</strong> {{ errorMessage }}
        </div>

        <RequirementInputStep
          v-if="currentStep === 1"
          :form="form"
          :meta="meta"
          :loading="clarifying || loadingMeta"
          :uploading-pdf="uploadingPdf"
          :pdf-file-name="pdfFileName"
          @submit="startClarify"
          @upload-pdf="handlePdfUpload"
        />

        <SummaryConfirmStep
          v-else-if="currentStep === 2 && summaryDraft && clarifyResult"
          :summary="summaryDraft"
          :clarification-questions="clarifyResult.clarification_questions"
          :clarification-draft-answers="clarificationDraftAnswers"
          :missing-fields="clarifyResult.missing_fields"
          :resolved-fields="clarifyResult.resolved_fields"
          :remaining-risks="clarifyResult.remaining_risks"
          :has-unanswered-blocking="hasUnansweredBlocking"
          :loading-refine="refiningSummary"
          :loading-generate="generatingDesign"
          @refine="refineSummary"
          @generate-design="generateDesign"
        />

        <TestDesignStep
          v-else-if="currentStep === 3 && summaryDraft && designResult"
          :api-base-url="apiBaseUrl"
          :platform="form.platform"
          :summary="summaryDraft"
          :design-result="designResult"
          :review-result="reviewResult"
          :selected-ids="selectedIds"
          :reviewing="reviewing"
          :generating-cases="generatingCases"
          @toggle-point="togglePoint"
          @select-all="selectAllPoints"
          @clear-selection="clearSelection"
          @review="reviewDesign"
          @generate-cases="generateCases"
          @add-point="addPoint"
          @remove-point="removePoint"
        />

        <CaseSuiteStep
          v-else-if="currentStep === 4 && summaryDraft && designResult && caseSuite"
          :api-base-url="apiBaseUrl"
          :platform="form.platform"
          :summary="summaryDraft"
          :design-result="designResult"
          :review-result="reviewResult"
          :case-suite="caseSuite"
        />
      </div>
    </main>
  </div>
</template>
