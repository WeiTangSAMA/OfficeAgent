import asyncio, json, shutil, uuid
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, SessionLocal, session_scope
from .models import Workspace, Document, Task, TaskEvent, Artifact, now
from .schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceOut, DocumentOut, TaskCreate, TaskOut
from .config import settings
from .security import validate_signature, sha256_file, safe_child
from .documents import parse_document
from .retrieval import index_document, remove_document

Base.metadata.create_all(engine)
app=FastAPI(title="办公文档 Agent",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173"],allow_methods=["*"],allow_headers=["*"])

def db_dep(): yield from session_scope()
def fail(status,code,message,details=None): raise HTTPException(status,{"error":{"code":code,"message":message,"details":details or {}}})

@app.exception_handler(HTTPException)
async def http_error(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(exc.detail if isinstance(exc.detail,dict) and "error" in exc.detail else {"error":{"code":"HTTP_ERROR","message":str(exc.detail),"details":{}}},status_code=exc.status_code)

@app.get("/api/health")
def health(): return {"status":"ok","model":settings.qwen_model,"model_configured":bool(settings.dashscope_api_key)}
@app.post("/api/workspaces",response_model=WorkspaceOut,status_code=201)
def create_workspace(body:WorkspaceCreate,db=Depends(db_dep)):
    w=Workspace(name=body.name.strip()); db.add(w); db.commit(); return w
@app.get("/api/workspaces",response_model=list[WorkspaceOut])
def list_workspaces(db=Depends(db_dep)): return list(db.scalars(select(Workspace).order_by(Workspace.updated_at.desc())))
@app.get("/api/workspaces/{workspace_id}",response_model=WorkspaceOut)
def get_workspace(workspace_id:str,db=Depends(db_dep)):
    w=db.get(Workspace,workspace_id)
    if not w: fail(404,"WORKSPACE_NOT_FOUND","工作区不存在")
    return w
@app.patch("/api/workspaces/{workspace_id}",response_model=WorkspaceOut)
def update_workspace(workspace_id:str,body:WorkspaceUpdate,db=Depends(db_dep)):
    w=db.get(Workspace,workspace_id)
    if not w: fail(404,"WORKSPACE_NOT_FOUND","工作区不存在")
    name=body.name.strip()
    if not name: fail(422,"INVALID_WORKSPACE_NAME","工作区名称不能为空")
    w.name=name; w.updated_at=now(); db.commit(); db.refresh(w); return w
@app.delete("/api/workspaces/{workspace_id}",status_code=204)
def delete_workspace(workspace_id:str,db=Depends(db_dep)):
    w=db.get(Workspace,workspace_id)
    if not w: fail(404,"WORKSPACE_NOT_FOUND","工作区不存在")
    db.delete(w); db.commit(); root=safe_child(settings.app_data_dir,"workspaces",workspace_id)
    if root.exists(): shutil.rmtree(root)

@app.post("/api/workspaces/{workspace_id}/documents",response_model=list[DocumentOut],status_code=201)
async def upload_documents(workspace_id:str,files:list[UploadFile]=File(...),db=Depends(db_dep)):
    if not db.get(Workspace,workspace_id): fail(404,"WORKSPACE_NOT_FOUND","工作区不存在")
    if len(files)>settings.max_files_per_upload: fail(413,"TOO_MANY_FILES","单次最多上传 20 个文件")
    root=safe_child(settings.app_data_dir,"workspaces",workspace_id,"uploads"); root.mkdir(parents=True,exist_ok=True); result=[]
    for upload in files:
        stored=f"{uuid.uuid4().hex}{Path(upload.filename or '').suffix.lower()}"; path=safe_child(root,stored); size=0
        with path.open("wb") as out:
            while chunk:=await upload.read(1024*1024):
                size+=len(chunk)
                if size>settings.max_file_size_mb*1024*1024: out.close(); path.unlink(missing_ok=True); fail(413,"FILE_TOO_LARGE","单文件最大 25 MB")
                out.write(chunk)
        try:
            validate_signature(path,upload.filename or "",upload.content_type or "application/octet-stream")
            doc=Document(workspace_id=workspace_id,original_name=Path(upload.filename or "未命名").name,stored_name=stored,media_type=upload.content_type or "application/octet-stream",size_bytes=size,sha256=sha256_file(path),status="parsing")
            db.add(doc); db.flush(); doc.chunks=parse_document(doc,path); db.commit()
        except IntegrityError:
            db.rollback(); path.unlink(missing_ok=True); fail(409,"DUPLICATE_DOCUMENT","该工作区已存在内容相同的文件")
        except Exception as e:
            db.rollback(); path.unlink(missing_ok=True); fail(422,"DOCUMENT_PARSE_FAILED","无法解析该文档",{"reason":str(e)})
        try:
            index_document(doc,doc.chunks)
            doc.status="ready"; doc.error_message=None; db.commit(); result.append(doc)
        except Exception as e:
            db.rollback(); failed_doc=db.get(Document,doc.id)
            if failed_doc:
                failed_doc.status="failed"; failed_doc.error_message=f"向量索引失败：{type(e).__name__}"; db.commit()
            fail(502,"DOCUMENT_INDEX_FAILED","文档已解析，但建立向量索引失败",{"reason":str(e)})
    return result
@app.get("/api/workspaces/{workspace_id}/documents",response_model=list[DocumentOut])
def list_documents(workspace_id:str,db=Depends(db_dep)): return list(db.scalars(select(Document).where(Document.workspace_id==workspace_id).order_by(Document.created_at.desc())))
@app.get("/api/documents/{document_id}",response_model=DocumentOut)
def get_document(document_id:str,db=Depends(db_dep)):
    d=db.get(Document,document_id)
    if not d: fail(404,"DOCUMENT_NOT_FOUND","文档不存在")
    return d
@app.delete("/api/documents/{document_id}",status_code=204)
def delete_document(document_id:str,db=Depends(db_dep)):
    d=db.get(Document,document_id)
    if not d: fail(404,"DOCUMENT_NOT_FOUND","文档不存在")
    active=db.scalar(select(func.count()).select_from(Task).where(Task.workspace_id==d.workspace_id,Task.status.in_(["queued","running"])))
    if active: fail(409,"DOCUMENT_IN_USE","文档正被运行中的任务引用")
    path=safe_child(settings.app_data_dir,"workspaces",d.workspace_id,"uploads",d.stored_name); remove_document(d); db.delete(d); db.commit(); path.unlink(missing_ok=True)

@app.post("/api/tasks",response_model=TaskOut,status_code=202)
def create_task(body:TaskCreate,db=Depends(db_dep)):
    if not db.get(Workspace,body.workspace_id): fail(404,"WORKSPACE_NOT_FOUND","工作区不存在")
    ready=db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id==body.workspace_id,Document.status=="ready"))
    if not ready: fail(409,"NO_READY_DOCUMENTS","请先上传并成功解析至少一份文档")
    t=Task(workspace_id=body.workspace_id,user_message=body.message.strip()); db.add(t); db.commit(); return t
@app.get("/api/tasks/{task_id}",response_model=TaskOut)
def get_task(task_id:str,db=Depends(db_dep)):
    t=db.get(Task,task_id)
    if not t: fail(404,"TASK_NOT_FOUND","任务不存在")
    return t
@app.get("/api/workspaces/{workspace_id}/tasks",response_model=list[TaskOut])
def list_tasks(workspace_id:str,db=Depends(db_dep)): return list(db.scalars(select(Task).where(Task.workspace_id==workspace_id).order_by(Task.created_at.desc())))
@app.post("/api/tasks/{task_id}/cancel",response_model=TaskOut)
def cancel_task(task_id:str,db=Depends(db_dep)):
    t=db.get(Task,task_id)
    if not t: fail(404,"TASK_NOT_FOUND","任务不存在")
    if t.status not in {"queued","running"}: fail(409,"TASK_NOT_CANCELLABLE","当前任务不能取消")
    t.status="cancelled"; t.completed_at=now(); db.commit(); return t
@app.post("/api/tasks/{task_id}/retry",response_model=TaskOut,status_code=202)
def retry_task(task_id:str,db=Depends(db_dep)):
    old=db.get(Task,task_id)
    if not old: fail(404,"TASK_NOT_FOUND","任务不存在")
    if old.status not in {"failed","cancelled","interrupted"}: fail(409,"TASK_NOT_RETRYABLE","当前任务不能重试")
    # A retry is a fresh execution. Reusing the old LangGraph thread restores
    # failed tool-call history and can immediately repeat the same loop.
    t=Task(workspace_id=old.workspace_id,user_message=old.user_message); db.add(t); db.commit(); return t
@app.get("/api/tasks/{task_id}/events")
async def task_events(task_id:str,request:Request):
    last=int(request.headers.get("last-event-id","0") or 0)
    async def stream():
        nonlocal last
        while True:
            if await request.is_disconnected(): break
            with SessionLocal() as db:
                task=db.get(Task,task_id)
                if not task: yield "event: error\ndata: {\"message\":\"TASK_NOT_FOUND\"}\n\n"; break
                events=list(db.scalars(select(TaskEvent).where(TaskEvent.task_id==task_id,TaskEvent.sequence>last).order_by(TaskEvent.sequence)))
                for e in events:
                    last=e.sequence; yield f"id: {e.sequence}\nevent: {e.type}\ndata: {json.dumps(e.payload_json,ensure_ascii=False)}\n\n"
                if task.status in {"completed","failed","cancelled"}: yield f"event: done\ndata: {json.dumps({'status':task.status})}\n\n"; break
            yield ": keepalive\n\n"; await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
@app.get("/api/tasks/{task_id}/artifacts")
def list_artifacts(task_id:str,db=Depends(db_dep)): return [{"id":a.id,"name":a.name,"type":a.type,"size_bytes":a.size_bytes} for a in db.scalars(select(Artifact).where(Artifact.task_id==task_id))]
@app.get("/api/artifacts/{artifact_id}/preview")
def preview_artifact(artifact_id:str,db=Depends(db_dep)):
    a=db.get(Artifact,artifact_id)
    if not a: fail(404,"ARTIFACT_NOT_FOUND","产物不存在")
    path=safe_child(settings.app_data_dir,*Path(a.path).parts)
    if a.type=="markdown": return PlainTextResponse(path.read_text(encoding="utf-8"))
    return {"name":a.name,"type":a.type,"size_bytes":a.size_bytes}
@app.get("/api/artifacts/{artifact_id}/download")
def download_artifact(artifact_id:str,db=Depends(db_dep)):
    a=db.get(Artifact,artifact_id)
    if not a: fail(404,"ARTIFACT_NOT_FOUND","产物不存在")
    return FileResponse(safe_child(settings.app_data_dir,*Path(a.path).parts),filename=a.name,media_type="application/octet-stream")

# PyCharm/local launcher: serve a previously built frontend from the same port.
# Docker keeps using the dedicated Nginx container because this directory is
# intentionally absent from the backend image.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="web")
