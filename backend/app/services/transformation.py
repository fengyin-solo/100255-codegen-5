"""技术改造项目的权限、归属、状态流转与移交规则。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from app.store import store

MODULE = "transformation"

PERM_CREATE = "技术改造立项"
PERM_EDIT = "技术改造编辑"
PERM_SUBMIT = "技术改造提交"
PERM_REVIEW = "技术改造审核"
PERM_IMPLEMENT = "技术改造实施"
PERM_ACCEPT = "技术改造验收"
PERM_TRANSFER = "技术改造责任移交"
PERM_VIEW_ALL = "技术改造全局查看"
PERM_OWNER_SCOPE = "技术改造项目归属"

ROLE_ALIASES = {
    "initiator": "立项人",
    "proposer": "立项人",
    "creator": "立项人",
    "owner": "立项人",
    "reviewer": "审核岗",
    "audit": "审核岗",
    "implementer": "实施岗",
    "implementation": "实施岗",
    "acceptor": "验收岗",
    "acceptance": "验收岗",
    "viewer": "查看岗",
    "readonly": "查看岗",
}

PERMISSION_ALIASES = {
    "transformation:create": PERM_CREATE,
    "create": PERM_CREATE,
    "transformation:edit": PERM_EDIT,
    "edit": PERM_EDIT,
    "transformation:submit": PERM_SUBMIT,
    "submit": PERM_SUBMIT,
    "transformation:review": PERM_REVIEW,
    "review": PERM_REVIEW,
    "transformation:implement": PERM_IMPLEMENT,
    "implement": PERM_IMPLEMENT,
    "transformation:accept": PERM_ACCEPT,
    "accept": PERM_ACCEPT,
    "transformation:transfer": PERM_TRANSFER,
    "transfer": PERM_TRANSFER,
    "transformation:view-all": PERM_VIEW_ALL,
    "view-all": PERM_VIEW_ALL,
}

STATUS_DRAFT = "待提交"
STATUS_REVIEWING = "待审核"
STATUS_RETURNED = "已退回"
STATUS_APPROVED = "审核通过"
STATUS_IMPLEMENTING = "实施中"
STATUS_WAIT_ACCEPTANCE = "完工待验"
STATUS_OPERATING = "已投运"

LOCKED_STATUSES = {STATUS_OPERATING}

EDITABLE_FIELDS = [
    "项目编号",
    "项目名称",
    "预算金额",
    "改造内容",
    "计划完成日期",
]
PROTECTED_FIELDS = {
    "验收结论",
    "投运日期",
}
REQUIRED_CREATE_FIELDS = ["项目编号", "项目名称", "预算金额"]

ROLE_PRESETS: list[dict[str, Any]] = [
    {
        "name": "张三",
        "role": "立项人",
        "department": "技术科",
        "permissions": [PERM_CREATE, PERM_EDIT, PERM_SUBMIT, PERM_TRANSFER],
    },
    {
        "name": "李四",
        "role": "审核岗",
        "department": "技术科",
        "permissions": [PERM_REVIEW, PERM_VIEW_ALL],
    },
    {
        "name": "王五",
        "role": "实施岗",
        "department": "施工科",
        "permissions": [PERM_IMPLEMENT, PERM_VIEW_ALL, PERM_TRANSFER],
    },
    {
        "name": "赵六",
        "role": "验收岗",
        "department": "技术科",
        "permissions": [PERM_ACCEPT, PERM_VIEW_ALL],
    },
    {
        "name": "钱七",
        "role": "查看岗",
        "department": "安全科",
        "permissions": [],
    },
]


class PermissionDenied(Exception):
    """业务层鉴权失败：由路由统一转成 403。"""

    def __init__(self, permission: str, message: str | None = None) -> None:
        self.permission = permission
        super().__init__(message or f"越权操作：缺少权限「{permission}」")


class BusinessValidationError(Exception):
    """业务校验失败：由路由统一转成 400。"""


@dataclass(frozen=True)
class Actor:
    name: str
    role: str
    department: str
    permissions: frozenset[str]

    @property
    def is_anonymous(self) -> bool:
        return not self.name

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def header_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "role": self.role,
            "department": self.department,
            "permissions": ",".join(sorted(self.permissions)),
        }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def _co_owners(entry: dict[str, Any]) -> list[dict[str, str]]:
    owners = entry.get("共同责任人") or []
    result: list[dict[str, str]] = []
    if isinstance(owners, list):
        for item in owners:
            if isinstance(item, dict):
                name = _text(item.get("name") or item.get("name"))
                department = _text(item.get("department"))
            else:
                name = _text(item)
                department = ""
            if name:
                result.append({"name": name, "department": department})
    return result


def _is_responsible(entry: dict[str, Any], actor: Actor) -> bool:
    if actor.is_anonymous:
        return False
    if actor.name == _text(entry.get("负责人")):
        return True
    return any(item.get("name") == actor.name for item in _co_owners(entry))


class TransformationService:
    def actor_from_headers(self, headers: Any) -> Actor:
        name = _text(headers.get("x-user-name") or headers.get("x-user") or headers.get("x-operator"))
        role_input = _text(headers.get("x-user-role") or headers.get("x-role"))
        role = ROLE_ALIASES.get(role_input.lower(), role_input)
        department = _text(headers.get("x-user-department") or headers.get("x-department"))
        raw_permissions = headers.get("x-permissions") or headers.get("x-user-permissions") or ""
        if isinstance(raw_permissions, str):
            raw_list = [item.strip() for item in raw_permissions.split(",") if item.strip()]
        elif isinstance(raw_permissions, Iterable):
            raw_list = [_text(item) for item in raw_permissions if _text(item)]
        else:
            raw_list = []
        permissions = {PERMISSION_ALIASES.get(item.lower(), item) for item in raw_list}

        # 只传角色时按内置岗位补齐权限，避免前端漏传后鉴权口径不一致。
        if role and not permissions:
            for preset in ROLE_PRESETS:
                if preset["role"] == role:
                    permissions = set(preset["permissions"])
                    if not name:
                        name = str(preset["name"])
                    if not department:
                        department = str(preset["department"])
                    break
        return Actor(name=name, role=role, department=department, permissions=frozenset(permissions))

    def list_entries(
        self,
        actor: Actor,
        *,
        keyword: str | None = None,
        status: str | None = None,
        department: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [row for row in store.rows(MODULE) if self.can_view(row, actor)]
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in _text(row.get("项目编号"))
                or keyword in _text(row.get("项目名称"))
                or keyword in _text(row.get("负责人"))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if department:
            rows = [row for row in rows if row.get("责任部门") == department]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._with_permissions(row, actor) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int, actor: Actor) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None or not self.can_view(entry, actor):
            return None
        return self._with_permissions(entry, actor)

    def ledger_view(self, entry_id: int, actor: Actor) -> dict[str, Any] | None:
        return self.get_entry(entry_id, actor)

    def proposal_view(self, entry_id: int, actor: Actor) -> dict[str, Any] | None:
        entry = self.get_entry(entry_id, actor)
        if entry is None:
            return None
        return {
            "id": entry["id"],
            "项目编号": entry["项目编号"],
            "项目名称": entry["项目名称"],
            "负责人": entry["负责人"],
            "责任部门": entry["责任部门"],
            "立项人": entry["立项人"],
            "立项部门": entry["立项部门"],
            "预算金额": entry["预算金额"],
            "改造内容": entry["改造内容"],
            "计划完成日期": entry["计划完成日期"],
            "项目状态": entry["status"],
            "退回理由": entry["退回理由"],
        }

    def acceptance_view(self, entry_id: int, actor: Actor) -> dict[str, Any] | None:
        entry = self.get_entry(entry_id, actor)
        if entry is None:
            return None
        return {
            "id": entry["id"],
            "项目编号": entry["项目编号"],
            "项目名称": entry["项目名称"],
            "负责人": entry["负责人"],
            "责任部门": entry["责任部门"],
            "项目状态": entry["status"],
            "验收结论": entry["验收结论"],
            "投运日期": entry["投运日期"],
            "共同责任人": entry["共同责任人"],
        }

    def can_view(self, entry: dict[str, Any], actor: Actor) -> bool:
        # 未带身份没有可见范围；跨部门项目只按共同责任人共享给具体人员。
        if actor.is_anonymous:
            return False
        if actor.can(PERM_VIEW_ALL):
            return True
        return _is_responsible(entry, actor)

    def create_entry(self, values: dict[str, Any], actor: Actor) -> tuple[dict[str, Any] | None, list[str]]:
        self._require(actor, PERM_CREATE)
        missing = [field for field in REQUIRED_CREATE_FIELDS if not _text(values.get(field))]
        if missing:
            return None, missing
        budget = _as_float(values.get("预算金额"))
        if budget < 0:
            raise BusinessValidationError("预算金额必须是不小于 0 的数字")

        # 立项归属只能来自当前登录人，不能通过表单把责任人或责任部门伪造给他人。
        department = actor.department
        owner = actor.name
        if not department or not owner:
            raise BusinessValidationError("当前岗位缺少姓名或部门，不能建立技术改造项目归属")
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "status": STATUS_DRAFT,
            "pending": True,
            "abnormal": False,
            "项目编号": _text(values.get("项目编号")),
            "项目名称": _text(values.get("项目名称")),
            "责任部门": department,
            "负责人": owner,
            "立项人": actor.name,
            "立项部门": actor.department or department,
            "预算金额": budget,
            "改造内容": _text(values.get("改造内容")),
            "计划完成日期": _text(values.get("计划完成日期")),
            "验收结论": "",
            "投运日期": "",
            "退回理由": "",
            "共同责任人": [],
            "移交记录": [
                {
                    "from": "",
                    "from_department": "",
                    "to": owner,
                    "to_department": department,
                    "time": _now(),
                    "reason": "立项建档",
                }
            ],
        }
        rows.append(entry)
        return self._with_permissions(entry, actor), []

    def update_entry(self, entry_id: int, values: dict[str, Any], actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        protected = [field for field in PROTECTED_FIELDS if field in values]
        if protected:
            self._require(actor, PERM_ACCEPT)
            if entry.get("status") in LOCKED_STATUSES:
                self._ensure_locked(entry)
            if entry.get("status") != STATUS_WAIT_ACCEPTANCE:
                raise BusinessValidationError("只有完工待验项目可以填写验收结论")
            raise BusinessValidationError("验收结论只能通过投运验收动作修改")
        self._require(actor, PERM_EDIT)
        self._ensure_locked(entry)
        self._ensure_owner(entry, actor)

        changed: list[str] = []
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            if field == "预算金额":
                budget = _as_float(values.get(field))
                if budget < 0:
                    raise BusinessValidationError("预算金额必须是不小于 0 的数字")
                entry[field] = budget
            else:
                entry[field] = _text(values.get(field))
            changed.append(field)
        if not changed:
            raise BusinessValidationError("没有可修改的技术改造字段")
        return self._with_permissions(entry, actor), f"已保存 {len(changed)} 个字段"

    def run_action(self, entry_id: int, action: str, values: dict[str, Any], actor: Actor) -> tuple[dict[str, Any], str]:
        if action == "提交审核":
            return self.submit(entry_id, actor)
        if action == "审核通过":
            return self.approve(entry_id, actor)
        if action == "退回":
            return self.reject(entry_id, _text(values.get("reason") or values.get("退回理由") or values.get("remark")), actor)
        if action == "开始实施":
            return self.start_implementation(entry_id, actor)
        if action == "完工填报":
            return self.complete_implementation(entry_id, actor)
        if action == "投运验收":
            return self.accept(
                entry_id,
                _text(values.get("验收结论")),
                _text(values.get("投运日期")),
                actor,
            )
        raise BusinessValidationError(f"动作「{action}」不属于技术改造项目可执行范围")

    def submit(self, entry_id: int, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_SUBMIT)
        self._ensure_locked(entry)
        self._ensure_owner(entry, actor)
        if entry["status"] not in {STATUS_DRAFT, STATUS_RETURNED}:
            raise BusinessValidationError(f"当前状态「{entry['status']}」不能提交审核")
        entry["status"] = STATUS_REVIEWING
        entry["退回理由"] = ""
        self._refresh_flags(entry)
        return self._with_permissions(entry, actor), "技术改造项目已提交审核"

    def approve(self, entry_id: int, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_REVIEW)
        if entry["status"] != STATUS_REVIEWING:
            raise BusinessValidationError(f"当前状态「{entry['status']}」不在待审核环节")
        entry["status"] = STATUS_APPROVED
        entry["退回理由"] = ""
        self._refresh_flags(entry)
        return self._with_permissions(entry, actor), "技术改造项目审核通过"

    def reject(self, entry_id: int, reason: str, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_REVIEW)
        if entry["status"] != STATUS_REVIEWING:
            raise BusinessValidationError(f"当前状态「{entry['status']}」不能退回")
        if not reason:
            raise BusinessValidationError("退回时必须写明退回理由")
        entry["status"] = STATUS_RETURNED
        entry["退回理由"] = reason
        entry["abnormal"] = True
        entry["pending"] = True
        return self._with_permissions(entry, actor), "技术改造项目已退回立项人"

    def start_implementation(self, entry_id: int, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_IMPLEMENT)
        self._ensure_locked(entry)
        if entry["status"] != STATUS_APPROVED:
            raise BusinessValidationError("只有审核通过的技术改造项目可以开始实施")
        entry["status"] = STATUS_IMPLEMENTING
        self._refresh_flags(entry)
        return self._with_permissions(entry, actor), "技术改造项目已进入实施"

    def complete_implementation(self, entry_id: int, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_IMPLEMENT)
        self._ensure_locked(entry)
        if entry["status"] != STATUS_IMPLEMENTING:
            raise BusinessValidationError("只有实施中的技术改造项目可以填报完工")
        entry["status"] = STATUS_WAIT_ACCEPTANCE
        self._refresh_flags(entry)
        return self._with_permissions(entry, actor), "技术改造项目已提交完工验收"

    def accept(self, entry_id: int, conclusion: str, operation_date: str, actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_ACCEPT)
        self._ensure_locked(entry)
        if entry["status"] != STATUS_WAIT_ACCEPTANCE:
            raise BusinessValidationError("只有完工待验的技术改造项目可以办理投运验收")
        if not conclusion:
            raise BusinessValidationError("投运验收必须填写验收结论")
        entry["验收结论"] = conclusion
        entry["投运日期"] = operation_date or datetime.now().strftime("%Y-%m-%d")
        entry["status"] = STATUS_OPERATING
        self._refresh_flags(entry)
        return self._with_permissions(entry, actor), "技术改造项目已投运验收"

    def transfer_owner(self, entry_id: int, values: dict[str, Any], actor: Actor) -> tuple[dict[str, Any], str]:
        entry = self._find_visible(entry_id, actor)
        self._require(actor, PERM_TRANSFER)
        if _text(entry.get("负责人")) != actor.name or actor.department != _text(entry.get("责任部门")):
            raise PermissionDenied(PERM_OWNER_SCOPE, "只有当前部门内登记的当前负责人可以移交技术改造项目")

        to_name = _text(values.get("to") or values.get("新负责人") or values.get("负责人"))
        to_department = _text(values.get("to_department") or values.get("新责任部门") or values.get("责任部门"))
        reason = _text(values.get("reason") or values.get("移交原因"))
        if not to_name or not to_department:
            raise BusinessValidationError("移交必须填写新负责人和新责任部门")
        if not reason:
            raise BusinessValidationError("移交必须填写移交原因")
        if to_name == _text(entry.get("负责人")) and to_department == _text(entry.get("责任部门")):
            raise BusinessValidationError("新负责人与当前负责人相同，无需移交")

        old_name = _text(entry.get("负责人"))
        old_department = _text(entry.get("责任部门"))
        co_owners = _co_owners(entry)

        if to_department == old_department:
            # 同部门移交是负责人替换，不能在同一部门保留两个责任人。
            co_owners = [item for item in co_owners if item.get("department") != to_department]
            entry["负责人"] = to_name
            entry["责任部门"] = to_department
        else:
            # 跨部门移交是主责切换：目标部门若原先是共同责任部门，则升为主责；
            # 原主责部门转为共同责任部门。每个部门仍然只保留一名责任人。
            co_owners = [
                item
                for item in co_owners
                if item.get("department") not in {old_department, to_department}
            ]
            if old_name:
                co_owners.append({"name": old_name, "department": old_department})
            entry["负责人"] = to_name
            entry["责任部门"] = to_department

        entry["共同责任人"] = co_owners
        record = {
            "from": old_name,
            "from_department": old_department,
            "to": to_name,
            "to_department": to_department,
            "time": _text(values.get("time")) or _now(),
            "reason": reason,
        }
        entry.setdefault("移交记录", []).append(record)
        return self._with_permissions(entry, actor), "责任人移交记录已保存"

    def _find_visible(self, entry_id: int, actor: Actor) -> dict[str, Any]:
        entry = store.find(MODULE, entry_id)
        if entry is None or not self.can_view(entry, actor):
            raise BusinessValidationError(f"技术改造项目 {entry_id} 不存在或无权访问")
        return entry

    def _require(self, actor: Actor, permission: str) -> None:
        if not actor.can(permission):
            raise PermissionDenied(permission)

    def _ensure_owner(self, entry: dict[str, Any], actor: Actor) -> None:
        if actor.name != _text(entry.get("负责人")) or not actor.department:
            raise PermissionDenied(PERM_OWNER_SCOPE, "越权修改：当前项目不归当前登录人负责")
        if actor.department != _text(entry.get("责任部门")):
            raise PermissionDenied(PERM_OWNER_SCOPE, "越权修改：当前项目不在当前登录人所属部门")

    def _ensure_locked(self, entry: dict[str, Any]) -> None:
        if entry.get("status") in LOCKED_STATUSES:
            raise BusinessValidationError("技术改造项目已投运，除责任移交和查看外不能再改动台账、预算或验收结论")

    def _refresh_flags(self, entry: dict[str, Any]) -> None:
        entry["pending"] = entry["status"] != STATUS_OPERATING
        entry["abnormal"] = entry["status"] == STATUS_RETURNED

    def _with_permissions(self, entry: dict[str, Any], actor: Actor) -> dict[str, Any]:
        result = dict(entry)
        is_owner = (
            actor.name == _text(entry.get("负责人"))
            and actor.department == _text(entry.get("责任部门"))
        )
        result["当前用户权限"] = {
            "可查看": self.can_view(entry, actor),
            "可编辑": is_owner and actor.can(PERM_EDIT) and entry.get("status") not in LOCKED_STATUSES,
            "可审核": actor.can(PERM_REVIEW) and entry.get("status") == STATUS_REVIEWING,
            "可验收": actor.can(PERM_ACCEPT) and entry.get("status") == STATUS_WAIT_ACCEPTANCE,
            "可移交": is_owner and actor.can(PERM_TRANSFER),
        }
        return result


service = TransformationService()
