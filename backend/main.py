"""
Todo-list Backend - FastAPI + SQLite (no ORM)
"""
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ─── Config ────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "todos.db")
DEMO_USER_ID = 1


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                due_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_user_status ON todos(user_id, status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_user_created ON todos(user_id, created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_user_due ON todos(user_id, due_at)")


init_db()


# ─── Schemas ───────────────────────────────────────────────
class TodoPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TodoStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    priority: Optional[TodoPriority] = TodoPriority.medium
    due_at: Optional[str] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    priority: Optional[TodoPriority] = None
    due_at: Optional[str] = None


class TodoStatusUpdate(BaseModel):
    status: TodoStatus


class APIResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[object] = None


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─── App ───────────────────────────────────────────────────
app = FastAPI(title="Todo-list API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.post("/api/v1/todos", response_model=APIResponse)
def create_todo(body: TodoCreate):
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO todos (user_id, title, description, status, priority, due_at, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (DEMO_USER_ID, body.title, body.description or "", body.priority.value if body.priority else "medium",
             body.due_at, now_iso(), now_iso()),
        )
        todo = db.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
        return APIResponse(data=row_to_dict(todo))


@app.get("/api/v1/todos", response_model=APIResponse)
def list_todos(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    order: Optional[str] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    allowed_sort = {"created_at", "updated_at", "due_at", "priority", "status"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    order_clause = "DESC" if order == "desc" else "ASC"

    conditions = ["user_id = ?", "deleted_at IS NULL"]
    params = [DEMO_USER_ID]
    if status:
        conditions.append("status = ?")
        params.append(status)
    if priority:
        conditions.append("priority = ?")
        params.append(priority)
    if keyword:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])

    where = " AND ".join(conditions)

    with get_db() as db:
        total = db.execute(f"SELECT COUNT(*) FROM todos WHERE {where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM todos WHERE {where} ORDER BY {sort_by} {order_clause} LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return APIResponse(data={
            "items": [row_to_dict(r) for r in rows],
            "pagination": {"page": page, "page_size": page_size, "total": total},
        })


@app.get("/api/v1/todos/{todo_id}", response_model=APIResponse)
def get_todo(todo_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (todo_id, DEMO_USER_ID),
        ).fetchone()
        if not row:
            raise HTTPException(404, detail={"code": 404001, "message": "Todo not found"})
        return APIResponse(data=row_to_dict(row))


@app.patch("/api/v1/todos/{todo_id}", response_model=APIResponse)
def update_todo(todo_id: int, body: TodoUpdate):
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (todo_id, DEMO_USER_ID),
        ).fetchone()
        if not existing:
            raise HTTPException(404, detail={"code": 404001, "message": "Todo not found"})

        updates = {}
        if body.title is not None:
            updates["title"] = body.title
        if body.description is not None:
            updates["description"] = body.description
        if body.priority is not None:
            updates["priority"] = body.priority.value
        if body.due_at is not None:
            updates["due_at"] = body.due_at
        updates["updated_at"] = now_iso()

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            db.execute(
                f"UPDATE todos SET {set_clause} WHERE id = ?",
                list(updates.values()) + [todo_id],
            )

        row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return APIResponse(data=row_to_dict(row))


@app.patch("/api/v1/todos/{todo_id}/status", response_model=APIResponse)
def update_todo_status(todo_id: int, body: TodoStatusUpdate):
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (todo_id, DEMO_USER_ID),
        ).fetchone()
        if not existing:
            raise HTTPException(404, detail={"code": 404001, "message": "Todo not found"})

        completed_at = now_iso() if body.status == TodoStatus.completed else None
        db.execute(
            "UPDATE todos SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (body.status.value, completed_at, now_iso(), todo_id),
        )
        row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return APIResponse(data=row_to_dict(row))


@app.delete("/api/v1/todos/{todo_id}", response_model=APIResponse)
def delete_todo(todo_id: int):
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM todos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (todo_id, DEMO_USER_ID),
        ).fetchone()
        if not existing:
            raise HTTPException(404, detail={"code": 404001, "message": "Todo not found"})

        db.execute(
            "UPDATE todos SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now_iso(), now_iso(), todo_id),
        )
        return APIResponse(data=True)


# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/assets", StaticFiles(directory=frontend_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes"""
        if full_path.startswith("api/"):
            raise HTTPException(404, detail="Not found")
        file_path = os.path.join(frontend_dir, full_path) if full_path else os.path.join(frontend_dir, "index.html")
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
