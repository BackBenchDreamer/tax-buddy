# Contributing to Tax Buddy

Thank you for your interest in contributing to Tax Buddy! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Project Structure](#project-structure)

---

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain professional communication

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.11 or higher
- Node.js 18 or higher
- Git
- Tesseract OCR
- Poppler utilities
- Docker or Podman (optional, for containerized development)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/tax-buddy.git
   cd tax-buddy
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/BackBenchDreamer/tax-buddy.git
   ```

---

## Development Setup

### Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  (Windows)

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Run backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Using Docker/Podman

```bash
# Docker
docker-compose up --build

# Podman
podman-compose up --build

# Clean rebuild with Podman
./rebuild-podman.sh
```

---

## Code Style

### Python (Backend)

- **Style Guide:** PEP 8
- **Line Length:** 100 characters maximum
- **Imports:** Group by standard library, third-party, local (separated by blank lines)
- **Type Hints:** Use type hints for function signatures
- **Docstrings:** Use Google-style docstrings

**Example:**

```python
from typing import Optional, List
import logging

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import settings


def process_document(
    file_path: str,
    confidence_threshold: float = 0.7
) -> dict:
    """
    Process a tax document using OCR and NER.
    
    Args:
        file_path: Path to the document file
        confidence_threshold: Minimum confidence score for extraction
        
    Returns:
        Dictionary containing extracted entities and metadata
        
    Raises:
        HTTPException: If file processing fails
    """
    # Implementation
    pass
```

### TypeScript/React (Frontend)

- **Style Guide:** Airbnb JavaScript Style Guide
- **Components:** Use functional components with hooks
- **Naming:** PascalCase for components, camelCase for functions/variables
- **Props:** Define explicit TypeScript interfaces

**Example:**

```typescript
interface FileUploadProps {
  onUpload: (file: File) => Promise<void>;
  maxSize?: number;
  acceptedTypes?: string[];
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onUpload,
  maxSize = 10 * 1024 * 1024,
  acceptedTypes = ['application/pdf', 'image/*']
}) => {
  // Implementation
};
```

### General Guidelines

- Write clear, self-documenting code
- Add comments for complex logic
- Keep functions small and focused (single responsibility)
- Use meaningful variable and function names
- Avoid magic numbers (use named constants)

---

## Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_pipeline.py -v

# Run with coverage
python -m pytest tests/ --cov=app --cov=ml --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Requirements

- **Unit Tests:** All new functions must have unit tests
- **Integration Tests:** API endpoints must have integration tests
- **Coverage:** Aim for >80% code coverage
- **Test Data:** Use fixtures for test data (see `tests/fixtures/`)

### Writing Tests

```python
import pytest
from app.services.tax_service import TaxService


@pytest.fixture
def tax_service():
    """Fixture for TaxService instance."""
    return TaxService()


def test_compute_old_regime_tax(tax_service):
    """Test old regime tax computation."""
    result = tax_service.compute_tax(
        gross_income=873898.0,
        deductions={"80C": 150000, "80D": 25000},
        regime="old"
    )
    
    assert result["total_tax"] > 0
    assert result["taxable_income"] < result["gross_income"]
    assert "breakdown" in result
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

---

## Pull Request Process

### Before Submitting

1. **Update from upstream:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes:**
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation if needed

4. **Run tests:**
   ```bash
   # Backend
   cd backend && pytest tests/ -v
   
   # Frontend
   cd frontend && npm test
   ```

5. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Use conventional commit messages:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Test additions/changes
   - `refactor:` Code refactoring
   - `style:` Code style changes
   - `chore:` Maintenance tasks

### Submitting the PR

1. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request on GitHub:**
   - Provide a clear title and description
   - Reference any related issues
   - Include screenshots for UI changes
   - List any breaking changes

3. **PR Template:**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Tests pass locally
   - [ ] Added new tests
   - [ ] Updated documentation
   
   ## Related Issues
   Fixes #123
   
   ## Screenshots (if applicable)
   ```

### Review Process

- Maintainers will review your PR
- Address any requested changes
- Once approved, your PR will be merged
- Delete your feature branch after merge

---

## Issue Reporting

### Bug Reports

Use the bug report template and include:

- **Description:** Clear description of the bug
- **Steps to Reproduce:** Detailed steps to reproduce the issue
- **Expected Behavior:** What should happen
- **Actual Behavior:** What actually happens
- **Environment:**
  - OS and version
  - Python version
  - Node.js version
  - Browser (for frontend issues)
- **Logs:** Relevant error messages or logs
- **Screenshots:** If applicable

### Feature Requests

Use the feature request template and include:

- **Problem:** What problem does this solve?
- **Proposed Solution:** How should it work?
- **Alternatives:** Other solutions considered
- **Additional Context:** Any other relevant information

### Questions

For questions:
- Check existing documentation first
- Search existing issues
- Use GitHub Discussions for general questions
- Use Issues for specific technical questions

---

## Project Structure

### Backend (`/backend`)

```
backend/
├── app/
│   ├── api/          # API routes and endpoints
│   ├── core/         # Core configuration and utilities
│   ├── models/       # Database models
│   ├── schemas/      # Pydantic schemas
│   └── services/     # Business logic services
├── ml/
│   ├── ocr/          # OCR services (PaddleOCR, Tesseract)
│   └── ner/          # NER services (regex, transformers)
├── tests/            # Test files
├── data/             # Data storage (uploads, database)
└── requirements.txt  # Python dependencies
```

### Frontend (`/frontend`)

```
frontend/
├── app/              # Next.js app directory
│   ├── page.tsx      # Main page
│   ├── layout.tsx    # Root layout
│   └── globals.css   # Global styles
├── components/       # React components
├── types/            # TypeScript type definitions
└── public/           # Static assets
```

### Key Files

- `README.md` - Main project documentation
- `ARCHITECTURE.md` - System architecture details
- `DEPLOYMENT.md` - Deployment instructions
- `docker-compose.yml` - Docker/Podman configuration
- `rebuild-podman.sh` - Podman rebuild script

---

## Development Tips

### Debugging

**Backend:**
```python
# Add logging
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")

# Use debugger
import pdb; pdb.set_trace()
```

**Frontend:**
```typescript
// Console logging
console.log('Debug:', data);
console.error('Error:', error);

// React DevTools
// Install React Developer Tools browser extension
```

### Common Issues

**PaddleOCR not working on ARM64 macOS:**
- System automatically falls back to Tesseract
- Check logs for "[OCR] PaddleOCR unavailable"

**Database errors:**
```bash
# Reset database
rm backend/data/taxbuddy.db*
# Restart backend (will recreate schema)
```

**Port conflicts:**
```bash
# Check what's using port 8000
lsof -i :8000
# Kill process
kill -9 <PID>
```

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PaddleOCR Documentation](https://github.com/PaddlePaddle/PaddleOCR)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [React Documentation](https://react.dev/)

---

## Questions?

- **Documentation:** Check [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
- **Issues:** [GitHub Issues](https://github.com/BackBenchDreamer/tax-buddy/issues)
- **Discussions:** [GitHub Discussions](https://github.com/BackBenchDreamer/tax-buddy/discussions)

---

**Thank you for contributing to Tax Buddy! 🎉**