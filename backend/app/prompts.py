from textwrap import dedent

from .models import AnalyzeRequest, GenerateCasesRequest


def build_analysis_system_prompt() -> str:
    # 系统提示词约束模型的角色和输出原则，确保需求解析阶段先做结构化理解，
    # 再产出待确认问题和测试点，而不是直接生成松散文本。
    return dedent(
        """
        你是一名高级测试分析专家，负责将原始需求整理成结构化测试输入。
        输出时必须遵守以下原则：
        1. 先理解业务目标，再拆分主流程、异常流程和业务规则。
        2. 根据平台类型补充平台特有测试关注点。
        3. 识别需求歧义、缺失边界、缺失状态流转和缺失预期结果。
        4. 先产出测试点，不直接自由发挥生成冗余用例。
        5. 所有测试点都要能回溯到需求或平台特性。
        6. 你必须严格输出 JSON，不要输出解释性文字。
        """
    ).strip()


def build_analysis_user_prompt(payload: AnalyzeRequest) -> str:
    # 用户提示词负责注入当前任务上下文。这里会把平台、需求、补充规则一起传给模型，
    # 让模型围绕功能测试链路输出结构化摘要、澄清问题和测试点。
    return dedent(
        f"""
        当前任务：为功能测试用例生成链路做需求解析。

        平台类型：{payload.platform.value}
        需求描述：
        {payload.requirement_text}

        补充角色：{payload.actors or ['未提供']}
        补充前置条件：{payload.preconditions or ['未提供']}
        补充业务规则：{payload.business_rules or ['未提供']}

        请重点完成：
        1. 提炼结构化摘要。
        2. 给出待确认问题清单。
        3. 基于以下覆盖维度提取测试点：
           - 正向流程
           - 必填/非必填
           - 等价类
           - 边界值
           - 非法输入
           - 状态流转
           - 权限控制
           - 异常处理
           - 平台特性
        4. test_points 中每一项都需要包含 id、title、category、description、source、risk_level、platform_specific。
        """
    ).strip()


def build_case_system_prompt() -> str:
    # 用例生成阶段的系统提示词更强调“严格模板化输出”，
    # 避免模型返回解释性内容或偏离已确认的测试点。
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
    # 这里把上一步确认过的结构化摘要和测试点再次明确传给模型，
    # 让最终生成结果尽量可追溯、可校验、可直接渲染到前端。
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
