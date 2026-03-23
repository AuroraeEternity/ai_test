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
  errorMessage.value = ''
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
      @select-record="loadHistoryRecord"
      @delete-record="deleteHistoryRecord"
    />

    <main class="app-main">
      <div v-if="!taskActive" class="welcome-page">
        <div class="welcome-content">
          <div class="welcome-hero">
            <div class="welcome-hero-badge">AI Test Platform</div>
            <h1 class="welcome-title">AI 测试设计工作台</h1>
            <p class="welcome-desc">
              从需求澄清到摘要确认，再到测试设计和回归资产生成，当前流程已经收口为正式的分阶段工作流。
            </p>
            <button class="btn btn-primary welcome-start" @click="startNewTask">
              新建测试任务
            </button>
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

        <div v-else-if="currentStep === 2 && summaryDraft && clarifyResult" class="step-stack">
          <SummaryConfirmStep
            :summary="summaryDraft"
            :clarification-questions="clarifyResult.clarification_questions"
            :clarification-draft-answers="clarificationDraftAnswers"
            :loading-refine="refiningSummary"
            :loading-generate="generatingDesign"
            @refine="refineSummary"
            @generate-design="generateDesign"
          />

          <section class="panel">
            <div class="panel-header">
              <div>
                <div class="panel-eyebrow">Clarify</div>
                <h2>需求缺口与风险</h2>
              </div>
              <span v-if="hasUnansweredBlocking" class="pill pill-danger">存在未回答阻塞问题</span>
              <span v-else class="pill pill-success">可进入测试设计</span>
            </div>

            <div class="clarify-grid">
              <div>
                <div class="sub-title">缺失字段</div>
                <div v-if="clarifyResult.missing_fields.length" class="issue-section">
                  <div v-for="item in clarifyResult.missing_fields" :key="`${item.field}-${item.detail}`" class="issue-item">
                    <span class="pill" :class="item.severity === 'high' ? 'pill-danger' : 'pill-info'">{{ item.field }}</span>
                    <span>{{ item.detail }}</span>
                  </div>
                </div>
                <div v-else class="empty-state">当前没有识别到额外缺失字段。</div>
              </div>

              <div>
                <div class="sub-title">已明确维度</div>
                <div class="pill-list" v-if="clarifyResult.resolved_fields.length">
                  <span v-for="item in clarifyResult.resolved_fields" :key="item" class="pill pill-success">{{ item }}</span>
                </div>
                <div v-else class="empty-state">暂无已明确维度。</div>

                <div class="sub-title sub-title-top">剩余风险</div>
                <div v-if="clarifyResult.remaining_risks.length" class="issue-section">
                  <div v-for="item in clarifyResult.remaining_risks" :key="item" class="issue-item">
                    <span>{{ item }}</span>
                  </div>
                </div>
                <div v-else class="empty-state">当前没有明显剩余风险。</div>
              </div>
            </div>
          </section>
        </div>

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
