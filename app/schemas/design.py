"""技术设计相关的 Pydantic Schema 定义。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceComponent(BaseModel):
    """服务组件。"""

    name: str = Field(..., description="服务名称")
    responsibility: str = Field(..., description="职责描述")
    tech_stack: list[str] = Field(default_factory=list, description="技术栈")


class DBTable(BaseModel):
    """数据库表设计。"""

    table_name: str = Field(..., description="表名")
    description: str = Field(..., description="表描述")
    columns: list[dict] = Field(default_factory=list, description="列定义列表, 每项包含 name/type/nullable/description")
    indexes: list[str] = Field(default_factory=list, description="索引描述")
    related_features: list[str] = Field(default_factory=list, description="覆盖的 PRD 功能模块名称")


class DBSchema(BaseModel):
    """数据库 Schema 设计。"""

    database_type: str = Field("PostgreSQL", description="数据库类型")
    tables: list[DBTable] = Field(default_factory=list, description="表列表")
    relationships: list[str] = Field(default_factory=list, description="表间关系描述")


class APIEndpoint(BaseModel):
    """API 端点设计。"""

    method: str = Field(..., description="HTTP 方法: GET / POST / PUT / DELETE")
    path: str = Field(..., description="端点路径")
    description: str = Field(..., description="端点描述")
    request_body: str = Field("", description="请求体描述")
    response_body: str = Field("", description="响应体描述")
    auth_required: bool = Field(True, description="是否需要认证")
    related_features: list[str] = Field(default_factory=list, description="覆盖的 PRD 功能模块名称")


class TechRisk(BaseModel):
    """技术风险。"""

    risk: str = Field(..., description="风险描述")
    impact: str = Field("medium", description="影响程度: high / medium / low")
    mitigation: str = Field("", description="缓解措施")


class CodeScaffold(BaseModel):
    """代码骨架建议。"""

    directory_structure: list[str] = Field(default_factory=list, description="目录结构")
    key_files: list[dict] = Field(
        default_factory=list,
        description="关键文件列表, 每项包含 path / purpose / skeleton",
    )
    dependencies: list[str] = Field(default_factory=list, description="核心依赖")


class TechnicalDesign(BaseModel):
    """Engineer Agent 输出的技术设计方案。"""

    architecture_overview: str = Field(..., description="架构概述")
    architecture_style: str = Field("", description="架构风格（微服务 / 单体 / Serverless 等）")
    services: list[ServiceComponent] = Field(default_factory=list, description="服务组件列表")
    db_schema: DBSchema = Field(default_factory=DBSchema, description="数据库设计")
    api_endpoints: list[APIEndpoint] = Field(default_factory=list, description="API 端点列表")
    tech_risks: list[TechRisk] = Field(default_factory=list, description="技术风险列表")
    code_scaffold: CodeScaffold = Field(default_factory=CodeScaffold, description="代码骨架建议")
