import logging
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateCasesRequest,
    GenerateCasesResponse,
    HistoryRecord,
    IntegrationTestsRequest,
    IntegrationTestsResponse,
    MetaResponse,
    MindMapRequest,
    MindMapResponse,
    ReviewTestPointsRequest,
    ReviewTestPointsResponse,
)
from .services.history_service import HistoryService
from .services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(title=settings.app_name)
workflow_service = WorkflowService()
history_service = HistoryService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta", response_model=MetaResponse)
async def get_meta() -> MetaResponse:
    return workflow_service.get_meta()


def _err_detail(label: str, exc: Exception) -> str:
    msg = str(exc) or f"{type(exc).__name__}: 请查看后端日志"
    return f"{label}：{msg}"


@app.post("/api/workflow/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return await workflow_service.analyze(payload)
    except Exception as exc:
        logger.error("analyze 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("需求解析失败", exc)) from exc


@app.post("/api/workflow/generate-cases", response_model=GenerateCasesResponse)
async def generate_cases(payload: GenerateCasesRequest) -> GenerateCasesResponse:
    try:
        return await workflow_service.generate_cases(payload)
    except Exception as exc:
        logger.error("generate-cases 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("测试用例生成失败", exc)) from exc


@app.post("/api/workflow/review-test-points", response_model=ReviewTestPointsResponse)
async def review_test_points(payload: ReviewTestPointsRequest) -> ReviewTestPointsResponse:
    try:
        return await workflow_service.review_test_points(payload)
    except Exception as exc:
        logger.error("review-test-points 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("测试点审核失败", exc)) from exc


@app.post("/api/workflow/integration-tests", response_model=IntegrationTestsResponse)
async def integration_tests(payload: IntegrationTestsRequest) -> IntegrationTestsResponse:
    try:
        return await workflow_service.generate_integration_tests(payload)
    except Exception as exc:
        logger.error("integration-tests 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("流程联动测试生成失败", exc)) from exc


@app.post("/api/workflow/mindmap", response_model=MindMapResponse)
async def generate_mindmap(payload: MindMapRequest) -> MindMapResponse:
    try:
        return await workflow_service.generate_mindmap(payload)
    except Exception as exc:
        logger.error("mindmap 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("思维导图生成失败", exc)) from exc


@app.get("/api/history", response_model=list[HistoryRecord])
async def list_history() -> list[HistoryRecord]:
    return history_service.list_records()


@app.post("/api/history", response_model=HistoryRecord)
async def save_history(record: HistoryRecord) -> HistoryRecord:
    return history_service.save_record(record)


@app.get("/api/history/{record_id}", response_model=HistoryRecord)
async def get_history(record_id: str) -> HistoryRecord:
    record = history_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@app.delete("/api/history/{record_id}")
async def delete_history(record_id: str) -> dict[str, str]:
    if not history_service.delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"status": "ok"}
