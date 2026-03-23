<script setup lang="ts">
import { computed, ref } from 'vue'
import MindMapView from './MindMapView.vue'
import type {
  GenerateCasesResponse,
  GenerateTestPointsResponse,
  ReviewTestPointsResponse,
  StructuredSummary,
  ValidationIssue,
} from '../types/workflow'

const props = defineProps<{
  apiBaseUrl: string
  platform: string
  summary: StructuredSummary
  designResult: GenerateTestPointsResponse
  reviewResult: ReviewTestPointsResponse | null
  caseSuite: GenerateCasesResponse
}>()

const mode = ref<'list' | 'mindmap'>('list')
const filter = ref<'all' | 'cases' | 'integration' | 'regression'>('all')

const points = computed(() =>
  props.reviewResult?.reviewed_test_points.length
    ? props.reviewResult.reviewed_test_points
    : props.designResult.test_points,
)

const issuesByCase = computed(() => {
  const map: Record<string, ValidationIssue[]> = {}
  for (const issue of props.caseSuite.validation_issues) {
    if (issue.target_id) {
      if (!map[issue.target_id]) map[issue.target_id] = []
      map[issue.target_id].push(issue)
    }
  }
  return map
})

const exportCsv = () => {
  const BOM = '\uFEFF'
  const headers = ['用例ID', '标题', '功能模块', '优先级', '类型', '前置条件', '测试数据', '步骤', '预期结果', '来源测试点']
  const rows = props.caseSuite.cases.map(c => [
    c.id,
    c.title,
    c.function_module,
    c.priority,
    c.case_type,
    c.preconditions.join('\n'),
    c.test_data.join('\n'),
    c.steps.map((s, i) => `${i + 1}. ${s}`).join('\n'),
    c.expected_results.map((r, i) => `${i + 1}. ${r}`).join('\n'),
    c.source_test_point_id,
  ])

  const escape = (val: string) => {
    if (val.includes(',') || val.includes('"') || val.includes('\n'))
      return `"${val.replace(/"/g, '""')}"`
    return val
  }

  const csvContent = BOM + [headers, ...rows].map(row => row.map(escape).join(',')).join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `test-cases-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

const exportIntegrationCsv = () => {
  const BOM = '\uFEFF'
  const headers = ['ID', '标题', '描述', '关联流程', '前置条件', '步骤', '预期结果']
  const rows = props.caseSuite.integration_tests.map(t => [
    t.id,
    t.title,
    t.description,
    t.flow,
    t.preconditions.join('\n'),
    t.steps.map((s, i) => `${i + 1}. ${s}`).join('\n'),
    t.expected_results.map((r, i) => `${i + 1}. ${r}`).join('\n'),
  ])

  const escape = (val: string) => {
    if (val.includes(',') || val.includes('"') || val.includes('\n'))
      return `"${val.replace(/"/g, '""')}"`
    return val
  }

  const csvContent = BOM + [headers, ...rows].map(row => row.map(escape).join(',')).join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `integration-tests-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">Step 4</div>
        <h2>用例与回归资产</h2>
      </div>
      <div class="action-group">
        <button class="btn btn-ghost" :class="{ active: mode === 'list' }" @click="mode = 'list'">列表</button>
        <button class="btn btn-ghost" :class="{ active: mode === 'mindmap' }" @click="mode = 'mindmap'">脑图</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-label">功能用例</span>
        <strong>{{ caseSuite.cases.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">联动测试</span>
        <strong>{{ caseSuite.integration_tests.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">回归集</span>
        <strong>{{ caseSuite.regression_suites.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">质量问题</span>
        <strong>{{ caseSuite.validation_issues.length }}</strong>
      </div>
    </div>

    <MindMapView
      v-if="mode === 'mindmap'"
      :api-base-url="apiBaseUrl"
      :platform="platform"
      :summary="summary"
      :functions="designResult.functions"
      :test-points="points"
      :cases="caseSuite.cases"
      :integration-tests="caseSuite.integration_tests"
    />

    <template v-else>
      <div class="toolbar">
        <div class="toolbar-group">
          <button class="btn btn-ghost" :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
          <button class="btn btn-ghost" :class="{ active: filter === 'cases' }" @click="filter = 'cases'">功能用例</button>
          <button class="btn btn-ghost" :class="{ active: filter === 'integration' }" @click="filter = 'integration'">联动测试</button>
          <button class="btn btn-ghost" :class="{ active: filter === 'regression' }" @click="filter = 'regression'">回归集</button>
        </div>
        <div class="toolbar-group">
          <button
            v-if="filter === 'all' || filter === 'cases'"
            class="btn btn-secondary btn-sm"
            @click="exportCsv"
          >
            导出功能用例 CSV
          </button>
          <button
            v-if="(filter === 'all' || filter === 'integration') && caseSuite.integration_tests.length"
            class="btn btn-secondary btn-sm"
            @click="exportIntegrationCsv"
          >
            导出联动测试 CSV
          </button>
        </div>
      </div>

      <div v-if="caseSuite.validation_issues.length && (filter === 'all')" class="issue-section">
        <div class="sub-title">质量校验</div>
        <div
          v-for="issue in caseSuite.validation_issues.filter(i => !i.target_id)"
          :key="`${issue.issue_type}-${issue.message}`"
          class="issue-item"
        >
          <span class="pill" :class="issue.severity === 'high' ? 'pill-danger' : 'pill-info'">{{ issue.severity }}</span>
          <span>{{ issue.message }}</span>
        </div>
      </div>

      <div v-if="filter === 'all' || filter === 'regression'" class="suite-section">
        <div class="sub-title">回归集</div>
        <div v-for="suite in caseSuite.regression_suites" :key="suite.id" class="suite-card">
          <div class="suite-top">
            <strong>{{ suite.title }}</strong>
            <span class="pill">{{ suite.id }}</span>
          </div>
          <p>{{ suite.description }}</p>
          <div class="suite-meta">
            <span>{{ suite.case_ids.length }} 功能用例</span>
            <span>{{ suite.integration_test_ids.length }} 联动测试</span>
          </div>
          <ul>
            <li v-for="item in suite.entry_criteria" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>

      <div v-if="filter === 'all' || filter === 'cases'" class="suite-section">
        <div class="sub-title">功能用例</div>
        <div v-for="item in caseSuite.cases" :key="item.id" class="case-card">
          <div class="suite-top">
            <strong>{{ item.id }} {{ item.title }}</strong>
            <div class="point-badges">
              <span class="pill">{{ item.function_module }}</span>
              <span class="pill">{{ item.priority }}</span>
              <span class="pill">{{ item.case_type }}</span>
            </div>
          </div>
          <div v-if="issuesByCase[item.id]?.length" class="case-inline-issues">
            <span
              v-for="issue in issuesByCase[item.id]"
              :key="issue.message"
              class="case-issue-tag"
              :class="issue.severity === 'high' ? 'issue-high' : 'issue-medium'"
              :title="issue.message"
            >
              {{ issue.issue_type }}：{{ issue.message }}
            </span>
          </div>
          <div class="case-grid">
            <div>
              <div class="mini-title">前置条件</div>
              <ul><li v-for="value in item.preconditions" :key="value">{{ value }}</li></ul>
            </div>
            <div>
              <div class="mini-title">测试数据</div>
              <ul><li v-for="value in item.test_data" :key="value">{{ value }}</li></ul>
            </div>
            <div>
              <div class="mini-title">步骤</div>
              <ol><li v-for="value in item.steps" :key="value">{{ value }}</li></ol>
            </div>
            <div>
              <div class="mini-title">预期结果</div>
              <ol><li v-for="value in item.expected_results" :key="value">{{ value }}</li></ol>
            </div>
          </div>
        </div>
      </div>

      <div v-if="filter === 'all' || filter === 'integration'" class="suite-section">
        <div class="sub-title">联动测试</div>
        <div v-if="caseSuite.integration_tests.length === 0" class="empty-state">当前没有生成联动测试。</div>
        <div v-for="item in caseSuite.integration_tests" :key="item.id" class="case-card">
          <div class="suite-top">
            <strong>{{ item.id }} {{ item.title }}</strong>
            <span class="pill">{{ item.flow }}</span>
          </div>
          <p>{{ item.description }}</p>
          <div class="case-grid">
            <div>
              <div class="mini-title">前置条件</div>
              <ul><li v-for="value in item.preconditions" :key="value">{{ value }}</li></ul>
            </div>
            <div>
              <div class="mini-title">步骤</div>
              <ol><li v-for="value in item.steps" :key="value">{{ value }}</li></ol>
            </div>
            <div>
              <div class="mini-title">预期结果</div>
              <ol><li v-for="value in item.expected_results" :key="value">{{ value }}</li></ol>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
