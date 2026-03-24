<script setup lang="ts">
import { ref } from 'vue'
import type { MetaResponse, TaskFormState } from '../types/workflow'

const props = defineProps<{
  form: TaskFormState
  meta: MetaResponse
  loading: boolean
  uploadingPdf: boolean
  pdfFileName: string
}>()

const emit = defineEmits<{
  submit: []
  uploadPdf: [file: File]
}>()

const showAdvanced = ref(false)

const onFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('uploadPdf', file)
  input.value = ''
}

const clearPdf = () => {
  props.form.requirementText = ''
}

const canSubmit = () => props.form.requirementText.trim().length > 0 && !props.loading
</script>

<template>
  <div class="ri-layout">

    <!-- Header -->
    <div class="ri-header">
      <div class="ri-eyebrow">Step 1 · 需求输入</div>
      <h2 class="ri-title">描述你要测试的需求</h2>
      <p class="ri-subtitle">粘贴 PRD 文本或上传 PDF，AI 将自动解析并提炼结构化摘要</p>
    </div>

    <!-- Config row: Platform only -->
    <div class="ri-config-row">
      <span class="ri-config-label">平台</span>
      <div class="ri-seg-ctrl">
        <button
          v-for="p in meta.platforms"
          :key="p.value"
          class="ri-seg-btn"
          :class="{ active: form.platform === p.value }"
          :title="p.description"
          @click="form.platform = p.value"
        >
          {{ p.label }}
        </button>
      </div>
      <span class="ri-platform-desc-text">
        {{ meta.platforms.find(p => p.value === form.platform)?.description }}
      </span>
    </div>

    <!-- Requirement Input -->
    <div class="ri-req-block">
      <div class="ri-req-toolbar">
        <span class="ri-req-label">
          需求描述
          <span class="ri-req-required">必填</span>
        </span>
        <label class="ri-pdf-btn" :class="{ uploading: uploadingPdf }">
          <input type="file" accept=".pdf" @change="onFileChange" :disabled="uploadingPdf" />
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          {{ uploadingPdf ? '解析 PDF 中…' : '上传 PDF' }}
        </label>
      </div>

      <div v-if="pdfFileName" class="ri-pdf-tag">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        {{ pdfFileName }}
        <button class="ri-pdf-remove" title="清除" @click="clearPdf">×</button>
      </div>

      <textarea
        class="ri-req-textarea"
        v-model="form.requirementText"
        rows="12"
        placeholder="粘贴 PRD 内容、用户故事、设计稿描述或任何需求文本…

示例：
用户可以通过邮箱和密码登录系统，支持记住登录状态 7 天，密码错误 5 次后锁定账号 30 分钟。"
      ></textarea>

      <div class="ri-req-footer">
        <span class="ri-char-count" :class="{ active: form.requirementText.length > 0 }">
          {{ form.requirementText.length }} 字
        </span>
      </div>
    </div>

    <!-- Advanced Toggle -->
    <button class="ri-advanced-toggle" @click="showAdvanced = !showAdvanced">
      <svg
        class="ri-toggle-arrow"
        :class="{ expanded: showAdvanced }"
        width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
      补充上下文信息
      <span class="ri-advanced-hint">角色 · 前置条件 · 业务规则（可选）</span>
    </button>

    <div v-if="showAdvanced" class="ri-advanced-panel">
      <!-- 项目 -->
      <label class="ri-adv-field" style="margin-bottom: 14px;">
        <span class="ri-adv-label">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 4h6l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>
          </svg>
          项目
        </span>
        <select class="ri-select" v-model="form.project" style="max-width: 240px;">
          <option value="">未指定</option>
          <option v-for="project in meta.projects" :key="project.value" :value="project.value">
            {{ project.label }}
          </option>
        </select>
      </label>

      <div class="ri-adv-grid">
        <label class="ri-adv-field">
          <span class="ri-adv-label">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            参与角色
          </span>
          <textarea
            class="ri-adv-textarea"
            v-model="form.actors"
            rows="4"
            placeholder="每行一个&#10;例：注册用户&#10;管理员"
          ></textarea>
        </label>

        <label class="ri-adv-field">
          <span class="ri-adv-label">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 11 12 14 22 4"/>
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
            </svg>
            前置条件
          </span>
          <textarea
            class="ri-adv-textarea"
            v-model="form.preconditions"
            rows="4"
            placeholder="每行一个&#10;例：用户已注册账号&#10;网络连接正常"
          ></textarea>
        </label>
      </div>

      <label class="ri-adv-field" style="margin-top: 14px;">
        <span class="ri-adv-label">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          补充业务规则
        </span>
        <textarea
          class="ri-adv-textarea"
          v-model="form.businessRules"
          rows="4"
          placeholder="补充边界规则、校验规则、特殊约束&#10;例：密码至少 8 位，包含数字和字母"
        ></textarea>
      </label>
    </div>

    <!-- Submit -->
    <div class="ri-submit-row">
      <button
        class="btn btn-primary ri-submit-btn"
        :disabled="!canSubmit()"
        @click="emit('submit')"
      >
        <svg v-if="!loading" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
        </svg>
        <svg v-else class="ri-spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
        {{ loading ? 'AI 解析中…' : '开始 AI 解析' }}
      </button>
      <p class="ri-submit-hint">AI 将自动提炼摘要、识别缺口，完成后进入第二步确认</p>
    </div>

  </div>
</template>
