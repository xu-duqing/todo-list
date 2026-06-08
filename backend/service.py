"""
Service 层 - 业务逻辑处理
"""

import re
from datetime import datetime
from typing import Optional


class TodoService:
    """Todo 业务逻辑层"""

    VALID_PRIORITIES = {"low", "medium", "high"}
    VALID_STATUSES = {"pending", "completed"}

    @staticmethod
    def validate_iso_datetime(dt_str: Optional[str]) -> bool:
        """校验 ISO 8601 时间格式"""
        if dt_str is None:
            return True
        try:
            datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return True
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def validate_priority(priority: Optional[str]) -> bool:
        """校验优先级"""
        if priority is None:
            return True
        return priority in TodoService.VALID_PRIORITIES

    @staticmethod
    def validate_status(status: str) -> bool:
        """校验状态"""
        return status in TodoService.VALID_STATUSES

    @staticmethod
    def sanitize_keyword(keyword: Optional[str]) -> Optional[str]:
        """关键词安全清理"""
        if keyword is None:
            return None
        # 移除 SQL 特殊字符但保留中文和常见搜索字符
        cleaned = re.sub(r"[%_'\"\\]", "", keyword)
        return cleaned.strip() or None
