"""Skills Registry —— 统一管理 Agent 可调用的工具（技能）。

每个工具通过 register() 注册时声明适用的节点（applicable_nodes），
get_tools_for_node() 按节点名动态返回工具列表，避免在各 Agent 文件中硬编码。

节点名约定：
  "engineer_prep"   —— Engineer 预热阶段（无 technical_design，只允许检索）
  "engineer_react"  —— Engineer ReAct 循环（可调用覆盖率验证）
  "reviewer"        —— Reviewer 预热阶段
  "all"             —— 所有节点均可用
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool


@dataclass
class SkillMeta:
    """工具元数据。"""

    name: str
    description: str
    applicable_nodes: list[str]
    tool: BaseTool
    tags: list[str] = field(default_factory=list)


_registry: dict[str, SkillMeta] = {}


def register(meta: SkillMeta) -> None:
    """注册一个工具到 registry。重复注册同名工具会覆盖旧条目。"""
    _registry[meta.name] = meta


def get_tools_for_node(node: str) -> list[BaseTool]:
    """返回适用于指定节点的所有工具实例列表。"""
    return [
        m.tool
        for m in _registry.values()
        if node in m.applicable_nodes or "all" in m.applicable_nodes
    ]


def list_skills() -> list[dict[str, Any]]:
    """返回所有已注册工具的摘要，供调试或管理接口使用。"""
    return [
        {
            "name": m.name,
            "description": m.description,
            "applicable_nodes": m.applicable_nodes,
            "tags": m.tags,
        }
        for m in _registry.values()
    ]
