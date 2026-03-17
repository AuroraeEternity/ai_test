from enum import Enum

from pydantic import BaseModel, Field


class PlatformType(str, Enum):
    WEB = "web"
    APP = "app"
    PLUGIN = "plugin"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    reason: str
    blocking: bool = True


class ClarificationAnswer(BaseModel):
    question_id: str
    question: str
    answer: str


# 需求经过第一次分析后的结构化摘要，后续所有阶段都依赖这份摘要。
class StructuredSummary(BaseModel):
    title: str
    business_goal: str
    actors: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    main_flow: list[str] = Field(default_factory=list)
    exception_flows: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    platform_focus: list[str] = Field(default_factory=list)


class TestPoint(BaseModel):
    id: str
    title: str
    category: str
    description: str
    source: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    platform_specific: bool = False


class ValidationIssue(BaseModel):
    issue_type: str
    message: str
    severity: RiskLevel = RiskLevel.MEDIUM


class ReviewNote(BaseModel):
    note_type: str
    message: str
    severity: RiskLevel = RiskLevel.MEDIUM
    target_test_point_id: str = ""


class TestCase(BaseModel):
    id: str
    title: str
    case_type: str = "functional"
    priority: Priority = Priority.P1
    requirement_refs: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    test_data: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    expected_results: list[str] = Field(default_factory=list)
    coverage_tags: list[str] = Field(default_factory=list)
    platform: PlatformType
    source_test_point_id: str
    confidence: float = 0.85


# 流程联动测试场景，跨模块/跨状态的端到端测试。
class IntegrationTest(BaseModel):
    id: str
    title: str
    description: str
    flow: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    expected_results: list[str] = Field(default_factory=list)


# --- Request / Response / LLMOutput ---

class AnalyzeRequest(BaseModel):
    platform: PlatformType
    requirement_text: str = Field(min_length=10)
    business_rules: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    platform: PlatformType
    summary: StructuredSummary
    functions: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)
    module_segments: dict[str, str] = Field(default_factory=dict)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    coverage_dimensions: list[str] = Field(default_factory=list)
    test_points: list[TestPoint] = Field(default_factory=list)
    prompts: dict[str, str] = Field(default_factory=dict)


class AnalyzeLLMOutput(BaseModel):
    summary: StructuredSummary
    functions: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)
    module_segments: dict[str, str] = Field(default_factory=dict)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    coverage_dimensions: list[str] = Field(default_factory=list)
    test_points: list[TestPoint] = Field(default_factory=list)


class ReviewTestPointsRequest(BaseModel):
    platform: PlatformType
    summary: StructuredSummary
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)
    test_points: list[TestPoint] = Field(default_factory=list)


class ReviewTestPointsResponse(BaseModel):
    platform: PlatformType
    reviewed_test_points: list[TestPoint] = Field(default_factory=list)
    review_notes: list[ReviewNote] = Field(default_factory=list)
    prompts: dict[str, str] = Field(default_factory=dict)


class ReviewTestPointsLLMOutput(BaseModel):
    reviewed_test_points: list[TestPoint] = Field(default_factory=list)
    review_notes: list[ReviewNote] = Field(default_factory=list)


class GenerateCasesRequest(BaseModel):
    platform: PlatformType
    summary: StructuredSummary
    selected_test_points: list[TestPoint] = Field(default_factory=list)


class GenerateCasesResponse(BaseModel):
    platform: PlatformType
    cases: list[TestCase] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    prompts: dict[str, str] = Field(default_factory=dict)


class GenerateCasesLLMOutput(BaseModel):
    cases: list[TestCase] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)


# 流程联动测试请求/响应
class IntegrationTestsRequest(BaseModel):
    platform: PlatformType
    summary: StructuredSummary
    flows: list[str] = Field(default_factory=list)
    reviewed_test_points: list[TestPoint] = Field(default_factory=list)


class IntegrationTestsResponse(BaseModel):
    platform: PlatformType
    integration_tests: list[IntegrationTest] = Field(default_factory=list)
    prompts: dict[str, str] = Field(default_factory=dict)


class IntegrationTestsLLMOutput(BaseModel):
    integration_tests: list[IntegrationTest] = Field(default_factory=list)


class PlatformOption(BaseModel):
    label: str
    value: PlatformType
    description: str


class MetaResponse(BaseModel):
    platforms: list[PlatformOption]
    workflow_steps: list[str]
