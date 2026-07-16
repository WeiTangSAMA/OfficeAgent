import hashlib, zipfile
from pathlib import Path

ALLOWED = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def validate_signature(path: Path, original: str, content_type: str) -> str:
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED: raise ValueError("UNSUPPORTED_FILE_TYPE")
    if content_type not in {ALLOWED[suffix], "application/octet-stream"}: raise ValueError("MIME_TYPE_MISMATCH")
    head = path.read_bytes()[:8]
    if suffix == ".pdf" and not head.startswith(b"%PDF-"): raise ValueError("FILE_SIGNATURE_MISMATCH")
    if suffix in {".docx", ".xlsx"}:
        if not head.startswith(b"PK"): raise ValueError("FILE_SIGNATURE_MISMATCH")
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 10000 or sum(i.file_size for i in infos) > 250 * 1024 * 1024: raise ValueError("OFFICE_ZIP_BOMB")
            marker = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
            if marker not in {i.filename for i in infos}: raise ValueError("OFFICE_PACKAGE_INVALID")
    return suffix

def safe_child(root: Path, *parts: str) -> Path:
    target = root.joinpath(*parts).resolve(); base = root.resolve()
    if base != target and base not in target.parents: raise ValueError("PATH_ESCAPE")
    return target
