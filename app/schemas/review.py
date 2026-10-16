"""评审结果相关的 Pydantic Schema 定义。"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReviewTargetType(str, Enum):
    """回流目标类型。"""

    SOLUTION = "solution"
    ENGINEER = "engineer"
    NONE = "none"

    # 添加 __reduce__ 方法以支持 msgpack 序列化
    def __reduce__(self):
        return (self.__class__, (self.value,))


class ReviewIssue(BaseModel):
    """评审发现的问题。"""

    category: str = Field(..., description="问题类别（一致性 / 完整性 / 可实现性 / 其他）")
    severity: str = Field("medium", description="严重程度: critical / high / medium / low")
    description: str = Field(..., description="问题描述")
    suggestion: str = Field("", description="修改建议")
    target: ReviewTargetType = Field(
        ReviewTargetType.NONE,
        description="应回流到哪个节点修复",
    )


class ReviewResult(BaseModel):
    """Reviewer Agent 输出的评审结果。"""

    overall_score: float = Field(..., ge=0, le=10, description="总体评分 0-10")
    prd_score: float = Field(0, ge=0, le=10, description="PRD 质量评分")
    tech_score: float = Field(0, ge=0, le=10, description="技术设计质量评分")
    issues: list[ReviewIssue] = Field(default_factory=list, description="问题列表")
    suggestions: list[str] = Field(default_factory=list, description="总体修订建议")
    passed: bool = Field(False, description="是否通过评审")
    reflow_target: ReviewTargetType = Field(
        ReviewTargetType.NONE,
        description="若未通过，应回流到哪个节点",
    )
    summary: str = Field("", description="评审总结")

    @property
    def needs_reflow(self) -> bool:
        return not self.passed and self.reflow_target != ReviewTargetType.NONE
