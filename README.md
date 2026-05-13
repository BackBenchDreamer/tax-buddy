# 🧾 Tax Buddy — AI-Powered Tax Filing Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Podman](https://img.shields.io/badge/Podman-Compatible-892CA0.svg)](https://podman.io/)

## 🔄 CI/CD Status

![CI Pipeline](https://github.com/USERNAME/tax-buddy/actions/workflows/ci.yml/badge.svg)
![Security Scan](https://github.com/USERNAME/tax-buddy/actions/workflows/security.yml/badge.svg)
![Code Quality](https://github.com/USERNAME/tax-buddy/actions/workflows/quality.yml/badge.svg)
![Release](https://github.com/USERNAME/tax-buddy/actions/workflows/release.yml/badge.svg)

> **Note:** Replace `USERNAME` with your GitHub username to activate badges.

> **OCR · NER · Validation · Tax Engine · ITR Generation · AI Assistance**
> Production-grade hybrid AI workflow for automated Indian income tax filing

Tax Buddy is an end-to-end system that processes Form 16 and Form 26AS documents, validates data across both forms, computes income tax under both Old and New regimes, and generates ITR forms (ITR-1/ITR-4) — all in under 5 seconds.

**Status:** ✅ Production-ready | Fully tested | Clean, reproducible setup

---

## ✨ Features

| Layer | What it does | Tech |
|-------|-------------|------|
| **OCR** | Multi-page PDF extraction via direct text → PaddleOCR → Tesseract | PaddleOCR, pytesseract, pdfplumber |
| **NER** | Section-aware field extraction from Form 16 & Form 26AS | Custom regex + XLM-RoBERTa (optional) |
| **Validation** | Cross-document validation with trust score (0-100) | 6 rules, penalty-based scoring |
| **Tax Engine** | Indian slab-based calculator — Old & New regime (AY 2024-25) | Full breakdown by bracket |
| **ITR Generation** | Auto-select and generate ITR-1 (Sahaj) or ITR-4 (Sugam) | JSON + PDF + prefill text |
| **AI Assistance** | Groq-powered field resolution, explanations, recommendations | llama3-70b-8192 / mixtral-8x7b-32768 |
| **PDF Export** | Download formatted tax summary report | reportlab |
| **Dashboard** | Interactive React UI for file upload & results | Next.js, Recharts, Tailwind |

---

## 🏗️ Architecture

### 6-Phase Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Document   │ →  │     OCR     │ →  │     NER     │
│  Acquisition│    │  Extraction │    │  Extraction │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     ITR     │ ←  │     Tax     │ ←  │ Validation  │
│  Generation │    │ Computation │    │   Engine    │
└─────────────┘    └─────────────┘    └─────────────┘
```

**See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.**

### OCR Priority Order (Strict)

```
1. Direct PDF Text Extraction (pdfplumber/PyMuPDF)
   ↓ (if no clean text)
2. PaddleOCR (primary OCR engine)
   ↓ (if fails or low confidence)
3. Tesseract OCR (fallback only)
```

### Groq AI Integration Points

1. **Ambiguous OCR field resolution** — when extracted text doesn't match expected patterns
2. **NER fallback** — when rule-based extraction fails
3. **Validation mismatch explanations** — user-friendly explanations of discrepancies
4. **Tax regime recommendations** — AI-powered advice on which regime is better

---

## 🚀 Quick Start

### Prerequisites

| Component | Requirement | Install |
|-----------|-------------|---------|
| **Python** | 3.11+ | [python.org](https://www.python.org) |
| **Node.js** | 18+ | [nodejs.org](https://www.nodejs.org) |
| **Tesseract** | 5.x+ | macOS: `brew install tesseract` / Linux: `apt-get install tesseract-ocr` |
| **Poppler** | latest | macOS: `brew install poppler` / Linux: `apt-get install poppler-utils` |

### Option A: Docker/Podman (Recommended)

#### Using Docker Compose

```bash
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Set Groq API key (optional, for AI features)
export GROQ_API_KEY=your_key_here

# Start both backend and frontend
docker-compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

#### Using Podman Compose

```bash
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Set Groq API key (optional, for AI features)
export GROQ_API_KEY=your_key_here

# Start both backend and frontend
podman-compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

**Clean rebuild with Podman:**
```bash
# Use the provided script for a complete clean rebuild
chmod +x rebuild-podman.sh
./rebuild-podman.sh
```

### Option B: Local Development

#### 1. Backend Setup

```bash
cd tax-buddy/backend

# Create virtual environment (REQUIRED)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  (Windows)

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set GROQ_API_KEY if using AI features

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
| `/extract` | `POST` | OCR + NER on Form 16 |
| `/extract-26as` | `POST` | OCR + NER on Form 26AS |
| `/validate` | `POST` | Cross-validate Form 16 vs Form 26AS |
| `/compute-tax` | `POST` | Calculate income tax (both regimes) |
| `/generate-itr` | `POST` | Generate ITR-1 or ITR-4 (JSON + PDF + text) |
| `/process` | `POST` | **RECOMMENDED** — Full pipeline in one request |
| `/generate-report` | `POST` | Generate downloadable PDF report |
| `/system/health` | `GET` | Health check |

### Example: Full Pipeline

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
    {"label": "PAN", "value": "AABCD1234E", "confidence": 0.98},
    {"label": "GrossSalary", "value": "873898.0", "confidence": 0.92}
  ],
  "validation": {
    "status": "ok",
    "score": 92,
    "issues": []
  },
  "tax": {
    "regime": "old",
    "gross_income": 873898.0,
    "taxable_income": 604280.0,
    "total_tax": 32090.24,
    "refund_or_payable": 2599.76,
    "breakdown": [...]
  }
}
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

# Groq API (for AI assistance)
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama3-70b-8192
GROQ_TIMEOUT=30
```

**Copy template:**

```bash
cd backend
cp .env.example .env
# Edit .env with your values
```

---

## ⚡ Performance

- **Full pipeline (PDF → JSON)**: < 5 seconds
- **OCR only**: ~3-4 seconds (first page)
- **NER only**: ~0.5 seconds
- **Tax computation**: < 100ms
- **PDF generation**: ~1 second

**Optimization strategies:**
- Direct PDF text extraction (when available)
- PaddleOCR processes first page only for speed
- Image preprocessing (denoise, contrast enhancement)
- Service singletons loaded once per worker
- Async Groq API calls with timeouts

---

## 🧪 Testing

```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Run tests
python -m pytest tests/test_pipeline.py -v

# Run with coverage
python -m pytest tests/ --cov=app --cov=ml
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
  -e GROQ_API_KEY=your_key_here \
  tax-buddy:latest
```

### Environment for Production

```bash
# backend/.env
DEBUG=false
OCR_CONFIDENCE_THRESHOLD=0.80
NER_CONFIDENCE_THRESHOLD=0.70
GROQ_API_KEY=your_production_key
```

---

## 🎯 Tax Computation Details

### Old Regime (AY 2024-25)

- **Slabs:** 0-2.5L (0%), 2.5-5L (5%), 5-10L (20%), 10L+ (30%)
- **Standard Deduction:** ₹50,000
- **Deductions:** 80C (₹1.5L), 80D, 80TTA, 80TTB
- **Rebate u/s 87A:** Taxable ≤ ₹5L → rebate up to ₹12,500
- **Cess:** 4%

### New Regime (AY 2024-25, Budget 2024)

- **Slabs:** 0-3L (0%), 3-7L (5%), 7-10L (10%), 10-12L (15%), 12-15L (20%), 15L+ (30%)
- **Standard Deduction:** ₹75,000 (Budget 2024)
- **No other deductions** (80C, 80D not allowed)
- **Rebate u/s 87A:** Taxable ≤ ₹7L → rebate up to ₹25,000
- **Cess:** 4%

**Both regimes are computed and compared side-by-side.**

---

## 📄 ITR Form Generation

### Supported Forms

- **ITR-1 (Sahaj):** For salaried individuals with income ≤ ₹50 lakhs
- **ITR-4 (Sugam):** For individuals/HUFs with presumptive income u/s 44AD, 44ADA, 44AE

### Auto-Selection Logic

```python
if total_income <= 50L and salary_only:
    return "ITR-1"
elif total_income <= 50L and presumptive_income:
    return "ITR-4"
else:
    return "ITR-2" or "ITR-3"
```

### Output Formats

1. **JSON:** Structured data matching ITR schema (for portal upload)
2. **PDF:** Human-readable tax summary report
3. **Plain Text:** Pre-fill reference for manual portal entry

---

## 🤖 AI Features (Groq Integration)

### 1. Ambiguous OCR Resolution

When OCR returns unclear text, Groq resolves it:

```
OCR: "Gr0ss S@lary: 8?3,898"
Groq: "873898"
```

### 2. NER Fallback

When regex fails to extract an entity, Groq steps in:

```
Text: "...employed by SIEMENS TECHNOLOGY..."
Groq: {"value": "SIEMENS TECHNOLOGY AND SERVICES PRIVATE LIMITED", "confidence": 0.92}
```

### 3. Validation Explanations

User-friendly explanations of validation issues:

```
Issue: TDS_MISMATCH
Groq: "Your employer reported ₹34,690 in TDS on Form 16, but Form 26AS shows ₹34,000. 
       This difference of ₹690 may be due to timing of TDS deposit. Verify with your employer."
```

### 4. Tax Regime Recommendation

AI-powered advice on which regime is better:

```
Groq: "The Old Regime saves you ₹7,310 because your deductions (₹1.75L under 80C and 80D) 
       exceed the additional standard deduction (₹25K) offered by the New Regime."
```

**Note:** All AI features are optional and gracefully degrade if Groq API is unavailable.

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

### PaddleOCR not working

- On ARM64 macOS, PaddleOCR may not have a wheel
- System will automatically fall back to Tesseract
- Check logs for "[OCR] PaddleOCR unavailable" message

### Groq API errors

- Verify `GROQ_API_KEY` is set correctly
- Check API quota/rate limits
- System will continue without AI features if Groq fails

### Database errors

```bash
# Reset database
rm backend/data/taxbuddy.db*
# Restart backend (will recreate schema)
```

---

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Detailed system design, pipeline phases, data flows
- **[API Docs](http://localhost:8000/docs)** — Interactive Swagger UI (when backend is running)
- **Inline Code Comments** — All modules are extensively documented

---

## 🎯 Known Limitations

1. **OCR on first page only** — Multi-page PDFs process only the first page (for <5s response time)
2. **Form 26AS optional** — Validation requires both forms, but system works with Form 16 alone
3. **ITR-1 and ITR-4 only** — ITR-2, ITR-3 support planned for future
4. **SQLite only** — Use PostgreSQL for production + concurrency
5. **Groq API required for AI features** — Falls back gracefully if unavailable

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Code style and standards
- Development setup
- Testing requirements
- Pull request process
- Issue reporting

**Quick Start for Contributors:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and add tests
4. Run tests: `cd backend && pytest tests/ -v`
5. Commit with clear messages: `git commit -m "feat: add new feature"`
6. Push and create a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for complete details.

---

## 📧 Support

For issues, questions, or feature requests: [GitHub Issues](https://github.com/BackBenchDreamer/tax-buddy/issues)

---

## 📝 License

[MIT License](LICENSE)

---

**Built with ❤️ for Indian taxpayers**

**Version:** 1.0.0  
**Last Updated:** 2026-05-12
