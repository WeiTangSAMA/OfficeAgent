import re
from sqlalchemy import text
from .config import settings
from .database import engine

def embedding_client():
    """Create a DashScope-compatible embedding client.

    LangChain normally tokenizes long inputs before calling OpenAI-compatible
    endpoints. DashScope text-embedding-v4 expects strings instead of token-id
    arrays, so raw text must be sent.
    """
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.dashscope_embedding_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        check_embedding_ctx_length=False,
        # DashScope text-embedding-v4 accepts at most 10 texts per request.
        # LangChain will transparently split larger documents into batches.
        chunk_size=10,
        max_retries=settings.qwen_max_retries,
    )

def ensure_fts():
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, workspace_id UNINDEXED, document_id UNINDEXED, content, tokenize='unicode61')")

def index_document(document, chunks):
    ensure_fts()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM chunks_fts WHERE document_id=:id"),{"id":document.id})
        for c in chunks:
            conn.execute(text("INSERT INTO chunks_fts(chunk_id,workspace_id,document_id,content) VALUES(:c,:w,:d,:t)"),{"c":c.id,"w":document.workspace_id,"d":document.id,"t":c.content})
    if settings.dashscope_api_key:
        from langchain_chroma import Chroma
        store=Chroma(collection_name=f"ws_{document.workspace_id.replace('-','_')}",embedding_function=embedding_client(),persist_directory=str(settings.app_data_dir/"chroma"))
        store.add_texts([c.content for c in chunks],metadatas=[{"chunk_id":c.id,"document_id":document.id} for c in chunks],ids=[c.id for c in chunks])

def remove_document(document):
    ensure_fts()
    with engine.begin() as conn: conn.execute(text("DELETE FROM chunks_fts WHERE document_id=:id"),{"id":document.id})
    if settings.dashscope_api_key:
        from langchain_chroma import Chroma
        store=Chroma(collection_name=f"ws_{document.workspace_id.replace('-','_')}",embedding_function=embedding_client(),persist_directory=str(settings.app_data_dir/"chroma"))
        store.delete(where={"document_id":document.id})

def hybrid_chunk_ids(workspace_id: str, query: str, limit: int=10):
    ensure_fts(); terms=re.findall(r"[\w\u4e00-\u9fff]+",query)[:12]
    keyword=[]
    if terms:
        match=" OR ".join(f'"{x}"' for x in terms)
        with engine.begin() as conn:
            keyword=[r[0] for r in conn.execute(text("SELECT chunk_id FROM chunks_fts WHERE workspace_id=:w AND chunks_fts MATCH :q ORDER BY bm25(chunks_fts) LIMIT 30"),{"w":workspace_id,"q":match})]
            # unicode61 does not segment every Chinese compound consistently;
            # an exact substring fallback preserves recall without losing FTS ranking.
            if not keyword:
                keyword=[r[0] for r in conn.execute(text("SELECT chunk_id FROM chunks_fts WHERE workspace_id=:w AND content LIKE :q LIMIT 30"),{"w":workspace_id,"q":f"%{query}%"})]
    semantic=[]
    if settings.dashscope_api_key:
        try:
            from langchain_chroma import Chroma
            store=Chroma(collection_name=f"ws_{workspace_id.replace('-','_')}",embedding_function=embedding_client(),persist_directory=str(settings.app_data_dir/"chroma"))
            semantic=[d.metadata["chunk_id"] for d,_ in store.similarity_search_with_relevance_scores(query,k=30)]
        except Exception:
            semantic=[]
    scores={}
    for weight,items in ((0.55,keyword),(0.45,semantic)):
        for rank,cid in enumerate(items,1): scores[cid]=scores.get(cid,0)+weight/(60+rank)
    return [cid for cid,_ in sorted(scores.items(),key=lambda x:x[1],reverse=True)[:limit]]
