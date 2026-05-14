#!/usr/bin/env python3
"""
Comprehensive validation script for tax-buddy application.
Tests imports, initialization, and core functionality after type fixes.
"""

import sys
import traceback
from typing import Dict, List, Tuple

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class ValidationResults:
    def __init__(self):
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []
        self.warnings: List[str] = []
    
    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"{GREEN}✓{RESET} {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"{RED}✗{RESET} {test_name}")
        print(f"  {RED}Error: {error}{RESET}")
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        print(f"{YELLOW}⚠{RESET} {message}")
    
    def print_summary(self):
        print(f"\n{BLUE}{'='*70}{RESET}")
        print(f"{BLUE}VALIDATION SUMMARY{RESET}")
        print(f"{BLUE}{'='*70}{RESET}")
        print(f"{GREEN}Passed:{RESET} {len(self.passed)}")
        print(f"{RED}Failed:{RESET} {len(self.failed)}")
        print(f"{YELLOW}Warnings:{RESET} {len(self.warnings)}")
        
        if self.failed:
            print(f"\n{RED}Failed Tests:{RESET}")
            for test_name, error in self.failed:
                print(f"  - {test_name}")
                print(f"    {error}")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print(f"\n{BLUE}{'='*70}{RESET}")
        
        if not self.failed:
            print(f"{GREEN}All validation checks passed!{RESET}")
            return 0
        else:
            print(f"{RED}Some validation checks failed.{RESET}")
            return 1

results = ValidationResults()

def test_import(module_name: str, test_name: str):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        results.add_pass(test_name)
        return True
    except Exception as e:
        results.add_fail(test_name, str(e))
        return False

def test_core_imports():
    """Test core module imports."""
    print(f"\n{BLUE}Testing Core Imports...{RESET}")
    
    test_import("app.core.config", "Import app.core.config")
    test_import("app.core.database", "Import app.core.database")
    test_import("app.core.logging_config", "Import app.core.logging_config")

def test_schema_imports():
    """Test schema imports."""
    print(f"\n{BLUE}Testing Schema Imports...{RESET}")
    
    test_import("app.schemas.schemas", "Import app.schemas.schemas")

def test_service_imports():
    """Test service imports."""
    print(f"\n{BLUE}Testing Service Imports...{RESET}")
    
    test_import("app.services.tax_service", "Import tax_service")
    test_import("app.services.itr_service", "Import itr_service")
    test_import("app.services.groq_service", "Import groq_service")
    test_import("app.services.ai_validation_service", "Import ai_validation_service")
    test_import("app.services.tax_optimization_service", "Import tax_optimization_service")
    test_import("app.services.validation_service", "Import validation_service")

def test_ml_imports():
    """Test ML module imports."""
    print(f"\n{BLUE}Testing ML Module Imports...{RESET}")
    
    test_import("ml.ocr.ocr_service", "Import OCR service")
    test_import("ml.ocr.preprocess", "Import OCR preprocessing")
    test_import("ml.ner.ner_service", "Import NER service")
    test_import("ml.ner.regex_utils", "Import regex_utils")
    test_import("ml.ner.regex_utils_26as", "Import regex_utils_26as")

def test_api_imports():
    """Test API module imports."""
    print(f"\n{BLUE}Testing API Imports...{RESET}")
    
    test_import("app.api.routes", "Import API routes")
    test_import("app.api.router", "Import API router")

def test_fastapi_app():
    """Test FastAPI app initialization."""
    print(f"\n{BLUE}Testing FastAPI App Initialization...{RESET}")
    
    try:
        from app.main import app
        results.add_pass("FastAPI app initialization")
        
        # Check if app has routes
        if hasattr(app, 'routes') and len(app.routes) > 0:
            results.add_pass(f"FastAPI app has {len(app.routes)} routes registered")
        else:
            results.add_warning("FastAPI app has no routes registered")
        
        return True
    except Exception as e:
        results.add_fail("FastAPI app initialization", str(e))
        traceback.print_exc()
        return False

def test_ocr_service():
    """Test OCR service functionality."""
    print(f"\n{BLUE}Testing OCR Service...{RESET}")
    
    try:
        from ml.ocr.ocr_service import OCRService
        
        # Try to instantiate
        ocr_service = OCRService()
        results.add_pass("OCR service instantiation")
        
        # Check if methods exist (check actual method names from the class)
        if hasattr(ocr_service, 'extract'):
            results.add_pass("OCR service has extract method")
        else:
            results.add_warning("OCR service missing extract method")
        
        if hasattr(ocr_service, 'paddle_ocr'):
            if ocr_service.paddle_ocr is not None:
                results.add_pass("OCR service has PaddleOCR configured")
            else:
                results.add_warning("OCR service using Tesseract fallback (PaddleOCR unavailable)")
        
        return True
    except Exception as e:
        results.add_fail("OCR service instantiation", str(e))
        return False

def test_tax_service():
    """Test tax service functionality."""
    print(f"\n{BLUE}Testing Tax Service...{RESET}")
    
    try:
        from app.services.tax_service import compute_tax, compute_old_regime, compute_new_regime
        
        results.add_pass("Tax service functions import")
        
        # Check if key functions are callable
        if callable(compute_tax):
            results.add_pass("compute_tax function is callable")
        if callable(compute_old_regime):
            results.add_pass("compute_old_regime function is callable")
        if callable(compute_new_regime):
            results.add_pass("compute_new_regime function is callable")
        
        return True
    except Exception as e:
        results.add_fail("Tax service functions import", str(e))
        return False
def test_ai_validation_service():
    """Test AI validation service functionality."""
    print(f"\n{BLUE}Testing AI Validation Service...{RESET}")
    
    try:
        from app.services.ai_validation_service import (
            validate_extracted_fields,
            validate_employee_name,
            validate_pan,
            apply_corrections
        )
        
        results.add_pass("AI validation service functions import")
        
        # Check if key functions are callable
        if callable(validate_extracted_fields):
            results.add_pass("validate_extracted_fields function is callable")
        if callable(validate_employee_name):
            results.add_pass("validate_employee_name function is callable")
        if callable(validate_pan):
            results.add_pass("validate_pan function is callable")
        
        return True
    except Exception as e:
        results.add_fail("AI validation service functions import", str(e))
        return False


def test_groq_service():
    """Test Groq service functionality."""
    print(f"\n{BLUE}Testing Groq Service...{RESET}")
    
    try:
        from app.services.groq_service import (
            set_user_api_key,
            get_user_api_key,
            clear_user_api_key
        )
        
        results.add_pass("Groq service functions import")
        
        # Check if key functions are callable
        if callable(set_user_api_key):
            results.add_pass("set_user_api_key function is callable")
        if callable(get_user_api_key):
            results.add_pass("get_user_api_key function is callable")
        
        return True
    except Exception as e:
        results.add_fail("Groq service functions import", str(e))
        return False


def test_schemas():
    """Test schema definitions."""
    print(f"\n{BLUE}Testing Schema Definitions...{RESET}")
    
    try:
        from app.schemas.schemas import (
            TaxRequest,
            TaxResponse,
            AIValidationRequest,
            AIValidationResponse,
            ValidationResponse
        )
        
        results.add_pass("Import core schemas")
        
        # Test schema instantiation
        try:
            # Test with minimal valid data
            data = TaxRequest(
                data={"income": 500000},
                regime="new"
            )
            results.add_pass("TaxRequest schema instantiation")
        except Exception as e:
            results.add_fail("TaxRequest schema instantiation", str(e))
        
        return True
    except Exception as e:
        results.add_fail("Schema imports", str(e))
        return False
def test_config():
    """Test configuration loading."""
    print(f"\n{BLUE}Testing Configuration...{RESET}")
    
    try:
        from app.core.config import settings
        
        results.add_pass("Configuration loading")
        
        # Check critical settings
        if hasattr(settings, 'GROQ_API_KEY'):
            if settings.GROQ_API_KEY:
                results.add_pass("GROQ_API_KEY is configured")
            else:
                results.add_warning("GROQ_API_KEY is not set (AI features may not work)")
        
        if hasattr(settings, 'TESSERACT_CMD'):
            results.add_pass("TESSERACT_CMD is configured")
        else:
            results.add_warning("TESSERACT_CMD not configured")
        
        return True
    except Exception as e:
        results.add_fail("Configuration loading", str(e))
        return False

def main():
    """Run all validation tests."""
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}TAX-BUDDY APPLICATION VALIDATION{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    # Run all tests
    test_config()
    test_core_imports()
    test_schema_imports()
    test_service_imports()
    test_ml_imports()
    test_api_imports()
    test_fastapi_app()
    test_schemas()
    test_ocr_service()
    test_tax_service()
    test_ai_validation_service()
    test_groq_service()
    
    # Print summary
    return results.print_summary()

if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
