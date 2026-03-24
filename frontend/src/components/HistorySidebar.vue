<script setup lang="ts">
import { ref } from 'vue'
import type { HistoryRecord } from '../types/workflow'

defineProps<{
  records: HistoryRecord[]
  activeId: string | null
  taskActive: boolean
}>()

const emit = defineEmits<{
  goHome: []
  newTask: []
  enterWorkflow: []
  selectRecord: [record: HistoryRecord]
  deleteRecord: [id: string]
}>()

const historyExpanded = ref(true)
</script>

<template>
  <aside class="app-sidebar">
    <div class="sidebar-logo" @click="emit('goHome')">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--primary); flex-shrink:0">
        <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/>
      </svg>
      <span>AI Test</span>
      <span class="status-dot online" style="margin-left: auto;"></span>
    </div>

    <nav class="sidebar-nav">
      <button class="nav-item" :class="{ active: !taskActive }" @click="emit('goHome')">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        <span>首页</span>
      </button>
    </nav>

    <div class="sidebar-section">
      <!-- AI 生成测试用例 folder -->
      <div class="sidebar-folder-row">
        <button class="sidebar-folder-label" :class="{ active: taskActive }" @click="emit('enterWorkflow')">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 4h6l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>
          </svg>
          <span>AI 生成测试用例</span>
        </button>
        <button class="folder-icon-btn folder-new-icon" title="新建任务" @click="emit('newTask')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
        <button class="folder-icon-btn" @click="historyExpanded = !historyExpanded">
          <svg :class="{ expanded: historyExpanded }" class="folder-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>

      <div v-if="historyExpanded" class="folder-body">
        <div class="folder-history">
          <div v-if="records.length === 0" class="folder-empty">暂无历史记录</div>
          <div
            v-for="record in records"
            :key="record.id"
            class="folder-record"
            :class="{ active: activeId === record.id }"
            @click="emit('selectRecord', record)"
          >
            <div class="folder-record-inner">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0; margin-top:2px; color: var(--text-faint)">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <div class="folder-record-content">
                <div class="folder-record-title">{{ record.title || '未命名任务' }}</div>
                <div class="folder-record-meta">
                  <span>{{ record.platform.toUpperCase() }}</span>
                  <span>{{ record.cases_count }}条</span>
                </div>
              </div>
            </div>
            <button class="folder-record-delete" @click.stop="emit('deleteRecord', record.id)" title="删除">
              &times;
            </button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
