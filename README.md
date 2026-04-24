# 🧾 Tax Buddy — AI-Powered Tax Filing Assistant

> **OCR · NER · Validation · Tax Engine · Interactive Dashboard**  
> Production-grade pipeline for automated Indian income tax analysis

Tax Buddy is an end-to-end system for extracting tax data from Form 16 PDFs, validating it against Form 26AS, computing income tax, and generating a downloadable tax summary report — all in under 5 seconds.

**Status:** ✅ Production-ready | Fully tested | Clean, reproducible setup

---

## ✨ Features

| Layer | What it does | Tech |
|-------|-------------|------|
| **OCR** | Multi-page PDF extraction via PaddleOCR v3 (or Tesseract fallback) | PaddleOCR, pytesseract |
| **NER** | Section-aware field extraction of PAN, TAN, Salary, TDS, Deductions | Custom regex + XLM-RoBERTa |
| **Validation** | Cross-check Form 16 vs Form 26AS with trust score | 6 rules, 0–100 scoring |
| **Tax Engine** | Indian slab-based calculator — Old & New regime | Full breakdown by bracket |
| **PDF Export** | Download a formatted tax summary report | reportlab |
| **Dashboard** | Interactive React UI for file upload & results | Next.js, Recharts, Tailwind |

---

## 🏗️ Architecture

### High-Level Pipeline

```
PDF Input
    │
    ▼
┌──────────────────────────┐
│  OCR (PaddleOCR/Tesseract)│  Extract text (first page only in <5s)
│  • Preprocessing         │  • Upscale, denoise, enhance
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  NER (Section-aware)     │  Extract tax fields
│  • Regex patterns        │  • Fallback: XLM-RoBERTa
│  • Known field mapping   │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Validation              │  Compare Form 16 vs Form 26AS
│  • PAN/TAN match         │  • Trust score calculation
│  • TDS reconciliation    │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Tax Computation         │  Calculate income tax
│  • Old regime slabs      │  • Rebates (87A)
│  • New regime slabs      │  • Cess (4%)
│  • Refund / payable      │
└──────┬───────────────────┘
       │
       ▼
   JSON Response + Optional PDF Report
```

### Codebase Structure

```
tax-buddy/
├── Dockerfile                      # Production backend image
├── docker-compose.yml              # Backend + Frontend orchestration
├── README.md                       # This file
├── .gitignore
│
├── backend/
│   ├── requirements.txt            # Python dependencies (pinned versions)
│   ├── .env.example                # Configuration template
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint + startup
│   │   ├── api/
│   │   │   ├── routes.py           # 8 API endpoints
│   │   │   └── router.py           # Route registration
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings (from .env)
│   │   │   ├── database.py         # SQLite via SQLAlchemy
│   │   │   └── logging_config.py   # Structured logging
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/
│   │   │   └── schemas.py          # Pydantic request/response models
│   │   └── services/
│   │       ├── tax_service.py      # Tax computation (old & new regime)
│   │       └── validation_service.py  # Cross-document validation
│   ├── ml/
│   │   ├── ocr/
│   │   │   ├── ocr_service.py      # PaddleOCR + Tesseract fallback
│   │   │   └── preprocess.py       # Image enhancement
│   │   └── ner/
│   │       ├── ner_service.py      # Hybrid NER
│   │       └── regex_utils.py      # Section-aware extraction
│   ├── data/
│   │   ├── uploads/                # User PDFs (runtime, git-ignored)
│   │   └── taxbuddy.db             # SQLite DB (runtime, git-ignored)
│   ├── logs/                       # Runtime logs (git-ignored)
│   └── tests/
│       └── test_pipeline.py        # Smoke tests
│
└── frontend/
    ├── app/                        # Next.js App Router
    ├── components/                 # React components
    ├── lib/                        # API client, utilities
    ├── types/                      # TypeScript types
    ├── next.config.ts
    ├── package.json
    └── tsconfig.json
```

---

## ⚙️ System Requirements

### Local Development

| Component | Requirement | Install |
|-----------|-------------|---------|
| **Python** | 3.11+ | [python.org](https://www.python.org) |
| **Node.js** | 18+ | [nodejs.org](https://www.nodejs.org) |
| **Tesseract** | 5.x+ | macOS: `brew install tesseract` / Linux: `apt-get install tesseract-ocr` |
| **Poppler** | latest | macOS: `brew install poppler` / Linux: `apt-get install poppler-utils` |

### Docker (Recommended)

- Docker 20.10+
- Docker Compose 1.29+

---

## 🚀 Quick Start

### Option A: Docker (Recommended for consistency)

```bash
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Start both backend and frontend
docker-compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Option B: Local Development

#### 1. Backend Setup

```bash
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy/backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  (Windows)

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# Run backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: **http://localhost:8000**  
API docs: **http://localhost:8000/docs**

#### 2. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend runs at: **http://localhost:3000**

---

## 🔌 API Endpoints

### Core Pipeline

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/upload` | `POST` | Upload a PDF/image file |
| `/extract` | `POST` | OCR + NER on uploaded file |
| `/validate` | `POST` | Cross-validate Form 16 vs Form 26AS |
| `/compute-tax` | `POST` | Calculate income tax |
| `/generate-itr` | `POST` | Generate ITR-1 JSON structure |
| `/process` | `POST` | **RECOMMENDED** — Full pipeline in one request |
| `/generate-report` | `POST` | Generate downloadable PDF report |
| `/system/health` | `GET` | Health check |

### Example: Full Pipeline (`/process`)

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@form16.pdf"
```

**Response** (JSON):

```json
{
  "file_id": "abc123def456",
  "text": "extracted text...",
  "entities": [
    {"label": "PAN", "value": "AABCD1234E", "confidence": 0.98}
  ],
  "validation": {
    "status": "passed",
    "score": 92,
    "issues": []
  },
  "tax": {
    "regime": "old",
    "gross_income": 873898.0,
    "taxable_income": 604280.0,
    "total_tax": 95642.0,
    "tax": null,
    "refund_or_payable": -60952.0,
    "breakdown": [...]
  }
}
```

### Example: Generate PDF Report

```bash
curl -X POST http://localhost:8000/api/v1/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "entities": [{"label": "PAN", "value": "AABCD1234E", "confidence": 0.98}],
    "validation": {"status": "passed", "score": 92, "issues": []},
    "tax": {...}
  }' \
  -o report.pdf
```

---

## 📋 Configuration

### Environment Variables (`.env`)

```bash
# API
PROJECT_NAME="AI Tax Filing System"
API_V1_STR=/api/v1
DEBUG=false

# Database
DATABASE_URL=sqlite:///./data/taxbuddy.db
UPLOAD_DIR=data/uploads

# OCR
OCR_CONFIDENCE_THRESHOLD=0.70
OCR_DPI=200

# NER
NER_USE_TRANSFORMER=false
NER_TRANSFORMER_MODEL=xlm-roberta-base
NER_CONFIDENCE_THRESHOLD=0.60

# Tax
DEFAULT_TAX_REGIME=old
```

**Copy template:**

```bash
cd backend
cp .env.example .env
# Edit as needed
```

---

## ⚡ Performance

- **Full pipeline (PDF → JSON)**: < 5 seconds
- **OCR only**: ~3-4 seconds (first page)
- **NER only**: ~0.5 seconds
- **Tax computation**: < 100ms
- **PDF generation**: ~1 second

**Optimization strategies:**
- PaddleOCR processes first page only for speed
- Image preprocessing (denoise, contrast enhancement)
- Service singletons loaded once per worker
- Structured logging with minimal I/O

---

## 🧪 Testing

```bash
cd backend

# Run smoke tests
python -m pytest tests/test_pipeline.py -v

# Run with coverage
python -m pytest tests/ --cov=app --cov=ml
```

---

## 🔧 Troubleshooting

### Tesseract not found

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

**macOS:**
```bash
brew install tesseract
```

### PDF extraction fails

- Ensure `poppler-utils` is installed
- Check `OCR_DPI` setting (200 is default)
- Try increasing `OCR_CONFIDENCE_THRESHOLD`

### NER fields not extracted

- Check that document contains expected fields (PAN, TAN, Salary, etc.)
- Verify `NER_CONFIDENCE_THRESHOLD` is not too high
- Set `NER_USE_TRANSFORMER=true` for stricter matching (slower)

### Database errors

```bash
# Reset database
rm backend/data/taxbuddy.db*
# Restart backend (will recreate schema)
```

---

## 📦 Deployment

### Docker Production Build

```bash
# Build image
docker build -t tax-buddy:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/backend/data:/app/data \
  -v $(pwd)/backend/logs:/app/logs \
  -e DEBUG=false \
  tax-buddy:latest
```

### Environment for Production

```bash
# backend/.env
DEBUG=false
OCR_CONFIDENCE_THRESHOLD=0.80
NER_CONFIDENCE_THRESHOLD=0.70
```

---

## 🎯 Known Limitations

1. **OCR on first page only** — Multi-page PDFs process only the first page (for <5s response time)
2. **PAN/TAN required** — Validation requires both Form 16 PAN and Form 26AS TAN
3. **New regime only allows ₹50k deduction** — Standalone investment deductions not supported
4. **SQLite only** — Use PostgreSQL for production + concurrency

---

## 📝 License

[MIT License](LICENSE)

---

## 🤝 Contributing

1. Clone repo
2. Create feature branch
3. Make changes
4. Run tests: `pytest`
5. Submit PR

---

## 📧 Support

For issues, questions, or feature requests: [GitHub Issues](https://github.com/BackBenchDreamer/tax-buddy/issues)

---

**Built with ❤️ for Indian taxpayers**
