<script setup lang="ts">
import type { MetaResponse, TaskFormState } from '../types/workflow'

defineProps<{
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

const onFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('uploadPdf', file)
  input.value = ''
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <div class="panel-eyebrow">Step 1</div>
        <h2>需求输入</h2>
      </div>
      <button class="btn btn-primary" :disabled="loading || !form.requirementText.trim()" @click="emit('submit')">
        {{ loading ? '解析中...' : '开始解析' }}
      </button>
    </div>

    <div class="form-grid">
      <label class="field">
        <span>平台</span>
        <select v-model="form.platform">
          <option v-for="platform in meta.platforms" :key="platform.value" :value="platform.value">
            {{ platform.label }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>项目</span>
        <select v-model="form.project">
          <option value="">未指定</option>
          <option v-for="project in meta.projects" :key="project.value" :value="project.value">
            {{ project.label }}
          </option>
        </select>
      </label>
    </div>

    <label class="field">
      <span>需求描述</span>
      <textarea v-model="form.requirementText" rows="10" placeholder="粘贴 PRD、用户故事或测试需求描述"></textarea>
    </label>

    <div class="upload-row">
      <label class="upload-btn">
        <input type="file" accept=".pdf" @change="onFileChange" />
        {{ uploadingPdf ? '解析 PDF 中...' : '上传 PDF' }}
      </label>
      <span class="upload-hint" v-if="pdfFileName">{{ pdfFileName }}</span>
    </div>

    <div class="form-grid form-grid-advanced">
      <label class="field">
        <span>角色</span>
        <textarea v-model="form.actors" rows="4" placeholder="每行一个角色，或用逗号分隔"></textarea>
      </label>
      <label class="field">
        <span>前置条件</span>
        <textarea v-model="form.preconditions" rows="4" placeholder="每行一个前置条件"></textarea>
      </label>
    </div>

    <label class="field">
      <span>补充业务规则</span>
      <textarea v-model="form.businessRules" rows="4" placeholder="补充边界规则、校验规则、特殊约束"></textarea>
    </label>
  </section>
</template>
