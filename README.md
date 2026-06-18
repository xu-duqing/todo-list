# Todo-list 技术设计文档

## 0. 项目实现与运行说明

当前仓库已包含一个可运行的最小可用版本实现，采用 Node.js 原生 HTTP 服务 + 本地 JSON 持久化，覆盖以下能力：

- 创建待办事项
- 查看列表
- 编辑任务
- 标记完成 / 取消完成
- 删除任务（软删除）
- 按状态、优先级、关键词筛选
- 按创建时间、更新时间、截止时间排序

### 快速开始

确保本机已安装 Node.js 18+，然后在仓库根目录运行：

```bash
npm install
npm start
```

启动后访问：

```text
http://localhost:3000
```

### 数据存储

应用数据默认保存在：

```text
data/todos.json
```

重启服务后数据仍会保留。

### API 概览

服务实现了以下接口：

- `POST /api/v1/todos`
- `GET /api/v1/todos`
- `GET /api/v1/todos/{id}`
- `PATCH /api/v1/todos/{id}`
- `PATCH /api/v1/todos/{id}/status`
- `DELETE /api/v1/todos/{id}`

---

## 1. 背景

Todo-list 是一个任务管理功能，用户可以创建、查看、编辑、完成和删除待办事项。该功能适用于个人任务管理、轻量项目跟踪、提醒事项记录等场景。

本文档描述 Todo-list 功能的技术设计，包括需求范围、系统架构、数据模型、接口设计、前端设计、后端设计、异常处理和后续扩展方案。

---

## 2. 目标

### 2.1 功能目标

支持用户完成以下操作：

1. 创建待办事项
2. 查看待办事项列表
3. 编辑待办事项内容
4. 标记待办事项为已完成或未完成
5. 删除待办事项
6. 按状态筛选待办事项
7. 支持基础排序，例如按创建时间、更新时间或截止时间排序

### 2.2 非功能目标

1. 操作响应快速，常规请求接口响应时间控制在 200ms 到 500ms 内
2. 数据持久化存储，避免刷新或重新登录后数据丢失
3. 接口设计清晰，便于后续扩展提醒、标签、优先级等能力
4. 前后端职责清晰，降低维护成本
5. 支持基础权限隔离，用户只能访问自己的待办事项

---

## 3. 非目标

当前版本暂不支持以下能力：

1. 多人协作任务
2. 子任务
3. 文件附件
4. 任务评论
5. 复杂日历视图
6. 实时多人同步
7. 离线编辑和冲突合并

这些能力可以作为后续版本演进方向。

---

## 4. 用户场景

### 4.1 创建任务

用户输入任务标题，可选填写描述、截止时间、优先级，然后点击创建。系统保存任务并展示在列表中。

### 4.2 查看任务列表

用户进入 Todo-list 页面后，系统默认展示当前用户的所有未删除任务。用户可以通过筛选条件查看全部、未完成或已完成任务。

### 4.3 完成任务

用户点击任务前的复选框，系统将任务状态更新为已完成。用户也可以再次点击，将任务恢复为未完成。

### 4.4 编辑任务

用户点击任务进入编辑状态，可以修改标题、描述、截止时间、优先级等字段。

### 4.5 删除任务

用户点击删除按钮后，系统将任务删除。为了降低误删风险，可以使用软删除方案。

---

## 5. 总体架构

系统采用前后端分离架构。

```text
Client
  |
  | HTTP / HTTPS
  v
API Server
  |
  | ORM / SQL
  v
Database
```

### 5.1 前端职责

1. 展示任务列表
2. 提供新增、编辑、删除、完成等交互
3. 管理页面状态和表单状态
4. 调用后端接口
5. 处理加载、错误、空状态等 UI 状态

### 5.2 后端职责

1. 提供 Todo 相关 REST API
2. 校验请求参数
3. 校验用户权限
4. 操作数据库
5. 返回统一格式响应
6. 记录必要日志

### 5.3 数据库职责

1. 持久化存储任务数据
2. 支持按用户、状态、时间等条件查询
3. 保证基础数据一致性

---

## 6. 数据模型设计

### 6.1 Todo 表

表名：`todos`

| 字段名          |            类型 | 是否必填 | 说明                     |
| ------------ | ------------: | ---: | ---------------------- |
| id           | bigint / uuid |    是 | 主键                     |
| user_id      | bigint / uuid |    是 | 所属用户 ID                |
| title        |  varchar(255) |    是 | 任务标题                   |
| description  |          text |    否 | 任务描述                   |
| status       |   varchar(32) |    是 | 任务状态：pending、completed |
| priority     |   varchar(32) |    否 | 优先级：low、medium、high    |
| due_at       |      datetime |    否 | 截止时间                   |
| completed_at |      datetime |    否 | 完成时间                   |
| created_at   |      datetime |    是 | 创建时间                   |
| updated_at   |      datetime |    是 | 更新时间                   |
| deleted_at   |      datetime |    否 | 软删除时间                  |

### 6.2 状态枚举

```text
pending    未完成
completed  已完成
```

### 6.3 优先级枚举

```text
low     低
medium  中
high    高
```

### 6.4 索引设计

建议增加以下索引：

```sql
CREATE INDEX idx_todos_user_status ON todos(user_id, status);
CREATE INDEX idx_todos_user_created_at ON todos(user_id, created_at);
CREATE INDEX idx_todos_user_due_at ON todos(user_id, due_at);
```

如果使用软删除，可以考虑：

```sql
CREATE INDEX idx_todos_user_deleted_at ON todos(user_id, deleted_at);
```

---

## 7. API 设计

接口统一前缀：

```text
/api/v1/todos
```

### 7.1 创建 Todo

```http
POST /api/v1/todos
```

#### 请求参数

```json
{
  "title": "完成周报",
  "description": "整理本周项目进展",
  "priority": "medium",
  "due_at": "2026-06-10T18:00:00Z"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "todo_001",
    "title": "完成周报",
    "description": "整理本周项目进展",
    "status": "pending",
    "priority": "medium",
    "due_at": "2026-06-10T18:00:00Z",
    "created_at": "2026-06-08T10:00:00Z",
    "updated_at": "2026-06-08T10:00:00Z"
  }
}
```

---

### 7.2 查询 Todo 列表

```http
GET /api/v1/todos
```

#### Query 参数

| 参数        |     类型 | 是否必填 | 说明                               |
| --------- | -----: | ---: | -------------------------------- |
| status    | string |    否 | pending / completed              |
| priority  | string |    否 | low / medium / high              |
| keyword   | string |    否 | 标题或描述关键词                         |
| sort_by   | string |    否 | created_at / updated_at / due_at |
| order     | string |    否 | asc / desc                       |
| page      | number |    否 | 页码                               |
| page_size | number |    否 | 每页数量                             |

#### 示例

```http
GET /api/v1/todos?status=pending&page=1&page_size=20
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "todo_001",
        "title": "完成周报",
        "status": "pending",
        "priority": "medium",
        "due_at": "2026-06-10T18:00:00Z",
        "created_at": "2026-06-08T10:00:00Z",
        "updated_at": "2026-06-08T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1
    }
  }
}
```

---

### 7.3 查询 Todo 详情

```http
GET /api/v1/todos/{id}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "todo_001",
    "title": "完成周报",
    "description": "整理本周项目进展",
    "status": "pending",
    "priority": "medium",
    "due_at": "2026-06-10T18:00:00Z",
    "completed_at": null,
    "created_at": "2026-06-08T10:00:00Z",
    "updated_at": "2026-06-08T10:00:00Z"
  }
}
```

---

### 7.4 更新 Todo

```http
PATCH /api/v1/todos/{id}
```

#### 请求参数

```json
{
  "title": "完成技术周报",
  "description": "补充风险和下周计划",
  "priority": "high",
  "due_at": "2026-06-10T18:00:00Z"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "todo_001",
    "title": "完成技术周报",
    "description": "补充风险和下周计划",
    "status": "pending",
    "priority": "high",
    "due_at": "2026-06-10T18:00:00Z",
    "updated_at": "2026-06-08T11:00:00Z"
  }
}
```

---

### 7.5 更新 Todo 状态

```http
PATCH /api/v1/todos/{id}/status
```

#### 请求参数

```json
{
  "status": "completed"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "todo_001",
    "status": "completed",
    "completed_at": "2026-06-08T12:00:00Z",
    "updated_at": "2026-06-08T12:00:00Z"
  }
}
```

状态从 `completed` 改回 `pending` 时，`completed_at` 应重置为 `null`。

---

### 7.6 删除 Todo

```http
DELETE /api/v1/todos/{id}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": true
}
```

建议采用软删除，将 `deleted_at` 设置为当前时间，而不是直接物理删除。

---

## 8. 后端设计

### 8.1 分层结构

```text
Controller
  |
Service
  |
Repository / DAO
  |
Database
```

### 8.2 Controller 层

负责：

1. 接收 HTTP 请求
2. 解析 Path、Query、Body 参数
3. 调用 Service
4. 返回统一响应

### 8.3 Service 层

负责核心业务逻辑：

1. 校验 Todo 是否存在
2. 校验 Todo 是否属于当前用户
3. 处理状态流转
4. 处理 completed_at、updated_at 等字段
5. 组织返回数据

### 8.4 Repository 层

负责数据库访问：

1. 新增 Todo
2. 查询 Todo 列表
3. 查询 Todo 详情
4. 更新 Todo
5. 软删除 Todo

---

## 9. 前端设计

### 9.1 页面结构

```text
TodoPage
  ├── TodoHeader
  ├── TodoCreateForm
  ├── TodoFilterBar
  ├── TodoList
  │     └── TodoItem
  └── Pagination
```

### 9.2 状态设计

前端可维护以下状态：

```ts
type TodoStatus = 'pending' | 'completed';

type TodoPriority = 'low' | 'medium' | 'high';

interface Todo {
  id: string;
  title: string;
  description?: string;
  status: TodoStatus;
  priority?: TodoPriority;
  due_at?: string;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface TodoListState {
  items: Todo[];
  loading: boolean;
  error: string | null;
  filter: {
    status?: TodoStatus;
    priority?: TodoPriority;
    keyword?: string;
  };
  pagination: {
    page: number;
    page_size: number;
    total: number;
  };
}
```

### 9.3 前端交互

#### 创建任务

1. 用户输入标题
2. 前端校验标题不能为空
3. 调用创建接口
4. 成功后刷新列表或将新任务插入列表顶部
5. 清空输入框

#### 完成任务

1. 用户点击复选框
2. 前端可先做乐观更新
3. 调用状态更新接口
4. 如果接口失败，回滚 UI 状态并提示错误

#### 删除任务

1. 用户点击删除
2. 弹出确认提示
3. 调用删除接口
4. 成功后从列表中移除

---

## 10. 参数校验

### 10.1 创建 Todo

| 字段          | 校验规则                   |
| ----------- | ---------------------- |
| title       | 必填，长度 1 到 255          |
| description | 可选，长度不超过 5000          |
| priority    | 可选，只能是 low、medium、high |
| due_at      | 可选，必须是合法时间格式           |

### 10.2 更新 Todo

| 字段          | 校验规则                   |
| ----------- | ---------------------- |
| title       | 可选，长度 1 到 255          |
| description | 可选，长度不超过 5000          |
| priority    | 可选，只能是 low、medium、high |
| due_at      | 可选，必须是合法时间格式           |

### 10.3 更新状态

| 字段     | 校验规则                       |
| ------ | -------------------------- |
| status | 必填，只能是 pending 或 completed |

---

## 11. 权限设计

每条 Todo 都属于一个用户。所有查询、更新、删除操作都必须带上 `user_id` 条件。

例如查询详情时：

```sql
SELECT *
FROM todos
WHERE id = :id
  AND user_id = :user_id
  AND deleted_at IS NULL;
```

禁止只通过 `id` 查询任务，否则可能出现越权访问问题。

---

## 12. 错误码设计

|    错误码 | 含义       |
| -----: | -------- |
|      0 | 成功       |
| 400001 | 参数错误     |
| 401001 | 未登录      |
| 403001 | 无权限      |
| 404001 | Todo 不存在 |
| 409001 | 状态冲突     |
| 500001 | 系统错误     |

### 错误响应示例

```json
{
  "code": 400001,
  "message": "title is required",
  "data": null
}
```

---

## 13. 并发与一致性

### 13.1 更新冲突

基础版本可以采用最后写入覆盖策略，即以后端最终更新为准。

如果后续需要更严格的一致性，可以增加 `version` 字段，实现乐观锁：

```sql
UPDATE todos
SET title = :title,
    version = version + 1
WHERE id = :id
  AND user_id = :user_id
  AND version = :version;
```

### 13.2 乐观更新

前端可以对完成、取消完成、删除等操作使用乐观更新，以提升体验。接口失败时需要回滚。

---

## 14. 性能设计

### 14.1 分页

列表接口必须支持分页，避免一次性返回过多数据。

默认：

```text
page = 1
page_size = 20
```

最大：

```text
page_size <= 100
```

### 14.2 索引

常见查询条件为 `user_id`、`status`、`created_at`、`due_at`，需要建立组合索引。

### 14.3 缓存

当前版本不强依赖缓存。Todo 数据更新频繁、用户维度隔离明显，优先保证数据库查询效率即可。

后续如有高频列表读取场景，可以考虑引入 Redis 缓存用户任务摘要数据。

---

## 15. 安全设计

1. 所有接口必须要求用户登录
2. 所有数据库查询必须带 `user_id`
3. 请求参数必须进行白名单校验
4. 防止 XSS：前端展示 title、description 时需要进行转义
5. 防止批量攻击：创建、更新、删除接口可增加限流
6. 日志中避免记录敏感信息

---

## 16. 可观测性设计

### 16.1 日志

关键操作记录业务日志：

1. 创建 Todo
2. 更新 Todo
3. 删除 Todo
4. 状态变更

日志字段建议包含：

```text
request_id
user_id
todo_id
action
status
created_at
```

### 16.2 指标

建议监控以下指标：

1. Todo 创建成功率
2. Todo 更新成功率
3. Todo 删除成功率
4. API 平均响应时间
5. API P95 响应时间
6. 接口错误率

### 16.3 告警

当接口错误率、响应时间或数据库异常明显升高时触发告警。

---

## 17. 测试方案

### 17.1 单元测试

覆盖 Service 层核心逻辑：

1. 创建 Todo 成功
2. 创建 Todo 参数错误
3. 更新不存在的 Todo
4. 更新他人的 Todo 被拒绝
5. 状态从 pending 改为 completed
6. 状态从 completed 改为 pending

### 17.2 接口测试

覆盖 API 层：

1. 未登录访问返回 401
2. 创建 Todo 返回正确数据
3. 查询列表支持分页
4. 查询列表支持状态筛选
5. 删除 Todo 后列表不再返回该数据

### 17.3 前端测试

覆盖核心交互：

1. 输入标题后可以创建任务
2. 空标题不能提交
3. 点击复选框可以完成任务
4. 删除任务前出现确认提示
5. 接口失败时展示错误提示

---

## 18. 发布方案

### 18.1 数据库变更

上线前执行建表 SQL，并确认索引创建成功。

### 18.2 后端发布

1. 发布 Todo API
2. 验证接口鉴权
3. 验证数据库读写正常
4. 验证日志和监控正常

### 18.3 前端发布

1. 发布 Todo 页面入口
2. 灰度开放给部分用户
3. 观察错误率和用户反馈
4. 无异常后全量开放

---

## 19. 回滚方案

### 19.1 前端回滚

隐藏 Todo 页面入口或回滚前端版本。

### 19.2 后端回滚

回滚 API 服务版本。数据库表可以保留，不影响已有系统。

### 19.3 数据回滚

由于 Todo 属于新增功能，通常不需要回滚用户数据。如出现严重数据问题，可通过 `created_at` 和发布窗口定位受影响数据。

---

## 20. 后续扩展

后续可以扩展以下能力：

1. 标签：支持按标签分类任务
2. 提醒：支持到期前通知
3. 子任务：支持任务拆分
4. 重复任务：支持每天、每周、每月重复
5. 协作任务：支持分配给其他用户
6. 附件：支持上传图片或文件
7. 搜索：支持全文搜索标题和描述
8. 日历视图：按截止时间展示任务
9. 移动端推送：支持任务提醒通知
10. 离线模式：支持本地缓存和断网编辑

---

## 21. 建表 SQL 示例

```sql
CREATE TABLE todos (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  priority VARCHAR(32) NULL,
  due_at DATETIME NULL,
  completed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME NULL,

  INDEX idx_todos_user_status (user_id, status),
  INDEX idx_todos_user_created_at (user_id, created_at),
  INDEX idx_todos_user_due_at (user_id, due_at),
  INDEX idx_todos_user_deleted_at (user_id, deleted_at)
);
```

---

## 22. 关键决策

| 决策点  | 方案                  | 原因              |
| ---- | ------------------- | --------------- |
| 删除方式 | 软删除                 | 支持误删恢复和问题排查     |
| 状态设计 | pending / completed | 当前场景简单，避免过度设计   |
| 接口风格 | REST API            | 简单清晰，适合 CRUD 场景 |
| 分页方式 | page/page_size      | 易理解，适合早期版本      |
| 权限隔离 | user_id 过滤          | 防止用户访问他人任务      |
| 缓存   | 暂不引入                | 数据更新频繁，先控制复杂度   |

---

## 23. 总结

Todo-list 当前版本以简单、稳定、可扩展为核心目标，优先完成任务管理的基础闭环。系统采用前后端分离架构，后端提供标准 REST API，数据库使用单表存储任务数据，并通过 `user_id` 做权限隔离。

该设计可以支撑基础个人任务管理场景，同时为后续扩展标签、提醒、重复任务、协作任务等能力预留空间。
