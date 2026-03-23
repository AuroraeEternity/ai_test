<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import MindElixir from 'mind-elixir'
import 'mind-elixir/style.css'
import type { IntegrationTest, StructuredSummary, TestCase, TestPoint } from '../types/workflow'

interface MindMapNode {
  topic: string
  children?: MindMapNode[]
}

const props = defineProps<{
  apiBaseUrl: string
  platform: string
  summary: StructuredSummary
  functions: string[]
  testPoints: TestPoint[]
  cases: TestCase[]
  integrationTests: IntegrationTest[]
}>()

const containerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
const copied = ref(false)
let meInstance: InstanceType<typeof MindElixir> | null = null
let cachedRoot: MindMapNode | null = null
let cachedKey = ''

function nodeToText(node: MindMapNode, depth = 0): string {
  let text = `${'\t'.repeat(depth)}${node.topic}\n`
  for (const child of node.children || []) {
    text += nodeToText(child, depth + 1)
  }
  return text
}

async function copyMindMap() {
  if (!cachedRoot) return
  const text = nodeToText(cachedRoot).trimEnd()
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

function buildCacheKey(): string {
  const caseIds = props.cases.map(c => c.id || '').join(',')
  const itIds = props.integrationTests.map(t => t.id || '').join(',')
  return `${props.platform}|${caseIds}|${itIds}`
}

function convertToMindElixirData(node: MindMapNode, id = 'root', depth = 0): Record<string, unknown> {
  return {
    topic: node.topic,
    id,
    ...(id === 'root' ? { root: true } : {}),
    ...(depth === 1 ? { direction: parseInt(id.split('-')[1]) % 2 === 0 ? 0 : 1 } : {}),
    children: (node.children || []).map((child, i) =>
      convertToMindElixirData(child, `${id}-${i}`, depth + 1)
    ),
  }
}

async function loadMindMap(forceRefresh = false) {
  const key = buildCacheKey()
  if (!forceRefresh && cachedRoot && cachedKey === key) {
    renderMindMap(cachedRoot)
    return
  }

  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${props.apiBaseUrl}/api/workflow/mindmap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: props.platform,
        summary: props.summary,
        functions: props.functions,
        test_points: props.testPoints,
        cases: props.cases,
        integration_tests: props.integrationTests,
      }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || '思维导图生成失败')
    }
    const data = await res.json()
    cachedRoot = data.root
    cachedKey = key
    renderMindMap(data.root)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '思维导图生成失败'
  } finally {
    loading.value = false
  }
}

function renderMindMap(root: MindMapNode) {
  if (!containerRef.value) return
  if (meInstance) {
    meInstance.destroy()
    meInstance = null
  }

  const nodeData = convertToMindElixirData(root)

  meInstance = new MindElixir({
    el: containerRef.value,
    direction: MindElixir.SIDE,
    draggable: true,
    editable: false,
    contextMenu: false,
    toolBar: true,
    keypress: false,
  } as ConstructorParameters<typeof MindElixir>[0])

  meInstance.init({ nodeData } as unknown as Parameters<typeof meInstance.init>[0])
}

onMounted(() => nextTick(loadMindMap))

watch(
  () => [props.cases, props.integrationTests],
  () => {
    cachedRoot = null
    cachedKey = ''
    nextTick(loadMindMap)
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (meInstance) {
    meInstance.destroy()
    meInstance = null
  }
})
</script>

<template>
  <div class="mindmap-wrapper">
    <div v-if="loading" class="mindmap-loading">
      <div class="mindmap-spinner"></div>
      <span>正在生成测试设计思维导图...</span>
    </div>
    <div v-else-if="error" class="mindmap-error">
      <span>{{ error }}</span>
      <button class="mindmap-retry" @click="loadMindMap(true)">重试</button>
    </div>
    <div v-show="!loading && !error" class="mindmap-content">
      <button class="mindmap-copy-btn" :class="{ copied }" @click="copyMindMap" :disabled="!cachedRoot" :title="copied ? '已复制' : '复制为文本'">
        <svg v-if="!copied" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
        <svg v-else width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        {{ copied ? '已复制' : '复制' }}
      </button>
      <div class="mindmap-container" ref="containerRef"></div>
    </div>
  </div>
</template>

<style scoped>
.mindmap-wrapper {
  width: 100%;
  min-height: 500px;
  position: relative;
}
.mindmap-container {
  width: 100%;
  height: 600px;
  border: 1px solid var(--border-color, #E2E8F0);
  border-radius: 8px;
  overflow: hidden;
  background: #FAFBFC;
}
.mindmap-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 400px;
  color: #64748B;
  font-size: 14px;
}
.mindmap-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #E2E8F0;
  border-top-color: #4F46E5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.mindmap-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 400px;
  color: #EF4444;
  font-size: 14px;
}
.mindmap-retry {
  padding: 6px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  background: white;
  color: #4F46E5;
  font-size: 13px;
  cursor: pointer;
}
.mindmap-retry:hover {
  background: #EEF2FF;
}
.mindmap-content {
  position: relative;
}
.mindmap-copy-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  background: rgba(255,255,255,0.92);
  color: #475569;
  font-size: 12px;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: all 0.15s ease;
}
.mindmap-copy-btn:hover {
  background: #EEF2FF;
  color: #4F46E5;
  border-color: #C7D2FE;
}
.mindmap-copy-btn.copied {
  background: #F0FDF4;
  color: #16A34A;
  border-color: #BBF7D0;
}
.mindmap-copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
