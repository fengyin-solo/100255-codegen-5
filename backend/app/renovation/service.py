"""技术改造项目领域服务：状态流转、权限拦截、责任人唯一约束与移交留痕。

归属规则（后端单点落地，三个页面共用同一份数据）：
1. 立项人只能改自己提交的项目；其他人改预算、改立项单都会被拦下。
2. 审核岗可通过、可退回，退回必须写明理由，项目回到"已退回"由立项人修改重提。
3. 已投运项目对其余岗位只读：预算、验收结论、责任人一律不可再动。
4. 同一个项目在同一个责任部门内只能有一个责任人；共同责任人必须来自其他部门。
5. 移交责任人写入移交记录表，刷新后仍可查；责任部门随新责任人变更。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.renovation.auth import (
    FIELD_OWNER,
    FIELD_OWNER_DEPT,
    FIELD_OWNER_ID,
    FIELD_PROPOSER,
    FIELD_PROPOSER_ID,
    PERM_ACCEPT,
    PERM_BUDGET_EDIT,
    PERM_COOWNER_ADD,
    PERM_IMPLEMENT,
    PERM_OWNER_TRANSFER,
    PERM_PROJECT_CREATE,
    PERM_RESUBMIT,
    PERM_REVIEW,
    PERM_REVIEW_REJECT,
    User,
    require,
)
from app.renovation.errors import PermissionDenied, ProjectNotFound, RuleViolation
from app.renovation.users import USERS, user_brief
from app.store import store

MODULE = "renovation_project"
TRANSFER_MODULE = "renovation_transfer"

# 立项 → 投运验收的状态序列
STATUS_DRAFT = "编制中"
STATUS_PENDING = "待审核"
STATUS_REJECTED = "已退回"
STATUS_APPROVED = "已批复"
STATUS_IMPLEMENTING = "实施中"
STATUS_ACCEPT_PENDING = "待验收"
STATUS_RUNNING = "已投运"

STATUSES = [
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_APPROVED,
    STATUS_IMPLEMENTING,
    STATUS_ACCEPT_PENDING,
    STATUS_RUNNING,
]

# 已投运之后任何写动作都不再开放
LOCKED_STATUSES = {STATUS_RUNNING}

REQUIRED_CREATE_FIELDS = ["项目名称"]


def _deny_not_owner(user: User, reason: str) -> PermissionDenied:
    return PermissionDenied(
        "renovation:owner:self",
        f"越权操作已拦截：{reason}。当前操作人{user.name}（{user.role}）不是该项目的归属人。",
    )


class RenovationService:
    # ---------------- 读取 ----------------
    def list_projects(
        self,
        user: User,
        *,
        keyword: str | None = None,
        status: str | None = None,
        department: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [row for row in store.rows(MODULE) if self.can_view(user, row)]
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("项目编号", "")) or keyword in str(row.get("项目名称", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if department:
            rows = [row for row in rows if row.get(FIELD_OWNER_DEPT) == department]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._serialize(row, user) for row in rows[start:start + size]], total

    def get_project(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_visible(user, project_id)
        return self._serialize(row, user)

    def transfer_logs(self, user: User, project_id: int) -> list[dict[str, Any]]:
        self._find_visible(user, project_id)
        return [
            dict(log)
            for log in store.rows(TRANSFER_MODULE)
            if int(log.get("project_id", 0)) == project_id
        ]

    # ---------------- 立项 ----------------
    def create_project(self, user: User, values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        require(user, PERM_PROJECT_CREATE, what="立项登记")
        missing = [f for f in REQUIRED_CREATE_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, missing  # type: ignore[return-value]
        budget = values.get("预算金额")
        if budget is not None:
            self._validate_budget(budget)
        rows = store.rows(MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        row = {
            "id": next_id,
            "项目编号": f"TECH-{datetime.now().year}-{next_id:03d}",
            "项目名称": str(values["项目名称"]).strip(),
            FIELD_OWNER_DEPT: user.department,
            FIELD_OWNER_ID: user.id,
            FIELD_PROPOSER_ID: user.id,
            "共同责任人Ids": [],
            "预算金额": budget,
            "status": STATUS_DRAFT,
            "pending": True,
            "abnormal": False,
            "退回理由": "",
            "验收结论": "",
        }
        rows.append(row)
        self._append_log(row, user, "立项", "立项登记，责任人默认为立项人本人")
        return self._serialize(row, user), []

    def patch_project(self, user: User, project_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        # 越权先报缺哪个权限：改预算走预算权限，改名称/立项单走归属
        if patch.get("预算金额") is not None:
            require(user, PERM_BUDGET_EDIT, what="修改预算")
        if row.get(FIELD_PROPOSER_ID) != user.id:
            # 立项单归属立项人本人：不是自己提交的项目，连名称都不能改
            raise PermissionDenied(
                "renovation:owner:self",
                f"越权操作已拦截：只能修改本人提交的改造项目。"
                f"当前操作人{user.name}（{user.role}）不是该项目的立项人。",
            )
        self._ensure_unlocked(row)
        if "项目名称" in patch and patch["项目名称"] is not None:
            if not str(patch["项目名称"]).strip():
                raise RuleViolation("项目名称不能为空")
            row["项目名称"] = str(patch["项目名称"]).strip()
        if "预算金额" in patch and patch["预算金额"] is not None:
            if row["status"] not in (STATUS_DRAFT, STATUS_REJECTED):
                raise RuleViolation(f"项目已进入{row['status']}环节，预算不能再修改")
            self._validate_budget(patch["预算金额"])
            row["预算金额"] = float(patch["预算金额"])
        self._append_log(row, user, "修改立项单", "更新立项单内容/预算")
        return self._serialize(row, user)

    # ---------------- 流程动作 ----------------
    def submit(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        if row.get(FIELD_PROPOSER_ID) != user.id:
            raise _deny_not_owner(user, "只能提交本人立项的改造项目")
        self._ensure_unlocked(row)
        if row["status"] not in (STATUS_DRAFT, STATUS_REJECTED):
            raise RuleViolation(f"当前状态为{row['status']}，不能重复提交")
        if row.get("预算金额") is None:
            raise RuleViolation("预算金额尚未编制，无法提交审核")
        row["status"] = STATUS_PENDING
        row["abnormal"] = False
        row["退回理由"] = ""
        self._append_log(row, user, "提交审核", "立项单提交至审核岗位")
        return self._serialize(row, user)

    def review_approve(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_REVIEW, what="审核通过")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_PENDING:
            raise RuleViolation(f"项目当前为{row['status']}，不在待审核环节")
        row["status"] = STATUS_APPROVED
        self._append_log(row, user, "审核通过", "同意立项批复")
        return self._serialize(row, user)

    def review_reject(self, user: User, project_id: int, reason: str) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_REVIEW_REJECT, what="退回立项单")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_PENDING:
            raise RuleViolation(f"项目当前为{row['status']}，不在待审核环节")
        reason = (reason or "").strip()
        if not reason:
            raise RuleViolation("退回必须写明理由，便于立项人修改后重新提交")
        row["status"] = STATUS_REJECTED
        row["abnormal"] = True
        row["退回理由"] = reason
        self._append_log(row, user, "审核退回", reason)
        return self._serialize(row, user)

    def resubmit(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_RESUBMIT, what="退回后重新提交")
        if row.get(FIELD_PROPOSER_ID) != user.id:
            raise _deny_not_owner(user, "只有立项人本人能在退回后修改重提")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_REJECTED:
            raise RuleViolation(f"项目当前为{row['status']}，不是退回状态")
        if not str(row.get("退回理由") or "").strip():
            raise RuleViolation("缺少退回记录，无法走重新提交流程")
        row["status"] = STATUS_PENDING
        row["abnormal"] = False
        self._append_log(row, user, "重新提交", "已按退回理由修改，重新送审")
        return self._serialize(row, user)

    def start_implementation(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_IMPLEMENT, what="安排实施")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_APPROVED:
            raise RuleViolation(f"项目当前为{row['status']}，须批复后才能安排实施")
        row["status"] = STATUS_IMPLEMENTING
        self._append_log(row, user, "安排实施", "项目进入现场实施")
        return self._serialize(row, user)

    def finish_implementation(self, user: User, project_id: int) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_IMPLEMENT, what="实施报竣")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_IMPLEMENTING:
            raise RuleViolation(f"项目当前为{row['status']}，未在实施中")
        row["status"] = STATUS_ACCEPT_PENDING
        self._append_log(row, user, "实施报竣", "现场施工完成，申请投运验收")
        return self._serialize(row, user)

    def accept(self, user: User, project_id: int, conclusion: str) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_ACCEPT, what="填写投运验收结论")
        self._ensure_unlocked(row)
        if row["status"] != STATUS_ACCEPT_PENDING:
            raise RuleViolation(f"项目当前为{row['status']}，还未到投运验收环节")
        conclusion = (conclusion or "").strip()
        if not conclusion:
            raise RuleViolation("投运验收必须填写验收结论")
        row["status"] = STATUS_RUNNING
        row["pending"] = False
        row["验收结论"] = conclusion
        # 投运后锁定：写动作统一由 _ensure_unlocked 拦死，其余岗位只读
        self._append_log(row, user, "投运验收", conclusion)
        return self._serialize(row, user)

    # ---------------- 责任人 ----------------
    def transfer_owner(self, user: User, project_id: int, to_user_id: str, reason: str | None) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_OWNER_TRANSFER, what="移交责任人")
        # 已投运项目对所有岗位只读：先于部门归属判定，统一给出只读提示
        self._ensure_unlocked(row)
        target = USERS.get((to_user_id or "").strip())
        if target is None:
            raise RuleViolation(f"系统内不存在人员「{to_user_id}」，无法移交")
        # 岗位侧约束：有移交权限的岗位只能动本部门持有的项目
        # （审核岗对在审项目除外，避免跨部门审核时无法纠正责任人）
        if user.role != "审核岗" and user.department != row[FIELD_OWNER_DEPT]:
            raise _deny_not_owner(user, "只能移交本部门持有的改造项目")
        if target.id == row[FIELD_OWNER_ID]:
            raise RuleViolation(f"{target.name}已经是该项目责任人，无需重复移交")

        # 同部门唯一责任人：新责任人部门里不能已有同项目责任人 ——
        # 共同责任人若与新责任人同部门，会造成一个部门两个责任人，拦下。
        co_ids: list[str] = row.get("共同责任人Ids", [])
        for co_id in co_ids:
            co = USERS.get(co_id)
            if co and co.department == target.department:
                raise RuleViolation(
                    f"{target.department}已有共同责任人{co.name}，"
                    "同一个改造项目在同一部门内不能出现两个责任人"
                )

        previous_owner_id = row[FIELD_OWNER_ID]
        previous = USERS[previous_owner_id]
        previous_dept = row[FIELD_OWNER_DEPT]
        row[FIELD_OWNER_ID] = target.id
        row[FIELD_OWNER_DEPT] = target.department

        record = {
            "id": max((int(log.get("id", 0)) for log in store.rows(TRANSFER_MODULE)), default=0) + 1,
            "project_id": project_id,
            "项目编号": row["项目编号"],
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "移交人Id": user.id,
            "移交人": user.name,
            "原责任人Id": previous_owner_id,
            "原责任人": previous.name,
            "原责任部门": previous_dept,
            "新责任人Id": target.id,
            "新责任人": target.name,
            "新责任部门": target.department,
            "移交原因": (reason or "").strip() or "工作调整",
        }
        store.rows(TRANSFER_MODULE).append(record)
        self._append_log(row, user, "责任人移交", f"{previous.name}（{previous_dept}）→ {target.name}（{target.department}）")
        return self._serialize(row, user)

    def add_co_owner(self, user: User, project_id: int, co_user_id: str) -> dict[str, Any]:
        row = self._find_for_write(project_id)
        require(user, PERM_COOWNER_ADD, what="指定跨部门共同责任人")
        # 已投运只读先于归属判定
        self._ensure_unlocked(row)
        if row.get(FIELD_PROPOSER_ID) != user.id and row[FIELD_OWNER_ID] != user.id:
            raise _deny_not_owner(user, "只有立项人或当前责任人能指定共同责任人")
        target = USERS.get((co_user_id or "").strip())
        if target is None:
            raise RuleViolation(f"系统内不存在人员「{co_user_id}」")
        if target.department == row[FIELD_OWNER_DEPT]:
            raise RuleViolation(
                f"{target.name}属于责任部门{target.department}，共同责任人必须来自其他部门"
            )
        co_ids: list[str] = row.setdefault("共同责任人Ids", [])
        # 同一部门不能出现两个责任人：已存在该部门的共同责任人则拒绝
        for existing_id in co_ids:
            existing = USERS.get(existing_id)
            if existing and existing.department == target.department:
                raise RuleViolation(
                    f"{target.department}已有共同责任人{existing.name}，"
                    "同一个改造项目在同一部门内不能出现两个责任人"
                )
        if target.id in co_ids:
            raise RuleViolation(f"{target.name}已是共同责任人")
        co_ids.append(target.id)
        self._append_log(row, user, "增加共同责任人", f"{target.name}（{target.department}）")
        return self._serialize(row, user)

    # ---------------- 可见性 ----------------
    def can_view(self, user: User, row: dict[str, Any]) -> bool:
        """项目台账的可见口径：责任部门成员、责任人/立项人、跨部门共同责任人。

        审核岗需看到待审/退回件，验收岗需看到待验收件 —— 按待办环节放行。
        """
        if user.department == row.get(FIELD_OWNER_DEPT):
            return True
        if user.id in (row.get(FIELD_OWNER_ID), row.get(FIELD_PROPOSER_ID)):
            return True
        if user.id in row.get("共同责任人Ids", []):
            return True
        if user.role == "审核岗" and row.get("status") in (STATUS_PENDING, STATUS_REJECTED):
            return True
        if user.role == "验收岗" and row.get("status") == STATUS_ACCEPT_PENDING:
            return True
        if user.role == "实施岗" and row.get("status") in (STATUS_APPROVED, STATUS_IMPLEMENTING):
            return True
        return False

    # ---------------- 内部工具 ----------------
    def _find_visible(self, user: User, project_id: int) -> dict[str, Any]:
        row = store.find(MODULE, project_id)
        if row is None or not self.can_view(user, row):
            # 对不可见的项目同样报"不存在"，避免借接口探测项目
            raise ProjectNotFound(f"改造项目 {project_id} 不存在或不在您的可见范围内")
        return row

    def _find_for_write(self, project_id: int) -> dict[str, Any]:
        """写路径专用：只确认项目存在。可见性不在这里挡，
        好让权限守卫先开口——越权时当场说明缺的是哪个权限。"""
        row = store.find(MODULE, project_id)
        if row is None:
            raise ProjectNotFound(f"改造项目 {project_id} 不存在或已归档")
        return row

    @staticmethod
    def _ensure_unlocked(row: dict[str, Any]) -> None:
        if row.get("status") in LOCKED_STATUSES:
            raise RuleViolation("该改造项目已投运验收，投运后各岗位仅可查看，不能再做任何改动")

    @staticmethod
    def _validate_budget(budget: Any) -> None:
        try:
            value = float(budget)
        except (TypeError, ValueError):
            raise RuleViolation("预算金额必须是数字（单位：万元）") from None
        if value < 0:
            raise RuleViolation("预算金额不能为负数")

    @staticmethod
    def _append_log(row: dict[str, Any], user: User, action: str, detail: str) -> None:
        row.setdefault("流转记录", []).append({
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "操作人": user.name,
            "岗位": user.role,
            "动作": action,
            "说明": detail,
        })

    def _serialize(self, row: dict[str, Any], user: User) -> dict[str, Any]:
        """台账、立项单、投运验收页都拿这个结果渲染，负责人字段只此一处。"""
        owner = user_brief(row.get(FIELD_OWNER_ID))
        proposer = user_brief(row.get(FIELD_PROPOSER_ID))
        co_owners = [user_brief(uid) for uid in row.get("共同责任人Ids", [])]
        result = dict(row)
        result[FIELD_OWNER] = owner["name"]
        result[FIELD_PROPOSER] = proposer["name"]
        result["责任部门"] = row.get(FIELD_OWNER_DEPT, owner["department"])
        result["共同责任人"] = "、".join(f"{c['name']}（{c['department']}）" for c in co_owners) or "—"
        result["共同责任人明细"] = co_owners
        result["流转记录"] = list(row.get("流转记录", []))
        result["权限"] = self._permissions(row, user)
        return result

    def _permissions(self, row: dict[str, Any], user: User) -> dict[str, bool]:
        """把当前操作人在这条项目上能做什么一并下发，按钮按它禁用。"""
        locked = row.get("status") in LOCKED_STATUSES
        is_proposer = row.get(FIELD_PROPOSER_ID) == user.id
        same_dept = user.department == row.get(FIELD_OWNER_DEPT)
        status = row.get("status")
        can_write = not locked

        def guarded(*, perm: bool, extra: bool = True) -> bool:
            return bool(can_write and perm and extra)

        return {
            "修改预算": guarded(perm=user.can(PERM_BUDGET_EDIT), extra=is_proposer or same_dept and user.can(PERM_BUDGET_EDIT) and status in (STATUS_DRAFT, STATUS_REJECTED)),
            "修改立项单": guarded(perm=is_proposer),
            "提交审核": guarded(perm=is_proposer, extra=status in (STATUS_DRAFT, STATUS_REJECTED)),
            "审核通过": guarded(perm=user.can(PERM_REVIEW), extra=status == STATUS_PENDING),
            "审核退回": guarded(perm=user.can(PERM_REVIEW_REJECT), extra=status == STATUS_PENDING),
            "重新提交": guarded(perm=user.can(PERM_RESUBMIT) and is_proposer, extra=status == STATUS_REJECTED),
            "安排实施": guarded(perm=user.can(PERM_IMPLEMENT), extra=status == STATUS_APPROVED),
            "实施报竣": guarded(perm=user.can(PERM_IMPLEMENT), extra=status == STATUS_IMPLEMENTING),
            "投运验收": guarded(perm=user.can(PERM_ACCEPT), extra=status == STATUS_ACCEPT_PENDING),
            "移交责任人": guarded(
                perm=user.can(PERM_OWNER_TRANSFER),
                extra=same_dept or user.role == "审核岗",
            ),
            "指定共同责任人": guarded(
                perm=user.can(PERM_COOWNER_ADD),
                extra=is_proposer or row.get(FIELD_OWNER_ID) == user.id,
            ),
            "已投运只读": locked,
        }


service = RenovationService()
