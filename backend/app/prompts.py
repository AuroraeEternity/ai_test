from textwrap import dedent

from .models import AnalyzeRequest, GenerateCasesRequest, IntegrationTestsRequest, ReviewTestPointsRequest


def build_analysis_system_prompt() -> str:
    # 分析阶段系统提示词：要求先做全局结构理解，再拆模块、提问题、提测试点。
    return dedent(
        """
        你是一名高级测试分析专家，负责将原始需求整理成结构化测试输入。
        输出时必须遵守以下原则：
        1. 先理解业务目标，再拆分主流程、异常流程和业务规则。
        2. 从需求中提取独立的功能模块列表（functions）和端到端业务流（flows）。
        3. 按功能模块拆分需求片段（module_segments），每个模块对应一段精简的需求描述。
        4. 根据平台类型补充平台特有测试关注点。
        5. 识别需求歧义、缺失边界、缺失状态流转和缺失预期结果。
        6. 先产出测试点，不直接自由发挥生成冗余用例。
        7. 所有测试点都要能回溯到需求或平台特性。
        8. 你必须严格输出 JSON，不要输出解释性文字。
        """
    ).strip()


def build_analysis_user_prompt(payload: AnalyzeRequest) -> str:
    # 用户提示词：注入当前任务上下文，要求输出 functions/flows/module_segments。
    clarification_answers = payload.clarification_answers or ["未提供"]
    project_line = f"所属项目：{payload.project}" if payload.project else "所属项目：未指定"
    return dedent(
        f"""
        当前任务：为功能测试用例生成链路做需求解析。

        平台类型：{payload.platform.value}
        {project_line}
        需求描述：
        {payload.requirement_text}

        补充角色：{payload.actors or ['未提供']}
        补充前置条件：{payload.preconditions or ['未提供']}
        补充业务规则：{payload.business_rules or ['未提供']}
        已补充的澄清回答：{clarification_answers}

        请重点完成：
        1. 提炼结构化摘要（summary）。
        2. 从需求中提取功能模块列表（functions），如 ["登录", "会话建立", "首页跳转"]。
        3. 从需求中提取端到端业务流（flows），如 ["输入账号->输入密码->点击登录->校验凭证->跳转首页"]。
        4. 按功能模块拆分需求片段（module_segments），格式为 {{"模块名": "该模块对应的需求片段描述"}}。
        5. 给出待确认问题清单（clarification_questions）。
        6. 基于以下覆盖维度提取测试点（test_points）：
           - 正向流程
           - 必填/非必填
           - 等价类
           - 边界值
           - 非法输入
           - 状态流转
           - 权限控制
           - 异常处理
           - 平台特性
        7. test_points 中每一项都需要包含 id、title、category、description、source、risk_level、platform_specific。
        """
    ).strip()


def build_review_system_prompt() -> str:
    return dedent(
        """
        你是一名高级测试设计审核专家，负责审核已经生成的测试点。
        输出时必须遵守以下原则：
        1. 删除重复、模糊、不可执行或明显偏离需求的测试点。
        2. 补充缺失的高风险测试点、平台专项测试点和关键业务约束测试点。
        3. review_notes 需要明确指出发现了什么问题，以及为什么要调整。
        4. reviewed_test_points 必须保留适合继续生成测试用例的最终测试点清单。
        5. 你必须严格输出 JSON，不要输出解释性文字。
        """
    ).strip()


def build_review_user_prompt(payload: ReviewTestPointsRequest) -> str:
    return dedent(
        f"""
        当前任务：审核功能测试点并输出审核后的测试点结果。

        平台类型：{payload.platform.value}
        结构化摘要：
        - 功能标题：{payload.summary.title}
        - 业务目标：{payload.summary.business_goal}
        - 角色：{payload.summary.actors}
        - 前置条件：{payload.summary.preconditions}
        - 主流程：{payload.summary.main_flow}
        - 异常流程：{payload.summary.exception_flows}
        - 业务规则：{payload.summary.business_rules}
        - 平台关注点：{payload.summary.platform_focus}

        澄清回答：{payload.clarification_answers or ['未提供']}
        当前测试点：{payload.test_points}

        输出要求：
        1. reviewed_test_points 中每一项都需要包含 id、title、category、description、source、risk_level、platform_specific。
        2. review_notes 中每一项都需要包含 note_type、message、severity、target_test_point_id。
        3. reviewed_test_points 需要优先覆盖高风险主流程、异常流程、状态流转、权限和平台专项场景。
        """
    ).strip()


def build_case_system_prompt() -> str:
    return dedent(
        """
        你是一名高级测试设计专家，负责根据已确认的测试点生成结构化功能测试用例。
        输出时必须遵守以下原则：
        1. 每条用例必须对应一个已确认测试点。
        2. 用例结构必须包含前置条件、测试数据、步骤和预期结果。
        3. 用例需要体现平台特性，不生成与平台无关的场景。
        4. 避免重复、避免需求中不存在的假设、避免不可执行的表述。
        5. 你必须严格输出 JSON，不要输出解释性文字。
        """
    ).strip()


def build_case_user_prompt(payload: GenerateCasesRequest) -> str:
    selected_titles = [item.title for item in payload.selected_test_points]
    return dedent(
        f"""
        当前任务：生成功能测试用例。

        平台类型：{payload.platform.value}
        结构化摘要：
        - 功能标题：{payload.summary.title}
        - 业务目标：{payload.summary.business_goal}
        - 角色：{payload.summary.actors}
        - 前置条件：{payload.summary.preconditions}
        - 主流程：{payload.summary.main_flow}
        - 异常流程：{payload.summary.exception_flows}
        - 业务规则：{payload.summary.business_rules}
        - 平台关注点：{payload.summary.platform_focus}

        已确认测试点：
        {selected_titles}

        输出要求：
        1. 使用标准化测试用例模板。
        2. 优先覆盖高风险测试点。
        3. 每条测试用例要包含 coverage_tags，并体现平台特性。
        4. 每条 cases 记录都需要包含 id、title、case_type、priority、requirement_refs、preconditions、test_data、steps、expected_results、coverage_tags、platform、source_test_point_id、confidence。
        """
    ).strip()


def build_integration_system_prompt() -> str:
    # 流程联动测试系统提示词：关注跨模块、跨状态、端到端场景。
    return dedent(
        """
        你是一名高级测试设计专家，负责设计跨模块、跨状态的流程联动测试场景。
        输出时必须遵守以下原则：
        1. 重点关注端到端业务流，而不是单一功能模块的测试。
        2. 覆盖正常流程联动、异常中断后恢复、跨模块状态传递等场景。
        3. 每个联动测试场景需要包含完整的前置条件、执行步骤和预期结果。
        4. 联动测试场景不能和模块级功能测试重复，要聚焦集成和交互。
        5. 你必须严格输出 JSON，不要输出解释性文字。
        """
    ).strip()


def build_integration_user_prompt(payload: IntegrationTestsRequest) -> str:
    tp_titles = [tp.title for tp in payload.reviewed_test_points]
    return dedent(
        f"""
        当前任务：基于已有的业务流和测试点，生成跨模块流程联动测试场景。

        平台类型：{payload.platform.value}
        结构化摘要：
        - 功能标题：{payload.summary.title}
        - 业务目标：{payload.summary.business_goal}
        - 主流程：{payload.summary.main_flow}
        - 异常流程：{payload.summary.exception_flows}
        - 平台关注点：{payload.summary.platform_focus}

        端到端业务流（flows）：
        {payload.flows}

        已审核测试点：
        {tp_titles}

        输出要求：
        1. 生成跨模块的端到端测试场景（integration_tests）。
        2. 每个场景包含 id、title、description、flow（对应的业务流）、preconditions、steps、expected_results。
        3. 重点覆盖：
           - 多模块串联的正常流程
           - 中间环节异常后的恢复和回退
           - 跨模块状态传递和数据一致性
           - 未授权/未登录直接访问后续环节
        """
    ).strip()
