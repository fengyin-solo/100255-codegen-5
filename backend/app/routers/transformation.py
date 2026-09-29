"""技术改造项目接口：立项、审核、实施、投运验收与责任移交。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.transformation import (
    ROLE_PRESETS,
    BusinessValidationError,
    PermissionDenied,
    service,
)

router = APIRouter(prefix="/api/transformation", tags=["技术改造"])


def _actor(request: Request):
    return service.actor_from_headers(request.headers)


def _fail(error: Exception):
    if isinstance(error, PermissionDenied):
        raise HTTPException(status_code=403, detail=f"{error}，请联系岗位管理员开通对应权限")
    if isinstance(error, BusinessValidationError):
        raise HTTPException(status_code=400, detail=str(error))
    raise error


def _paginated_views(rows: list[dict[str, Any]], request: Request, view_name: str) -> list[dict[str, Any]]:
    actor = _actor(request)
    items: list[dict[str, Any]] = []
    for row in rows:
        if view_name == "proposal":
            view = service.proposal_view(int(row["id"]), actor)
        else:
            view = service.acceptance_view(int(row["id"]), actor)
        if view is not None:
            items.append(view)
    return items


@router.get("", response_model=PageResult[dict])
def list_entries(
    request: Request,
    keyword: str | None = Query(default=None, description="按项目编号、项目名称或负责人检索"),
    status: str | None = Query(default=None, description="项目状态"),
    department: str | None = Query(default=None, description="责任部门"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """返回当前身份可见的技术改造项目台账。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        _actor(request),
        keyword=keyword,
        status=status,
        department=department,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/roles")
def roles() -> dict[str, Any]:
    """给前端角色切换器提供岗位、部门和权限样例。"""
    return {"items": ROLE_PRESETS}


@router.get("/proposal")
def list_proposals(
    request: Request,
    keyword: str | None = None,
    status: str | None = None,
    department: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """立项单列表，负责人口径与项目台账保持一致。"""
    rows, _ = service.list_entries(
        _actor(request),
        keyword=keyword,
        status=status,
        department=department,
        page=page,
        size=size,
    )
    items = _paginated_views(rows, request, "proposal")
    return PageResult(items=items, total=len(items), page=page, size=size)


@router.get("/acceptance")
def list_acceptance(
    request: Request,
    keyword: str | None = None,
    status: str | None = None,
    department: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """投运验收列表，直接读取同一条项目主记录，避免三处负责人不一致。"""
    rows, _ = service.list_entries(
        _actor(request),
        keyword=keyword,
        status=status,
        department=department,
        page=page,
        size=size,
    )
    items = _paginated_views(rows, request, "acceptance")
    return PageResult(items=items, total=len(items), page=page, size=size)


@router.get("/export")
def export_entries(request: Request) -> dict[str, Any]:
    """导出可见技术改造项目清单。"""
    items, total = service.list_entries(_actor(request), page=1, size=10000)
    return {"module": "transformation", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, request: Request) -> dict:
    try:
        entry = service.get_entry(entry_id, _actor(request))
    except (PermissionDenied, BusinessValidationError) as error:
        _fail(error)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"技术改造项目 {entry_id} 不存在或无权访问")
    return entry


@router.get("/{entry_id}/proposal", response_model=dict)
def get_proposal(entry_id: int, request: Request) -> dict:
    entry = service.proposal_view(entry_id, _actor(request))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"立项单 {entry_id} 不存在或无权访问")
    return entry


@router.get("/{entry_id}/acceptance", response_model=dict)
def get_acceptance(entry_id: int, request: Request) -> dict:
    entry = service.acceptance_view(entry_id, _actor(request))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投运验收页 {entry_id} 不存在或无权访问")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, request: Request) -> ActionResult:
    try:
        entry, missing = service.create_entry(payload.values, _actor(request))
    except (PermissionDenied, BusinessValidationError) as error:
        _fail(error)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="技术改造项目已立项", entry=entry)


@router.patch("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload, request: Request) -> ActionResult:
    try:
        entry, message = service.update_entry(entry_id, payload.values, _actor(request))
    except (PermissionDenied, BusinessValidationError) as error:
        _fail(error)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, request: Request) -> ActionResult:
    values = payload.values
    action = str(values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, values, _actor(request))
    except (PermissionDenied, BusinessValidationError) as error:
        _fail(error)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/transfer", response_model=ActionResult)
def transfer_owner(entry_id: int, payload: EntryPayload, request: Request) -> ActionResult:
    try:
        entry, message = service.transfer_owner(entry_id, payload.values, _actor(request))
    except (PermissionDenied, BusinessValidationError) as error:
        _fail(error)
    return ActionResult(ok=True, message=message, entry=entry)
