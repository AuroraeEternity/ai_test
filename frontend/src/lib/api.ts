import type {
  ClarificationAnswer,
  ClarifyResponse,
  GenerateCasesResponse,
  GenerateTestPointsResponse,
  HistoryRecord,
  MetaResponse,
  ReviewTestPointsResponse,
  StructuredSummary,
  TestPoint,
} from '../types/workflow'
import type { Platform, TaskFormState } from '../types/workflow'

const extractErrorMessage = async (response: Response, fallback: string) => {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') return payload.detail
    if (Array.isArray(payload.detail)) return fallback
    return fallback
  } catch {
    return fallback
  }
}

const requestJson = async <T>(input: string, init: RequestInit, fallback: string): Promise<T> => {
  const response = await fetch(input, init)
  if (!response.ok) throw new Error(await extractErrorMessage(response, fallback))
  return response.json() as Promise<T>
}

export const createWorkflowApi = (baseUrl: string) => ({
  async getMeta(): Promise<MetaResponse> {
    return requestJson<MetaResponse>(`${baseUrl}/api/meta`, { method: 'GET' }, '获取平台配置失败')
  },

  async uploadPdf(file: File): Promise<{ text: string; pages: number }> {
    const formData = new FormData()
    formData.append('file', file)
    return requestJson<{ text: string; pages: number }>(
      `${baseUrl}/api/upload-pdf`,
      { method: 'POST', body: formData },
      'PDF 解析失败',
    )
  },

  async clarify(form: TaskFormState, clarificationAnswers: ClarificationAnswer[]): Promise<ClarifyResponse> {
    return requestJson<ClarifyResponse>(
      `${baseUrl}/api/workflow/clarify`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: form.platform,
          project: form.project,
          requirement_text: form.requirementText,
          actors: splitLines(form.actors),
          preconditions: splitLines(form.preconditions),
          business_rules: splitLines(form.businessRules),
          clarification_answers: clarificationAnswers,
        }),
      },
      '需求解析失败',
    )
  },

  async generateTestPoints(
    platform: Platform,
    summary: StructuredSummary,
    clarificationAnswers: ClarificationAnswer[],
  ): Promise<GenerateTestPointsResponse> {
    return requestJson<GenerateTestPointsResponse>(
      `${baseUrl}/api/workflow/generate-test-points`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          summary,
          clarification_answers: clarificationAnswers,
        }),
      },
      '测试点生成失败',
    )
  },

  async reviewTestPoints(
    platform: Platform,
    summary: StructuredSummary,
    clarificationAnswers: ClarificationAnswer[],
    testPoints: TestPoint[],
  ): Promise<ReviewTestPointsResponse> {
    return requestJson<ReviewTestPointsResponse>(
      `${baseUrl}/api/workflow/review-test-points`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          summary,
          clarification_answers: clarificationAnswers,
          test_points: testPoints,
        }),
      },
      '测试点审核失败',
    )
  },

  async generateCaseSuite(
    platform: Platform,
    summary: StructuredSummary,
    functions: string[],
    flows: string[],
    moduleSegments: Record<string, string>,
    selectedTestPoints: TestPoint[],
  ): Promise<GenerateCasesResponse> {
    return requestJson<GenerateCasesResponse>(
      `${baseUrl}/api/workflow/generate-cases`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          summary,
          functions,
          flows,
          module_segments: moduleSegments,
          selected_test_points: selectedTestPoints,
        }),
      },
      '测试用例生成失败',
    )
  },

  async listHistory(): Promise<HistoryRecord[]> {
    return requestJson<HistoryRecord[]>(`${baseUrl}/api/history`, { method: 'GET' }, '获取历史记录失败')
  },

  async saveHistory(record: HistoryRecord): Promise<HistoryRecord> {
    return requestJson<HistoryRecord>(
      `${baseUrl}/api/history`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record),
      },
      '保存历史记录失败',
    )
  },

  async deleteHistory(id: string): Promise<void> {
    await requestJson<{ status: string }>(
      `${baseUrl}/api/history/${id}`,
      { method: 'DELETE' },
      '删除历史记录失败',
    )
  },
})

export const splitLines = (value: string) =>
  value
    .split(/\n|,|，/)
    .map(item => item.trim())
    .filter(Boolean)
