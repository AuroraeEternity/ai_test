# AI Test Platform

一个面向测试工程师的 AI 测试平台 MVP。

当前版本先聚焦 `功能测试用例生成`，并支持根据平台类型 `Web / App` 输出针对性的测试点和测试用例。

## 当前流程
产品流程按照你前面确认的链路落地：

1. 选择平台
2. 输入需求
3. AI 解析需求
4. 补充平台特性测试点
5. 输出待确认问题
6. 生成测试点
7. 用户确认测试点
8. 生成测试用例

## 项目结构
```text
ai_test/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── config.py         # 配置项
│   │   ├── main.py           # API 入口
│   │   ├── models.py         # Pydantic 模型
│   │   ├── prompts.py        # Prompt 模板
│   │   └── services/
│   │       ├── llm.py        # OpenAI 兼容 LLM 客户端
│   │       └── workflow_service.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # Vue 3 + Vite 前端
│   └── src/
│       ├── App.vue           # 单页工作台
│       └── style.css         # 界面样式
└── README.md
```

## 后端能力
后端当前提供 3 个接口：

- `GET /health`
- `GET /api/meta`
- `POST /api/workflow/analyze`
- `POST /api/workflow/generate-cases`

当前版本必须接入 `OpenAI 兼容` 的真实大模型接口后才能运行工作流。
如果模型配置缺失、调用失败或返回 JSON 不符合约束，接口会直接报错，不再做本地兜底生成。

当前默认按 `Google AI Studio / Gemini API` 配置。

如果需要接入真实大模型，可以在 `backend/.env` 中配置：

- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_TEMPERATURE`

示例：

```bash
LLM_PROVIDER=gemini
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=60
LLM_TEMPERATURE=0.2
```

说明：

- `LLM_API_KEY` 使用你在 Google AI Studio 申请的 Gemini API Key
- `LLM_BASE_URL` 使用 Gemini OpenAI 兼容地址
- 当前代码已针对 Gemini 的 JSON 返回做了兼容处理

## 前端能力
前端当前是一个工作台式单页界面，包含：

- 平台选择
- 需求输入
- AI 解析结果展示
- 待确认问题展示
- 测试点勾选
- 测试用例结果展示
- Prompt 预览

## 本地启动
### 1. 启动后端
```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
cp .env.example .env
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动前请先编辑 `backend/.env`，填入真实模型提供方、API Key、Base URL 和模型名称。

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev
```

默认前端访问后端地址：

- `http://127.0.0.1:8000`

如果你后续想改前端 API 地址，可以新增 `frontend/.env`：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 已完成的 MVP 设计要点
- 先做结构化需求解析，再生成测试用例
- 先输出待确认问题，避免黑盒生成
- 先产出测试点，再产出测试用例
- 根据 `Web / App` 平台特性补充专项测试点
- 测试用例使用统一结构化模板输出
- 生成后增加基础校验结果展示

## 后续可继续扩展
- 增加历史缺陷 / 优质用例知识库
- 增加导出 Excel / Markdown / JSON
- 增加人工编辑与审批流
- 增加接口测试用例生成链路