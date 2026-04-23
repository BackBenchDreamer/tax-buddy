# Tax Buddy

Hybrid AI workflow for automated tax return filing in India. The project combines document preprocessing, OCR, transformer-assisted entity extraction, cross-document validation, rule-based tax computation, and ITR output generation.

## Architecture

```text
[Upload PDF/Image]
        |
        v
[Preprocess: denoise -> deskew -> binarize]
        |
        v
[OCR Layer]
   |-> PaddleOCR primary
   |-> Tesseract fallback
        |
        v
[Text Normalize + Layout Metadata]
        |
        v
[Hybrid Entity Extraction]
   |-> XLM-R NER model
   |-> regex + heuristics for PAN/TAN/TDS/deductions
        |
        v
[Cross-Document Validation]
   |-> PAN/TAN reconciliation
   |-> Form 16 vs Form 26AS TDS matching
   |-> income / deduction mismatch detection
        |
        v
[Tax Engine]
   |-> old regime
   |-> new regime
   |-> explainable slab breakdown
        |
        v
[Outputs]
   |-> ITR JSON
   |-> ITR XML
   |-> PDF summary report
        |
        v
[Dashboard UI]
   |-> upload
   |-> editable extracted fields
   |-> validation warnings
   |-> tax charts
   |-> downloads
```

## Folder Structure

```text
backend/
  app/
    api/
    core/
    ml/
    services/
    db.py
    main.py
    schemas.py
  tests/
  pyproject.toml
frontend/
  src/
    components/
    lib/
    App.tsx
    main.tsx
    index.css
  package.json
```

## Key Capabilities

- Document ingestion for PDFs and scanned images.
- OCR with PaddleOCR first and Tesseract fallback.
- Hybrid NER: XLM-R token classification plus regex and heuristics.
- Validation for PAN, TAN, TDS, salary, and deduction mismatches.
- Tax computation for old and new regimes with step-by-step breakdown.
- ITR output generation as JSON, XML, and PDF summary.
- Editable dashboard with confidence-aware fields and charted results.

## Backend API

- `POST /api/upload`
- `POST /api/extract/{document_id}`
- `POST /api/validate/{document_id}`
- `POST /api/compute-tax/{document_id}`
- `POST /api/generate-itr/{document_id}`
- `POST /api/pipeline/{document_id}`
- `GET /api/documents/{document_id}`

## Dataset Format

The NER training pipeline accepts JSONL with token-level labels:

```json
{"tokens":["PAN","ABCDE1234F"],"ner_tags":[0,0]}
```

For span-based annotation:

```json
{
  "text": "PAN ABCDE1234F",
  "entities": [
    {"start": 4, "end": 14, "label": "PAN"}
  ]
}
```

Recommended labels are defined in [backend/app/ml/schema.py](backend/app/ml/schema.py).

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Optional extras:

```bash
pip install -e .[ocr,ml,dev]
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL=http://localhost:8000/api` if the backend is not on the default URL.

## Deployment Guide

- Backend can run on a container platform or VM with `uvicorn` behind a reverse proxy.
- Use PostgreSQL in production by setting `DATABASE_URL` in `.env`.
- Store uploads and generated outputs in object storage for long-term retention.
- Frontend can be deployed as a static Vite build behind a CDN.
- OCR/ML models should be packaged as external artifacts or pulled from a model registry.

## Notes

- The implementation is designed to be modular and replaceable; OCR, NER, and tax rules can be swapped independently.
- The current code base favors robust defaults and graceful degradation when optional ML/OCR packages are not installed.
