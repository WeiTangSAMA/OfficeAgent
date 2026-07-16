export type Workspace={id:string;name:string;created_at:string};
export type Doc={id:string;original_name:string;media_type:string;size_bytes:number;sha256:string;status:string;page_count:number|null;error_message:string|null};
export type Citation={id:string;document_id:string;document_name:string;location:Record<string,unknown>;quote:string};
export type Task={id:string;workspace_id:string;user_message:string;status:string;plan_json:string[];final_answer_json:null|{summary:string;findings:{statement:string;citation_ids:string[]}[];citations:Citation[];warnings:string[];artifact_ids:string[]};error_code:string|null;error_message:string|null;created_at:string};
export type Artifact={id:string;name:string;type:string;size_bytes:number};
async function request<T>(url:string,init?:RequestInit):Promise<T>{const r=await fetch(url,init);const data=await r.json().catch(()=>null);if(!r.ok)throw new Error(data?.error?.message||'请求失败');return data}
export const api={
  workspaces:()=>request<Workspace[]>('/api/workspaces'),
  createWorkspace:(name:string)=>request<Workspace>('/api/workspaces',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}),
  documents:(id:string)=>request<Doc[]>(`/api/workspaces/${id}/documents`),
  upload:(id:string,files:File[])=>{const f=new FormData();files.forEach(x=>f.append('files',x));return request<Doc[]>(`/api/workspaces/${id}/documents`,{method:'POST',body:f})},
  deleteDocument:(id:string)=>fetch(`/api/documents/${id}`,{method:'DELETE'}).then(r=>{if(!r.ok)throw new Error('删除失败')}),
  tasks:(id:string)=>request<Task[]>(`/api/workspaces/${id}/tasks`), task:(id:string)=>request<Task>(`/api/tasks/${id}`),
  createTask:(workspace_id:string,message:string)=>request<Task>('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id,message})}),
  cancel:(id:string)=>request<Task>(`/api/tasks/${id}/cancel`,{method:'POST'}), retry:(id:string)=>request<Task>(`/api/tasks/${id}/retry`,{method:'POST'}),
  artifacts:(id:string)=>request<Artifact[]>(`/api/tasks/${id}/artifacts`)
};
