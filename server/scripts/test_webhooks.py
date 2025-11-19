#!/usr/bin/env python3
"""Test script for Webhook CRUD endpoints and webhook delivery."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx

# Default base URL - can be overridden via environment variable
BASE_URL = os.getenv("API_URL", "http://localhost:8000")
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


def test_list_webhooks(base_url: str) -> list[dict[str, Any]]:
    """Test GET /api/webhooks - List all webhooks."""
    print_section("1. List Webhooks (GET /api/webhooks)")
    
    url = f"{base_url}{API_PREFIX}/webhooks"
    
    with httpx.Client(timeout=30.0) as client:
        print("Test 1.1: List all webhooks")
        response = client.get(url)
        data = print_response(response, expected_status=200)
        
        if data:
            print(f"Found {len(data)} webhook(s)")
            return data
        return []


def test_create_webhook(base_url: str, webhook_url: str = "https://webhook.site/unique-id") -> dict[str, Any] | None:
    """Test POST /api/webhooks - Create a new webhook."""
    print_section("2. Create Webhook (POST /api/webhooks)")
    
    url = f"{base_url}{API_PREFIX}/webhooks"
    
    # Test 1: Create webhook with product events
    print("Test 2.1: Create webhook for product events")
    payload = {
        "url": webhook_url,
        "events": ["product.created", "product.updated", "product.deleted"],
        "enabled": True,
    }
    
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload)
        data = print_response(response, expected_status=201)
        
        if data:
            print(f"✓ Created webhook with ID: {data.get('id')}")
            return data
        
        # Test 2: Create webhook with import events
        print("\nTest 2.2: Create webhook for import events")
        payload2 = {
            "url": f"{webhook_url}-import",
            "events": ["import.completed", "import.failed"],
            "enabled": True,
        }
        
        response2 = client.post(url, json=payload2)
        data2 = print_response(response2, expected_status=201)
        
        if data2:
            print(f"✓ Created webhook with ID: {data2.get('id')}")
        
        return data


def test_get_webhook(base_url: str, webhook_id: int) -> dict[str, Any] | None:
    """Test GET /api/webhooks/{id} - Get webhook by ID."""
    print_section(f"3. Get Webhook (GET /api/webhooks/{webhook_id})")
    
    url = f"{base_url}{API_PREFIX}/webhooks/{webhook_id}"
    
    with httpx.Client(timeout=30.0) as client:
        print(f"Test 3.1: Get webhook {webhook_id}")
        response = client.get(url)
        data = print_response(response, expected_status=200)
        return data


def test_update_webhook(base_url: str, webhook_id: int) -> dict[str, Any] | None:
    """Test PUT /api/webhooks/{id} - Update webhook."""
    print_section(f"4. Update Webhook (PUT /api/webhooks/{webhook_id})")
    
    url = f"{base_url}{API_PREFIX}/webhooks/{webhook_id}"
    
    # Test 1: Update events list
    print("Test 4.1: Update webhook events")
    payload = {
        "events": ["product.created", "product.updated", "product.deleted", "product.bulk_deleted"],
    }
    
    with httpx.Client(timeout=30.0) as client:
        response = client.put(url, json=payload)
        data = print_response(response, expected_status=200)
        
        if data:
            print(f"✓ Updated webhook events: {data.get('events')}")
        
        # Test 2: Disable webhook
        print("\nTest 4.2: Disable webhook")
        payload2 = {"enabled": False}
        response2 = client.put(url, json=payload2)
        data2 = print_response(response2, expected_status=200)
        
        if data2:
            print(f"✓ Webhook enabled status: {data2.get('enabled')}")
        
        # Test 3: Re-enable webhook
        print("\nTest 4.3: Re-enable webhook")
        payload3 = {"enabled": True}
        response3 = client.put(url, json=payload3)
        data3 = print_response(response3, expected_status=200)
        
        if data3:
            print(f"✓ Webhook enabled status: {data3.get('enabled')}")
        
        return data3


def test_test_webhook(base_url: str, webhook_id: int) -> dict[str, Any] | None:
    """Test POST /api/webhooks/{id}/test - Test webhook synchronously."""
    print_section(f"5. Test Webhook (POST /api/webhooks/{webhook_id}/test)")
    
    url = f"{base_url}{API_PREFIX}/webhooks/{webhook_id}/test"
    
    with httpx.Client(timeout=30.0) as client:
        print(f"Test 5.1: Send test event to webhook {webhook_id}")
        print("   (This will make a synchronous HTTP POST to the webhook URL)")
        response = client.post(url)
        data = print_response(response, expected_status=200)
        
        if data:
            if data.get("success"):
                print(f"✓ Webhook test succeeded!")
                print(f"  Response code: {data.get('response_code')}")
                print(f"  Response time: {data.get('response_time_ms')}ms")
            else:
                print(f"✗ Webhook test failed")
                print(f"  Error: {data.get('error')}")
                print(f"  Response code: {data.get('response_code')}")
        
        return data


def test_get_deliveries(base_url: str, webhook_id: int) -> list[dict[str, Any]]:
    """Test GET /api/webhooks/{id}/deliveries - Get delivery history."""
    print_section(f"6. Get Delivery History (GET /api/webhooks/{webhook_id}/deliveries)")
    
    url = f"{base_url}{API_PREFIX}/webhooks/{webhook_id}/deliveries"
    
    with httpx.Client(timeout=30.0) as client:
        print(f"Test 6.1: Get delivery history for webhook {webhook_id}")
        response = client.get(url, params={"page": 1, "page_size": 10})
        data = print_response(response, expected_status=200)
        
        if data:
            print(f"Found {len(data)} delivery record(s)")
            if data:
                print("\nRecent deliveries:")
                for delivery in data[:5]:  # Show first 5
                    print(f"  - Event: {delivery.get('event_type')}, "
                          f"Status: {delivery.get('status')}, "
                          f"Code: {delivery.get('response_code')}, "
                          f"Time: {delivery.get('response_time_ms')}ms")
        
        return data or []


def test_delete_webhook(base_url: str, webhook_id: int) -> bool:
    """Test DELETE /api/webhooks/{id} - Delete webhook."""
    print_section(f"7. Delete Webhook (DELETE /api/webhooks/{webhook_id})")
    
    url = f"{base_url}{API_PREFIX}/webhooks/{webhook_id}"
    
    with httpx.Client(timeout=30.0) as client:
        print(f"Test 7.1: Delete webhook {webhook_id}")
        response = client.delete(url)
        
        if response.status_code == 204:
            print("✅ Webhook deleted successfully (204 No Content)")
            return True
        else:
            print_response(response, expected_status=204)
            return False


def test_webhook_validation(base_url: str) -> None:
    """Test webhook validation (invalid URLs, empty events, etc.)."""
    print_section("8. Webhook Validation Tests")
    
    url = f"{base_url}{API_PREFIX}/webhooks"
    
    with httpx.Client(timeout=30.0) as client:
        # Test 1: Invalid URL (not http/https)
        print("Test 8.1: Invalid URL (should fail)")
        payload = {
            "url": "ftp://example.com/webhook",
            "events": ["product.created"],
            "enabled": True,
        }
        response = client.post(url, json=payload)
        print_response(response, expected_status=422)
        
        # Test 2: Empty events list
        print("\nTest 8.2: Empty events list (should fail)")
        payload2 = {
            "url": "https://example.com/webhook",
            "events": [],
            "enabled": True,
        }
        response2 = client.post(url, json=payload2)
        print_response(response2, expected_status=422)
        
        # Test 3: Missing required fields
        print("\nTest 8.3: Missing required fields (should fail)")
        payload3 = {
            "url": "https://example.com/webhook",
            # Missing events
        }
        response3 = client.post(url, json=payload3)
        print_response(response3, expected_status=422)


def main() -> int:
    """Run all webhook endpoint tests."""
    print("=" * 60)
    print("  Webhook API Endpoint Tests")
    print("=" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API Prefix: {API_PREFIX}\n")
    
    # Check if server is running
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                print("⚠️  Server health check failed")
    except Exception as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Error: {e}")
        print("\n💡 Make sure the FastAPI server is running:")
        print("   cd server && uv run uvicorn app.main:app --reload")
        return 1
    
    print("✅ Server is running\n")
    
    # Get webhook URL from user or use default
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print("💡 Tip: Set WEBHOOK_URL environment variable to use a custom webhook receiver")
        print("   Example: export WEBHOOK_URL='https://webhook.site/your-unique-id'")
        print("   Or use: https://webhook.site to get a unique URL\n")
        webhook_url = "https://webhook.site/unique-id"
    
    created_webhook_id: int | None = None
    
    try:
        # Run tests
        test_list_webhooks(BASE_URL)
        
        webhook_data = test_create_webhook(BASE_URL, webhook_url)
        if webhook_data:
            created_webhook_id = webhook_data.get("id")
        
        if created_webhook_id:
            test_get_webhook(BASE_URL, created_webhook_id)
            test_update_webhook(BASE_URL, created_webhook_id)
            test_test_webhook(BASE_URL, created_webhook_id)
            
            # Wait a bit for async delivery to complete
            print("\n⏳ Waiting 3 seconds for async webhook delivery to complete...")
            time.sleep(3)
            
            test_get_deliveries(BASE_URL, created_webhook_id)
        
        test_webhook_validation(BASE_URL)
        
        # Cleanup: Delete created webhook (optional)
        if created_webhook_id:
            print("\n" + "=" * 60)
            try:
                response = input(f"\nDelete test webhook {created_webhook_id}? (y/N): ").strip().lower()
                if response == "y":
                    test_delete_webhook(BASE_URL, created_webhook_id)
                else:
                    print(f"✓ Keeping webhook {created_webhook_id} for inspection")
            except (EOFError, KeyboardInterrupt):
                # Non-interactive mode or interrupted
                print(f"✓ Keeping webhook {created_webhook_id} for inspection")
        
        print_section("Test Summary")
        print("✅ All webhook endpoint tests completed!")
        print("\n💡 Next steps:")
        print("   1. Check your webhook receiver URL to see if test events were received")
        print("   2. Try creating a product to trigger product.created webhook")
        print("   3. Check delivery history to see async webhook deliveries")
        
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

