"""在岗人员花名册：演示用，真实系统里这张表来自组织架构服务。"""
from __future__ import annotations

from app.renovation.auth import User

USERS: dict[str, User] = {
    user.id: user
    for user in [
        User("u_zhang", "张立", "立项岗", "信号技术科"),
        User("u_chen", "陈审", "审核岗", "技术改造科"),
        User("u_sun", "孙算", "预算岗", "计划财务科"),
        User("u_li", "李工", "实施岗", "信号车间"),
        User("u_zhou", "周验", "验收岗", "安全质量科"),
        User("u_wang", "王看", "查看岗", "运营管理科"),
        # 跨部门共同责任人场景：另一个部门的立项人
        User("u_wu", "吴协", "立项岗", "通信技术科"),
    ]
}


def get_user(user_id: str) -> User | None:
    return USERS.get(user_id)


def user_brief(user_id: str | None) -> dict[str, str]:
    user = USERS.get(user_id or "")
    if user is None:
        return {"id": "", "name": "—", "role": "", "department": ""}
    return {"id": user.id, "name": user.name, "role": user.role, "department": user.department}
