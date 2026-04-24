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
| **Dashboard** | Next.js (App Router) fintech-style UI with Recharts and Tailwind CSS |

---

## 🏗️ Architecture

```
tax-buddy/
├── Dockerfile                  # Backend Docker image
├── docker-compose.yml          # Backend + Frontend services
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env                    # Runtime config (git-ignored)
│   ├── .env.example            # Template (safe to commit)
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint (logging + DB init)
│   │   ├── api/
│   │   │   ├── router.py       # API router registration
│   │   │   └── routes.py       # Endpoint controllers + DB persistence
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic Settings (reads .env)
│   │   │   ├── database.py     # SQLite via SQLAlchemy (4 tables)
│   │   │   └── logging_config.py  # Structured logging setup
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   └── services/
│   │       ├── validation_service.py  # Form 16 vs 26AS rule engine
│   │       └── tax_service.py         # Slab-based tax computation
│   ├── ml/
│   │   ├── ocr/
│   │   │   ├── ocr_service.py  # Multi-page OCR (Tesseract + PaddleOCR)
│   │   │   └── preprocess.py   # Upscale, CLAHE, adaptive threshold, deskew
│   │   └── ner/
│   │       ├── ner_service.py  # Regex-primary + transformer-optional NER
│   │       └── regex_utils.py  # Deterministic field extractors
│   ├── data/
│   │   ├── uploads/            # Uploaded files (git-ignored)
│   │   ├── samples/            # Sample Form 16 PDFs for testing
│   │   └── taxbuddy.db         # SQLite database (git-ignored)
│   ├── logs/                   # Rotating log files (git-ignored)
│   └── tests/
│       └── test_pipeline.py    # Smoke tests (8 tests, 0.02s)
│
└── frontend/
    ├── app/                    # Next.js App Router pages & layout
    ├── components/             # Reusable UI components (shadcn, charts)
    ├── lib/                    # API client and utilities
    ├── types/                  # TypeScript interfaces
    └── package.json
```

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------| 
| Python | 3.10–3.13 | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
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

### 3. Frontend Setup (Next.js)

> **Note:** The frontend is now a Next.js app (not Streamlit). Requires **Node.js 18+**.  
> If a Python venv is active, deactivate it first: `deactivate`

```bash
cd frontend
npm install       # installs ~450 packages
npm run dev
# → http://localhost:3000
```

If `npm install` shows "audited 1 package" or `npm run dev` fails with "Missing script",  
run a clean install:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### 4. Run tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
# 8 passed in 0.02s
```

### 5. Docker (alternative)

```bash
# Build & start everything
docker compose up --build

# Backend only
docker build -t tax-buddy-backend .
docker run -p 8000:8000 -v $(pwd)/backend/data:/app/data tax-buddy-backend
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
| `next` | React framework |
| `tailwindcss` | Utility-first CSS |
| `recharts` | Interactive charts |
| `lucide-react` | Icons |
| `sonner` | Toast notifications |

---

## 📄 License

MIT — see [LICENSE](./LICENSE)

---

## 🙏 Acknowledgements

- [Income Tax India](https://incometax.gov.in) — official tax slab reference
- [TRACES](https://www.tdscpc.gov.in) — Form 16 / 26AS format specification
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR engine
- [HuggingFace Transformers](https://huggingface.co/transformers) — XLM-RoBERTa
