"""
Repository 层 - 数据库 CRUD 操作
"""

from datetime import datetime
from typing import Optional


class TodoRepository:
    """Todo 数据访问对象"""

    def __init__(self, db_conn):
        self.conn = db_conn

    def create(self, user_id: str, title: str, description: Optional[str] = None,
               priority: Optional[str] = None, due_at: Optional[str] = None) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO todos (user_id, title, description, priority, due_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title, description, priority, due_at, now, now)
        )
        self.conn.commit()
        return self._get_by_id(cursor.lastrowid)

    def list_todos(self, user_id: str, status: Optional[str] = None,
                   priority: Optional[str] = None, keyword: Optional[str] = None,
                   sort_by: str = "created_at", order: str = "desc",
                   page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        """查询 Todo 列表，返回 (items, total)"""

        # 验证排序字段
        allowed_sort = {"created_at", "updated_at", "due_at"}
        if sort_by not in allowed_sort:
            sort_by = "created_at"
        order = order.upper() if order.upper() in ("ASC", "DESC") else "DESC"

        # 构建 WHERE 条件
        conditions = ["user_id = ?", "deleted_at IS NULL"]
        params: list = [user_id]

        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if keyword:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            like_kw = f"%{keyword}%"
            params.extend([like_kw, like_kw])

        where_clause = " AND ".join(conditions)

        # 查询总数
        count_sql = f"SELECT COUNT(*) as cnt FROM todos WHERE {where_clause}"
        total = self.conn.execute(count_sql, params).fetchone()["cnt"]

        # 分页查询
        offset = (page - 1) * page_size
        data_sql = f"""SELECT * FROM todos WHERE {where_clause}
                       ORDER BY {sort_by} {order} LIMIT ? OFFSET ?"""
        params.extend([page_size, offset])
        rows = self.conn.execute(data_sql, params).fetchall()

        items = [dict(row) for row in rows]
        return items, total

    def get_by_id(self, todo_id: int, user_id: str) -> Optional[dict]:
        """根据 ID 和 user_id 查询单个 Todo（权限隔离）"""
        row = self.conn.execute(
            """SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL""",
            (todo_id, user_id)
        ).fetchone()
        return dict(row) if row else None

    def _get_by_id(self, todo_id: int) -> Optional[dict]:
        """内部方法：仅用 ID 查询（不限制 user_id）"""
        row = self.conn.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, todo_id: int, user_id: str, **kwargs) -> Optional[dict]:
        """更新 Todo 字段"""
        existing = self.get_by_id(todo_id, user_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat()
        fields = []
        values = []

        for key, value in kwargs.items():
            if value is not None and key in ("title", "description", "priority", "due_at"):
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return existing

        fields.append("updated_at = ?")
        values.append(now)
        values.extend([todo_id, user_id])

        sql = f"UPDATE todos SET {', '.join(fields)} WHERE id = ? AND user_id = ? AND deleted_at IS NULL"
        self.conn.execute(sql, values)
        self.conn.commit()
        return self._get_by_id(todo_id)

    def update_status(self, todo_id: int, user_id: str, status: str) -> Optional[dict]:
        """更新任务状态，自动管理 completed_at"""
        existing = self.get_by_id(todo_id, user_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat()
        completed_at = now if status == "completed" else None

        self.conn.execute(
            """UPDATE todos SET status = ?, completed_at = ?, updated_at = ?
               WHERE id = ? AND user_id = ? AND deleted_at IS NULL""",
            (status, completed_at, now, todo_id, user_id)
        )
        self.conn.commit()
        return self._get_by_id(todo_id)

    def soft_delete(self, todo_id: int, user_id: str) -> bool:
        """软删除 Todo"""
        existing = self.get_by_id(todo_id, user_id)
        if not existing:
            return False

        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "UPDATE todos SET deleted_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (now, now, todo_id, user_id)
        )
        self.conn.commit()
        return True
