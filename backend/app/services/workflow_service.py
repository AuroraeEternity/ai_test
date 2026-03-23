from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from ..config import get_settings
from ..models import (
    ClarificationGap,
    ClarificationQuestion,
    ClarifyLLMOutput,
    ClarifyRequest,
    ClarifyResponse,
    GenerateCasesLLMOutput,
    GenerateCasesRequest,
    GenerateCasesResponse,
    GenerateTestPointsLLMOutput,
    GenerateTestPointsRequest,
    GenerateTestPointsResponse,
    IntegrationTest,
    IntegrationTestsLLMOutput,
    IntegrationTestsRequest,
    IntegrationTestsResponse,
    MetaResponse,
    MindMapLLMOutput,
    MindMapRequest,
    MindMapResponse,
    PlatformOption,
    PlatformType,
    Priority,
    ProjectOption,
    RegressionSuite,
    ReviewTestPointsLLMOutput,
    ReviewNote,
    ReviewTestPointsRequest,
    ReviewTestPointsResponse,
    RiskLevel,
    TestCase,
    TestPoint,
    ValidationIssue,
)
from ..prompts import (
    build_case_system_prompt,
    build_case_user_prompt,
    build_clarify_system_prompt,
    build_clarify_user_prompt,
    build_generate_test_points_system_prompt,
    build_generate_test_points_user_prompt,
    build_integration_system_prompt,
    build_integration_user_prompt,
    build_mindmap_system_prompt,
    build_mindmap_user_prompt,
    build_review_system_prompt,
    build_review_user_prompt,
)
from .llm import LLMService

logger = logging.getLogger(__name__)


class WorkflowValidationError(ValueError):
    """客户端可修复的工作流校验错误。"""


class WorkflowService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = LLMService(self.settings)

    # ------------------------------------------------------------------ #
    # Step 1 — 需求澄清
    # ------------------------------------------------------------------ #

    async def clarify(self, payload: ClarifyRequest) -> ClarifyResponse:
        """
        将原始需求文本整理为结构化摘要，同时输出仍需 QA 确认的澄清问题。

        支持多轮澄清：每次调用时将已回答的问题通过 clarification_answers 传入，
        模型会基于已有回答更新摘要，并不再重复追问已解答的内容。

        temperature=0.1：摘要生成要求确定性强，避免随机发挥。
        """
        logger.info(
            "clarify 开始 | platform=%s project=%s 需求长度=%d 已有回答数=%d",
            payload.platform.value,
            payload.project or "未指定",
            len(payload.requirement_text),
            len(payload.clarification_answers),
        )

        system_prompt = build_clarify_system_prompt()
        user_prompt = build_clarify_user_prompt(payload)
        result = await self._run_llm(
            schema=ClarifyLLMOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            required_field="summary",
        )

        # 用已回答问题的数量推算当前是第几轮澄清（去重防止重复计算同一问题）
        round_num = len({answer.question_id for answer in payload.clarification_answers}) + 1

        logger.info(
            "clarify 完成 | round=%d 澄清问题数=%d",
            round_num,
            len(result.clarification_questions),
        )

        return ClarifyResponse(
            platform=payload.platform,
            summary=result.summary,
            clarification_questions=result.clarification_questions,
            missing_fields=result.missing_fields,
            resolved_fields=result.resolved_fields,
            remaining_risks=result.remaining_risks,
            round=round_num,
            prompts={
                "clarify_system_prompt": system_prompt,
                "clarify_user_prompt": user_prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # Step 2 — 测试点生成
    # ------------------------------------------------------------------ #

    async def generate_test_points(self, payload: GenerateTestPointsRequest) -> GenerateTestPointsResponse:
        """
        基于已经人工确认的需求摘要，生成测试设计初稿。

        输出包含：
        - functions：识别出的功能模块列表
        - flows：业务流名称列表（供后续联动测试使用）
        - module_segments：每个模块对应的需求片段描述
        - coverage_dimensions：覆盖维度说明
        - test_points：测试点列表（经过标准化处理）

        temperature=0.35：测试点生成需要一定的发散性以覆盖边界场景，
        但不能太高避免生成无关内容。
        """
        logger.info(
            "generate_test_points 开始 | platform=%s 摘要标题=%s",
            payload.platform.value,
            payload.summary.title,
        )
        self._ensure_blocking_questions_answered(payload.clarification_questions, payload.clarification_answers)

        system_prompt = build_generate_test_points_system_prompt()
        user_prompt = build_generate_test_points_user_prompt(payload)
        result = await self._run_llm(
            schema=GenerateTestPointsLLMOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
            required_field="test_points",
        )

        # 标准化：补全缺失的 id、function_module，修正优先级与风险等级不一致的情况
        test_points = self._normalize_test_points(result.test_points, result.functions)

        logger.info(
            "generate_test_points 完成 | 功能模块数=%d 业务流数=%d 测试点数=%d",
            len(result.functions),
            len(result.flows),
            len(test_points),
        )

        return GenerateTestPointsResponse(
            platform=payload.platform,
            functions=result.functions,
            flows=result.flows,
            module_segments=result.module_segments,
            coverage_dimensions=result.coverage_dimensions,
            test_points=test_points,
            prompts={
                "test_points_system_prompt": system_prompt,
                "test_points_user_prompt": user_prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # Step 3 — 测试点 AI 评审（可选）
    # ------------------------------------------------------------------ #

    async def review_test_points(self, payload: ReviewTestPointsRequest) -> ReviewTestPointsResponse:
        """
        对已有测试点做 AI 评审，输出优化后的测试点和评审说明。

        定位：辅助工具，而非强制门控。QA 可以选择性触发，
        评审结果仅供参考，最终以人工筛选为准。

        temperature=0.1：评审需要稳定、可复现的输出，避免每次结果差异过大。
        """
        logger.info(
            "review_test_points 开始 | platform=%s 待评审测试点数=%d",
            payload.platform.value,
            len(payload.test_points),
        )

        system_prompt = build_review_system_prompt()
        user_prompt = build_review_user_prompt(payload)
        result = await self._run_llm(
            schema=ReviewTestPointsLLMOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            required_field="reviewed_test_points",
        )

        # fallback_functions 从原始测试点中提取，确保标准化时 function_module 有兜底值
        reviewed = self._normalize_test_points(
            result.reviewed_test_points,
            [item.function_module for item in payload.test_points if item.function_module],
        )
        validation_issues = self._validate_review_notes(payload.test_points, reviewed, result.review_notes)

        logger.info(
            "review_test_points 完成 | 评审后测试点数=%d 评审备注数=%d",
            len(reviewed),
            len(result.review_notes),
        )

        return ReviewTestPointsResponse(
            platform=payload.platform,
            reviewed_test_points=reviewed,
            review_notes=result.review_notes,
            validation_issues=validation_issues,
            prompts={
                "review_system_prompt": system_prompt,
                "review_user_prompt": user_prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # Step 4 — 用例生成（含联动测试和回归集）
    # ------------------------------------------------------------------ #

    async def generate_cases(self, payload: GenerateCasesRequest) -> GenerateCasesResponse:
        """
        基于人工筛选后的测试点，生成三类测试资产：
        1. cases：功能测试用例，每条用例严格对应一个 source_test_point_id
        2. integration_tests：跨模块联动测试场景（仅在 flows 不为空时生成）
        3. regression_suites：按优先级和风险等级自动分级的回归测试集

        同时执行两阶段质量校验：
        - normalize 阶段：补全缺失字段、修正优先级继承
        - validate 阶段：检查格式、重复、完整性、可追溯性、覆盖率

        temperature=0.2：用例生成要求格式规范、内容确定，温度不宜过高。
        """
        logger.info(
            "generate_cases 开始 | platform=%s 选中测试点数=%d flows数=%d",
            payload.platform.value,
            len(payload.selected_test_points),
            len(payload.flows),
        )
        if not payload.selected_test_points:
            raise WorkflowValidationError("至少需要选择 1 个测试点后才能生成测试用例。")
        if not payload.functions:
            raise WorkflowValidationError("缺少功能模块信息，无法生成测试用例。")

        system_prompt = build_case_system_prompt()
        grouped_points = self._group_test_points_by_module(payload.selected_test_points)
        raw_cases: list[TestCase] = []
        prompt_bundle: dict[str, str] = {"case_system_prompt": system_prompt}
        for module_name, points in grouped_points.items():
            module_payload = GenerateCasesRequest(
                platform=payload.platform,
                summary=payload.summary,
                functions=[module_name],
                flows=payload.flows,
                module_segments={module_name: payload.module_segments.get(module_name, "")},
                selected_test_points=points,
            )
            user_prompt = build_case_user_prompt(module_payload)
            llm_output = await self._run_llm(
                schema=GenerateCasesLLMOutput,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                required_field="cases",
            )
            raw_cases.extend(llm_output.cases)
            prompt_bundle[f"case_user_prompt::{module_name}"] = user_prompt

        # normalize：补全 id、platform、function_module，继承测试点的 P0 优先级
        cases, normalize_issues = self._normalize_cases(payload, raw_cases)
        # validate：格式校验、重复检测、完整性检查、覆盖率检查
        validation_issues = normalize_issues + self._validate_cases(cases, payload.selected_test_points, payload.functions)

        logger.info(
            "generate_cases 用例生成完成 | 用例数=%d 质量问题数=%d",
            len(cases),
            len(validation_issues),
        )
        if validation_issues:
            logger.warning(
                "存在 %d 个质量问题 | high=%d medium=%d low=%d",
                len(validation_issues),
                sum(1 for i in validation_issues if i.severity == RiskLevel.HIGH),
                sum(1 for i in validation_issues if i.severity == RiskLevel.MEDIUM),
                sum(1 for i in validation_issues if i.severity == RiskLevel.LOW),
            )

        # 联动测试：只有当存在业务流时才生成，避免无意义的空调用
        integration_tests: list[IntegrationTest] = []
        integration_prompts: dict[str, str] = {}
        if payload.flows:
            logger.info("检测到 flows，开始生成联动测试")
            integration_payload = IntegrationTestsRequest(
                platform=payload.platform,
                summary=payload.summary,
                flows=payload.flows,
                reviewed_test_points=payload.selected_test_points,
                functional_case_titles=[item.title for item in cases],
            )
            integration_response = await self.generate_integration_tests(integration_payload)
            integration_tests = integration_response.integration_tests
            integration_prompts = integration_response.prompts
            validation_issues.extend(integration_response.validation_issues)
        else:
            logger.info("未检测到 flows，跳过联动测试生成")

        # 基于用例优先级和测试点风险等级，自动构建四个分级回归集
        regression_suites = self._build_regression_suites(cases, payload.selected_test_points, integration_tests)

        logger.info(
            "generate_cases 全部完成 | 用例数=%d 联动测试数=%d 回归集数=%d",
            len(cases),
            len(integration_tests),
            len(regression_suites),
        )

        return GenerateCasesResponse(
            platform=payload.platform,
            cases=cases,
            integration_tests=integration_tests,
            regression_suites=regression_suites,
            validation_issues=validation_issues,
            prompts={
                **prompt_bundle,
                **integration_prompts,
            },
        )

    # ------------------------------------------------------------------ #
    # 联动测试生成（也可独立调用）
    # ------------------------------------------------------------------ #

    async def generate_integration_tests(self, payload: IntegrationTestsRequest) -> IntegrationTestsResponse:
        """
        基于业务流生成跨模块联动测试场景。

        只覆盖跨模块、跨状态、恢复和授权类场景，
        不与单点功能用例重复（通过传入已有用例标题让模型感知）。

        temperature=0.35：联动场景需要一定发散性来覆盖复杂交互路径。
        """
        logger.info(
            "generate_integration_tests 开始 | platform=%s flows数=%d",
            payload.platform.value,
            len(payload.flows),
        )

        system_prompt = build_integration_system_prompt()
        user_prompt = build_integration_user_prompt(payload)
        result = await self._run_llm(
            schema=IntegrationTestsLLMOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
            required_field="integration_tests",
        )

        integration_tests = self._normalize_integration_tests(result.integration_tests)
        validation_issues = self._validate_integration_tests(integration_tests, payload.functional_case_titles)

        logger.info("generate_integration_tests 完成 | 联动测试数=%d", len(integration_tests))

        return IntegrationTestsResponse(
            platform=payload.platform,
            integration_tests=integration_tests,
            validation_issues=validation_issues,
            prompts={
                "integration_system_prompt": system_prompt,
                "integration_user_prompt": user_prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # 脑图生成
    # ------------------------------------------------------------------ #

    async def generate_mindmap(self, payload: MindMapRequest) -> MindMapResponse:
        """
        基于测试设计结果生成脑图数据结构。

        脑图按「功能模块 -> 测试维度 -> 测试点」三层组织，
        不作为主流程的强制门控，仅供可视化浏览使用。

        temperature=0.1：脑图结构要求稳定，减少随机性。
        """
        logger.info(
            "generate_mindmap 开始 | platform=%s 测试点数=%d 用例数=%d",
            payload.platform.value,
            len(payload.test_points),
            len(payload.cases),
        )

        system_prompt = build_mindmap_system_prompt()
        user_prompt = build_mindmap_user_prompt(payload)
        result = await self._run_llm(
            schema=MindMapLLMOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            required_field="root",
        )

        logger.info("generate_mindmap 完成 | 根节点=%s", result.root.topic)

        return MindMapResponse(
            root=result.root,
            prompts={
                "mindmap_system_prompt": system_prompt,
                "mindmap_user_prompt": user_prompt,
            },
        )

    # ------------------------------------------------------------------ #
    # 元数据
    # ------------------------------------------------------------------ #

    def get_meta(self) -> MetaResponse:
        """返回平台选项、项目选项和工作流步骤定义，供前端初始化使用。"""
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
            projects=[ProjectOption(label="Solvely", value="solvely")],
            workflow_steps=[
                "需求输入",
                "摘要确认",
                "测试设计",
                "测试点评审",
                "用例与回归资产",
            ],
        )

    # ------------------------------------------------------------------ #
    # 内部工具方法
    # ------------------------------------------------------------------ #

    async def _run_llm(
        self,
        *,
        schema: type,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        required_field: str,
    ) -> Any:
        """
        统一的 LLM 调用入口。

        职责：
        1. 调用 LLMService 获取原始 JSON
        2. 用 Pydantic schema 做结构验证
        3. 检查必填字段不为空，防止模型漏输出关键内容
        """
        raw_result = await self.llm_service.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=schema.model_json_schema(),
            temperature=temperature,
        )
        result = schema.model_validate(raw_result)
        value = getattr(result, required_field, None)
        if value in (None, [], {}):
            logger.error("LLM 输出缺失必填字段 | schema=%s required_field=%s", schema.__name__, required_field)
            raise ValueError(f"LLM 未返回有效的 {required_field}。")
        return result

    def _normalize_test_points(self, test_points: list[TestPoint], fallback_functions: list[str]) -> list[TestPoint]:
        """
        标准化测试点列表：
        - 补全缺失的 id（按 TP-001 格式递增）
        - 补全缺失的 function_module（使用第一个功能模块作为兜底）
        - 修正优先级：高风险测试点不应低于 P1，若模型给了 P2 则自动提升
        """
        normalized: list[TestPoint] = []
        fallback_function = fallback_functions[0] if fallback_functions else ""
        patched_priority_count = 0
        next_num = self._next_identifier_seed([item.id for item in test_points], r"^TP-(\d{3})$")
        seen_ids: set[str] = set()
        valid_functions = set(fallback_functions)

        for item in test_points:
            if not re.match(r"^TP-\d{3}$", item.id) or item.id in seen_ids:
                item.id = f"TP-{next_num:03d}"
                next_num += 1
            seen_ids.add(item.id)
            if not item.function_module or (valid_functions and item.function_module not in valid_functions):
                item.function_module = fallback_function
            # 高风险测试点优先级不能低于 P1
            if item.risk_level == RiskLevel.HIGH and item.priority == Priority.P2:
                item.priority = Priority.P1
                patched_priority_count += 1
            normalized.append(item)

        if patched_priority_count:
            logger.debug("_normalize_test_points | 自动提升优先级的测试点数=%d", patched_priority_count)

        return normalized

    def _normalize_cases(
        self,
        payload: GenerateCasesRequest,
        cases: list[TestCase],
    ) -> tuple[list[TestCase], list[ValidationIssue]]:
        """
        标准化用例列表，同时收集标准化过程中发现的问题：
        - 补全缺失的 id（按 TC-001 格式递增）
        - 补全 platform 字段
        - 补全缺失的 function_module（优先从对应测试点继承，否则使用第一个模块）
        - 继承优先级：若来源测试点为 P0，则用例也强制为 P0
        - 记录 traceability 问题：source_test_point_id 无法匹配已选测试点时告警
        """
        normalized_cases: list[TestCase] = []
        issues: list[ValidationIssue] = []
        # 构建测试点 id -> 测试点 的快速查找表
        point_map = {item.id: item for item in payload.selected_test_points}
        default_function = payload.functions[0] if payload.functions else ""
        next_num = self._next_identifier_seed([item.id for item in cases], r"^TC-(\d{3})$")
        seen_ids: set[str] = set()

        for case in cases:
            if not re.match(r"^TC-\d{3}$", case.id) or case.id in seen_ids:
                case.id = f"TC-{next_num:03d}"
                next_num += 1
            seen_ids.add(case.id)
            case.platform = payload.platform
            if not case.function_module:
                source_point = point_map.get(case.source_test_point_id)
                case.function_module = source_point.function_module if source_point else default_function
            if case.source_test_point_id in point_map:
                point = point_map[case.source_test_point_id]
                # P0 测试点对应的用例必须也是 P0，确保冒烟集不遗漏关键用例
                if point.priority == Priority.P0:
                    case.priority = Priority.P0
            else:
                logger.warning("用例 %s 的 source_test_point_id=%s 无法匹配已选测试点", case.id, case.source_test_point_id)
                issues.append(
                    ValidationIssue(
                        issue_type="traceability",
                        message=f"{case.id} 的 source_test_point_id 无法匹配已选测试点，请人工确认。",
                        severity=RiskLevel.HIGH,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            normalized_cases.append(case)

        return normalized_cases, issues

    def _validate_cases(
        self,
        cases: list[TestCase],
        selected_test_points: list[TestPoint],
        functions: list[str],
    ) -> list[ValidationIssue]:
        """
        对用例列表做质量校验，输出结构化问题列表。

        校验维度：
        - format：id 格式是否符合 TC-001 规范
        - duplicate：id 或标题是否重复
        - completeness：是否缺少前置条件
        - executability：步骤和预期结果是否过少（< 2 条）
        - traceability：是否缺少 requirement_refs
        - consistency：function_module 是否在合法模块列表内
        - coverage：是否有选中的测试点没有对应用例
        """
        issues: list[ValidationIssue] = []
        id_pattern = re.compile(r"^TC-\d{3}$")
        valid_functions = set(functions)
        seen_ids: set[str] = set()

        # 格式校验 + 重复 id 检测
        for case in cases:
            if not id_pattern.match(case.id):
                issues.append(
                    ValidationIssue(
                        issue_type="format",
                        message=f"{case.id} 的用例编号格式不符合 TC-001 规范。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if case.id in seen_ids:
                issues.append(
                    ValidationIssue(
                        issue_type="duplicate",
                        message=f"{case.id} 编号重复出现。",
                        severity=RiskLevel.HIGH,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            seen_ids.add(case.id)

        # 重复标题检测
        for title, count in Counter(item.title for item in cases).items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        issue_type="duplicate",
                        message=f"存在重复用例标题：{title}",
                        severity=RiskLevel.MEDIUM,
                        target_type="global",
                    )
                )

        # 完整性、可执行性、可追溯性、一致性校验
        for case in cases:
            if not case.preconditions:
                issues.append(
                    ValidationIssue(
                        issue_type="completeness",
                        message=f"{case.id} 缺少前置条件。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if len(case.steps) < 2:
                issues.append(
                    ValidationIssue(
                        issue_type="executability",
                        message=f"{case.id} 的步骤过少，建议补充可执行操作。",
                        severity=RiskLevel.HIGH,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if len(case.expected_results) < 2:
                issues.append(
                    ValidationIssue(
                        issue_type="executability",
                        message=f"{case.id} 的预期结果过少，建议补充可断言结果。",
                        severity=RiskLevel.HIGH,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if not case.requirement_refs:
                issues.append(
                    ValidationIssue(
                        issue_type="traceability",
                        message=f"{case.id} 缺少 requirement_refs，无法回溯到需求。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if not case.summary_refs:
                issues.append(
                    ValidationIssue(
                        issue_type="traceability",
                        message=f"{case.id} 缺少 summary_refs，无法定位到摘要结构中的来源片段。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if not case.source_origin:
                issues.append(
                    ValidationIssue(
                        issue_type="traceability",
                        message=f"{case.id} 缺少 source_origin，无法区分来自主流程、异常流程还是业务规则。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if not case.coverage_tags:
                issues.append(
                    ValidationIssue(
                        issue_type="coverage",
                        message=f"{case.id} 缺少 coverage_tags，无法表达覆盖维度。",
                        severity=RiskLevel.LOW,
                        target_type="case",
                        target_id=case.id,
                    )
                )
            if valid_functions and case.function_module and case.function_module not in valid_functions:
                issues.append(
                    ValidationIssue(
                        issue_type="consistency",
                        message=f"{case.id} 的 function_module 不在当前模块列表中。",
                        severity=RiskLevel.MEDIUM,
                        target_type="case",
                        target_id=case.id,
                    )
                )

        # 覆盖率检查：所有选中的测试点都必须有对应用例
        selected_ids = {item.id for item in selected_test_points}
        generated_ids = {case.source_test_point_id for case in cases}
        missing_ids = selected_ids - generated_ids
        if missing_ids:
            logger.warning("以下测试点未生成对应用例: %s", missing_ids)
        for missing_id in missing_ids:
            issues.append(
                ValidationIssue(
                    issue_type="coverage",
                    message=f"测试点 {missing_id} 尚未生成对应测试用例。",
                    severity=RiskLevel.HIGH,
                    target_type="test_point",
                    target_id=missing_id,
                )
            )

        logger.debug("_validate_cases 完成 | 发现问题数=%d", len(issues))
        return issues

    def _ensure_blocking_questions_answered(
        self,
        questions: list[ClarificationQuestion],
        answers: list,
    ) -> None:
        blocking_questions = [item for item in questions if item.blocking]
        if not blocking_questions:
            return
        answered_ids = {item.question_id for item in answers if item.answer.strip()}
        unanswered = [item.question for item in blocking_questions if item.id not in answered_ids]
        if unanswered:
            raise WorkflowValidationError(
                "仍存在未回答的阻塞性澄清问题，请先完成确认后再生成测试点："
                + "；".join(unanswered)
            )

    def _validate_review_notes(
        self,
        original_points: list[TestPoint],
        reviewed_points: list[TestPoint],
        review_notes: list[ReviewNote],
    ) -> list[ValidationIssue]:
        valid_ids = {item.id for item in original_points} | {item.id for item in reviewed_points}
        issues: list[ValidationIssue] = []
        for note in review_notes:
            if note.target_test_point_id and note.target_test_point_id not in valid_ids:
                issues.append(
                    ValidationIssue(
                        issue_type="reference",
                        message=f"评审备注 {note.note_type} 指向了不存在的测试点 {note.target_test_point_id}。",
                        severity=RiskLevel.MEDIUM,
                        target_type="review_note",
                        target_id=note.target_test_point_id,
                    )
                )
        return issues

    def _group_test_points_by_module(self, points: list[TestPoint]) -> dict[str, list[TestPoint]]:
        grouped: dict[str, list[TestPoint]] = {}
        for point in points:
            module_name = point.function_module or "未归类"
            grouped.setdefault(module_name, []).append(point)
        return grouped

    def _normalize_integration_tests(self, tests: list[IntegrationTest]) -> list[IntegrationTest]:
        next_num = self._next_identifier_seed([item.id for item in tests], r"^IT-(\d{3})$")
        seen_ids: set[str] = set()
        normalized: list[IntegrationTest] = []
        for test in tests:
            if not re.match(r"^IT-\d{3}$", test.id) or test.id in seen_ids:
                test.id = f"IT-{next_num:03d}"
                next_num += 1
            seen_ids.add(test.id)
            normalized.append(test)
        return normalized

    def _validate_integration_tests(
        self,
        tests: list[IntegrationTest],
        functional_case_titles: list[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        seen_ids: set[str] = set()
        seen_titles: set[str] = set()
        normalized_case_titles = {self._normalize_text(title) for title in functional_case_titles if title}
        for test in tests:
            if not re.match(r"^IT-\d{3}$", test.id):
                issues.append(
                    ValidationIssue(
                        issue_type="format",
                        message=f"{test.id} 的联动测试编号格式不符合 IT-001 规范。",
                        severity=RiskLevel.MEDIUM,
                        target_type="integration_test",
                        target_id=test.id,
                    )
                )
            if test.id in seen_ids:
                issues.append(
                    ValidationIssue(
                        issue_type="duplicate",
                        message=f"{test.id} 联动测试编号重复出现。",
                        severity=RiskLevel.HIGH,
                        target_type="integration_test",
                        target_id=test.id,
                    )
                )
            seen_ids.add(test.id)
            normalized_title = self._normalize_text(test.title)
            if normalized_title in seen_titles:
                issues.append(
                    ValidationIssue(
                        issue_type="duplicate",
                        message=f"联动测试标题重复：{test.title}",
                        severity=RiskLevel.MEDIUM,
                        target_type="integration_test",
                        target_id=test.id,
                    )
                )
            seen_titles.add(normalized_title)
            if normalized_title in normalized_case_titles:
                issues.append(
                    ValidationIssue(
                        issue_type="duplicate",
                        message=f"{test.id} 与已有功能用例标题重复，请人工确认是否应保留联动测试：{test.title}",
                        severity=RiskLevel.MEDIUM,
                        target_type="integration_test",
                        target_id=test.id,
                    )
                )
        return issues

    def _next_identifier_seed(self, values: list[str], pattern: str) -> int:
        max_num = 0
        compiled = re.compile(pattern)
        for value in values:
            match = compiled.match(value or "")
            if match:
                max_num = max(max_num, int(match.group(1)))
        return max_num + 1

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"[\s\-_:：，,。/]+", "", value.lower())

    def _build_regression_suites(
        self,
        cases: list[TestCase],
        selected_test_points: list[TestPoint],
        integration_tests: list[IntegrationTest],
    ) -> list[RegressionSuite]:
        """
        基于用例优先级和测试点风险等级，自动构建四个分级回归集：
        - RS-SMOKE：P0 用例 + 高风险测试点对应用例，用于快速主链路验证
        - RS-CORE：P0/P1 用例 + 全部联动测试，用于常规版本回归
        - RS-HIGH-RISK：高风险测试点对应用例，用于专项回归
        - RS-FULL：全量用例 + 全部联动测试，用于完整回归

        所有 case_ids 经过去重和空值过滤处理。
        """
        # 构建测试点 id -> 测试点 的快速查找表，用于判断用例对应的风险等级
        point_map = {item.id: item for item in selected_test_points}

        smoke_case_ids = [
            case.id
            for case in cases
            if case.priority == Priority.P0
            or (
                point_map.get(case.source_test_point_id)
                and point_map[case.source_test_point_id].risk_level == RiskLevel.HIGH
            )
        ]
        core_case_ids = [case.id for case in cases if case.priority in {Priority.P0, Priority.P1}]
        high_risk_case_ids = [
            case.id
            for case in cases
            if point_map.get(case.source_test_point_id)
            and point_map[case.source_test_point_id].risk_level == RiskLevel.HIGH
        ]
        full_case_ids = [case.id for case in cases]
        integration_ids = [item.id for item in integration_tests]

        def unique(values: list[str]) -> list[str]:
            """去重并过滤空字符串，同时保持原有顺序。"""
            seen: set[str] = set()
            result: list[str] = []
            for value in values:
                if value and value not in seen:
                    seen.add(value)
                    result.append(value)
            return result

        logger.debug(
            "_build_regression_suites | smoke=%d core=%d high_risk=%d full=%d integration=%d",
            len(unique(smoke_case_ids)),
            len(unique(core_case_ids)),
            len(unique(high_risk_case_ids)),
            len(full_case_ids),
            len(integration_ids),
        )

        return [
            RegressionSuite(
                id="RS-SMOKE",
                title="冒烟回归集",
                description="聚焦核心主流程和高风险测试点，适合快速验证主链路。",
                case_ids=unique(smoke_case_ids),
                # 冒烟集只取前两个联动测试，保持执行时间可控
                integration_test_ids=integration_ids[:2],
                entry_criteria=["需求已确认", "主流程相关数据已准备"],
            ),
            RegressionSuite(
                id="RS-CORE",
                title="核心流程回归集",
                description="覆盖 P0/P1 重点流程，适合版本提测后的常规回归。",
                case_ids=unique(core_case_ids),
                integration_test_ids=integration_ids,
                entry_criteria=["关键模块可用", "基础环境稳定"],
            ),
            RegressionSuite(
                id="RS-HIGH-RISK",
                title="高风险专项回归集",
                description="聚焦高风险测试点和关键联动场景。",
                case_ids=unique(high_risk_case_ids),
                integration_test_ids=integration_ids,
                entry_criteria=["高风险需求已完成联调"],
            ),
            RegressionSuite(
                id="RS-FULL",
                title="全量回归集",
                description="包含当前任务的全部功能和联动测试资产。",
                case_ids=unique(full_case_ids),
                integration_test_ids=integration_ids,
                entry_criteria=["完整测试环境可用"],
            ),
        ]
