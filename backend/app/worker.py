import time
from sqlalchemy import update, select
from .database import Base, engine, SessionLocal
from .models import Task, now
from .services import run_task, add_event

def recover():
    with SessionLocal() as db: db.execute(update(Task).where(Task.status=="running").values(status="interrupted",error_code="WORKER_RESTARTED",error_message="Worker 重启，任务已中断")); db.commit()

def claim(db):
    candidate=db.scalar(select(Task.id).where(Task.status=="queued").order_by(Task.created_at).limit(1))
    if not candidate: return None
    changed=db.execute(update(Task).where(Task.id==candidate,Task.status=="queued").values(status="running",started_at=now())).rowcount; db.commit()
    return db.get(Task,candidate) if changed else None

def main():
    Base.metadata.create_all(engine); recover()
    while True:
        with SessionLocal() as db:
            task=claim(db)
            if task:
                try:
                    add_event(db,task.id,"step",{"title":"Worker 已领取任务","status":"completed"}); db.refresh(task)
                    if task.status!="cancelled": run_task(db,task)
                except Exception as e:
                    db.rollback(); task=db.get(Task,task.id); task.status="failed"; task.error_code=str(e); task.error_message="任务执行失败"; task.completed_at=now(); db.commit(); add_event(db,task.id,"error",{"code":str(e),"message":"任务执行失败，可检查文档后重试。"})
        time.sleep(1)

if __name__=="__main__": main()
