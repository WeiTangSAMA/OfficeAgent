from datetime import datetime
from pydantic import BaseModel, Field

class WorkspaceCreate(BaseModel): name: str = Field(min_length=1, max_length=120)
class WorkspaceOut(BaseModel):
    id: str; name: str; created_at: datetime; updated_at: datetime
    model_config = {"from_attributes": True}
class DocumentOut(BaseModel):
    id: str; workspace_id: str; original_name: str; media_type: str; size_bytes: int; sha256: str; status: str; page_count: int|None; metadata_json: dict; error_message: str|None; created_at: datetime
    model_config = {"from_attributes": True}
class TaskCreate(BaseModel): workspace_id: str; message: str = Field(min_length=1, max_length=10000)
class TaskOut(BaseModel):
    id: str; workspace_id: str; thread_id: str; user_message: str; status: str; plan_json: list; final_answer_json: dict|None; error_code: str|None; error_message: str|None; created_at: datetime; started_at: datetime|None; completed_at: datetime|None
    model_config = {"from_attributes": True}
class Finding(BaseModel): statement: str; citation_ids: list[str] = []
class Citation(BaseModel): id: str; document_id: str; document_name: str; location: dict; quote: str
class TaskResult(BaseModel): summary: str; findings: list[Finding]; citations: list[Citation]; warnings: list[str]; artifact_ids: list[str]
