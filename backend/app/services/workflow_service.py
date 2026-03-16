from __future__ import annotations

from collections import Counter

from ..config import get_settings
from ..models import (
    AnalyzeLLMOutput,
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateCasesLLMOutput,
    GenerateCasesRequest,
    GenerateCasesResponse,
    MetaResponse,
    PlatformOption,
    PlatformType,
    RiskLevel,
    TestCase,
    ValidationIssue,
)
from ..prompts import (
    build_analysis_system_prompt,
    build_analysis_user_prompt,
    build_case_system_prompt,
    build_case_user_prompt,
)
from .llm import LLMService


class WorkflowService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = LLMService(self.settings)

    async def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        system_prompt = build_analysis_system_prompt()
        user_prompt = build_analysis_user_prompt(payload)
        llm_output = await self._analyze_with_llm(system_prompt, user_prompt)

        return AnalyzeResponse(
            platform=payload.platform,
            summary=llm_output.summary,
            clarification_questions=llm_output.clarification_questions,
            coverage_dimensions=llm_output.coverage_dimensions,
            test_points=llm_output.test_points,
            prompts={
                "analysis_system_prompt": system_prompt,
                "analysis_user_prompt": user_prompt,
                "execution_mode": "llm",
            },
        )

    async def generate_cases(self, payload: GenerateCasesRequest) -> GenerateCasesResponse:
        system_prompt = build_case_system_prompt()
        user_prompt = build_case_user_prompt(payload)
        llm_output = await self._generate_cases_with_llm(system_prompt, user_prompt)
        cases = self._normalize_cases(payload, llm_output.cases)
        validation_issues = llm_output.validation_issues
        validation_issues = validation_issues + self._validate_cases(cases)

        return GenerateCasesResponse(
            platform=payload.platform,
            cases=cases,
            validation_issues=validation_issues,
            prompts={
                "case_system_prompt": system_prompt,
                "case_user_prompt": user_prompt,
                "execution_mode": "llm",
            },
        )

    def get_meta(self) -> MetaResponse:
        return MetaResponse(
            platforms=[
                PlatformOption(
                    label="Web",
                    value=PlatformType.WEB,
                    description="适合后台、官网、管理端、表单系统等页面型产品",
                ),
                PlatformOption(
                    label="App",
                    value=PlatformType.APP,
                    description="适合 iOS / Android 原生或混合应用场景",
                ),
            ],
            workflow_steps=[
                "选择平台",
                "输入需求",
                "AI 解析需求",
                "补充平台特性测试点",
                "确认歧义问题",
                "生成测试点",
                "确认测试点",
                "生成测试用例",
            ],
        )

    async def _analyze_with_llm(self, system_prompt: str, user_prompt: str) -> AnalyzeLLMOutput:
        raw_result = await self.llm_service.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=AnalyzeLLMOutput.model_json_schema(),
        )
        result = AnalyzeLLMOutput.model_validate(raw_result)
        if not result.coverage_dimensions:
            raise ValueError("LLM 未返回 coverage_dimensions。")
        if not result.test_points:
            raise ValueError("LLM 未返回 test_points。")
        return result

    async def _generate_cases_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> GenerateCasesLLMOutput:
        raw_result = await self.llm_service.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=GenerateCasesLLMOutput.model_json_schema(),
        )
        result = GenerateCasesLLMOutput.model_validate(raw_result)
        if not result.cases:
            raise ValueError("LLM 未返回任何测试用例。")
        return result

    def _normalize_cases(
        self,
        payload: GenerateCasesRequest,
        cases: list[TestCase],
    ) -> list[TestCase]:
        normalized_cases: list[TestCase] = []
        fallback_map = {item.id: item for item in payload.selected_test_points}

        for index, case in enumerate(cases, start=1):
            if not case.id:
                case.id = f"TC-{index:03d}"
            case.platform = payload.platform
            if not case.case_type:
                case.case_type = "functional"
            if case.source_test_point_id not in fallback_map and payload.selected_test_points:
                case.source_test_point_id = payload.selected_test_points[min(index - 1, len(payload.selected_test_points) - 1)].id
            normalized_cases.append(case)

        return normalized_cases

    def _validate_cases(self, cases: list[TestCase]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        duplicated_titles = [title for title, count in Counter(case.title for case in cases).items() if count > 1]
        for title in duplicated_titles:
            issues.append(
                ValidationIssue(
                    issue_type="duplicate",
                    message=f"存在重复用例标题：{title}",
                    severity=RiskLevel.MEDIUM,
                )
            )

        for case in cases:
            if len(case.expected_results) < 2:
                issues.append(
                    ValidationIssue(
                        issue_type="executability",
                        message=f"{case.id} 的预期结果过少，建议补充可断言结果。",
                        severity=RiskLevel.HIGH,
                    )
                )
        return issues

