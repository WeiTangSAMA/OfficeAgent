# 办公文档 Agent 项目计划

## 1. 项目定位

构建一个运行在本机 Docker 环境中的 Web 办公文档 Agent。用户通过浏览器上传 PDF、Word、Excel 文件，用自然语言要求 Agent 检索、归纳、对比和分析文档，并生成新的 Word、Excel 或报告文件。

项目定位为“可真实使用的作品集”，重点展示：

- 多格式办公文档解析与统一索引
- 基于 LangChain 的 Agent、Tools、Middleware 和结构化输出
- 基于 LangGraph 的任务状态、持久化、流式事件和失败恢复
- 使用阿里云百炼 `qwen3.7-plus` 完成推理和工具调用
- 带精确来源定位的跨文档问答
- 安全、可验证的 DOCX、XLSX 和报告生成
- 清晰的执行时间线、错误状态、取消和重试能力

第一版不读取用户电脑上的任意目录，不覆盖原文件，不发送邮件，不操作外部业务系统，也不执行模型生成的任意代码。

## 2. 第一版成功标准

用户能够完成以下完整流程：

1. 在浏览器创建一个工作区。
2. 拖拽上传多个 `.pdf`、`.docx`、`.xlsx` 文件。
3. 系统解析文本、段落、表格、工作表和来源位置。
4. 用户输入自然语言任务，例如：
   - “总结这些合同的甲乙方、金额、截止日期和风险条款。”
   - “比较三份报价单，生成供应商价格汇总表。”
   - “分析销售数据，找出下降最明显的产品并生成周报。”
5. Agent 显示计划、当前步骤、工具调用摘要、引用和警告。
6. 页面通过 SSE 实时接收执行事件。
7. 最终回答中的关键事实带有可点击来源。
8. 用户可以下载生成的 DOCX、XLSX、Markdown 或 HTML 报告。
9. 上传的原始文件始终不被修改。
10. 任务失败或被取消后，可以查看原因并重新运行。

## 3. 范围边界

### 第一版包含

- 本机 Docker 部署、单用户使用
- 中文界面，支持处理中英文文档
- PDF、DOCX、XLSX 上传和解析
- 文档全文检索、语义检索和来源引用
- 合同信息提取、文件对比、表格统计、报告生成
- 聊天区、文件面板、执行时间线、产物下载
- Qwen 工具调用、任务限制和错误恢复

### 第一版不包含

- 扫描件 OCR、手写识别、图片内容理解
- PPTX、旧版 `.doc`、`.xls` 和宏文件
- 邮箱、网盘、微信、Office 桌面程序连接
- 多用户登录、权限管理和公网部署
- 多 Agent 协作
- 任意 Python、Shell 或 SQL 执行
- 自动修改或覆盖原始文件

## 4. 技术架构

### 4.1 前端

- React + TypeScript + Vite
- React Router：工作区和任务路由
- TanStack Query：服务端状态、缓存和重试
- SSE：接收 Agent 执行事件
- Markdown 渲染：回答和报告预览
- CSS Variables：颜色、间距和主题令牌
- 桌面浏览器优先，兼容平板和基础移动端查看

核心页面采用三栏工作台：

- 左侧：工作区文件、上传、解析状态和删除入口
- 中间：对话历史、引用、输入框和常用任务模板
- 右侧：计划、步骤、工具调用、错误、警告和生成文件

### 4.2 后端

- Python 3.12
- FastAPI + Pydantic
- SQLAlchemy + SQLite
- Alembic 数据库迁移
- 独立 worker 进程执行长任务
- Docker Compose 启动 `web`、`api`、`worker`
- API 与 worker 共用任务数据库，但由事务保证同一任务只被领取一次

第一版不引入 Redis。任务保存在 SQLite 中，worker 轮询并通过原子状态更新领取任务。应用数据和 LangGraph 检查点使用两个独立 SQLite 文件，降低锁竞争。

### 4.3 LangChain 与 LangGraph

- `langchain`：Agent 高层接口、消息、Tools、Middleware、结构化输出
- `langchain-openai`：通过 OpenAI 兼容接口连接阿里云百炼
- `langgraph`：Agent 的底层运行时、流式执行和状态图
- `langgraph-checkpoint-sqlite`：任务检查点和会话记忆
- `langchain-chroma`：本地持久化向量库
- `langsmith`：仅在开发环境按需启用 tracing，默认关闭

Agent 使用 LangChain `create_agent` 创建。LangChain Agent 构建在 LangGraph 之上；LangGraph 提供持久化、流式执行和可恢复运行能力，适合长时间文档任务。[LangGraph 官方说明](https://docs.langchain.com/oss/python/langgraph/overview)

模型初始化采用 `ChatOpenAI`，但替换为百炼配置：

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model=settings.qwen_model,
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_base_url,
    temperature=settings.qwen_temperature,
    timeout=settings.qwen_timeout_seconds,
    max_retries=settings.qwen_max_retries,
)
```

主模型固定为 `qwen3.7-plus`。该模型支持 Function Calling 和结构化输出，适合文档处理与 Agent 工具调用。[阿里云百炼模型说明](https://help.aliyun.com/zh/model-studio/text-generation-model)

### 4.4 文档处理

- PDF：PyMuPDF
- Word：python-docx
- Excel：openpyxl + pandas
- 关键词检索：SQLite FTS5
- 向量检索：`text-embedding-v4` + Chroma
- 文本切分：自定义结构感知切分器
- DOCX 输出：python-docx
- XLSX 输出：openpyxl
- 报告输出：Markdown + 可打印 HTML

切分必须保留来源信息：PDF 页码、Word 标题路径和段落号、Excel 工作表与单元格范围。不得只保存无定位信息的纯文本块。

## 5. 目录和数据隔离

```text
data/
  app.db
  checkpoints.db
  chroma/
  workspaces/{workspace_id}/
    uploads/
    extracted/
    artifacts/{task_id}/
```

- 上传文件统一改为随机存储名，原始文件名只保存在数据库。
- 所有文件路径由服务端根据 ID 计算，API 不接受客户端传入的真实磁盘路径。
- 每个工作区拥有独立的向量集合和文件目录。
- 每个任务只能写入自己的 `artifacts/{task_id}` 目录。
- 删除工作区时，同时删除文档、向量、任务、检查点和文件目录。

## 6. 数据模型

### Workspace

- `id`
- `name`
- `created_at`
- `updated_at`

### Document

- `id`
- `workspace_id`
- `original_name`
- `stored_name`
- `media_type`
- `size_bytes`
- `sha256`
- `status`: `uploaded | parsing | ready | unsupported | failed`
- `page_count`
- `metadata_json`
- `error_message`
- `created_at`

### DocumentChunk

- `id`
- `document_id`
- `chunk_index`
- `content`
- `location_json`
- `token_count`
- `vector_id`

`location_json` 保存页码、标题路径、段落编号、工作表名称或单元格范围，用于回答引用和来源预览。

### Task

- `id`
- `workspace_id`
- `thread_id`
- `user_message`
- `status`: `queued | running | completed | failed | cancelled | interrupted`
- `plan_json`
- `final_answer_json`
- `error_code`
- `error_message`
- `created_at`
- `started_at`
- `completed_at`

### TaskEvent

- `id`
- `task_id`
- `sequence`
- `type`: `plan | step | tool_call | observation | citation | warning | artifact | error`
- `payload_json`
- `created_at`

### Artifact

- `id`
- `task_id`
- `name`
- `type`: `markdown | html | docx | xlsx`
- `path`
- `size_bytes`
- `sha256`
- `created_at`

## 7. API 设计

### 工作区

- `POST /api/workspaces`
- `GET /api/workspaces`
- `GET /api/workspaces/{workspace_id}`
- `DELETE /api/workspaces/{workspace_id}`

### 文档

- `POST /api/workspaces/{workspace_id}/documents`
  - `multipart/form-data`
  - 支持一次上传多个文件
- `GET /api/workspaces/{workspace_id}/documents`
- `GET /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`

文档被运行中任务引用时，删除接口返回 `409 DOCUMENT_IN_USE`。

### Agent 任务

- `POST /api/tasks`
  - 请求：`{ "workspace_id": string, "message": string }`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/events`
  - SSE，支持 `Last-Event-ID` 断线续传
- `POST /api/tasks/{task_id}/cancel`
- `POST /api/tasks/{task_id}/retry`
- `GET /api/workspaces/{workspace_id}/tasks`

### 产物

- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/artifacts/{artifact_id}/preview`
- `GET /api/artifacts/{artifact_id}/download`

统一错误结构：

```json
{
  "error": {
    "code": "DOCUMENT_PARSE_FAILED",
    "message": "无法解析该文档",
    "details": {}
  }
}
```

## 8. Agent 设计

### 8.1 单 Agent 方案

第一版仅创建一个 `OfficeDocumentAgent`。它负责理解任务并选择工具，不使用多个角色互相对话。

系统约束：

- 只能使用当前工作区中状态为 `ready` 的文档。
- 不得声称读取了不存在、未解析或解析失败的文件。
- 关键事实必须关联来源位置。
- 信息不足或相互矛盾时必须明确提示。
- 禁止修改、覆盖上传文件。
- 禁止访问网络、邮件、操作系统命令和其他工作区。
- 禁止执行模型生成的代码或任意 SQL。
- 生成文件后必须调用验证工具。

### 8.2 LangChain Tools

所有工具通过 `@tool` 定义，参数和返回值使用 Pydantic 模型。

- `list_documents`：列出文件、格式、解析状态和元数据。
- `search_documents`：执行关键词与语义混合检索。
- `read_document_section`：按页码、标题路径或 chunk ID 读取上下文。
- `inspect_workbook`：返回工作表、表头、行数、列类型、公式和空值统计。
- `read_worksheet_range`：读取受限单元格区域。
- `analyze_table`：执行白名单统计操作，例如分组、求和、排序、同比和缺失值分析。
- `create_report`：生成 Markdown 和 HTML 报告。
- `create_docx`：根据结构化章节生成 Word 文件。
- `create_xlsx`：根据结构化工作表定义生成 Excel 文件。
- `validate_artifact`：重新打开产物，检查格式、内容和文件大小。

工具必须从 `ToolRuntime` 或任务上下文取得 `workspace_id` 和 `task_id`，不得信任模型自行传入的工作区路径。

### 8.3 Middleware

实现以下 Middleware：

- 动态系统提示：注入当前工作区文档摘要和任务限制。
- 模型调用限制：限制单任务模型调用次数和总 token。
- 工具调用限制：限制读取 chunk 数、表格区域大小和产物数量。
- 工具错误转换：把异常转换为可恢复的结构化观察结果。
- 敏感信息过滤：日志和 tracing 不保存 API Key 或文档全文。
- 任务取消检查：每次模型调用和工具调用前检查取消状态。

### 8.4 结构化输出

Agent 最终结果使用 Pydantic 模型：

```text
TaskResult
  summary: string
  findings: Finding[]
  citations: Citation[]
  warnings: string[]
  artifact_ids: string[]
```

采用 LangChain `ToolStrategy(TaskResult)`，让模型通过工具调用生成结构化结果；如果校验失败，最多自动修复两次，之后任务失败并保存原始错误摘要。

### 8.5 LangGraph 状态与恢复

每个任务对应一个 `thread_id`，使用 SQLite checkpointer 保存图状态。LangGraph 检查点可支持会话记忆、失败恢复和状态检查。[持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)

任务流程：

1. API 校验工作区、任务文本和可用文档。
2. worker 原子领取任务。
3. 创建或恢复 LangGraph thread。
4. Agent 获取文档清单并输出简短计划。
5. 按需检索和读取相关片段。
6. 通过白名单工具分析表格。
7. 生成带引用的结构化结论。
8. 如有需要，创建新文件并验证。
9. 保存最终结果和产物。
10. 将任务标记为完成。

进程异常退出时，把仍处于 `running` 的任务标记为 `interrupted`；用户点击重试后从最近的安全检查点恢复。任何可能重复生成文件的节点必须使用幂等 artifact key。

## 9. 检索方案

### 文档入库

1. 校验文件类型、大小和文件签名。
2. 计算 SHA-256，检测重复文件。
3. 提取结构化文本和表格。
4. 按标题、段落、页码和表格边界切分。
5. 写入 SQLite FTS5。
6. 调用 `text-embedding-v4` 生成向量并写入 Chroma。
7. 记录解析统计、警告和失败原因。

### 混合检索

- FTS5 返回关键词候选。
- Chroma 返回语义候选。
- 使用加权 Reciprocal Rank Fusion 合并结果。
- 同一来源的相邻 chunk 在 token 预算内合并。
- 每次工具调用最多返回 10 个候选片段。
- 回答只能引用真实返回的 chunk ID。

## 10. 文件支持限制

### PDF

支持原生文本 PDF、页码引用和基础表格文本；不支持扫描件 OCR、手写内容、加密文件和复杂图表理解。

### DOCX

支持标题、段落、列表和表格；暂不支持批注、修订记录、宏、内嵌对象和图片文字识别。

### XLSX

支持多工作表、单元格值、公式文本、缓存值和基础统计；不支持 VBA、外部连接刷新、数据透视表重算和 Excel 公式重新计算。公式没有缓存结果时必须显示警告。

### 默认上传限制

- 单文件最大 25 MB
- 单次最多 20 个文件
- 单工作区原始文件总量最大 100 MB
- 允许扩展名：`.pdf`、`.docx`、`.xlsx`
- 文件扩展名、MIME 类型和文件签名必须同时校验
- Office ZIP 包必须限制解压文件数与解压后总大小，防止压缩炸弹

## 11. 安全与隐私

- `DASHSCOPE_API_KEY` 仅通过服务端 `.env` 读取。
- API Key 不进入前端、数据库、任务事件、错误响应或日志。
- `.env` 必须加入 `.gitignore`；只提交 `.env.example`。
- 上传文件默认保存在本机，直到用户删除工作区。
- 只向模型发送完成当前任务所需的片段，不默认上传全部原文。
- 禁止路径穿越、符号链接逃逸和任意路径下载。
- HTML 预览必须清理脚本、事件属性和危险 URL。
- Docker 容器以非 root 用户运行。
- 服务对宿主机只绑定 `127.0.0.1`。
- LangSmith tracing 默认关闭；启用时仍不记录文档全文。

## 12. 可观测性和成本控制

- 每个任务记录 trace ID、耗时、模型调用次数、token 用量和工具调用次数。
- 单任务默认最多 12 次模型调用。
- 单任务默认最大运行时间 5 分钟。
- 单次检索最多返回 10 个片段。
- 模型超时默认 120 秒，瞬时错误最多重试两次并使用指数退避。
- embedding 以文档 SHA-256 和切分版本缓存。
- 达到调用或 token 限制时安全停止并显示明确错误。
- 开发者可通过环境变量选择性启用 LangSmith tracing。

## 13. 测试计划

### 单元测试

- PDF、DOCX、XLSX 解析和来源定位
- 文件类型、大小、文件签名和重复文件校验
- 工作区路径隔离
- 文本切分、FTS5、向量检索和混合排序
- Excel 数据类型和缺失值检测
- LangChain Tool 参数验证和错误转换
- Middleware 调用限制和取消检查
- TaskResult 结构化输出校验
- DOCX、XLSX 生成和重新打开验证
- SSE 事件序列化和任务状态转换

### 集成测试

- 上传、解析、索引和检索完整流程
- 多文件问答和精确引用
- Excel 分析并生成新工作簿
- 合同总结并生成 Word 报告
- Qwen 超时、限流、无效工具参数和无效结构化结果
- 任务取消、SSE 断线续传和任务重试
- worker 重启后的 interrupted 状态及检查点恢复
- 删除工作区后数据库、向量和文件全部清理
- 不同工作区之间无法访问文档或产物

### 安全测试

- `../` 路径穿越和绝对路径注入
- 恶意文件名、伪造扩展名和超大文件
- Office 压缩炸弹
- HTML 和 DOCX 中的脚本内容
- Prompt injection 要求读取其他工作区或执行命令
- 枚举其他 artifact ID 的越权下载
- 日志、SSE 和错误响应中的 API Key 泄露检查

### 端到端验收数据

准备三套固定演示数据：

1. 三份合同：提取合同方、金额、日期和风险条款并生成 DOCX。
2. 三份供应商报价：比较价格并生成 XLSX。
3. 一份销售数据：完成分组统计、趋势分析和 Markdown/HTML 报告。

验收要求：

- 三个场景均可独立完成。
- 关键事实均有可点击来源。
- 生成文件能被 Word 或 Excel 正常打开。
- 原始文件的 SHA-256 在任务前后保持不变。
- 标准演示任务在正常网络下五分钟内完成。
- 失败时页面提供可理解的错误、取消和重试入口。

## 14. 实施阶段

### 阶段一：项目骨架

- 建立 React、FastAPI、worker 和 Docker Compose。
- 建立 SQLite 数据模型、Alembic 和统一错误结构。
- 完成配置读取、健康检查和工作区 CRUD。

### 阶段二：文档系统

- 完成安全上传、哈希、隔离存储和删除。
- 实现 PDF、DOCX、XLSX 解析。
- 保存结构化 chunk、表格和来源位置。
- 建立 FTS5、Chroma 和 embedding 缓存。

### 阶段三：LangChain Agent

- 配置 `ChatOpenAI` 连接百炼 `qwen3.7-plus`。
- 创建 `OfficeDocumentAgent`、Tools、Middleware 和 TaskResult。
- 实现混合检索、表格分析和引用约束。
- 添加模型与工具调用限制。

### 阶段四：LangGraph 运行系统

- 接入 SQLite checkpointer。
- 实现持久化任务、worker、取消和恢复。
- 通过 SSE 映射 LangGraph 流式事件。
- 保证产物节点幂等。

### 阶段五：文件生成和界面

- 实现 Markdown、HTML、DOCX、XLSX 生成和验证。
- 完成三栏工作台、引用查看器、时间线和下载。
- 补齐空状态、解析状态、错误状态和断线恢复。

### 阶段六：测试和交付

- 完成单元、集成、安全和端到端测试。
- 准备演示数据、架构图、截图和演示视频。
- README 写明一键启动、环境变量、功能边界和常见错误。

## 15. 环境配置

仓库只提交 `.env.example`。首次运行时复制：

```powershell
Copy-Item .env.example .env
```

随后只在 `.env` 中填写真实的百炼 API Key：

```dotenv
DASHSCOPE_API_KEY=你的APIKey
```

默认使用百炼北京区标准 OpenAI 兼容地址：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

API Key 必须与 Base URL 的区域和计费方案匹配。Token Plan 和 Coding Plan 面向交互式编程工具，不作为本项目后端服务地址。[百炼 Base URL 说明](https://help.aliyun.com/en/model-studio/base-url)

## 16. 后续扩展

按优先级考虑：

1. 扫描 PDF 和图片 OCR。
2. PPTX 解析与演示文稿生成。
3. Google Drive、OneDrive 或 SharePoint 接入。
4. 邮件草稿与人工审批。
5. 本地目录连接器。
6. 多用户云端部署与权限控制。
7. 将文档工具封装为 MCP Server。
8. 复杂度确有需要时，再拆分检索、分析和报告 Agent。

## 17. 最终技术选型摘要

| 层级 | 技术 |
|---|---|
| 前端 | React、TypeScript、Vite、TanStack Query |
| API | FastAPI、Pydantic、SQLAlchemy、Alembic |
| Agent | LangChain `create_agent`、Tools、Middleware、ToolStrategy |
| 运行时 | LangGraph、SQLite Checkpointer |
| 主模型 | 阿里云百炼 `qwen3.7-plus` |
| 模型适配 | `langchain-openai` + 百炼 OpenAI 兼容 Base URL |
| 检索 | SQLite FTS5、Chroma、`text-embedding-v4` |
| 文档 | PyMuPDF、python-docx、openpyxl、pandas |
| 存储 | SQLite、本地文件系统、Chroma |
| 部署 | Docker Compose，本机单用户 |
| 可观测性 | 本地结构化日志；LangSmith 可选且默认关闭 |

