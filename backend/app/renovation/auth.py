"""岗位与权限：技术改造项目从立项到投运验收经过的岗位都在这里登记。

当前骨架没有登录体系，用请求头 X-Operator-Id 表示"当前是谁在岗"，
前端顶栏切换岗位时把该头带给后端。权限码与中文说明同时下发给前端，
越权时后端报缺哪个权限，前端可以原样提示。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from app.renovation.errors import PermissionDenied

# ---- 权限码：一个动作一个权限，错误提示里直接报缺哪一个 ----
PERM_PROJECT_CREATE = "renovation:project:create"        # 立项
PERM_BUDGET_EDIT = "renovation:budget:edit"              # 编制/修改预算
PERM_REVIEW = "renovation:review"                        # 审核通过
PERM_REVIEW_REJECT = "renovation:review:reject"          # 审核退回并写明理由
PERM_RESUBMIT = "renovation:resubmit"                    # 退回后修改重新提交
PERM_IMPLEMENT = "renovation:implement"                  # 实施推进
PERM_ACCEPT = "renovation:accept"                        # 投运验收 / 填写验收结论
PERM_OWNER_TRANSFER = "renovation:owner:transfer"        # 移交责任人
PERM_COOWNER_ADD = "renovation:owner:coadd"              # 指定跨部门共同责任人
PERM_VIEW_SHARED = "renovation:shared:view"              # 跨部门共同责任人共享查看

PERMISSION_LABELS: dict[str, str] = {
    PERM_PROJECT_CREATE: "立项",
    PERM_BUDGET_EDIT: "预算编制与修改",
    PERM_REVIEW: "审核通过",
    PERM_REVIEW_REJECT: "审核退回",
    PERM_RESUBMIT: "退回修改重新提交",
    PERM_IMPLEMENT: "实施推进",
    PERM_ACCEPT: "投运验收",
    PERM_OWNER_TRANSFER: "责任人移交",
    PERM_COOWNER_ADD: "共同责任人指定",
    PERM_VIEW_SHARED: "共享查看",
}

# 项目台账、立项单、投运验收三处出现的负责人，后端只保留这一个字段，
# 三处页面都从它渲染，天然保证是同一个人。
FIELD_OWNER = "责任人"
FIELD_OWNER_ID = "责任人Id"
FIELD_OWNER_DEPT = "责任部门"
FIELD_PROPOSER_ID = "立项人Id"
FIELD_PROPOSER = "立项人"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: str
    department: str

    @property
    def permissions(self) -> frozenset[str]:
        return ROLE_PERMISSIONS.get(self.role, frozenset())

    def can(self, permission: str) -> bool:
        return permission in self.permissions


# 岗位 -> 权限。审核岗位既能通过也能退回；查看岗什么改动权限都没有；
# 其余岗位只拿到本环节需要的权限，已投运项目能不能改由业务状态再卡一道。
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "立项岗": frozenset({
        PERM_PROJECT_CREATE,
        PERM_BUDGET_EDIT,
        PERM_RESUBMIT,
        PERM_OWNER_TRANSFER,
        PERM_COOWNER_ADD,
    }),
    "审核岗": frozenset({PERM_REVIEW, PERM_REVIEW_REJECT, PERM_OWNER_TRANSFER}),
    "预算岗": frozenset({PERM_BUDGET_EDIT}),
    "实施岗": frozenset({PERM_IMPLEMENT, PERM_OWNER_TRANSFER}),
    "验收岗": frozenset({PERM_ACCEPT, PERM_OWNER_TRANSFER}),
    "查看岗": frozenset(),
}

ROLE_LABELS: dict[str, str] = {
    "立项岗": "立项人",
    "审核岗": "审核岗位",
    "预算岗": "预算岗位",
    "实施岗": "实施岗位",
    "验收岗": "验收岗位",
    "查看岗": "查看岗位",
}


def require(user: User, permission: str, *, what: str | None = None) -> None:
    """权限守卫：缺权限当场拦下，错误信息写明缺的是哪个权限。"""
    if not user.can(permission):
        label = PERMISSION_LABELS.get(permission, permission)
        action = what or "该操作"
        raise PermissionDenied(
            permission,
            f"越权操作已拦截：当前岗位「{user.role}」缺少「{label}」权限（{permission}），无法{action}。"
        )


def current_operator(x_operator_id: str | None = Header(default=None, alias="X-Operator-Id")) -> User:
    """FastAPI 依赖：从请求头解析当前操作人；未识别时按 401 处理。"""
    from app.renovation.users import get_user  # 局部导入，避免与 users 模块循环引用

    user = get_user((x_operator_id or "").strip() or "u_zhang")
    if user is None:
        raise PermissionDenied(
            "renovation:login",
            f"未识别的操作人「{x_operator_id}」，请先在右上角切换到有效岗位。",
        )
    return user
