#!/usr/bin/env python3
"""Test script for Product CRUD endpoints (excluding delete operations)."""
from __future__ import annotations

import json
import sys
from typing import Any

import httpx

# Default base URL - can be overridden via environment variable
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api"


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_response(response: httpx.Response, expected_status: int | None = None) -> dict[str, Any] | None:
    """Print formatted response information."""
    status_emoji = "✅" if response.status_code < 400 else "❌"
    status_text = httpx.codes.get_reason_phrase(response.status_code) or "Unknown"
    print(f"{status_emoji} Status: {response.status_code} {status_text}")
    
    if expected_status and response.status_code != expected_status:
        print(f"⚠️  Expected status {expected_status}, got {response.status_code}")
    
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return data
    except Exception:
        print(f"Response text: {response.text[:500]}")
        return None


def test_list_products(base_url: str) -> None:
    """Test GET /api/products - List products."""
    print_section("1. List Products (GET /api/products)")
    
    url = f"{base_url}{API_PREFIX}/products"
    
    with httpx.Client(timeout=30.0) as client:
        # Test 1: List all products (default pagination)
        print("Test 1.1: List all products (default)")
        response = client.get(url)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Found {data.get('total', 0)} total products, {len(data.get('items', []))} in this page")
        
        # Test 2: List with pagination
        print("\nTest 1.2: List with pagination (page=1, page_size=5)")
        response = client.get(url, params={"page": 1, "page_size": 5})
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Page: {data.get('page')}, Page Size: {data.get('page_size')}")
        
        # Test 3: Filter by active status
        print("\nTest 1.3: Filter by active=True")
        response = client.get(url, params={"active": True})
        data = print_response(response, expected_status=200)
        if data:
            active_count = sum(1 for item in data.get('items', []) if item.get('active'))
            print(f"   Found {active_count} active products")
        
        # Test 4: Filter by SKU (partial match)
        print("\nTest 1.4: Filter by SKU (partial match)")
        response = client.get(url, params={"sku": "test"})
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Found {data.get('total', 0)} products matching SKU filter")
        
        # Test 5: Filter by name (partial match)
        print("\nTest 1.5: Filter by name (partial match)")
        response = client.get(url, params={"name": "product"})
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Found {data.get('total', 0)} products matching name filter")


def test_create_product(base_url: str) -> int | None:
    """Test POST /api/products - Create product."""
    print_section("2. Create Product (POST /api/products)")
    
    url = f"{base_url}{API_PREFIX}/products"
    
    with httpx.Client(timeout=30.0) as client:
        # Test 1: Create a new product
        print("Test 2.1: Create a new product")
        product_data = {
            "sku": f"TEST-SKU-{hash(str(sys.argv)) % 10000}",
            "name": "Test Product",
            "description": "This is a test product created by the test script",
            "active": True,
        }
        print(f"   Creating product: {product_data['sku']}")
        response = client.post(url, json=product_data)
        data = print_response(response, expected_status=201)
        
        created_sku = product_data["sku"]
        product_id = None
        if data and "id" in data:
            product_id = data["id"]
            print(f"   ✅ Created product with ID: {product_id}")
        
        # Test 2: Try to create duplicate SKU (should fail)
        print("\nTest 2.2: Attempt to create duplicate SKU (should fail)")
        if created_sku:
            duplicate_data = {
                "sku": created_sku,  # Use same SKU
                "name": "Duplicate Product",
                "active": True,
            }
            response = client.post(url, json=duplicate_data)
            print_response(response, expected_status=409)
        
        # Test 3: Create product with minimal fields
        print("\nTest 2.3: Create product with minimal fields")
        minimal_data = {
            "sku": f"MIN-SKU-{hash(str(sys.argv)) % 10000}",
            "name": "Minimal Product",
        }
        response = client.post(url, json=minimal_data)
        minimal_data_response = print_response(response, expected_status=201)
        
        if not product_id and minimal_data_response and "id" in minimal_data_response:
            product_id = minimal_data_response["id"]
        
        return product_id


def test_get_product(base_url: str, product_id: int) -> None:
    """Test GET /api/products/{id} - Get product by ID."""
    print_section("3. Get Product by ID (GET /api/products/{id})")
    
    url = f"{base_url}{API_PREFIX}/products/{product_id}"
    
    with httpx.Client(timeout=30.0) as client:
        # Test 1: Get existing product
        print(f"Test 3.1: Get product with ID {product_id}")
        response = client.get(url)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Product: {data.get('name')} (SKU: {data.get('sku')})")
        
        # Test 2: Get non-existent product (should fail)
        print("\nTest 3.2: Get non-existent product (should return 404)")
        fake_id = 999999
        response = client.get(f"{base_url}{API_PREFIX}/products/{fake_id}")
        print_response(response, expected_status=404)


def test_update_product(base_url: str, product_id: int) -> None:
    """Test PUT /api/products/{id} - Update product."""
    print_section("4. Update Product (PUT /api/products/{id})")
    
    url = f"{base_url}{API_PREFIX}/products/{product_id}"
    
    with httpx.Client(timeout=30.0) as client:
        # Test 1: Update product name
        print(f"Test 4.1: Update product name")
        update_data = {
            "name": "Updated Test Product Name",
        }
        response = client.put(url, json=update_data)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Updated name to: {data.get('name')}")
        
        # Test 2: Update multiple fields
        print("\nTest 4.2: Update multiple fields")
        update_data = {
            "name": "Fully Updated Product",
            "description": "This product has been fully updated",
            "active": False,
        }
        response = client.put(url, json=update_data)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Updated: name={data.get('name')}, active={data.get('active')}")
        
        # Test 3: Update SKU
        print("\nTest 4.3: Update SKU")
        update_data = {
            "sku": f"UPDATED-SKU-{product_id}",
        }
        response = client.put(url, json=update_data)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Updated SKU to: {data.get('sku')}")
        
        # Test 4: Update non-existent product (should fail)
        print("\nTest 4.4: Update non-existent product (should return 404)")
        fake_id = 999999
        response = client.put(
            f"{base_url}{API_PREFIX}/products/{fake_id}",
            json={"name": "Should Fail"},
        )
        print_response(response, expected_status=404)
        
        # Test 5: Partial update (only description)
        print("\nTest 4.5: Partial update (only description)")
        update_data = {
            "description": "Only description was updated",
        }
        response = client.put(url, json=update_data)
        data = print_response(response, expected_status=200)
        if data:
            print(f"   Description: {data.get('description')}")


def main() -> None:
    """Run all product CRUD tests (excluding delete)."""
    import os
    
    base_url = os.getenv("API_BASE_URL", BASE_URL)
    
    print("=" * 60)
    print("  Product CRUD Endpoint Tests")
    print("  (Excluding Delete Operations)")
    print("=" * 60)
    print(f"\nBase URL: {base_url}")
    print(f"API Prefix: {API_PREFIX}")
    
    # Check if server is running
    try:
        health_url = f"{base_url}/health"
        with httpx.Client(timeout=5.0) as client:
            response = client.get(health_url)
            if response.status_code != 200:
                print(f"\n❌ Server health check failed: {response.status_code}")
                sys.exit(1)
            print("✅ Server is running")
    except httpx.RequestError as e:
        print(f"\n❌ Cannot connect to server at {base_url}")
        print(f"   Error: {e}")
        print("\n   Make sure the FastAPI server is running:")
        print("   cd server && uv run uvicorn app.main:app --reload")
        sys.exit(1)
    
    # Run tests
    try:
        # 1. List products
        test_list_products(base_url)
        
        # 2. Create product
        product_id = test_create_product(base_url)
        
        if not product_id:
            print("\n⚠️  Could not create a product for testing. Some tests will be skipped.")
            return
        
        # 3. Get product
        test_get_product(base_url, product_id)
        
        # 4. Update product
        test_update_product(base_url, product_id)
        
        print_section("Test Summary")
        print("✅ All CRUD tests completed (excluding delete operations)")
        print(f"\n   Test product ID: {product_id}")
        print(f"   You can manually verify the product at: {base_url}{API_PREFIX}/products/{product_id}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

