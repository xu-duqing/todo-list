"""
Todo-list Backend - FastAPI Application
主入口文件，定义所有 REST API 端点
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_db, init_db
from repository import TodoRepository
from service import TodoService
from schemas import (
    CreateTodoRequest, UpdateTodoRequest, UpdateStatusRequest,
    TodoResponse, TodoListData,
)

# 静态文件目录（前端页面）
STATIC_DIR = Path(__file__).parent.parent / "static"

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- 应用生命周期 ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库"""
    logger.info("Initializing database...")
    init_db()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Todo-list API",
    description="基于 README.md 设计文档的 Todo-list REST API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 统一响应工具函数 ----

def ok(data=None, message="success"):
    return {"code": 0, "message": message, "data": data}


def error(code: int, message: str):
    return JSONResponse(status_code=200, content={"code": code, "message": message, "data": None})


def _row_to_dict(row) -> dict:
    return dict(row) if row else {}


# ==================== 1. 创建 Todo ====================

@app.post("/api/v1/todos", response_model=dict)
async def create_todo(req: CreateTodoRequest):
    """
    创建待办事项
    支持字段：title(必填), description, priority, due_at
    """
    # 校验优先级
    if req.priority and not TodoService.validate_priority(req.priority):
        return error(400001, "priority must be one of: low, medium, high")

    # 校验时间格式
    if not TodoService.validate_iso_datetime(req.due_at):
        return error(400001, "due_at must be a valid ISO 8601 datetime")

    conn = get_db()
    try:
        repo = TodoRepository(conn)
        result = repo.create(
            user_id="default_user",
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            priority=req.priority,
            due_at=req.due_at,
        )
        logger.info(f"Created todo id={result['id']}, title={result['title']}")
        return ok(result)
    except Exception as e:
        logger.error(f"Create todo failed: {e}")
        return error(500001, f"System error: {str(e)}")
    finally:
        conn.close()


# ==================== 2. 查询 Todo 列表 ====================

@app.get("/api/v1/todos", response_model=dict)
async def list_todos(
    status: Optional[str] = Query(None, description="pending / completed"),
    priority: Optional[str] = Query(None, description="low / medium / high"),
    keyword: Optional[str] = Query(None, description="标题或描述关键词"),
    sort_by: str = Query("created_at", description="排序字段: created_at / updated_at / due_at"),
    order: str = Query("desc", description="asc / desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量 (max 100)"),
):
    """
    查询待办事项列表
    支持筛选、排序、分页
    """
    # 校验状态参数
    if status and not TodoService.validate_status(status):
        return error(400001, "status must be 'pending' or 'completed'")

    # 校验优先级参数
    if priority and not TodoService.validate_priority(priority):
        return error(400001, "priority must be one of: low, medium, high")

    # 安全清理关键词
    keyword = TodoService.sanitize_keyword(keyword)

    conn = get_db()
    try:
        repo = TodoRepository(conn)
        items, total = repo.list_todos(
            user_id="default_user",
            status=status,
            priority=priority,
            keyword=keyword,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
        return ok({
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        })
    except Exception as e:
        logger.error(f"List todos failed: {e}")
        return error(500001, f"System error: {str(e)}")
    finally:
        conn.close()


# ==================== 3. 查询 Todo 详情 ====================

@app.get("/api/v1/todos/{todo_id}", response_model=dict)
async def get_todo(todo_id: int):
    """查询单个待办事项详情（权限隔离）"""
    conn = get_db()
    try:
        repo = TodoRepository(conn)
        result = repo.get_by_id(todo_id, user_id="default_user")
        if not result:
            return error(404001, "Todo not found or no permission")
        return ok(result)
    finally:
        conn.close()


# ==================== 4. 更新 Todo ====================

@app.patch("/api/v1/todos/{todo_id}", response_model=dict)
async def update_todo(todo_id: int, req: UpdateTodoRequest):
    """
    更新待办事项内容
    可更新字段：title, description, priority, due_at
    （至少传入一个字段）
    """
    # 校验优先级
    if req.priority and not TodoService.validate_priority(req.priority):
        return error(400001, "priority must be one of: low, medium, high")

    # 校验时间格式
    if not TodoService.validate_iso_datetime(req.due_at):
        return error(400001, "due_at must be a valid ISO 8601 datetime")

    conn = get_db()
    try:
        repo = TodoRepository(conn)
        updates = {}
        if req.title is not None:
            updates["title"] = req.title.strip()
        if req.description is not None:
            updates["description"] = req.description.strip()
        if req.priority is not None:
            updates["priority"] = req.priority
        if req.due_at is not None:
            updates["due_at"] = req.due_at

        if not updates:
            return error(400001, "At least one field is required for update")

        result = repo.update(todo_id, user_id="default_user", **updates)
        if not result:
            return error(404001, "Todo not found or no permission")
        logger.info(f"Updated todo id={todo_id}")
        return ok(result)
    finally:
        conn.close()


# ==================== 5. 更新 Todo 状态 ====================

@app.patch("/api/v1/todos/{todo_id}/status", response_model=dict)
async def update_todo_status(todo_id: int, req: UpdateStatusRequest):
    """
    切换任务完成状态
    pending -> completed (自动设置 completed_at)
    completed -> pending (自动清除 completed_at)
    """
    if not TodoService.validate_status(req.status):
        return error(400001, "status must be 'pending' or 'completed'")

    conn = get_db()
    try:
        repo = TodoRepository(conn)
        result = repo.update_status(todo_id, user_id="default_user", status=req.status)
        if not result:
            return error(404001, "Todo not found or no permission")
        logger.info(f"Updated todo id={todo_id} status to {req.status}")
        return ok(result)
    finally:
        conn.close()


# ==================== 6. 软删除 Todo ====================

@app.delete("/api/v1/todos/{todo_id}", response_model=dict)
async def delete_todo(todo_id: int):
    """
    软删除待办事项
    将 deleted_at 设为当前时间，不物理删除数据
    """
    conn = get_db()
    try:
        repo = TodoRepository(conn)
        success = repo.soft_delete(todo_id, user_id="default_user")
        if not success:
            return error(404001, "Todo not found or no permission")
        logger.info(f"Soft deleted todo id={todo_id}")
        return ok(True)
    finally:
        conn.close()


# ---- 健康检查 ----

@app.get("/api/health")
async def health_check():
    return ok({"status": "ok"})


# ---- 前端页面托管 ----

@app.get("/")
async def serve_frontend():
    """返回前端 HTML 页面"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return {"message": "Todo-list API is running. See /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
