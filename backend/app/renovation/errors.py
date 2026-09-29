"""技术改造模块的领域异常：路由层统一翻译成 HTTP 状态码。"""
from __future__ import annotations


class RenovationError(Exception):
    """所有改造项目领域错误的基类，消息都面向终端用户可读。"""


class PermissionDenied(RenovationError):
    """越权操作：必须说明缺的是哪个权限。"""

    def __init__(self, required: str, message: str) -> None:
        super().__init__(message)
        self.required = required
        self.message = message


class RuleViolation(RenovationError):
    """业务规则冲突（状态不允许、同部门责任人重复等），HTTP 400。"""


class ProjectNotFound(RenovationError):
    """项目不存在，或不在当前操作人的可见范围内，HTTP 404。"""
