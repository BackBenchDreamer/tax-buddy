"""
SQLite storage layer via SQLAlchemy (sync, lightweight).

Tables
------
documents        — uploaded file metadata
extracted_data   — JSON blob of NER entity_map per document
validation_results — JSON blob of validation output per document
tax_results      — JSON blob of tax computation per document

Design choices
--------------
* No complex FK relationships — keeping it simple and fast.
* JSON columns stored as TEXT (SQLite-native).
* All timestamps are UTC ISO-8601 strings.
* A single DB session context-manager: `get_db()`.
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from sqlalchemy import Column, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=settings.DEBUG,
)

# Enable WAL mode for better concurrency
@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id        = Column(Integer, primary_key=True, index=True)
    file_id   = Column(String(64), unique=True, index=True, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(512), nullable=False)
    upload_time = Column(String(32), nullable=False)   # UTC ISO-8601


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id          = Column(Integer, primary_key=True, index=True)
    file_id     = Column(String(64), index=True, nullable=False)
    entity_json = Column(Text, nullable=False)          # JSON string
    created_at  = Column(String(32), nullable=False)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id           = Column(Integer, primary_key=True, index=True)
    file_id      = Column(String(64), index=True, nullable=False)
    status       = Column(String(32), nullable=True)
    score        = Column(Integer, nullable=True)
    result_json  = Column(Text, nullable=False)
    created_at   = Column(String(32), nullable=False)


class TaxResult(Base):
    __tablename__ = "tax_results"

    id          = Column(Integer, primary_key=True, index=True)
    file_id     = Column(String(64), index=True, nullable=False)
    regime      = Column(String(8), nullable=True)
    total_tax   = Column(String(32), nullable=True)
    result_json = Column(Text, nullable=False)
    created_at  = Column(String(32), nullable=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create all tables (idempotent — safe to call on every startup)."""
    Base.metadata.create_all(bind=engine)
    log.info("[DB] Tables initialised at %s", settings.DATABASE_URL)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Yield a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CRUD helpers (thin wrappers — keep business logic in services)
# ---------------------------------------------------------------------------

def save_document(file_id: str, file_name: str, file_path: str) -> None:
    with get_db() as db:
        doc = Document(
            file_id=file_id,
            file_name=file_name,
            file_path=file_path,
            upload_time=_now(),
        )
        db.merge(doc)   # upsert-like (idempotent on re-process)
    log.info("[DB] Document saved — file_id=%s", file_id)


def save_extracted_data(file_id: str, entity_map: Dict[str, Any]) -> None:
    with get_db() as db:
        row = ExtractedData(
            file_id=file_id,
            entity_json=json.dumps(entity_map, default=str),
            created_at=_now(),
        )
        db.add(row)
    log.debug("[DB] Extracted data saved — file_id=%s", file_id)


def save_validation_result(file_id: str, result: Dict[str, Any]) -> None:
    with get_db() as db:
        row = ValidationResult(
            file_id=file_id,
            status=result.get("status"),
            score=result.get("score"),
            result_json=json.dumps(result, default=str),
            created_at=_now(),
        )
        db.add(row)
    log.debug("[DB] Validation result saved — file_id=%s", file_id)


def save_tax_result(file_id: str, result: Dict[str, Any], regime: str = "old") -> None:
    with get_db() as db:
        row = TaxResult(
            file_id=file_id,
            regime=regime,
            total_tax=str(result.get("total_tax", "")),
            result_json=json.dumps(result, default=str),
            created_at=_now(),
        )
        db.add(row)
    log.debug("[DB] Tax result saved — file_id=%s", file_id)


def get_document(file_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        doc = db.query(Document).filter(Document.file_id == file_id).first()
        if doc:
            return {"file_id": doc.file_id, "file_path": doc.file_path, "upload_time": doc.upload_time}
    return None
