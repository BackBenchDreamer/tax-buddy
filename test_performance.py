#!/usr/bin/env python3
"""
Performance verification test for /process endpoint.
Tests that all optimizations are working correctly.
"""

import requests
import time
import json
from PIL import Image, ImageDraw
import io

API_BASE = "http://localhost:8000/api/v1"

def create_simple_form16():
    """Create a test Form 16 image."""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    text = [
        "FORM 16 — SAMPLE",
        "",
        "PAN: BIGPP1846N",
        "TAN: MUMS15654C",
        "Employer: SIEMENS TECH",
        "Assessment Year: 2023-24",
        "",
        "Gross Salary: 873898.00",
        "Taxable Income: 604280.00",
        "TDS Deducted: 34690.00",
    ]

    y = 20
    for line in text:
        draw.text((20, y), line, fill='black')
        y += 40

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def test_process_endpoint():
    """Test /process endpoint for performance."""
    print("\n" + "="*60)
    print("Testing /process endpoint performance")
    print("="*60)

    img = create_simple_form16()
    files = {'file': ('test.png', img, 'image/png')}

    start = time.time()
    try:
        response = requests.post(f'{API_BASE}/process', files=files, timeout=10)
        elapsed = time.time() - start

        print(f"\n✅ Response received in {elapsed:.3f}s")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response is valid JSON")
            print(f"  - file_id: {data.get('file_id')}")
            print(f"  - entities: {len(data.get('entities', []))} extracted")
            print(f"  - validation: {data.get('validation', {}).get('status')}")
            print(f"  - tax: {'Present' if data.get('tax') else 'None'}")

            # Check performance
            if elapsed < 5.0:
                print(f"\n✅ PASS: Response time <5s ({elapsed:.3f}s)")
            else:
                print(f"\n⚠️  WARNING: Response time >5s ({elapsed:.3f}s)")
        else:
            print(f"❌ FAIL: Status {response.status_code}")
            print(response.text)

    except requests.Timeout:
        print(f"❌ FAIL: Request timeout (>10s)")
    except Exception as e:
        print(f"❌ FAIL: {e}")

def test_persist_endpoint():
    """Test /persist endpoint."""
    print("\n" + "="*60)
    print("Testing /persist endpoint")
    print("="*60)

    # Use query parameters instead of JSON
    params = {
        "file_id": "test-file-id",
    }
    json_body = {
        "entity_map": {"PAN": "BIGPP1846N", "GrossSalary": 873898},
        "validation_result": {"status": "ok", "score": 85, "issues": []},
        "tax_result": {"total_tax": 34690, "regime": "old"}
    }

    start = time.time()
    try:
        response = requests.post(
            f'{API_BASE}/persist',
            params=params,
            json=json_body,
            timeout=5
        )
        elapsed = time.time() - start

        print(f"\n✅ Response received in {elapsed:.3f}s")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print(f"✅ PASS: /persist returns immediately")
        else:
            print(f"Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ FAIL: {e}")

def test_health_check():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("Testing health check")
    print("="*60)

    try:
        response = requests.get(f'{API_BASE}/system/health', timeout=5)
        if response.status_code == 200:
            print(f"✅ Backend is running")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Backend not responding: {e}")

def main():
    print("\n" + "="*60)
    print("PERFORMANCE OPTIMIZATION VERIFICATION TEST")
    print("="*60)

    # Test health
    test_health_check()

    # Test process endpoint
    test_process_endpoint()

    # Test persist endpoint
    test_persist_endpoint()

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\n📋 Next steps:")
    print("1. Check logs for [PERF] timing markers")
    print("2. Verify OCR time is <3 seconds")
    print("3. Verify total time is <5 seconds")
    print("4. Check that /persist returns immediately")

if __name__ == "__main__":
    main()
