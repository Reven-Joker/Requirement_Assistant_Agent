"""Repairer Agent — 轻量修复，只修补 Reviewer 指出的具体覆盖缺口。

与 Engineer 完整重做不同，Repairer 仅针对 missing_api / missing_db
清单生成精准的 API 端点和 DB 表，保留已有设计不变。
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import get_structured_llm
from app.core.logger import logger
from app.graph.state import AgentState
from app.memory.short_term import add_entry
from app.tools.coverage_metrics import missing_feature_mappings

REPAIRER_SYSTEM = """你是一名精准修复工程师。现有技术设计未能完全覆盖 PRD 的功能模块。

你的任务：**只生成缺失部分的 API 端点和数据库表**，已有的设计不要改动。

要求：
- 每个缺失的功能模块生成 1-2 个语义明确的 API 端点（路径包含功能关键词，如 /orders/refund 而非 /feature-modules/slug/actions）
- 每个缺失的功能模块生成 1 张语义明确的 DB 表（表名包含功能关键词，如 refund_records）
- API 端点包含：method, path, description, request_body, response_body, auth_required
- DB 表包含：table_name, description, columns（id/业务字段/status/created_at）, indexes

输出只包含 JSON（不要 markdown）：
{
  "api_endpoints": [{...}],
  "db_tables": [{...}]
}"""


class RepairOutput(BaseModel):
    """Repairer 轻量修复输出 — 仅包含缺失的 API 端点和 DB 表。"""

    api_endpoints: list[dict] = Field(default_factory=list)
    db_tables: list[dict] = Field(default_factory=list)


def repairer_node(state: AgentState) -> dict:
    """Repairer 节点：精准修补技术设计中的覆盖缺口。"""
    logger.info("Repairer Agent 开始执行", extra={"node": "repairer"})

    prd_doc = state.get("prd_doc", {})
    design = state.get("technical_design", {})
    review_result = state.get("review_result", {})

    missing = missing_feature_mappings(prd_doc, design)

    if not missing["api"] and not missing["db"]:
        logger.info("Repairer: 无覆盖缺口，跳过修复")
        return {
            "repair_attempted": True,
            "current_node": "repairer",
            "execution_logs": [{
                "node": "repairer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "no_gaps_found",
            }],
        }

    review_issues = review_result.get("issues") or []
    review_suggestions = review_result.get("suggestions") or []
    extra_hints = ""
    for issue in review_issues:
        if issue.get("target") == "engineer":
            extra_hints += f"- [{issue.get('severity', '?')}] {issue.get('description', '')}: {issue.get('suggestion', '')}\n"
    for s in review_suggestions[:3]:
        extra_hints += f"- {s}\n"

    existing_summary = _summarize_existing(design)

    prompt = (
        f"## PRD 功能模块描述\n{json.dumps(prd_doc.get('feature_modules', []), ensure_ascii=False, indent=2)[:2000]}\n\n"
        f"## 已有设计摘要（请勿改动）\n{existing_summary}\n\n"
        f"## 缺失的 API 覆盖（功能模块）\n{', '.join(missing['api'])}\n\n"
        f"## 缺失的 DB 覆盖（功能模块）\n{', '.join(missing['db'])}\n\n"
        f"## Reviewer 意见\n{extra_hints or '无'}\n\n"
        "请生成缺失的 API 端点和 DB 表（只输出 JSON）。"
    )

    settings = get_settings()
    structured_llm = get_structured_llm(RepairOutput, temperature=0.2)

    try:
        result: RepairOutput = structured_llm.invoke([
            SystemMessage(content=REPAIRER_SYSTEM),
            HumanMessage(content=prompt),
        ])
        repair_json = result.model_dump()
    except Exception as exc:
        logger.warning("Repairer LLM 调用失败，跳过修复", extra={"error": str(exc)[:200]})
        return {
            "repair_attempted": True,
            "current_node": "repairer",
            "execution_logs": [{
                "node": "repairer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "llm_failed",
                "error": str(exc)[:200],
            }],
        }

    patched = _merge_repairs(design, repair_json)

    new_api = len(repair_json.get("api_endpoints") or [])
    new_tables = len(repair_json.get("db_tables") or [])

    logger.info(
        "Repairer Agent 执行完成",
        extra={"node": "repairer", "new_api": new_api, "new_tables": new_tables},
    )

    task_mem = add_entry(
        state, "repairer",
        summary=f"精准修补：新增 {new_api} 个 API、{new_tables} 张 DB 表",
        key_decisions=[f"缺失 API: {', '.join(missing['api'][:5])}",
                       f"缺失 DB: {', '.join(missing['db'][:5])}"],
        metrics={"new_api": new_api, "new_tables": new_tables},
    )

    return {
        "technical_design": patched,
        "repair_attempted": True,
        "current_node": "repairer",
        **task_mem,
        "execution_logs": [{
            "node": "repairer",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "repaired",
            "new_api_endpoints": new_api,
            "new_db_tables": new_tables,
        }],
    }


def _summarize_existing(design: dict) -> str:
    """Build a compact summary of existing design for the repair prompt."""
    api_paths = [e.get("path", "") for e in (design.get("api_endpoints") or [])[:10]]
    tables = [t.get("table_name", "") for t in ((design.get("db_schema") or {}).get("tables") or [])[:10]]
    services = [s.get("name", "") for s in (design.get("services") or [])[:5]]
    return (
        f"API: {', '.join(api_paths) if api_paths else '无'}\n"
        f"DB 表: {', '.join(tables) if tables else '无'}\n"
        f"服务: {', '.join(services) if services else '无'}\n"
        f"架构风格: {design.get('architecture_style', '未知')}"
    )


def _merge_repairs(design: dict, repair: dict) -> dict:
    """Merge repaired entries into the existing design."""
    patched = deepcopy(design)
    patched.setdefault("api_endpoints", [])
    patched.setdefault("db_schema", {})
    patched["db_schema"].setdefault("tables", [])

    for ep in repair.get("api_endpoints") or []:
        patched["api_endpoints"].append(ep)

    for table in repair.get("db_tables") or []:
        patched["db_schema"]["tables"].append(table)

    return patched
