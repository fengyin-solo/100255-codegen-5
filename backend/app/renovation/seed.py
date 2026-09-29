"""技术改造项目示例数据：覆盖立项、退回、实施、投运、跨部门共享等场景。"""
from __future__ import annotations

from typing import Any


def _project(  # noqa: PLR0913 - 种子数据字段多，位置参数更直观
    pid: int,
    code: str,
    name: str,
    department: str,
    owner_id: str,
    proposer_id: str,
    status: str,
    *,
    budget: float | None = None,
    co_owner_ids: list[str] | None = None,
    reject_reason: str = "",
    acceptance_conclusion: str = "",
) -> dict[str, Any]:
    return {
        "id": pid,
        "项目编号": code,
        "项目名称": name,
        "责任部门": department,
        "责任人Id": owner_id,
        "立项人Id": proposer_id,
        "共同责任人Ids": list(co_owner_ids or []),
        "预算金额": budget,
        "status": status,
        "pending": status not in ("已投运",),
        "abnormal": status == "已退回",
        "退回理由": reject_reason,
        "验收结论": acceptance_conclusion,
    }


def build_renovation_seed() -> dict[str, list[dict[str, Any]]]:
    projects = [
        _project(
            1, "TECH-2026-001", "车站信号机LED光源改造", "信号技术科",
            "u_zhang", "u_zhang", "待审核", budget=38.5,
        ),
        _project(
            2, "TECH-2026-002", "轨道电路分路不良整治", "信号技术科",
            "u_zhang", "u_zhang", "已退回", budget=52.0,
            reject_reason="预算缺少分项测算依据，请补充器材与施工费用明细后重新提交。",
        ),
        _project(
            3, "TECH-2026-003", "联锁系统上位机升级", "技术改造科",
            "u_li", "u_zhang", "实施中", budget=126.8,
        ),
        _project(
            4, "TECH-2026-004", "应答器报文动态监测改造", "信号技术科",
            "u_zhou", "u_zhang", "已投运", budget=88.0,
            acceptance_conclusion="2026-08-20 投运验收合格，监测数据上传稳定，满足设计要求。",
        ),
        _project(
            5, "TECH-2026-005", "信号—通信联合电源监测改造", "信号技术科",
            "u_zhang", "u_zhang", "待验收", budget=73.2,
            co_owner_ids=["u_wu"],
        ),
        _project(
            6, "TECH-2026-006", "道岔转辙机摩擦电流在线监测", "信号车间",
            "u_li", "u_zhang", "编制中", budget=None,
        ),
    ]
    return {"renovation_project": projects}
