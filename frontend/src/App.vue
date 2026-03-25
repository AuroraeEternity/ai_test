<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import CaseSuiteStep from './components/CaseSuiteStep.vue'
import HistorySidebar from './components/HistorySidebar.vue'
import RequirementInputStep from './components/RequirementInputStep.vue'
import SummaryConfirmStep from './components/SummaryConfirmStep.vue'
import TestDesignStep from './components/TestDesignStep.vue'
import { createWorkflowApi, splitLines } from './lib/api'
import type {
  ClarificationAnswer,
  ClarifyResponse,
  GenerateCasesResponse,
  GenerateTestPointsResponse,
  HistoryRecord,
  HistoryStage,
  IntegrationTestsResponse,
  MetaResponse,
  ReviewTestPointsResponse,
  StructuredSummary,
  TaskFormState,
  TestPoint,
} from './types/workflow'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const api = createWorkflowApi(apiBaseUrl)

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
const integrationResult = ref<IntegrationTestsResponse | null>(null)
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

const isRequirementComplete = computed(() => clarifyResult.value?.is_complete ?? false)

const serialize = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

const resetWorkflowState = () => {
  summaryDraft.value = null
  clarifyResult.value = null
  designResult.value = null
  reviewResult.value = null
  caseSuite.value = null
  integrationResult.value = null
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

const startClarify = async () => {
  clarifying.value = true
  errorMessage.value = ''
  resetWorkflowState()
  try {
    const result = await api.clarify(form, [])
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
    const result = await api.clarify(form, collectClarificationAnswers())
    clarifyResult.value = result
    summaryDraft.value = serialize(result.summary)
    // 清空旧的回答，避免新问题的输入框中残留上轮内容
    Object.keys(clarificationDraftAnswers).forEach(key => delete clarificationDraftAnswers[key])
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
    integration_count: integrationResult.value?.integration_tests.length || 0,
    timestamp: new Date().toISOString(),
    data: {
      task_input: {
        requirement_text: form.requirementText,
        actors: splitLines(form.actors),
        preconditions: splitLines(form.preconditions),
        business_rules: splitLines(form.businessRules),
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
            integration_tests: integrationResult.value?.integration_tests || [],
            regression_suites: [],
            validation_issues: caseSuite.value.validation_issues,
          }
        : null,
    },
  }

  try {
    await api.saveHistory(record)
    activeHistoryId.value = recordId
    await loadHistory()
  } catch {
    // ignore history errors to avoid blocking the main workflow
  }
}

const generateDesign = async () => {
  if (!summaryDraft.value || !clarifyResult.value) return
  generatingDesign.value = true
  errorMessage.value = ''
  try {
    // 链式调用：先结构分析，再测试点生成，用户只等一次
    const structure = await api.analyzeStructure(
      form.platform,
      summaryDraft.value,
      collectClarificationAnswers(),
      clarifyResult.value.clarification_questions,
    )
    designResult.value = await api.generateTestPoints(
      form.platform,
      summaryDraft.value,
      structure.functions,
      structure.flows,
      structure.module_segments,
      structure.coverage_dimensions,
      collectClarificationAnswers(),
    )
    reviewResult.value = null
    caseSuite.value = null
    integrationResult.value = null
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
    reviewResult.value = await api.reviewTestPoints(
      form.platform,
      summaryDraft.value,
      collectClarificationAnswers(),
      designResult.value.test_points,
    )
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

const updatePoint = (updated: TestPoint) => {
  replaceDisplayedPoints(displayedPoints.value.map(p => p.id === updated.id ? updated : p))
}

const generateCases = async () => {
  if (!designResult.value || !summaryDraft.value || selectedPoints.value.length === 0) return
  generatingCases.value = true
  errorMessage.value = ''
  try {
    caseSuite.value = await api.generateCaseSuite(
      form.platform,
      summaryDraft.value,
      designResult.value.functions,
      designResult.value.flows,
      designResult.value.module_segments,
      selectedPoints.value,
    )
    integrationResult.value = null
    currentStep.value = 4
    await saveCurrentHistory('case_suite')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '测试用例生成失败'
  } finally {
    generatingCases.value = false
  }
}

const generateIntegration = async () => {
  if (!designResult.value || !summaryDraft.value || !caseSuite.value) return
  errorMessage.value = ''
  try {
    integrationResult.value = await api.generateIntegrationTests(
      form.platform,
      summaryDraft.value,
      designResult.value.flows,
      selectedPoints.value,
      caseSuite.value.cases.map(c => c.title),
    )
    await saveCurrentHistory('case_suite')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '联动测试生成失败'
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
    const data = await api.uploadPdf(file)
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
    meta.value = await api.getMeta()
  } catch {
    meta.value = fallbackMeta
  } finally {
    loadingMeta.value = false
  }
}

const loadHistory = async () => {
  try {
    historyRecords.value = await api.listHistory()
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
    is_complete: true,
    missing_fields: record.data.test_design.missing_fields,
    resolved_fields: record.data.test_design.resolved_fields,
    remaining_risks: record.data.test_design.remaining_risks,
    round: 1,
    prompts: {},
  }
  // 恢复结构分析结果（从 functions/flows 等字段重建）
  designResult.value = record.data.test_design.test_points.length
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
        validation_issues: record.data.case_suite.validation_issues,
        prompts: {},
      }
    : null
  integrationResult.value = record.data.case_suite?.integration_tests?.length
    ? {
        platform: record.platform,
        integration_tests: record.data.case_suite.integration_tests,
        validation_issues: [],
        prompts: {},
      }
    : null
  selectedIds.value = (reviewResult.value?.reviewed_test_points || designResult.value?.test_points || []).map(point => point.id)
  if (caseSuite.value) {
    currentStep.value = 4
  } else if (designResult.value) {
    currentStep.value = 3
  } else {
    currentStep.value = 2
  }
  Object.keys(clarificationDraftAnswers).forEach(key => delete clarificationDraftAnswers[key])
  for (const item of record.data.test_design.clarification_answers) {
    clarificationDraftAnswers[item.question_id] = item.answer
  }
  errorMessage.value = ''
}

const deleteHistoryRecord = async (id: string) => {
  try {
    await api.deleteHistory(id)
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
              从需求到可交付的测试资产，最快几分钟完成。
            </p>
            <button class="btn btn-primary welcome-cta" @click="startNewTask">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              新建测试任务
            </button>
          </div>

          <!-- 4-step flow -->
          <div class="welcome-section">
            <div class="welcome-section-label">工作流程</div>
            <div class="welcome-steps">
              <div class="welcome-step" v-for="(step, idx) in [
                { title: '需求输入', desc: '粘贴需求文本或上传 PDF，补充角色与业务规则' },
                { title: '摘要确认', desc: 'AI 提取结构化摘要，识别澄清问题，人工确认后进入设计' },
                { title: '测试设计', desc: '按模块生成测试点，支持 AI 评审、手动编辑，选择进入用例' },
                { title: '用例生成', desc: '生成功能用例与联动测试，导出可直接使用的测试资产' },
              ]" :key="idx">
                <div class="welcome-step-header">
                  <div class="welcome-step-num">{{ idx + 1 }}</div>
                  <div v-if="idx < 3" class="welcome-step-line"></div>
                </div>
                <div class="welcome-step-title">{{ step.title }}</div>
                <div class="welcome-step-desc">{{ step.desc }}</div>
              </div>
            </div>
          </div>

          <!-- Module Cards -->
          <div class="welcome-section">
            <div class="welcome-section-label">功能模块</div>
            <div class="welcome-module-grid">

              <div class="module-card module-card--active" @click="startNewTask">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #EEF2FF;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--live">可用</span>
                </div>
                <div class="module-card-title">AI 生成测试用例</div>
                <div class="module-card-desc">需求澄清 → 测试点设计 → 用例生成全流程</div>
              </div>

              <div class="module-card module-card--soon">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #F0FDF4;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--soon">规划中</span>
                </div>
                <div class="module-card-title">Android 埋点测试</div>
                <div class="module-card-desc">ADB 命令接入，AI 自动验证埋点数据上报</div>
              </div>

              <div class="module-card module-card--soon">
                <div class="module-card-header">
                  <div class="module-card-icon" style="background: #FFF7ED;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <ellipse cx="12" cy="5" rx="9" ry="3"/>
                      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                    </svg>
                  </div>
                  <span class="module-status module-status--soon">规划中</span>
                </div>
                <div class="module-card-title">BigQuery 数据校验</div>
                <div class="module-card-desc">自动比对测试前后数据变化，AI 驱动数据层验证</div>
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
          :is-complete="isRequirementComplete"
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
          @update-point="updatePoint"
        />

        <CaseSuiteStep
          v-else-if="currentStep === 4 && summaryDraft && designResult && caseSuite"
          :api-base-url="apiBaseUrl"
          :platform="form.platform"
          :summary="summaryDraft"
          :design-result="designResult"
          :review-result="reviewResult"
          :case-suite="caseSuite"
          :integration-result="integrationResult"
          :selected-points="selectedPoints"
          @generate-integration="generateIntegration"
        />
      </div>
    </main>
  </div>
</template>
