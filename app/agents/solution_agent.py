"""Solution Agent —— 生成产品方案、PRD 草稿与功能模块。

基于 Planner 输出的需求澄清结果，生成完整的 PRD 文档。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_structured_llm
from app.core.logger import logger
from app.core.config import get_settings
from app.core.prompts import SOLUTION_SYSTEM_PROMPT, SOLUTION_USER_PROMPT
from app.graph.state import AgentState
from app.memory.short_term import add_entry, format_for_prompt
from app.memory.few_shot import build_few_shot_for_task
from app.schemas.prd import PRDDocument


def solution_node(state: AgentState) -> dict:
    """Solution 节点：基于需求澄清结果生成 PRD 文档。"""
    logger.info("Solution Agent 开始执行", extra={"node": "solution"})

    clarified_req = state.get("clarified_requirement", {})
    human_feedback = state.get("human_feedback", "")
    review_result = state.get("review_result")

    extra_context = ""
    if human_feedback:
        extra_context += f"用户反馈：\n{human_feedback}\n\n"
    if review_result and not review_result.get("passed", False):
        suggestions = review_result.get("suggestions", [])
        issues = [
            i for i in review_result.get("issues", [])
            if i.get("target") == "solution"
        ]
        if suggestions or issues:
            extra_context += "评审修订建议：\n"
            for s in suggestions:
                extra_context += f"- {s}\n"
            for issue in issues:
                extra_context += f"- [{issue.get('severity')}] {issue.get('description')}: {issue.get('suggestion')}\n"

    structured_llm = get_structured_llm(PRDDocument, temperature=0.5)

    task_memory_text = format_for_prompt(
        state.get("task_memory"),
        max_chars=get_settings().short_term_memory_max_chars,
    )

    few_shot_text = build_few_shot_for_task(
        prd_doc={}, clarified_req=clarified_req
    )

    messages = [
        SystemMessage(content=SOLUTION_SYSTEM_PROMPT),
        HumanMessage(
            content=SOLUTION_USER_PROMPT.format(
                clarified_requirement=json.dumps(clarified_req, ensure_ascii=False, indent=2),
                extra_context=extra_context,
                few_shot_examples=few_shot_text,
                task_memory=task_memory_text,
            )
        ),
    ]

    result: PRDDocument = structured_llm.invoke(messages)
    result_dict = result.model_dump()

    logger.info(
        "Solution Agent 执行完成",
        extra={
            "node": "solution",
            "feature_count": len(result.feature_modules),
        },
    )

    decisions = [
        f"产品定位={result.positioning[:60]}" if result.positioning else "",
        f"优先级最高的功能={result.feature_modules[0].name}" if result.feature_modules else "",
    ]
    decisions = [d for d in decisions if d]
    task_mem = add_entry(
        state, "solution",
        summary=f"产出了 {len(result.feature_modules)} 个功能模块、{len(result.user_stories)} 个用户故事",
        key_decisions=decisions,
        metrics={
            "feature_count": len(result.feature_modules),
            "user_stories": len(result.user_stories),
            "user_flows": len(result.user_flows or []),
            "success_metrics": len(result.success_metrics or []),
        },
    )

    return {
        "prd_doc": result_dict,
        "current_node": "solution",
        **task_mem,
        "execution_logs": [
            {
                "node": "solution",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "feature_count": len(result.feature_modules),
            }
        ],
    }
