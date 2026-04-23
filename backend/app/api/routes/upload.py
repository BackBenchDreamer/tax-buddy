import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import Document
from app.models.schemas import UploadResponse, DocType

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.other),
    session_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if not session_id:
        session_id = uuid.uuid4().hex

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.max_upload_size_mb} MB.")

    session_dir = settings.upload_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{doc_type.value}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = session_dir / safe_name
    dest.write_bytes(content)

    doc = Document(
        session_id=session_id,
        filename=file.filename,
        doc_type=doc_type.value,
        file_path=str(dest),
        status="uploaded",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    logger.info(f"Uploaded [{doc_type}] '{file.filename}' -> {dest} (session={session_id})")
    return UploadResponse(
        session_id=session_id,
        document_id=doc.id,
        filename=file.filename,
        doc_type=doc_type.value,
        status="uploaded",
    )
