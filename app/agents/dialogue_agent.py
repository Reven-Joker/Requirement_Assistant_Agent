"""Dialogue Agent — multi-round technical Q&A between Reviewer and Engineer/Solution.

Replaces the single "reflow with issue list" with a structured dialogue:
  1. Reviewer asks deep technical questions (not checklist items)
  2. Engineer/Solution answers with concrete details + revises design
  3. Reviewer re-evaluates; may ask follow-ups or pass
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import get_llm, get_structured_llm
from app.core.logger import logger
from app.graph.state import AgentState
from app.memory.context_compression import compress_dialogue_rounds
from app.memory.short_term import add_entry, format_for_prompt
from app.schemas.design import TechnicalDesign
from app.schemas.prd import PRDDocument
from app.schemas.review import ReviewResult


def dialogue_reviewer_node(state: AgentState) -> dict:
    """Reviewer generates deep technical questions for a dialogue round.

    Returns:
      dialogue_questions: list of {target, question} dicts
      dialogue_targets: list of node names to engage in dialogue
      dialogue_round: incremented
    """
    review = state.get("review_result") or {}
    prd_doc = state.get("prd_doc") or {}
    design = state.get("technical_design") or {}
    clarified_req = state.get("clarified_requirement") or {}
    dialogue_history = state.get("dialogue_history") or []
    current_round = state.get("dialogue_round", 0)

    logger.info(
        f"Dialogue Reviewer 开始第 {current_round + 1} 轮",
        extra={"node": "dialogue_reviewer"},
    )

    history_text = _format_dialogue_history(
        dialogue_history, current_round=current_round, max_tokens=1500
    )
    issues = review.get("issues") or []

    # Determine which agents need dialogue
    engineer_issues = [i for i in issues if i.get("target") == "engineer"]
    solution_issues = [i for i in issues if i.get("target") == "solution"]

    targets: list[str] = []
    if engineer_issues:
        targets.append("engineer")
    if solution_issues:
        targets.append("solution")
    if not targets:
        targets = ["engineer"]  # default

    # Build prompt: review findings → generate deep questions
    issue_summary_lines = []
    for issue in issues[:8]:
        issue_summary_lines.append(
            f"- [{issue.get('severity', '?')}][{issue.get('target', '?')}] "
            f"{issue.get('description', '')}"
        )
    issue_summary = "\n".join(issue_summary_lines) if issue_summary_lines else "（无具体问题）"

    user_prompt = DIALOGUE_REVIEWER_USER_PROMPT.format(
        review_summary=review.get("summary", ""),
        review_score=str(review.get("overall_score", "?")),
        issue_summary=issue_summary,
        dialogue_history=history_text or "（首轮对话）",
    )

    dialogue_messages = [
        SystemMessage(content=DIALOGUE_REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    task_mem = add_entry(
        state, "dialogue_reviewer",
        summary=f"生成第 {current_round + 1} 轮对话问题",
        metrics={"dialogue_round": current_round + 1, "targets": targets},
    )

    return {
        **task_mem,
        "dialogue_questions": _parse_questions(dialogue_messages, targets),
        "dialogue_targets": targets,
        "dialogue_round": current_round + 1,
        "dialogue_active": True,
        "current_node": "dialogue_reviewer",
        "execution_logs": [
            {
                "node": "dialogue_reviewer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "round": current_round + 1,
                "targets": targets,
            }
        ],
    }


def dialogue_engineer_node(state: AgentState) -> dict:
    """Engineer answers Reviewer questions and updates the technical design."""
    logger.info("Dialogue Engineer 开始回复", extra={"node": "dialogue_engineer"})

    questions = state.get("dialogue_questions") or []
    prd_doc = state.get("prd_doc") or {}
    design = state.get("technical_design") or {}
    clarified_req = state.get("clarified_requirement") or {}

    engineer_qs = [q for q in questions if q.get("target") == "engineer"]
    q_text = _format_questions(engineer_qs)

    task_memory_text = format_for_prompt(
        state.get("task_memory"),
        max_chars=get_settings().short_term_memory_max_chars,
        max_tokens=1200,
    )

    structured_llm = get_structured_llm(TechnicalDesign)
    user_content = DIALOGUE_ENGINEER_PROMPT.format(
        dialogue_questions=q_text,
        prd_doc=json.dumps(prd_doc, ensure_ascii=False, indent=2),
        current_design=json.dumps(design, ensure_ascii=False, indent=2),
        task_memory=task_memory_text,
    )

    messages = [
        SystemMessage(content=ENGINEER_DIALOGUE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    result: TechnicalDesign = structured_llm.invoke(messages)
    result_dict = result.model_dump()

    api_count = len(result_dict.get("api_endpoints") or [])
    table_count = len((result_dict.get("db_schema") or {}).get("tables") or [])

    task_mem = add_entry(
        state, "dialogue_engineer",
        summary=f"回答了 {len(engineer_qs)} 个问题，更新了技术设计",
        metrics={"api_count": api_count, "table_count": table_count},
    )

    dialogue_history = (state.get("dialogue_history") or []) + [
        {"role": "reviewer", "questions": engineer_qs},
        {"role": "engineer", "summary": f"更新了设计，API={api_count}, 表={table_count}"},
    ]

    return {
        **task_mem,
        "technical_design": result_dict,
        "dialogue_history": dialogue_history,
        "current_node": "dialogue_engineer",
        "execution_logs": [
            {
                "node": "dialogue_engineer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "questions_answered": len(engineer_qs),
            }
        ],
    }


def dialogue_solution_node(state: AgentState) -> dict:
    """Solution answers Reviewer questions and updates the PRD."""
    logger.info("Dialogue Solution 开始回复", extra={"node": "dialogue_solution"})

    questions = state.get("dialogue_questions") or []
    clarified_req = state.get("clarified_requirement") or {}
    prd_doc = state.get("prd_doc") or {}

    solution_qs = [q for q in questions if q.get("target") == "solution"]
    q_text = _format_questions(solution_qs)

    task_memory_text = format_for_prompt(
        state.get("task_memory"),
        max_chars=get_settings().short_term_memory_max_chars,
        max_tokens=1200,
    )

    structured_llm = get_structured_llm(PRDDocument, temperature=0.5)
    user_content = DIALOGUE_SOLUTION_PROMPT.format(
        dialogue_questions=q_text,
        clarified_requirement=json.dumps(clarified_req, ensure_ascii=False, indent=2),
        current_prd=json.dumps(prd_doc, ensure_ascii=False, indent=2),
        task_memory=task_memory_text,
    )

    messages = [
        SystemMessage(content=SOLUTION_DIALOGUE_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    result: PRDDocument = structured_llm.invoke(messages)
    result_dict = result.model_dump()

    task_mem = add_entry(
        state, "dialogue_solution",
        summary=f"回答了 {len(solution_qs)} 个问题，更新了 PRD",
        metrics={"feature_count": len(result.feature_modules)},
    )

    dialogue_history = (state.get("dialogue_history") or []) + [
        {"role": "reviewer", "questions": solution_qs},
        {"role": "solution", "summary": f"更新了PRD，功能模块={len(result.feature_modules)}"},
    ]

    return {
        **task_mem,
        "prd_doc": result_dict,
        "dialogue_history": dialogue_history,
        "current_node": "dialogue_solution",
        "execution_logs": [
            {
                "node": "dialogue_solution",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "questions_answered": len(solution_qs),
            }
        ],
    }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DIALOGUE_REVIEWER_SYSTEM_PROMPT = """你是一名资深技术评审专家。上一次评审未通过，但你不应直接列出问题清单，
而应与工程师/产品经理进行深入的技术对话。通过提出具体、深入的技术问题，引导他们自己发现和解决问题。

生成问题要求：
1. 每个问题必须针对具体的功能模块或技术决策，引用上轮问题的描述
2. 问"如何实现"而不是"请补充"——引导工程师说明具体的技术方案
3. 覆盖深层关注点：幂等性、并发控制、数据一致性、安全审计、扩展策略
4. 如果历史对话中已有类似问题，应追问更具体的实现细节
5. 明确标注问题的目标角色（engineer 或 solution）"""

DIALOGUE_REVIEWER_USER_PROMPT = """## 评审摘要
{review_summary}

## 总体评分：{review_score}/10

## 上轮评审发现的问题
{issue_summary}

## 历史对话记录
{dialogue_history}

请针对以上评审结果，生成 2-5 个技术对话问题。"""

ENGINEER_DIALOGUE_SYSTEM_PROMPT = """你是一名资深技术架构师。评审专家向你的技术设计提出了深入的问题。
请逐一回答每个问题，给出具体、可操作的技术方案，然后基于讨论结果更新完整的技术设计。

回答原则：
- 每个回答必须包含具体的实现细节（代码模式、数据库字段、API 参数等）
- 如果评审专家的建议合理，接受并融入到更新后的设计中
- 如果不同意，礼貌地解释你的技术决策理由
- 更新设计时要保持已有的正确部分，只修改问题涉及的部分"""

DIALOGUE_ENGINEER_PROMPT = """## 评审专家的问题

{dialogue_questions}

## 当前 PRD
{prd_doc}

## 当前技术设计
{current_design}

## 短期记忆
{task_memory}

请逐一回答问题，然后输出更新后的完整技术设计方案。"""

SOLUTION_DIALOGUE_SYSTEM_PROMPT = """你是一名资深产品经理。评审专家对你的 PRD 提出了深入的问题。
请逐一回答每个问题，给出具体的产品逻辑和业务规则，然后更新 PRD 文档。

回答原则：
- 每个回答必须明确业务规则和用户流程
- 接受合理的建议并融入 PRD
- 保持已有的正确内容"""

DIALOGUE_SOLUTION_PROMPT = """## 评审专家的问题

{dialogue_questions}

## 需求澄清结果
{clarified_requirement}

## 当前 PRD
{current_prd}

## 短期记忆
{task_memory}

请逐一回答问题，然后输出更新后的完整 PRD 文档。"""


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class DialogueQuestion(BaseModel):
    """Dialogue Reviewer 生成的单个对话问题。"""

    target: str = Field(..., description="目标角色：engineer 或 solution")
    question: str = Field(..., description="具体、有深度的技术问题")
    context: str = Field("", description="引用上轮问题的背景信息")


class DialogueQuestionList(BaseModel):
    """对话问题列表的容器模型（function calling 要求顶层为 object）。"""

    questions: list[DialogueQuestion]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_questions(questions: list[dict]) -> str:
    if not questions:
        return "（无具体问题）"
    lines = []
    for i, q in enumerate(questions, 1):
        ctx = q.get("context", "")
        ctx_str = f"\n   背景：{ctx}" if ctx else ""
        lines.append(f"Q{i} [{q.get('target', '?')}]：{q.get('question', '')}{ctx_str}")
    return "\n\n".join(lines)


def _format_dialogue_history(
    history: list[dict],
    current_round: int = 0,
    max_tokens: int = 1500,
) -> str:
    """Format dialogue history with compression for rounds beyond threshold.

    - Round <= threshold: keep all entries in full
    - Round > threshold: compress old rounds via LLM, keep recent round full
    """
    if not history:
        return ""

    settings = get_settings()

    if not settings.dialogue_compression_enabled:
        # Fallback: simple last-6 truncation
        lines = []
        for entry in history[-6:]:
            role = entry.get("role", "?")
            if role == "reviewer":
                for q in entry.get("questions") or []:
                    lines.append(f"Reviewer Q: {q.get('question', '')[:120]}")
            elif role in ("engineer", "solution"):
                lines.append(f"{role}: {entry.get('summary', '')[:100]}")
        return "\n".join(lines) if lines else ""

    if current_round <= settings.dialogue_compression_threshold:
        # Under threshold: full detail
        from app.memory.context_compression import _format_history_entries

        return _format_history_entries(history)

    # Over threshold: compress old rounds
    try:
        llm = get_llm(temperature=0.2)
    except Exception:
        logger.warning("Failed to get LLM for dialogue compression, falling back to truncation")
        lines = []
        for entry in history[-6:]:
            role = entry.get("role", "?")
            if role == "reviewer":
                for q in entry.get("questions") or []:
                    lines.append(f"Reviewer Q: {q.get('question', '')[:120]}")
            elif role in ("engineer", "solution"):
                lines.append(f"{role}: {entry.get('summary', '')[:100]}")
        return "\n".join(lines) if lines else ""

    compressed, tokens = compress_dialogue_rounds(history, current_round, max_tokens, llm)
    logger.info(
        f"Dialogue history compressed: round={current_round}, "
        f"entries={len(history)}, tokens={tokens}, max={max_tokens}"
    )
    return compressed


def _parse_questions(messages: list, targets: list[str]) -> list[dict[str, Any]]:
    """Generate structured dialogue questions via with_structured_output.

    Falls back to simple questions if the LLM call fails.
    """
    from app.core.llm import get_structured_llm

    try:
        structured_llm = get_structured_llm(DialogueQuestionList, temperature=0.3)
        result: DialogueQuestionList = structured_llm.invoke(messages)
        questions = [q.model_dump() for q in result.questions]
        if questions:
            return questions
    except Exception:
        logger.warning("Structured dialogue question generation failed, using fallback")

    # Fallback: generate simple questions from targets
    fallback = []
    for target in targets:
        fallback.append({
            "target": target,
            "question": f"请针对上轮评审发现的问题，说明你将如何改进{'技术设计' if target == 'engineer' else 'PRD文档'}。",
            "context": "评审未通过，需要具体的技术方案",
        })
    return fallback
