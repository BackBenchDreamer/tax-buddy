from datetime import datetime
from sqlalchemy import String, DateTime, Text, JSON, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(50))  # form16, form26as, other
    file_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(50), default="uploaded")  # uploaded, processed, failed
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extraction: Mapped["ExtractionResult"] = relationship("ExtractionResult", back_populates="document", uselist=False)

class ExtractionResult(Base):
    __tablename__ = "extraction_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), unique=True)
    raw_text: Mapped[str] = mapped_column(Text)
    entities: Mapped[dict] = mapped_column(JSON)  # structured extracted entities
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ner_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    document: Mapped["Document"] = relationship("Document", back_populates="extraction")

class ValidationResult(Base):
    __tablename__ = "validation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50))  # passed, warnings, failed
    mismatches: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TaxComputation(Base):
    __tablename__ = "tax_computations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    regime: Mapped[str] = mapped_column(String(20))  # old, new
    gross_income: Mapped[float] = mapped_column(Float)
    total_deductions: Mapped[float] = mapped_column(Float)
    taxable_income: Mapped[float] = mapped_column(Float)
    tax_liability: Mapped[float] = mapped_column(Float)
    cess: Mapped[float] = mapped_column(Float)
    total_tax: Mapped[float] = mapped_column(Float)
    tds_paid: Mapped[float] = mapped_column(Float)
    refund_or_payable: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)  # step-by-step
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
