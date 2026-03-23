<script setup lang="ts">
import type { HistoryRecord } from '../types/workflow'

defineProps<{
  records: HistoryRecord[]
  activeId: string | null
  taskActive: boolean
}>()

const emit = defineEmits<{
  goHome: []
  newTask: []
  selectRecord: [record: HistoryRecord]
  deleteRecord: [id: string]
}>()

const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })
</script>

<template>
  <aside class="app-sidebar">
    <div class="sidebar-logo" @click="emit('goHome')">
      <span>AI Test</span>
      <span class="status-dot online"></span>
    </div>

    <nav class="sidebar-nav">
      <button class="nav-item" :class="{ active: !taskActive }" @click="emit('goHome')">
        <span>产品首页</span>
      </button>
      <button class="nav-item" :class="{ active: taskActive }" @click="emit('newTask')">
        <span>新建任务</span>
      </button>
    </nav>

    <div class="nav-dropdown">
      <div class="dropdown-label">历史记录</div>
      <div v-if="records.length === 0" class="dropdown-empty">暂无记录</div>
      <div
        v-for="record in records"
        :key="record.id"
        class="dropdown-history-item"
        :class="{ active: activeId === record.id }"
        @click="emit('selectRecord', record)"
      >
        <div class="dropdown-history-content">
          <div class="dropdown-history-title">{{ record.title || '未命名任务' }}</div>
          <div class="dropdown-history-meta">
            <span>{{ record.platform.toUpperCase() }}</span>
            <span>{{ record.cases_count }}条</span>
            <span>{{ formatTime(record.timestamp) }}</span>
          </div>
        </div>
        <button class="dropdown-history-delete" @click.stop="emit('deleteRecord', record.id)" title="删除">
          &times;
        </button>
      </div>
    </div>
  </aside>
</template>
