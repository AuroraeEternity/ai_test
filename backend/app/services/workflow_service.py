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
    IntegrationTestsLLMOutput,
    IntegrationTestsRequest,
    IntegrationTestsResponse,
    MetaResponse,
    PlatformOption,
    PlatformType,
    ReviewTestPointsLLMOutput,
    ReviewTestPointsRequest,
    ReviewTestPointsResponse,
    ReviewNote,
    RiskLevel,
    TestPoint,
    TestCase,
    ValidationIssue,
)
from ..prompts import (
    build_analysis_system_prompt,
    build_analysis_user_prompt,
    build_case_system_prompt,
    build_case_user_prompt,
    build_integration_system_prompt,
    build_integration_user_prompt,
    build_review_system_prompt,
    build_review_user_prompt,
)
from .llm import LLMService


class WorkflowService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = LLMService(self.settings)

    # ------------------------------------------------------------------ #
    # Stage 1-3: 结构分析 + 缺失检查 + 模块拆分（合并为一次 LLM 调用）
    # ------------------------------------------------------------------ #
    async def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        system_prompt = build_analysis_system_prompt()
        user_prompt = build_analysis_user_prompt(payload)
        llm_output = await self._analyze_with_llm(system_prompt, user_prompt)

        return AnalyzeResponse(
            platform=payload.platform,
            summary=llm_output.summary,
            functions=llm_output.functions,
            flows=llm_output.flows,
            module_segments=llm_output.module_segments,
            clarification_questions=llm_output.clarification_questions,
            coverage_dimensions=llm_output.coverage_dimensions,
            test_points=llm_output.test_points,
            prompts={
                "analysis_system_prompt": system_prompt,
                "analysis_user_prompt": user_prompt,
                "execution_mode": "llm",
            },
        )

    # ------------------------------------------------------------------ #
    # Stage 4: 测试点审核
    # ------------------------------------------------------------------ #
    async def review_test_points(self, payload: ReviewTestPointsRequest) -> ReviewTestPointsResponse:
        system_prompt = build_review_system_prompt()
        user_prompt = build_review_user_prompt(payload)
        llm_output = await self._review_test_points_with_llm(system_prompt, user_prompt)

        return ReviewTestPointsResponse(
            platform=payload.platform,
            reviewed_test_points=self._normalize_reviewed_test_points(llm_output.reviewed_test_points),
            review_notes=llm_output.review_notes,
            prompts={
                "review_system_prompt": system_prompt,
                "review_user_prompt": user_prompt,
                "execution_mode": "llm",
            },
        )

    # ------------------------------------------------------------------ #
    # Stage 5: 模块/功能测试用例生成
    # ------------------------------------------------------------------ #
    async def generate_cases(self, payload: GenerateCasesRequest) -> GenerateCasesResponse:
        system_prompt = build_case_system_prompt()
        user_prompt = build_case_user_prompt(payload)
        llm_output = await self._generate_cases_with_llm(system_prompt, user_prompt)
        cases = self._normalize_cases(payload, llm_output.cases)
        validation_issues = llm_output.validation_issues
        validation_issues = validation_issues + self._validate_cases(cases, payload.selected_test_points, payload.platform)

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

    # ------------------------------------------------------------------ #
    # Stage 6: 流程联动测试生成
    # ------------------------------------------------------------------ #
    async def generate_integration_tests(self, payload: IntegrationTestsRequest) -> IntegrationTestsResponse:
        system_prompt = build_integration_system_prompt()
        user_prompt = build_integration_user_prompt(payload)
        llm_output = await self._generate_integration_tests_with_llm(system_prompt, user_prompt)

        tests = llm_output.integration_tests
        for idx, test in enumerate(tests, start=1):
            if not test.id:
                test.id = f"IT-{idx:03d}"

        return IntegrationTestsResponse(
            platform=payload.platform,
            integration_tests=tests,
            prompts={
                "integration_system_prompt": system_prompt,
                "integration_user_prompt": user_prompt,
                "execution_mode": "llm",
            },
        )

    # ------------------------------------------------------------------ #
    # Meta
    # ------------------------------------------------------------------ #
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
                PlatformOption(
                    label="插件",
                    value=PlatformType.PLUGIN,
                    description="适合浏览器插件、IDE 插件、编辑器扩展等",
                ),
            ],
            workflow_steps=[
                "选择平台",
                "输入需求",
                "AI 结构分析",
                "缺失检查与澄清",
                "审核测试点",
                "生成功能用例",
                "流程联动测试",
            ],
        )

    # ================================================================== #
    # Internal LLM wrappers
    # ================================================================== #

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

    async def _review_test_points_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ReviewTestPointsLLMOutput:
        raw_result = await self.llm_service.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=ReviewTestPointsLLMOutput.model_json_schema(),
        )
        result = ReviewTestPointsLLMOutput.model_validate(raw_result)
        if not result.reviewed_test_points:
            raise ValueError("LLM 未返回 reviewed_test_points。")
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

    async def _generate_integration_tests_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> IntegrationTestsLLMOutput:
        raw_result = await self.llm_service.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=IntegrationTestsLLMOutput.model_json_schema(),
        )
        result = IntegrationTestsLLMOutput.model_validate(raw_result)
        if not result.integration_tests:
            raise ValueError("LLM 未返回任何流程联动测试场景。")
        return result

    # ================================================================== #
    # Normalization & Validation helpers
    # ================================================================== #

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

    def _normalize_reviewed_test_points(self, test_points: list[TestPoint]) -> list[TestPoint]:
        normalized_test_points: list[TestPoint] = []

        for index, test_point in enumerate(test_points, start=1):
            if not test_point.id:
                test_point.id = f"tp-{index}"
            normalized_test_points.append(test_point)

        return normalized_test_points

    def _validate_cases(
        self,
        cases: list[TestCase],
        selected_test_points: list[TestPoint],
        platform: PlatformType,
    ) -> list[ValidationIssue]:
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
            if not case.preconditions:
                issues.append(
                    ValidationIssue(
                        issue_type="completeness",
                        message=f"{case.id} 缺少前置条件。",
                        severity=RiskLevel.MEDIUM,
                    )
                )
            if len(case.steps) < 2:
                issues.append(
                    ValidationIssue(
                        issue_type="executability",
                        message=f"{case.id} 的测试步骤过少，建议补充可执行操作。",
                        severity=RiskLevel.HIGH,
                    )
                )
            if len(case.expected_results) < 2:
                issues.append(
                    ValidationIssue(
                        issue_type="executability",
                        message=f"{case.id} 的预期结果过少，建议补充可断言结果。",
                        severity=RiskLevel.HIGH,
                    )
                )
            if not case.requirement_refs:
                issues.append(
                    ValidationIssue(
                        issue_type="traceability",
                        message=f"{case.id} 缺少 requirement_refs，无法回溯到需求或测试点。",
                        severity=RiskLevel.MEDIUM,
                    )
                )
            if platform.value not in case.coverage_tags:
                issues.append(
                    ValidationIssue(
                        issue_type="platform",
                        message=f"{case.id} 缺少平台标签 {platform.value}。",
                        severity=RiskLevel.MEDIUM,
                    )
                )

        selected_ids = {item.id for item in selected_test_points}
        generated_ids = {case.source_test_point_id for case in cases}
        missing_ids = selected_ids - generated_ids
        for missing_id in missing_ids:
            issues.append(
                ValidationIssue(
                    issue_type="coverage",
                    message=f"测试点 {missing_id} 未生成对应测试用例。",
                    severity=RiskLevel.HIGH,
                )
            )
        return issues
