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
    build_review_system_prompt,
    build_review_user_prompt,
)
from .llm import LLMService


class WorkflowService:
    def __init__(self) -> None:
        # 这里统一持有配置和 LLM 客户端，方便后续继续扩展知识库检索、
        # 审核器、导出器等流程组件，而不需要把初始化逻辑散落到接口层。
        self.settings = get_settings()
        self.llm_service = LLMService(self.settings)

    async def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        # analyze 阶段负责把原始需求转成结构化摘要、待确认问题和测试点。
        # 这一步是整个工作流的入口，后续前端展示和用例生成都依赖这里的输出。
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
        # generate_cases 阶段只消费已经确认过的测试点，
        # 不再重新理解需求，避免生成结果偏离用户已确认的范围。
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

    async def review_test_points(self, payload: ReviewTestPointsRequest) -> ReviewTestPointsResponse:
        # review_test_points 阶段专门用于“收敛”测试点质量，
        # 让最终进入用例生成阶段的输入更稳定、更完整。
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

    def get_meta(self) -> MetaResponse:
        # 这部分返回给前端固定元数据，用于渲染平台卡片和流程步骤条。
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
                "确认歧义问题",
                "审核测试点",
                "生成测试用例",
            ],
        )

    async def _analyze_with_llm(self, system_prompt: str, user_prompt: str) -> AnalyzeLLMOutput:
        # 先按 AnalyzeLLMOutput 的 schema 调用模型，再用 Pydantic 二次校验，
        # 防止模型返回结构看似正确但字段缺失、类型错误。
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
        # 用例生成和需求解析共用同一个 LLM 客户端，但使用不同 schema。
        # 这里要求模型必须返回 cases，否则直接视为失败，避免前端拿到空结果误判成功。
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
        # 模型输出的结构不一定完全可靠，这里做一次最小归一化：
        # 补默认 case_id、强制对齐平台字段，并尽量把用例重新挂回已选测试点。
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
        # 这里先做轻量级规则校验，主要拦截明显重复和不可执行结果。
        # 后续如果要增强质量，可以继续拆成重复检查器、完整性检查器等独立模块。
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

