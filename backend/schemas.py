"""
Pydantic 模型定义 - 请求/响应数据校验
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---- 请求模型 ----

class CreateTodoRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="任务标题，必填")
    description: Optional[str] = Field(None, max_length=5000, description="任务描述")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$", description="优先级")
    due_at: Optional[str] = Field(None, description="截止时间，ISO 8601 格式")


class UpdateTodoRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    due_at: Optional[str] = Field(None)


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|completed)$", description="目标状态")


# ---- 响应模型 ----

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: Optional[str] = None
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


class TodoListData(BaseModel):
    items: list[TodoResponse]
    page: int
    page_size: int
    total: int


# ---- 统一响应包装 ----

class SuccessResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict | list | bool | None = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
