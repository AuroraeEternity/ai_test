<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import MindMapView from './MindMapView.vue'
import { categoryLabels } from '../types/workflow'
import type {
  GenerateTestPointsResponse,
  ReviewTestPointsResponse,
  StructuredSummary,
  TestPoint,
} from '../types/workflow'

const props = defineProps<{
  apiBaseUrl: string
  platform: string
  summary: StructuredSummary
  designResult: GenerateTestPointsResponse
  reviewResult: ReviewTestPointsResponse | null
  selectedIds: string[]
  reviewing: boolean
  generatingCases: boolean
}>()

const emit = defineEmits<{
  togglePoint: [id: string]
  selectAll: []
  clearSelection: []
  review: []
  generateCases: []
  addPoint: [point: TestPoint]
  removePoint: [id: string]
}>()

const filterModule = ref('all')
const mindmapMode = ref<'list' | 'mindmap'>('list')
const collapsedModules = reactive<Record<string, boolean>>({})
const showAddForm = ref(false)
const addForm = reactive({
  title: '',
  function_module: '',
  category: 'positive' as TestPoint['category'],
  description: '',
  risk_level: 'medium' as TestPoint['risk_level'],
  priority: 'P1' as TestPoint['priority'],
})

const displayedPoints = computed(() =>
  props.reviewResult?.reviewed_test_points.length
    ? props.reviewResult.reviewed_test_points
    : props.designResult.test_points,
)

const modules = computed(() => ['all', ...props.designResult.functions])

const filteredPoints = computed(() =>
  displayedPoints.value.filter(
    item => filterModule.value === 'all' || item.function_module === filterModule.value,
  ),
)

const groupedPoints = computed(() => {
  const groups: Record<string, TestPoint[]> = {}
  for (const point of filteredPoints.value) {
    const mod = point.function_module || '未归类'
    if (!groups[mod]) groups[mod] = []
    groups[mod].push(point)
  }
  return groups
})

const groupStats = (points: TestPoint[]) => {
  const total = points.length
  const selected = points.filter(p => props.selectedIds.includes(p.id)).length
  const highRisk = points.filter(p => p.risk_level === 'high').length
  return { total, selected, highRisk }
}

const isGroupAllSelected = (points: TestPoint[]) =>
  points.every(p => props.selectedIds.includes(p.id))

const toggleGroup = (points: TestPoint[]) => {
  if (isGroupAllSelected(points)) {
    points.forEach(p => {
      if (props.selectedIds.includes(p.id)) emit('togglePoint', p.id)
    })
  } else {
    points.forEach(p => {
      if (!props.selectedIds.includes(p.id)) emit('togglePoint', p.id)
    })
  }
}

const toggleCollapse = (mod: string) => {
  collapsedModules[mod] = !collapsedModules[mod]
}

const nextTpId = computed(() => {
  const maxNum = displayedPoints.value.reduce((max, p) => {
    const match = p.id.match(/^TP-(\d+)$/)
    return match ? Math.max(max, parseInt(match[1])) : max
  }, 0)
  return `TP-${String(maxNum + 1).padStart(3, '0')}`
})

const resetAddForm = () => {
  addForm.title = ''
  addForm.function_module = props.designResult.functions[0] || ''
  addForm.category = 'positive'
  addForm.description = ''
  addForm.risk_level = 'medium'
  addForm.priority = 'P1'
}

const openAddForm = () => {
  resetAddForm()
  showAddForm.value = true
}

const submitAddForm = () => {
  if (!addForm.title.trim() || !addForm.description.trim()) return
  const newPoint: TestPoint = {
    id: nextTpId.value,
    title: addForm.title.trim(),
    function_module: addForm.function_module || '未归类',
    category: addForm.category,
    description: addForm.description.trim(),
    source: '人工添加',
    risk_level: addForm.risk_level,
    priority: addForm.priority,
    platform_specific: false,
  }
  emit('addPoint', newPoint)
  showAddForm.value = false
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">Step 3</div>
        <h2>测试设计</h2>
      </div>
      <div class="action-group">
        <button class="btn btn-secondary" :disabled="reviewing" @click="emit('review')">
          {{ reviewing ? 'AI 审核中...' : 'AI Diff 审核' }}
        </button>
        <button
          class="btn btn-primary"
          :disabled="generatingCases || selectedIds.length === 0"
          @click="emit('generateCases')"
        >
          {{ generatingCases ? '生成中...' : `生成用例（${selectedIds.length}）` }}
        </button>
      </div>
    </div>

    <div class="toolbar">
      <div class="toolbar-group">
        <select v-model="filterModule">
          <option v-for="name in modules" :key="name" :value="name">
            {{ name === 'all' ? '全部模块' : name }}
          </option>
        </select>
        <button class="btn btn-ghost" @click="emit('selectAll')">全选</button>
        <button class="btn btn-ghost" @click="emit('clearSelection')">清空</button>
        <button class="btn btn-ghost" @click="openAddForm">+ 添加测试点</button>
      </div>
      <div class="toolbar-group">
        <button class="btn btn-ghost" :class="{ active: mindmapMode === 'list' }" @click="mindmapMode = 'list'">
          列表
        </button>
        <button class="btn btn-ghost" :class="{ active: mindmapMode === 'mindmap' }" @click="mindmapMode = 'mindmap'">
          脑图
        </button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-label">功能模块</span>
        <strong>{{ designResult.functions.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">测试点</span>
        <strong>{{ displayedPoints.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">已选中</span>
        <strong>{{ selectedIds.length }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-label">业务流</span>
        <strong>{{ designResult.flows.length }}</strong>
      </div>
    </div>

    <!-- Add test point form -->
    <div v-if="showAddForm" class="add-point-form">
      <div class="add-point-form-header">
        <strong>添加测试点</strong>
        <button class="btn btn-ghost" @click="showAddForm = false">&times;</button>
      </div>
      <div class="form-grid">
        <label class="field">
          <span>标题</span>
          <input v-model="addForm.title" placeholder="测试点标题（10-20 字）" />
        </label>
        <label class="field">
          <span>功能模块</span>
          <select v-model="addForm.function_module">
            <option v-for="fn in designResult.functions" :key="fn" :value="fn">{{ fn }}</option>
          </select>
        </label>
      </div>
      <label class="field">
        <span>描述</span>
        <textarea v-model="addForm.description" rows="3" placeholder="测试目的、输入条件和预期判断标准"></textarea>
      </label>
      <div class="form-grid form-grid-advanced">
        <label class="field">
          <span>分类</span>
          <select v-model="addForm.category">
            <option v-for="(label, key) in categoryLabels" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="field">
          <span>风险</span>
          <select v-model="addForm.risk_level">
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
        </label>
        <label class="field">
          <span>优先级</span>
          <select v-model="addForm.priority">
            <option value="P0">P0</option>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
          </select>
        </label>
      </div>
      <div class="action-group" style="justify-content: flex-end; margin-top: 8px">
        <button class="btn btn-secondary" @click="showAddForm = false">取消</button>
        <button
          class="btn btn-primary"
          :disabled="!addForm.title.trim() || !addForm.description.trim()"
          @click="submitAddForm"
        >
          确认添加 ({{ nextTpId }})
        </button>
      </div>
    </div>

    <div v-if="reviewResult?.review_notes.length" class="review-notes">
      <div class="sub-title">AI 审核建议</div>
      <div
        v-for="note in reviewResult.review_notes"
        :key="`${note.note_type}-${note.target_test_point_id}-${note.message}`"
        class="review-note"
      >
        <span class="pill pill-info">{{ note.note_type }}</span>
        <span>{{ note.message }}</span>
      </div>
    </div>

    <MindMapView
      v-if="mindmapMode === 'mindmap'"
      :api-base-url="apiBaseUrl"
      :platform="platform"
      :summary="summary"
      :functions="designResult.functions"
      :test-points="displayedPoints"
      :cases="[]"
      :integration-tests="[]"
    />

    <div v-else class="point-list">
      <div v-for="(points, mod) in groupedPoints" :key="mod" class="point-group">
        <div class="point-group-header" @click="toggleCollapse(mod)">
          <div class="point-group-left">
            <span class="point-group-arrow" :class="{ collapsed: collapsedModules[mod] }">&#9662;</span>
            <input
              type="checkbox"
              :checked="isGroupAllSelected(points)"
              @click.stop="toggleGroup(points)"
            />
            <strong>{{ mod }}</strong>
          </div>
          <div class="point-group-stats">
            <span>{{ groupStats(points).selected }}/{{ groupStats(points).total }} 选中</span>
            <span v-if="groupStats(points).highRisk" class="pill pill-danger pill-sm">
              {{ groupStats(points).highRisk }} 高风险
            </span>
          </div>
        </div>

        <div v-show="!collapsedModules[mod]" class="point-group-body">
          <label v-for="point in points" :key="point.id" class="point-card">
            <input
              :checked="selectedIds.includes(point.id)"
              type="checkbox"
              @change="emit('togglePoint', point.id)"
            />
            <div class="point-card-body">
              <div class="point-card-top">
                <strong>{{ point.title }}</strong>
                <div class="point-badges">
                  <span class="pill">{{ categoryLabels[point.category] }}</span>
                  <span class="pill" :class="point.risk_level === 'high' ? 'pill-danger' : 'pill-info'">
                    {{ point.risk_level }}
                  </span>
                  <span class="pill">{{ point.priority }}</span>
                  <button
                    v-if="point.source === '人工添加'"
                    class="btn-icon-delete"
                    title="删除测试点"
                    @click.prevent="emit('removePoint', point.id)"
                  >
                    &times;
                  </button>
                </div>
              </div>
              <p>{{ point.description }}</p>
              <div class="point-source">来源：{{ point.source }}</div>
            </div>
          </label>
        </div>
      </div>
    </div>
  </section>
</template>
