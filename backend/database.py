"""
Todo-list Backend - Database Layer
SQLite 数据库初始化与连接管理
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todos.db")


def get_db():
    """获取数据库连接（上下文管理器）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default_user',
            title VARCHAR(255) NOT NULL,
            description TEXT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            priority VARCHAR(32) NULL,
            due_at DATETIME NULL,
            completed_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT (datetime('now')),
            updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
            deleted_at DATETIME NULL
        );

        CREATE INDEX IF NOT EXISTS idx_todos_user_status ON todos(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_todos_user_created_at ON todos(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_todos_user_due_at ON todos(user_id, due_at);
        CREATE INDEX IF NOT EXISTS idx_todos_user_deleted_at ON todos(user_id, deleted_at);
    """)
    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
