# 🧾 Tax Buddy — AI-Powered Tax Filing Assistant

> OCR · NER · Validation · Tax Engine · Interactive Dashboard

Tax Buddy is a production-grade, end-to-end pipeline for automated Indian income tax analysis. Upload a Form 16 PDF and get back structured entity extraction, cross-document validation against Form 26AS, tax computation under Old or New regime, and a downloadable ITR-1 JSON — all in under 30 seconds.

---

## ✨ Features

| Layer | What it does |
|-------|-------------|
| **OCR** | Multi-page PDF extraction via Tesseract (PaddleOCR v3 fallback) |
| **NER** | Deterministic regex extraction of PAN, TAN, Salary, TDS, AY, Deductions |
| **Validation** | Rule-based cross-check of Form 16 vs Form 26AS with trust score (0–100) |
| **Tax Engine** | Indian slab-based calculator — Old & New regime, Section 87A rebate, 4% cess |
| **ITR Generation** | Structured ITR-1 (Sahaj) JSON output |
| **Dashboard** | Streamlit fintech-style UI with Plotly charts and editable entity tables |

---

## 🏗️ Architecture

```
tax-buddy/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   ├── router.py       # API router registration
│   │   │   └── routes.py       # Endpoint controllers
│   │   ├── core/               # Config & settings
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── validation_service.py  # Form 16 vs 26AS rule engine
│   │   │   └── tax_service.py         # Slab-based tax computation
│   │   └── main.py             # FastAPI app entry point
│   ├── ml/
│   │   ├── ocr/
│   │   │   ├── ocr_service.py  # Multi-page OCR (Tesseract + PaddleOCR)
│   │   │   └── preprocess.py   # PDF→image, grayscale, denoise, deskew
│   │   └── ner/
│   │       ├── ner_service.py  # Regex-primary + transformer-optional NER
│   │       └── regex_utils.py  # Deterministic field extractors
│   ├── data/
│   │   └── uploads/            # Uploaded files (git-ignored)
│   └── requirements.txt
│
└── frontend/                   # Streamlit dashboard
    ├── app.py                  # Main dashboard (3-column layout)
    └── requirements.txt
```

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10–3.13 | [python.org](https://python.org) |
| Tesseract OCR | 5.x | `brew install tesseract` |
| Poppler | latest | `brew install poppler` |

> **Note:** PaddleOCR 3.x requires `paddlepaddle` which currently has no ARM64/Python 3.14 wheel. Tesseract is used as the primary engine and works fully.

---

### 1. Clone

```bash
git clone https://github.com/<your-username>/tax-buddy.git
cd tax-buddy
```

### 2. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install pdf2image python-multipart
```

Create a `.env` file (optional):

```bash
cp .env.example .env   # edit as needed
```

Start the API server:

```bash
python -m app.main
# → http://localhost:8000
# → Swagger docs: http://localhost:8000/docs
```

### 3. Frontend Setup

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate

pip install streamlit plotly pandas requests
streamlit run app.py
# → http://localhost:8501
```

---

## 🔌 API Reference

Base URL: `http://localhost:8000/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload a PDF or image file |
| `POST` | `/extract` | Run OCR + NER on an uploaded file |
| `POST` | `/validate` | Cross-validate Form 16 vs Form 26AS |
| `POST` | `/compute-tax` | Compute tax (old/new regime) |
| `POST` | `/generate-itr` | Generate ITR-1 JSON |
| `POST` | `/process` | **End-to-end pipeline** (recommended) |
| `GET` | `/system/health` | Health check |

### End-to-End Example

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@form16.pdf"
```

**Response:**
```json
{
  "file_id": "abc123",
  "entities": [
    { "label": "PAN",           "value": "BIGPP1846N", "confidence": 1.0 },
    { "label": "TAN",           "value": "MUMS15654C", "confidence": 1.0 },
    { "label": "GrossSalary",   "value": "751585.0",   "confidence": 1.0 },
    { "label": "TaxableIncome", "value": "604280.0",   "confidence": 1.0 },
    { "label": "TDS",           "value": "34690.0",    "confidence": 1.0 },
    { "label": "AssessmentYear","value": "2023-24",    "confidence": 1.0 }
  ],
  "validation": {
    "status": "ok",
    "score": 100,
    "issues": []
  },
  "tax": {
    "total_tax": 34690.24,
    "taxable_income": 604280.0,
    "tds_paid": 34690.0,
    "refund_or_payable": -0.24
  }
}
```

---

## 🧠 NER Extraction Logic

The NER service uses a **regex-primary, transformer-optional** architecture:

```
OCR Text (15,000+ chars from 8 pages)
        │
        ▼
┌─────────────────────────────┐
│   Regex Layer (PRIMARY)     │  ← Always runs, deterministic
│   extract_fields(text)      │
│   PAN · TAN · AY ·          │
│   GrossSalary · TaxableIncome│
│   TDS · Section80C          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Transformer Layer (OPTIONAL)│  ← xlm-roberta-base (when available)
│  Supplements soft fields    │
│  EmployerName · EmployeeName│
└─────────────┬───────────────┘
              │
              ▼
     entity_map (flat dict)
     { "PAN": "...", "TDS": 34690.0, ... }
```

### Validation Rules

| Rule | Severity | Description |
|------|----------|-------------|
| PAN Match | HIGH | PAN must match across Form 16 and Form 26AS |
| TAN Match | HIGH | Employer TAN must be consistent |
| TDS Reconciliation | HIGH | TDS diff ≤ ₹5 tolerance |
| Income Sanity | HIGH | TaxableIncome must be ≤ GrossSalary |
| Assessment Year | MEDIUM | AY must match across documents |

### Tax Slabs (Old Regime — Individual < 60 yrs)

| Income Range | Rate |
|-------------|------|
| Up to ₹2,50,000 | 0% |
| ₹2,50,001 – ₹5,00,000 | 5% |
| ₹5,00,001 – ₹10,00,000 | 20% |
| Above ₹10,00,000 | 30% |

Rebate u/s 87A (Old): ₹12,500 if taxable income ≤ ₹5,00,000  
Cess: 4% on (tax + surcharge)

---

## 🧪 Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## 🛣️ Roadmap

- [ ] PostgreSQL persistence (SQLAlchemy models ready)
- [ ] User authentication (JWT)
- [ ] Fine-tuned XLM-RoBERTa on annotated Form 16 dataset
- [ ] Form 26AS upload and auto-parse
- [ ] New Regime tax comparison chart
- [ ] Docker Compose deployment
- [ ] Support for ITR-2, ITR-3 forms

---

## 📦 Dependencies

### Backend

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | API framework |
| `pydantic` | Schema validation |
| `pytesseract` | OCR engine |
| `paddleocr` | OCR engine (v3, optional) |
| `opencv-python` | Image preprocessing |
| `pdf2image` | PDF → image conversion |
| `transformers` + `torch` | NER transformer model |
| `sqlalchemy` | ORM (future persistence) |

### Frontend

| Package | Purpose |
|---------|---------|
| `streamlit` | Dashboard framework |
| `plotly` | Interactive charts |
| `pandas` | Data tables |
| `requests` | API client |

---

## 📄 License

MIT — see [LICENSE](./LICENSE)

---

## 🙏 Acknowledgements

- [Income Tax India](https://incometax.gov.in) — official tax slab reference
- [TRACES](https://www.tdscpc.gov.in) — Form 16 / 26AS format specification
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR engine
- [HuggingFace Transformers](https://huggingface.co/transformers) — XLM-RoBERTa
