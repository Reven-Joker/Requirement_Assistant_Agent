"""Export Tool —— 将最终结果导出为 Markdown 文件。

V1 仅支持 Markdown 导出，后续可扩展 PDF / DOCX / Notion。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.logger import logger
from app.tools.template_tool import render_template


def export_deliverable(state_data: dict, task_id: str = "") -> dict[str, str]:
    """将交付产物导出为 Markdown 文件。

    Args:
        state_data: 包含所有产物的状态字典
        task_id: 任务 ID

    Returns:
        文件名到文件路径的映射。
    """
    settings = get_settings()
    output_dir = settings.output_dir / (task_id or "default")
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = {}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 1. 导出 PRD
    prd_doc = state_data.get("prd_doc")
    if prd_doc:
        try:
            content = render_template("prd", prd_doc)
            path = output_dir / f"prd_{timestamp}.md"
            path.write_text(content, encoding="utf-8")
            exported["prd"] = str(path)
        except Exception as e:
            logger.error(f"导出 PRD 失败: {e}")
            # 回退为 JSON 导出
            path = output_dir / f"prd_{timestamp}.json"
            path.write_text(json.dumps(prd_doc, ensure_ascii=False, indent=2), encoding="utf-8")
            exported["prd"] = str(path)

    # 2. 导出技术设计
    tech_design = state_data.get("technical_design")
    if tech_design:
        try:
            content = render_template("technical_design", tech_design)
            path = output_dir / f"technical_design_{timestamp}.md"
            path.write_text(content, encoding="utf-8")
            exported["technical_design"] = str(path)
        except Exception as e:
            logger.error(f"导出技术设计失败: {e}")
            path = output_dir / f"technical_design_{timestamp}.json"
            path.write_text(json.dumps(tech_design, ensure_ascii=False, indent=2), encoding="utf-8")
            exported["technical_design"] = str(path)

    # 3. 导出评审报告
    review_result = state_data.get("review_result")
    if review_result:
        try:
            content = render_template("review_report", review_result)
            path = output_dir / f"review_report_{timestamp}.md"
            path.write_text(content, encoding="utf-8")
            exported["review_report"] = str(path)
        except Exception as e:
            logger.error(f"导出评审报告失败: {e}")
            path = output_dir / f"review_report_{timestamp}.json"
            path.write_text(json.dumps(review_result, ensure_ascii=False, indent=2), encoding="utf-8")
            exported["review_report"] = str(path)

    # 4. 导出需求澄清结果
    clarified = state_data.get("clarified_requirement")
    if clarified:
        path = output_dir / f"requirement_{timestamp}.json"
        path.write_text(json.dumps(clarified, ensure_ascii=False, indent=2), encoding="utf-8")
        exported["clarified_requirement"] = str(path)

    # 5. 导出完整交付包 JSON
    path = output_dir / f"full_deliverable_{timestamp}.json"
    path.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8")
    exported["full_deliverable"] = str(path)

    logger.info(f"导出完成，共 {len(exported)} 个文件", extra={"task_id": task_id})
    return exported
