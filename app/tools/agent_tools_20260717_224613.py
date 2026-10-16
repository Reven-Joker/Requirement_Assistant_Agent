"""Agent 工具定义，供 Engineer / Reviewer 通过 tool calling 主动调用。

工具通过 LangChain 标准接口绑定，不依赖具体模型厂商。所选模型本身需要支持
tool calling；不支持该能力的轻量模型建议关闭相应实验能力。
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from app.core.config import get_settings
from app.tools.registry import SkillMeta, get_tools_for_node, register
from app.storage.repo_memory import search_memory_sync
from app.tools.coverage_metrics import (
    missing_feature_mappings,
    score_api_feature_coverage,
    score_db_feature_coverage,
    score_prd_tech_coverage,
)


@tool
def search_memory(query: str, memory_type: str = "case") -> str:
    """搜索历史项目案例、架构模式或评审记录。

    Args:
        query: 搜索关键词，描述当前需求的领域或功能特征
        memory_type: 记忆类型，可选 'case'（历史案例）、
                     'architecture_pattern'（架构模式）、'review'（评审记录）
    """
    allowed = {"case", "architecture_pattern", "review"}
    if memory_type not in allowed:
        memory_type = "case"
    hits = search_memory_sync(
        query,
        top_k=get_settings().memory_top_k,
        memory_types=[memory_type],
    )
    if not hits:
        return "未找到相关记忆。"
    lines = []
    for i, item in enumerate(hits, 1):
        meta = item.get("metadata") or {}
        content = str(item.get("content", ""))[:600]
        lines.append(
            f"{i}. [score={item.get('score')} domain={meta.get('domain', '')}]\n{content}"
        )
    return "\n\n".join(lines)


@tool
def validate_coverage(prd_json: str, design_json: str) -> str:
    """检查技术设计对 PRD 功能模块的覆盖率，返回缺失的模块列表。

    Args:
        prd_json: PRD 文档的 JSON 字符串
        design_json: 技术设计的 JSON 字符串
    """
    try:
        prd = json.loads(prd_json)
        design = json.loads(design_json)
    except json.JSONDecodeError as exc:
        return f"JSON 解析失败：{exc}"

    api_cov = score_api_feature_coverage(prd, design)
    db_cov = score_db_feature_coverage(prd, design)
    prd_cov = score_prd_tech_coverage(prd, design)
    missing = missing_feature_mappings(prd, design)

    result: dict[str, Any] = {
        "prd_coverage": round(prd_cov, 3),
        "api_coverage": round(api_cov, 3),
        "db_coverage": round(db_cov, 3),
        "missing_api_modules": missing["api"],
        "missing_db_modules": missing["db"],
        "passed": api_cov >= 0.8 and db_cov >= 0.8,
    }
    return json.dumps(result, ensure_ascii=False)


# ── Skills Registry 注册 ──────────────────────────────────────────────────────
register(SkillMeta(
    name="search_memory",
    description="搜索历史项目案例、架构模式或评审记录",
    applicable_nodes=["engineer_prep", "engineer_react", "reviewer"],
    tool=search_memory,
    tags=["memory", "rag"],
))

register(SkillMeta(
    name="validate_coverage",
    description="检查技术设计对 PRD 功能模块的覆盖率，返回缺失模块列表",
    applicable_nodes=["engineer_react"],
    tool=validate_coverage,
    tags=["coverage", "quality"],
))

# 动态从 registry 生成工具列表，新增工具只需 register() 一处
ENGINEER_PREP_TOOLS = get_tools_for_node("engineer_prep")
ENGINEER_REACT_TOOLS = get_tools_for_node("engineer_react")
REVIEWER_TOOLS = get_tools_for_node("reviewer")
