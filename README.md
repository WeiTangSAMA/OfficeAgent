# 案牍 · 办公文档 Agent

本机运行的中文办公文档 Agent。支持上传 PDF、DOCX、XLSX，保留页码、段落或工作表范围，使用阿里云百炼 `qwen3.7-plus` 完成工具调用与结构化回答，并通过 SSE 展示执行状态。

## 一键启动

需要 Docker Desktop 与有效的百炼 API Key：

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 DASHSCOPE_API_KEY
docker compose up --build
```

浏览器打开 `http://127.0.0.1:5173`。API 文档位于 `http://127.0.0.1:8000/docs`。

未配置 API Key 时系统仍可运行，会明确使用本地关键词检索摘要，方便验证上传、解析、引用、SSE 与下载流程；不会假装调用模型。

## 服务

- `web`：React + TypeScript + Vite 三栏工作台，由 Nginx 提供静态文件。
- `api`：FastAPI、SQLAlchemy、SQLite，负责工作区、上传、任务、SSE 与产物。
- `worker`：轮询 SQLite，通过条件更新原子领取任务，异常重启后标记 `interrupted`。
- `data/app.db` 与 `data/checkpoints.db` 分离；文件位于 `data/workspaces/{id}`。

## 安全边界

- 只接受 `.pdf`、`.docx`、`.xlsx`，同时校验扩展名、MIME、文件签名和 Office ZIP 结构。
- 单文件 25 MB、单次 20 个文件；拒绝压缩炸弹和重复文档。
- 客户端不传真实磁盘路径；服务端计算并验证所有路径。
- 上传文件随机命名、只读使用，产物只写入当前任务目录。
- Agent 没有网络、Shell、SQL 或任意代码执行工具。
- API Key 不进入前端、数据库、SSE 或错误响应。

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
$env:PYTHONPATH="backend"
pytest backend\tests

Set-Location frontend
npm install
npm run dev
```

另开终端运行 API 与 worker：

```powershell
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload
python -m app.worker
```

## 在 PyCharm 中一键运行

1. 在项目根目录创建独立环境并安装依赖（不要对 uv 管理的全局 Python 使用 `--break-system-packages`）：

   ```powershell
   uv venv .venv --python 3.12
   uv pip install --python .venv\Scripts\python.exe -r backend\requirements.txt
   ```

2. 在 PyCharm 的 **Settings → Python Interpreter → Add Interpreter → Existing** 中选择 `.venv\Scripts\python.exe`。
3. 如需同时查看 Web 界面，先在 `frontend` 目录执行一次 `npm install` 和 `npm run build`。
4. 新建 **Python** Run Configuration，将 Script path 设置为项目根目录的 `pycharm_run.py`。
5. 直接运行，无需另外配置 Working directory 或 `PYTHONPATH`。

启动类会同时运行 FastAPI 和 worker：

- 工作台：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

停止 PyCharm Run Configuration 时，worker 子进程也会自动结束。

## 第一版边界

不支持 OCR、PPTX、旧版 Office、宏、邮件/网盘连接、多用户权限、外部系统操作或覆盖原文件。Excel 公式只读取公式文本/缓存值，不重新计算。
