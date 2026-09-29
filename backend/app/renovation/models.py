"""技术改造项目的出入参模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    项目名称: str = Field(min_length=1)
    预算金额: float | None = None


class ProjectPatch(BaseModel):
    """立项单可改字段；预算与名称走不同权限，服务层逐项校验。"""

    项目名称: str | None = None
    预算金额: float | None = None


class ProjectAction(BaseModel):
    action: str
    reason: str | None = None          # 审核退回理由（必填）
    conclusion: str | None = None      # 投运验收结论（必填）


class TransferPayload(BaseModel):
    to_user_id: str
    reason: str | None = None


class CoOwnerPayload(BaseModel):
    user_id: str


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None
