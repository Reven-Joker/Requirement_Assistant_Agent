"""Self-Refine: LLM self-critique => improved regeneration.

Replaces rule-only ReAct feedback with LLM-generated self-critique,
combined with rule-detected gaps, for semantically richer revision guidance.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.core.config import get_settings
from app.core.llm import get_llm

# ---------------------------------------------------------------------------
# Self-critique prompts
# ---------------------------------------------------------------------------

ENGINEER_SELF_CRITIQUE_PROMPT = """你是一名资深技术架构师。请严格审视你刚刚生成的技术设计方案，从以下角度逐一进行自我批评：

1. **映射完整性**：规则检测发现以下 PRD 功能模块缺少 API 或 DB 映射：
   缺少 API 的模块：{missing_api}
   缺少 DB 的模块：{missing_db}
   请分析为什么这些模块被遗漏——是忽略了功能描述中的隐含需求，还是设计过于抽象？

2. **API 特异性**：当前设计的 API 路径是否过于通用（如 /items, /users, /data）而缺少领域特定端点？
   每个 PRD 功能模块是否都有清晰的、可追溯的 API 端点？

3. **数据库完整性**：表设计是否包含了业务关键字段（幂等键、状态枚举、时间戳、审计字段、索引）？
   表之间的关系（外键或逻辑关联）是否明确？

4. **技术风险**：是否考虑了并发一致性、幂等性、权限控制、数据加密、速率限制等横切关注点？
   对于高风险的领域（支付、库存、审核、隐私），是否有针对性的设计措施？

5. **与历史案例对比**：参考以下历史成功案例的模式，你的设计在深度和追溯性上有哪些差距？
{{
{few_shot_text}
}}

请输出具体的、可操作的自我批评（每点 1-2 句），不要泛泛而谈。直接指出设计的具体缺陷和改进方向。
"""

REVIEWER_SELF_CRITIQUE_PROMPT = """你是一名资深技术评审专家。请严格审视你刚刚做出的评审结论。

你的结论是"通过"，但以下覆盖率问题被规则检测到：
{rule_conflicts}

请从以下角度进行自我批评：

1. **漏检分析**：为什么你在评审中未能发现这些覆盖率问题？是过于关注整体结构而忽略了逐模块追溯吗？

2. **标准一致性**：如果这次你放宽了标准，具体是在哪个维度上放宽的（API 数量足够？功能描述含糊？）？
   与严格的交付标准相比，这个评审结论是否过于宽松？

3. **深层风险**：除了规则检测到的覆盖率问题，被评审的技术设计是否还存在其他隐患（架构风格不匹配、扩展性不足、安全漏洞）？

4. **历史参照**：回顾你见过的历史评审记录，本次评审的标准和深度是否一致？

请输出具体、诚实的自我批评，直接指出评审中的疏漏和需要修正的判断。
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def engineer_self_critique(
    design_json: str,
    prd_json: str,
    missing_api: list[str],
    missing_db: list[str],
    few_shot_text: str,
) -> str:
    """Ask the LLM to critique its own technical design.

    Uses a non-structured LLM call (free text) for faster critique generation.
    Only triggered when coverage is below threshold.
    """
    prompt = ENGINEER_SELF_CRITIQUE_PROMPT.format(
        missing_api=", ".join(missing_api) if missing_api else "（无）",
        missing_db=", ".join(missing_db) if missing_db else "（无）",
        few_shot_text=few_shot_text or "（无可用历史案例）",
    )

    settings = get_settings()
    critique_llm = get_llm(temperature=0.3)
    response = critique_llm.invoke([HumanMessage(content=prompt)])
    critique = (response.content or "").strip()

    if len(critique) > settings.self_refine_max_chars:
        critique = critique[: settings.self_refine_max_chars].rstrip() + "\n...[self-critique 已截断]"

    return critique


def reviewer_self_critique(
    review_json: str,
    prd_json: str,
    design_json: str,
    conflict_issues: list[dict],
) -> str:
    """Ask the Reviewer LLM to critique its own review.

    Triggered when rules override the LLM's "passed" conclusion.
    """
    conflict_lines = []
    for issue in conflict_issues[:5]:
        severity = issue.get("severity", "?")
        desc = issue.get("description", "")
        conflict_lines.append(f"- [{severity}] {desc}")
    rule_conflicts_text = "\n".join(conflict_lines) if conflict_lines else "（无具体问题）"

    prompt = REVIEWER_SELF_CRITIQUE_PROMPT.format(
        rule_conflicts=rule_conflicts_text,
    )

    settings = get_settings()
    critique_llm = get_llm(temperature=0.3)
    response = critique_llm.invoke([HumanMessage(content=prompt)])
    critique = (response.content or "").strip()

    if len(critique) > settings.self_refine_max_chars:
        critique = critique[: settings.self_refine_max_chars].rstrip() + "\n...[self-critique 已截断]"

    return critique


def build_refined_feedback(
    self_critique: str,
    coverage_info: str,
    missing_modules: str,
) -> str:
    """Merge self-critique and rule feedback into one refined message.

    Structure:
    1. Self-critique (LLM's own analysis of what went wrong)
    2. Rule-detected gaps (what the system found)
    3. Action instruction (what to do next)
    """
    parts = [
        "## 自我反思与改进指导",
        "",
        "### 你的自我批评",
        self_critique,
        "",
        "### 规则检测到的覆盖率缺口",
        coverage_info,
        "",
        missing_modules,
        "",
        "请基于以上自我反思和规则检测结果，重新输出完整的技术设计方案。",
        "特别注意：每个 PRD 功能模块必须有明确的 API 端点和数据库表映射，",
        "API 路径应使用领域特定术语，数据库表应包含业务关键字段（如幂等键、状态枚举、审计字段）。",
    ]
    return "\n".join(parts)
