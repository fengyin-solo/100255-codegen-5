"""技术改造项目接口：台账、立项单、投运验收、责任人移交共用同一组数据。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.renovation.auth import (
    PERMISSION_LABELS,
    ROLE_LABELS,
    User,
    current_operator,
)
from app.renovation.errors import PermissionDenied, ProjectNotFound, RenovationError, RuleViolation
from app.renovation.models import (
    ActionResult,
    CoOwnerPayload,
    ProjectAction,
    ProjectCreate,
    ProjectPatch,
    TransferPayload,
)
from app.renovation.service import STATUSES, service
from app.renovation.users import USERS

router = APIRouter(prefix="/api/renovation", tags=["技术改造"])


def _raise_domain(error: Exception) -> None:
    if isinstance(error, PermissionDenied):
        raise HTTPException(
            status_code=403,
            detail={"message": error.message, "required_permission": error.required},
        )
    if isinstance(error, ProjectNotFound):
        raise HTTPException(status_code=404, detail={"message": str(error)})
    if isinstance(error, RuleViolation):
        raise HTTPException(status_code=400, detail={"message": str(error)})
    raise error


@router.get("/meta")
def meta() -> dict[str, object]:
    """岗位花名册、状态枚举与权限说明：前端顶栏切换岗位、渲染按钮都靠它。"""
    users = [
        {"id": u.id, "name": u.name, "role": u.role, "department": u.department,
         "permissions": sorted(u.permissions)}
        for u in USERS.values()
    ]
    return {
        "statuses": STATUSES,
        "users": users,
        "roles": [{"code": code, "label": label} for code, label in ROLE_LABELS.items()],
        "permission_labels": PERMISSION_LABELS,
    }


@router.get("/projects")
def list_projects(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    department: str | None = Query(default=None),
    page: int = 1,
    size: int = 50,
    user: User = Depends(current_operator),
) -> dict[str, object]:
    try:
        items, total = service.list_projects(
            user, keyword=keyword, status=status, department=department, page=page, size=size
        )
    except RenovationError as exc:
        _raise_domain(exc)
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/projects/{project_id}")
def get_project(project_id: int, user: User = Depends(current_operator)) -> dict[str, object]:
    try:
        entry = service.get_project(user, project_id)
        logs = service.transfer_logs(user, project_id)
    except Exception as exc:  # 领域异常统一翻译
        _raise_domain(exc)
    return {"entry": entry, "transfer_logs": logs}


@router.post("/projects", response_model=ActionResult)
def create_project(payload: ProjectCreate, user: User = Depends(current_operator)) -> ActionResult:
    try:
        entry, missing = service.create_project(user, payload.model_dump())
    except Exception as exc:
        _raise_domain(exc)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="改造项目已立项，责任人默认为立项人本人", entry=entry)


@router.patch("/projects/{project_id}", response_model=ActionResult)
def patch_project(project_id: int, payload: ProjectPatch, user: User = Depends(current_operator)) -> ActionResult:
    try:
        entry = service.patch_project(user, project_id, payload.model_dump(exclude_unset=True))
    except Exception as exc:
        _raise_domain(exc)
    return ActionResult(ok=True, message="立项单已更新", entry=entry)


@router.post("/projects/{project_id}/actions", response_model=ActionResult)
def run_action(
    project_id: int,
    payload: ProjectAction,
    user: User = Depends(current_operator),
) -> ActionResult:
    """流程动作：提交/通过/退回/重提/实施/报竣/投运，全部在此收口。"""
    handlers = {
        "提交审核": lambda: service.submit(user, project_id),
        "审核通过": lambda: service.review_approve(user, project_id),
        "审核退回": lambda: service.review_reject(user, project_id, payload.reason or ""),
        "重新提交": lambda: service.resubmit(user, project_id),
        "安排实施": lambda: service.start_implementation(user, project_id),
        "实施报竣": lambda: service.finish_implementation(user, project_id),
        "投运验收": lambda: service.accept(user, project_id, payload.conclusion or ""),
    }
    handler = handlers.get(payload.action)
    if handler is None:
        raise HTTPException(status_code=400, detail={"message": f"动作「{payload.action}」不在允许范围内"})
    try:
        entry = handler()
    except Exception as exc:
        _raise_domain(exc)
    return ActionResult(ok=True, message=f"{payload.action}已完成", entry=entry)


@router.post("/projects/{project_id}/transfer", response_model=ActionResult)
def transfer_owner(
    project_id: int,
    payload: TransferPayload,
    user: User = Depends(current_operator),
) -> ActionResult:
    try:
        entry = service.transfer_owner(user, project_id, payload.to_user_id, payload.reason)
    except Exception as exc:
        _raise_domain(exc)
    return ActionResult(ok=True, message="责任人移交已完成并留痕", entry=entry)


@router.post("/projects/{project_id}/co-owners", response_model=ActionResult)
def add_co_owner(
    project_id: int,
    payload: CoOwnerPayload,
    user: User = Depends(current_operator),
) -> ActionResult:
    try:
        entry = service.add_co_owner(user, project_id, payload.user_id)
    except Exception as exc:
        _raise_domain(exc)
    return ActionResult(ok=True, message="已指定跨部门共同责任人，可共享查看", entry=entry)


@router.get("/projects/{project_id}/transfers")
def list_transfers(project_id: int, user: User = Depends(current_operator)) -> dict[str, object]:
    """移交记录：刷新页面后仍从这里取回，保证移交历史不丢。"""
    try:
        logs = service.transfer_logs(user, project_id)
    except Exception as exc:
        _raise_domain(exc)
    return {"items": logs}
