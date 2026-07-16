import enum, uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    documents = relationship("Document", cascade="all, delete-orphan")
    tasks = relationship("Task", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255)); stored_name: Mapped[str] = mapped_column(String(80))
    media_type: Mapped[str] = mapped_column(String(100)); size_bytes: Mapped[int] = mapped_column(Integer); sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="uploaded"); page_count: Mapped[int|None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict); error_message: Mapped[str|None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    chunks = relationship("DocumentChunk", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("workspace_id", "sha256", name="uq_doc_hash"),)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer); content: Mapped[str] = mapped_column(Text)
    location_json: Mapped[dict] = mapped_column(JSON); token_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_id: Mapped[str|None] = mapped_column(String, nullable=True)

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[str] = mapped_column(String, default=uid); user_message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True); plan_json: Mapped[list] = mapped_column(JSON, default=list)
    final_answer_json: Mapped[dict|None] = mapped_column(JSON, nullable=True); error_code: Mapped[str|None] = mapped_column(String, nullable=True); error_message: Mapped[str|None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); started_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True); completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    events = relationship("TaskEvent", cascade="all, delete-orphan"); artifacts = relationship("Artifact", cascade="all, delete-orphan")

class TaskEvent(Base):
    __tablename__ = "task_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid); task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer); type: Mapped[str] = mapped_column(String(30)); payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("task_id", "sequence", name="uq_task_event_sequence"),)

class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid); task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255)); type: Mapped[str] = mapped_column(String(20)); path: Mapped[str] = mapped_column(String(500)); size_bytes: Mapped[int] = mapped_column(Integer); sha256: Mapped[str] = mapped_column(String(64)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
