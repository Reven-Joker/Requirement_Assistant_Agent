"""Template Tool —— 加载 PRD / API / 项目目录模板。

V1 提供内置的 Jinja2 模板渲染能力，后续可加入更多企业模板。
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from app.core.config import get_settings

# 内置模板（当文件系统模板不存在时使用）
_BUILTIN_TEMPLATES = {
    "prd": """# {{ product_name }} - 产品需求文档 (PRD)

## 1. 产品定位
{{ positioning }}

## 2. 用户故事
{% for story in user_stories %}
- 作为 **{{ story.role }}**，我希望 {{ story.action }}，以便 {{ story.benefit }}
{% endfor %}

## 3. 功能模块
{% for module in feature_modules %}
### {{ module.priority }} - {{ module.name }}
{{ module.description }}
{% if module.sub_features %}
{% for sub in module.sub_features %}
  - {{ sub }}
{% endfor %}
{% endif %}
{% endfor %}

## 4. 用户流程
{% for flow in user_flows %}
### {{ flow.name }}
{% for step in flow.steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{% endfor %}

## 5. 非功能性需求
{% for nfr in non_functional_requirements %}
- **{{ nfr.category }}**：{{ nfr.description }}{% if nfr.metric %}（指标：{{ nfr.metric }}）{% endif %}
{% endfor %}

## 6. 成功指标
{% for metric in success_metrics %}
- {{ metric }}
{% endfor %}

## 7. 不在范围内
{% for item in out_of_scope %}
- {{ item }}
{% endfor %}
""",
    "technical_design": """# {{ architecture_overview }} - 技术设计方案

## 1. 架构风格
{{ architecture_style }}

## 2. 服务组件
{% for svc in services %}
### {{ svc.name }}
- 职责：{{ svc.responsibility }}
- 技术栈：{{ svc.tech_stack | join(', ') }}
{% endfor %}

## 3. 数据库设计（{{ db_schema.database_type }}）
{% for table in db_schema.tables %}
### {{ table.table_name }}
{{ table.description }}

| 字段 | 类型 | 可空 | 描述 |
|------|------|------|------|
{% for col in table.columns %}
| {{ col.name }} | {{ col.type }} | {{ col.nullable }} | {{ col.description }} |
{% endfor %}
{% endfor %}

## 4. API 端点
{% for api in api_endpoints %}
### {{ api.method }} {{ api.path }}
{{ api.description }}
- 认证：{{ "是" if api.auth_required else "否" }}
{% endfor %}

## 5. 技术风险
{% for risk in tech_risks %}
- **{{ risk.impact }}** - {{ risk.risk }}
  - 缓解：{{ risk.mitigation }}
{% endfor %}

## 6. 代码骨架
```
{% for dir in code_scaffold.directory_structure %}
{{ dir }}
{% endfor %}
```
""",
    "review_report": """# 评审报告

## 评分总览
- 总体评分：{{ overall_score }} / 10
- PRD 评分：{{ prd_score }} / 10
- 技术评分：{{ tech_score }} / 10
- 是否通过：{{ "通过" if passed else "未通过" }}

## 问题列表
{% for issue in issues %}
### [{{ issue.severity | upper }}] {{ issue.category }}
{{ issue.description }}
- 建议：{{ issue.suggestion }}
- 回流目标：{{ issue.target }}
{% endfor %}

## 修订建议
{% for s in suggestions %}
- {{ s }}
{% endfor %}

## 评审总结
{{ summary }}
""",
}


def render_template(template_name: str, data: dict) -> str:
    """渲染模板。

    优先从文件系统加载，找不到则使用内置模板。

    Args:
        template_name: 模板名称（不带扩展名）
        data: 模板变量字典

    Returns:
        渲染后的 Markdown 文本。
    """
    settings = get_settings()
    templates_dir = settings.templates_dir

    # 尝试文件系统模板
    file_path = templates_dir / f"{template_name}.md.j2"
    if file_path.exists():
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template(f"{template_name}.md.j2")
        return template.render(**data)

    # 使用内置模板
    if template_name in _BUILTIN_TEMPLATES:
        env = Environment(loader=BaseLoader())
        template = env.from_string(_BUILTIN_TEMPLATES[template_name])
        return template.render(**data)

    raise ValueError(f"模板 '{template_name}' 不存在")


def list_templates() -> list[str]:
    """列出所有可用模板名称。"""
    settings = get_settings()
    templates_dir = settings.templates_dir

    names = set(_BUILTIN_TEMPLATES.keys())
    if templates_dir.exists():
        for f in templates_dir.glob("*.md.j2"):
            names.add(f.stem.replace(".md", ""))
    return sorted(names)
