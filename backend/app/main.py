import logging
import traceback

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import (
    ClarifyRequest,
    ClarifyResponse,
    GenerateCasesRequest,
    GenerateCasesResponse,
    GenerateTestPointsRequest,
    GenerateTestPointsResponse,
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


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    try:
        raw = await file.read()
        if len(raw) < 100:
            raise HTTPException(status_code=400, detail="文件内容过小，可能不是有效的 PDF")
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > 50:
            raise HTTPException(status_code=400, detail=f"文件 {size_mb:.1f} MB，超过 50 MB 上限")
        logger.info("收到 PDF: %s, 大小: %.1f MB", file.filename, size_mb)

        doc = pymupdf.open(stream=raw, filetype="pdf")
        pages_text: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text)
        doc.close()

        if not pages_text:
            raise HTTPException(status_code=422, detail="PDF 中未提取到文本内容")
        extracted = "\n\n".join(pages_text)
        logger.info("PDF 文本提取完成: %d 页, %d 字符", len(pages_text), len(extracted))
        return {"text": extracted, "pages": len(pages_text)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("PDF 解析失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=_err_detail("PDF 解析失败", exc)) from exc


@app.post("/api/workflow/clarify", response_model=ClarifyResponse)
async def clarify(payload: ClarifyRequest) -> ClarifyResponse:
    try:
        return await workflow_service.clarify(payload)
    except Exception as exc:
        logger.error("clarify 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("需求澄清失败", exc)) from exc


@app.post("/api/workflow/generate-test-points", response_model=GenerateTestPointsResponse)
async def generate_test_points(payload: GenerateTestPointsRequest) -> GenerateTestPointsResponse:
    try:
        return await workflow_service.generate_test_points(payload)
    except Exception as exc:
        logger.error("generate-test-points 失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=_err_detail("测试点生成失败", exc)) from exc


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
