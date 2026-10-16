"""Context window compression for dialogue and short-term memory layers.

When dialogue rounds exceed the compression threshold (default 2), older rounds
are summarized via LLM into structured key points, keeping only the most recent
round in full detail. This prevents prompt bloat while preserving critical context.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.logger import logger

# ---------------------------------------------------------------------------
# Compression prompts
# ---------------------------------------------------------------------------

DIALOGUE_COMPRESSION_SYSTEM_PROMPT = """你是一名技术文档压缩专家。你的任务是将多轮技术评审对话压缩为结构化摘要。

要求：
1. 只保留关键决策、未解决的问题、技术约束
2. 去除非实质性的寒暄和重复讨论
3. 使用简洁的技术语言，每条不超过 40 字
4. 输出严格 JSON，不要包裹在 ``` 中"""

DIALOGUE_COMPRESSION_USER_PROMPT = """请将以下历史对话记录压缩为结构化摘要。

历史对话：
{dialogue_text}

输出 JSON 格式：
{{
  "key_decisions": ["关键决策1", "关键决策2", ...],
  "unresolved_issues": ["未解决问题1", "未解决问题2", ...],
  "technical_constraints": ["技术约束1", "技术约束2", ...]
}}

每条最多 3-5 项，空列表用 []。直接输出 JSON："""


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Chinese/English text.

    Rough heuristic:
    - CJK characters: ~1.5 chars per token
    - ASCII/English: ~4 chars per token
    - Numbers/punctuation: negligible, folded into surrounding text
    """
    if not text:
        return 0

    cjk_chars = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    ascii_chars = len(text) - cjk_chars

    cjk_tokens = cjk_chars / 1.5
    ascii_tokens = ascii_chars / 4.0

    return int(cjk_tokens + ascii_tokens) + 1  # +1 for rounding safety


# ---------------------------------------------------------------------------
# Adaptive truncation
# ---------------------------------------------------------------------------

def adaptive_truncate(text: str, max_tokens: int) -> str:
    """Truncate text to fit within max_tokens, breaking at paragraph boundaries."""
    if not text or max_tokens <= 0:
        return ""

    if estimate_tokens(text) <= max_tokens:
        return text

    suffix = "\n...[已压缩]"
    suffix_tokens = estimate_tokens(suffix)
    budget = max_tokens - suffix_tokens

    if budget <= 0:
        return text[:max_tokens * 2] + suffix  # rough fallback

    paragraphs = text.split("\n\n")
    result_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if current_tokens + para_tokens > budget:
            break
        result_parts.append(para)
        current_tokens += para_tokens

    if not result_parts:
        # Even the first paragraph is too long, truncate mid-paragraph
        result = text[:budget * 2]  # rough char estimate
        return result.rstrip() + suffix

    return "\n\n".join(result_parts) + suffix


# ---------------------------------------------------------------------------
# Dialogue compression
# ---------------------------------------------------------------------------

def _format_history_entries(entries: list[dict]) -> str:
    """Format dialogue history entries into readable text."""
    if not entries:
        return ""
    lines: list[str] = []
    for entry in entries:
        role = entry.get("role", "?")
        if role == "reviewer":
            for q in entry.get("questions") or []:
                lines.append(f"Reviewer 问: {q.get('question', '')}")
        elif role in ("engineer", "solution"):
            lines.append(f"{role} 答: {entry.get('summary', '')}")
    return "\n".join(lines)


def _summarize_rounds(old_entries: list[dict], llm: Any) -> dict[str, list[str]]:
    """Call LLM to compress old dialogue rounds into structured summary."""
    dialogue_text = _format_history_entries(old_entries)

    if not dialogue_text.strip():
        return {"key_decisions": [], "unresolved_issues": [], "technical_constraints": []}

    user_prompt = DIALOGUE_COMPRESSION_USER_PROMPT.format(dialogue_text=dialogue_text)

    try:
        response = llm.invoke([
            SystemMessage(content=DIALOGUE_COMPRESSION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        raw = (response.content or "").strip()

        # Try direct JSON parse
        result = json.loads(raw)
        if isinstance(result, dict):
            return {
                "key_decisions": result.get("key_decisions", []) or [],
                "unresolved_issues": result.get("unresolved_issues", []) or [],
                "technical_constraints": result.get("technical_constraints", []) or [],
            }

    except json.JSONDecodeError:
        # Try extracting from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, dict):
                    return {
                        "key_decisions": result.get("key_decisions", []) or [],
                        "unresolved_issues": result.get("unresolved_issues", []) or [],
                        "technical_constraints": result.get("technical_constraints", []) or [],
                    }
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse dialogue compression result, using fallback")

    except Exception:
        logger.warning("Dialogue compression LLM call failed, using fallback")

    # Fallback: extract last round's key info
    fallback_issues: list[str] = []
    for entry in old_entries[-4:]:
        if entry.get("role") == "reviewer":
            for q in (entry.get("questions") or [])[:2]:
                fallback_issues.append(q.get("question", "")[:80])

    return {
        "key_decisions": [],
        "unresolved_issues": fallback_issues,
        "technical_constraints": [],
    }


def _format_compressed_summary(summary: dict[str, list[str]]) -> str:
    """Format the compressed summary dict into prompt text."""
    parts: list[str] = ["## 历史对话摘要（前几轮压缩）"]

    decisions = summary.get("key_decisions") or []
    if decisions:
        parts.append("### 已做出的关键决策")
        for d in decisions:
            parts.append(f"- {d}")

    issues = summary.get("unresolved_issues") or []
    if issues:
        parts.append("### 仍未解决的问题")
        for i in issues:
            parts.append(f"- {i}")

    constraints = summary.get("technical_constraints") or []
    if constraints:
        parts.append("### 已确立的技术约束")
        for c in constraints:
            parts.append(f"- {c}")

    return "\n".join(parts) if len(parts) > 1 else ""


def compress_dialogue_rounds(
    history: list[dict],
    current_round: int,
    max_tokens: int,
    llm: Any,
) -> tuple[str, int]:
    """Compress dialogue history for prompt injection.

    Strategy:
    - current_round <= 2: keep all entries in full
    - current_round > 2: compress old rounds via LLM, keep recent round full

    Returns:
        (formatted_text, estimated_tokens)
    """
    if not history:
        return "", 0

    # Each round typically has 2 entries (reviewer questions + engineer/solution response)
    entries_per_round = 2

    if current_round <= 2:
        text = _format_history_entries(history)
        tokens = estimate_tokens(text)
        if tokens > max_tokens:
            text = adaptive_truncate(text, max_tokens)
            tokens = estimate_tokens(text)
        return text, tokens

    # Split: old rounds vs recent round
    recent_count = entries_per_round
    old_entries = history[:-recent_count] if len(history) > recent_count else []
    recent_entries = history[-recent_count:]

    if not old_entries:
        text = _format_history_entries(recent_entries)
        tokens = estimate_tokens(text)
        return text, tokens

    # Budget allocation: 60% for compressed summary, 40% for recent round
    recent_budget = int(max_tokens * 0.4)
    summary_budget = int(max_tokens * 0.6)

    summary_dict = _summarize_rounds(old_entries, llm)
    summary_text = _format_compressed_summary(summary_dict)
    summary_tokens = estimate_tokens(summary_text)

    if summary_tokens > summary_budget:
        summary_text = adaptive_truncate(summary_text, summary_budget)

    recent_text = _format_history_entries(recent_entries)
    recent_tokens = estimate_tokens(recent_text)
    if recent_tokens > recent_budget:
        recent_text = adaptive_truncate(recent_text, recent_budget)

    parts = []
    if summary_text:
        parts.append(summary_text)
    if recent_text:
        parts.append("\n## 最近一轮对话\n" + recent_text)

    result = "\n".join(parts)
    return result, estimate_tokens(result)
