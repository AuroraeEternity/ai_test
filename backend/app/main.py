from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateCasesRequest,
    GenerateCasesResponse,
    MetaResponse,
    ReviewTestPointsRequest,
    ReviewTestPointsResponse,
)
from .services.workflow_service import WorkflowService

settings = get_settings()
app = FastAPI(title=settings.app_name)
workflow_service = WorkflowService()

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


@app.post("/api/workflow/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return await workflow_service.analyze(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"需求解析失败：{exc}") from exc


@app.post("/api/workflow/generate-cases", response_model=GenerateCasesResponse)
async def generate_cases(payload: GenerateCasesRequest) -> GenerateCasesResponse:
    try:
        return await workflow_service.generate_cases(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"测试用例生成失败：{exc}") from exc


@app.post("/api/workflow/review-test-points", response_model=ReviewTestPointsResponse)
async def review_test_points(payload: ReviewTestPointsRequest) -> ReviewTestPointsResponse:
    try:
        return await workflow_service.review_test_points(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"测试点审核失败：{exc}") from exc
