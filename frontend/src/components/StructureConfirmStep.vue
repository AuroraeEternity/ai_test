<script setup lang="ts">
import type { AnalyzeStructureResponse } from '../types/workflow'

const props = defineProps<{
  structureResult: AnalyzeStructureResponse
  loading: boolean
}>()

const emit = defineEmits<{
  confirm: []
}>()
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">Step 3 · 结构确认</div>
        <h2>确认功能模块与业务流</h2>
        <p class="panel-subtitle">AI 已完成需求结构分析，请确认以下模块拆分和业务流是否合理。</p>
      </div>
    </div>

    <div class="structure-grid">
      <div class="structure-section">
        <div class="structure-label">功能模块（{{ structureResult.functions.length }}）</div>
        <div class="structure-tags">
          <span v-for="fn in structureResult.functions" :key="fn" class="structure-tag">{{ fn }}</span>
          <span v-if="structureResult.functions.length === 0" class="structure-empty">未识别到模块</span>
        </div>
      </div>

      <div class="structure-section">
        <div class="structure-label">业务流（{{ structureResult.flows.length }}）</div>
        <div class="structure-list">
          <div v-for="flow in structureResult.flows" :key="flow" class="structure-flow-item">{{ flow }}</div>
          <div v-if="structureResult.flows.length === 0" class="structure-empty">未识别到业务流</div>
        </div>
      </div>

      <div class="structure-section">
        <div class="structure-label">模块描述</div>
        <div class="structure-segments">
          <div v-for="(desc, name) in structureResult.module_segments" :key="name" class="structure-segment">
            <strong>{{ name }}</strong>
            <p>{{ desc }}</p>
          </div>
          <div v-if="Object.keys(structureResult.module_segments).length === 0" class="structure-empty">无模块描述</div>
        </div>
      </div>

      <div v-if="structureResult.coverage_dimensions.length" class="structure-section">
        <div class="structure-label">覆盖维度</div>
        <div class="structure-tags">
          <span v-for="dim in structureResult.coverage_dimensions" :key="dim" class="structure-tag structure-tag--dim">{{ dim }}</span>
        </div>
      </div>
    </div>

    <div class="structure-actions">
      <button
        class="btn btn-primary"
        :disabled="loading || structureResult.functions.length === 0"
        @click="emit('confirm')"
      >
        {{ loading ? '生成测试点中…' : '确认结构，生成测试点' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.panel-subtitle {
  color: var(--text-secondary, #64748b);
  font-size: 13px;
  margin-top: 4px;
}
.structure-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 16px 0;
}
.structure-section {}
.structure-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  margin-bottom: 8px;
}
.structure-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.structure-tag {
  display: inline-block;
  padding: 4px 12px;
  background: var(--bg-subtle, #f1f5f9);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary, #334155);
}
.structure-tag--dim {
  background: #eff6ff;
  color: #3b82f6;
}
.structure-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.structure-flow-item {
  padding: 8px 12px;
  background: var(--bg-subtle, #f8fafc);
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid var(--primary, #4f46e5);
}
.structure-segments {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.structure-segment {
  padding: 10px 14px;
  background: var(--bg-subtle, #f8fafc);
  border-radius: 8px;
  font-size: 13px;
}
.structure-segment strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary, #1e293b);
}
.structure-segment p {
  margin: 0;
  color: var(--text-secondary, #64748b);
  line-height: 1.5;
}
.structure-empty {
  color: var(--text-faint, #94a3b8);
  font-size: 13px;
}
.structure-actions {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}
</style>
