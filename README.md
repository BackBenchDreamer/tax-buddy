# Tax Buddy — AI-Powered Tax Filing Assistant

[![CI Pipeline](https://github.com/BackBenchDreamer/tax-buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/BackBenchDreamer/tax-buddy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)

## Overview

Production-ready AI tax assistant that automates Indian income tax filing by processing Form 16 and Form 26AS documents. Combines OCR, NER, and LLM-powered validation to compute taxes under both Old and New regimes, generating ITR-1/ITR-4 forms in under 5 seconds. Built with enterprise-grade testing (36/36 tests passing) and hardened CI/CD pipelines.

## Key Features

- **Intelligent OCR Pipeline** — Multi-stage extraction (direct PDF text → PaddleOCR → Tesseract fallback)
- **Named Entity Recognition** — Section-aware field extraction from tax documents using custom regex patterns
- **AI-Powered Validation** — Cross-document verification with trust scoring and LLM-based discrepancy resolution
- **Dual Tax Computation** — Automatic calculation under both Old and New regimes (AY 2024-25) with regime comparison
- **ITR Generation** — Auto-selects and generates ITR-1 (Sahaj) or ITR-4 (Sugam) in JSON, PDF, and text formats
- **Smart Recommendations** — Groq LLM provides tax-saving insights and regime optimization advice
- **Interactive Dashboard** — Modern Next.js UI with real-time processing visualization

## Tech Stack

**Backend**
- FastAPI 0.136.1, Python 3.11+, Pydantic v2
- Groq AI (llama-3.3-70b-versatile), spaCy NER
- PaddleOCR, Tesseract OCR, pdfplumber
- SQLite/PostgreSQL, pytest (36 tests)

**Frontend**
- Next.js 15, TypeScript, React 19
- Tailwind CSS, Recharts, shadcn/ui

**ML/AI**
- PaddleOCR (primary OCR engine)
- Custom regex-based NER for Indian tax forms
- Groq LLM for validation and recommendations

**Infrastructure**
- Docker & Podman ready
- GitHub Actions CI/CD
- Ruff, Black, isort (code quality)

## Architecture

High-level processing flow: **Upload → OCR → NER → Validation → Tax Computation → ITR Generation**

The system uses a 6-phase pipeline with intelligent fallbacks at each stage. OCR prioritizes direct PDF text extraction, falling back to PaddleOCR, then Tesseract. NER uses section-aware regex patterns with optional transformer models. AI validation provides trust scoring (0-100) and human-readable explanations for discrepancies.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design and data flows.

## Quick Setup

### Prerequisites
- Python 3.11+, Node.js 20+
- Tesseract OCR: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Linux)
- Poppler: `brew install poppler` (macOS) or `apt-get install poppler-utils` (Linux)

### Docker (Recommended)

```bash
git clone https://github.com/BackBenchDreamer/tax-buddy.git
cd tax-buddy

# Set API key (optional, for AI features)
export GROQ_API_KEY=your_key_here

# Start services
docker-compose up --build

# Access:
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Local Development

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Configure GROQ_API_KEY
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GROQ_API_KEY` | Groq AI API key for LLM features | No* | - |
| `DATABASE_URL` | Database connection string | Yes | `sqlite:///./data/taxbuddy.db` |
| `UPLOAD_DIR` | File upload directory | Yes | `data/uploads` |
| `OCR_CONFIDENCE_THRESHOLD` | Minimum OCR confidence score | No | `0.70` |
| `NER_CONFIDENCE_THRESHOLD` | Minimum NER confidence score | No | `0.60` |
| `DEFAULT_TAX_REGIME` | Default tax regime (old/new) | No | `old` |
| `GROQ_MODEL` | Groq model identifier | No | `llama-3.3-70b-versatile` |
| `DEBUG` | Enable debug mode | No | `false` |

*System works without Groq API key but AI features will be disabled.

## API Overview

**Interactive Documentation:** http://localhost:8000/docs

**Key Endpoints:**
- `POST /api/v1/process` — Full pipeline (upload → ITR generation)
- `POST /api/v1/extract` — OCR + NER on Form 16
- `POST /api/v1/validate` — Cross-validate Form 16 vs Form 26AS
- `POST /api/v1/compute-tax` — Calculate tax under both regimes
- `POST /api/v1/generate-itr` — Generate ITR-1 or ITR-4
- `GET /api/v1/system/health` — Health check

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@form16.pdf"
```

## Project Structure

```
tax-buddy/
├── backend/              # FastAPI application
│   ├── app/             # API routes, services, schemas
│   ├── ml/              # OCR and NER modules
│   ├── tests/           # 36 passing tests
│   └── requirements.txt
├── frontend/            # Next.js application
│   ├── app/            # Pages and layouts
│   ├── components/     # React components
│   └── types/          # TypeScript definitions
├── .github/            # CI/CD workflows
│   └── workflows/      # GitHub Actions
├── docs/               # Additional documentation
├── ARCHITECTURE.md     # System design details
├── CONTRIBUTING.md     # Contribution guidelines
└── docker-compose.yml  # Multi-container setup
```

## Development

**Run Tests:**
```bash
cd backend
source venv/bin/activate
pytest tests/ -v --cov=app --cov=ml
```

**Linting & Formatting:**
```bash
cd backend
ruff check .
black .
isort .
```

**Docker Development:**
```bash
docker-compose up --build
docker-compose down -v  # Clean rebuild
```

## Deployment

Docker Compose ready for production deployment. Configure environment variables for production settings (disable debug, increase confidence thresholds, set production API keys).

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions and best practices.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on code style, testing requirements, and pull request process.

## License

MIT License — see [LICENSE](LICENSE) file for details.

---

**Built by [Jeyadheep V](https://github.com/BackBenchDreamer)** | Production-ready AI tax assistant for Indian taxpayers
