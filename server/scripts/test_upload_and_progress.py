#!/usr/bin/env python3
"""
Test script to verify upload and progress endpoints.

This script uploads a sample CSV file and monitors progress via SSE.

Usage:
    python scripts/test_upload_and_progress.py [csv_file]

If no CSV file is provided, it will create a sample file.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


def create_sample_csv(path: Path, num_rows: int = 100) -> None:
    """Create a sample CSV file for testing."""
    print(f"Creating sample CSV with {num_rows} rows at {path}")
    
    with open(path, "w") as f:
        f.write("sku,name,description,active\n")
        for i in range(1, num_rows + 1):
            f.write(f"TEST-{i:05d},Test Product {i},Description for product {i},true\n")
    
    print(f"✓ Sample CSV created: {path}")


def upload_csv(api_url: str, csv_path: Path) -> dict | None:
    """Upload CSV file to the import API."""
    print(f"\n📤 Uploading CSV: {csv_path}")
    print(f"   API URL: {api_url}/api/upload")
    
    try:
        with open(csv_path, "rb") as f:
            response = requests.post(
                f"{api_url}/api/upload",
                files={"file": (csv_path.name, f, "text/csv")},
                timeout=30,
            )
        
        if response.status_code == 202:
            data = response.json()
            print(f"✓ Upload accepted")
            print(f"  Job ID: {data['job_id']}")
            print(f"  SSE URL: {data['sse_url']}")
            print(f"  Message: {data['message']}")
            return data
        else:
            print(f"✗ Upload failed with status {response.status_code}")
            print(f"  Error: {response.json()}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Connection error: Unable to connect to {api_url}")
        print("  Make sure the FastAPI server is running.")
        return None
    except Exception as e:
        print(f"✗ Upload error: {e}")
        return None


def monitor_progress(api_url: str, job_id: str) -> None:
    """Monitor import progress via SSE stream."""
    print(f"\n📊 Monitoring progress for job: {job_id}")
    print(f"   SSE URL: {api_url}/api/progress/{job_id}")
    print("   (Press Ctrl+C to stop)\n")
    
    progress_url = f"{api_url}/api/progress/{job_id}"
    
    try:
        with requests.get(
            progress_url,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=300,  # 5 minute timeout
        ) as response:
            
            if response.status_code != 200:
                print(f"✗ Error: {response.json()}")
                return
            
            # Process SSE stream
            for line in response.iter_lines():
                if not line:
                    continue
                
                line = line.decode("utf-8")
                
                # Skip comments (heartbeats)
                if line.startswith(":"):
                    continue
                
                # Parse data events
                if line.startswith("data:"):
                    data_json = line.replace("data:", "").strip()
                    
                    try:
                        event = json.loads(data_json)
                        
                        # Skip internal close events
                        if event.get("event") == "close":
                            continue
                        
                        # Extract progress info
                        status = event.get("status", "unknown")
                        stage = event.get("stage", "")
                        progress = event.get("progress_percent", 0)
                        processed = event.get("processed_rows", 0)
                        total = event.get("total_rows", 0)
                        error_msg = event.get("error_message")
                        
                        # Format status with emoji
                        status_emoji = {
                            "queued": "⏳",
                            "uploading": "📤",
                            "parsing": "📖",
                            "importing": "⚙️",
                            "done": "✅",
                            "failed": "❌",
                        }.get(status.lower(), "❓")
                        
                        # Print progress update
                        if total > 0:
                            progress_bar = create_progress_bar(progress, width=30)
                            print(
                                f"{status_emoji} [{status.upper():10s}] "
                                f"{progress_bar} {progress:5.1f}% "
                                f"({processed:,}/{total:,} rows)"
                            )
                        else:
                            print(f"{status_emoji} [{status.upper():10s}] {stage}")
                        
                        # Check for completion
                        if status.lower() == "done":
                            print(f"\n✓ Import completed successfully!")
                            print(f"  Total rows imported: {processed:,}")
                            break
                        elif status.lower() == "failed":
                            print(f"\n✗ Import failed!")
                            if error_msg:
                                print(f"  Error: {error_msg}")
                            break
                    
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        pass
            
            print("\n📡 SSE stream closed")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring interrupted by user")
        print("   (The import job continues running in the background)")
    except requests.exceptions.Timeout:
        print("\n✗ Connection timeout")
    except Exception as e:
        print(f"\n✗ Error monitoring progress: {e}")


def create_progress_bar(percent: float, width: int = 30) -> str:
    """Create a text-based progress bar."""
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test CSV upload and progress monitoring endpoints"
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        help="Path to CSV file to upload (creates sample if not provided)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1000,
        help="Number of rows in sample CSV (default: 1000)",
    )
    parser.add_argument(
        "--skip-progress",
        action="store_true",
        help="Skip progress monitoring after upload",
    )
    
    args = parser.parse_args()
    
    # Determine CSV file path
    if args.csv_file:
        csv_path = Path(args.csv_file)
        if not csv_path.exists():
            print(f"✗ Error: File not found: {csv_path}")
            sys.exit(1)
    else:
        # Create temporary sample CSV
        temp_dir = Path(tempfile.gettempdir())
        csv_path = temp_dir / "sample_products.csv"
        create_sample_csv(csv_path, num_rows=args.rows)
    
    # Upload CSV
    result = upload_csv(args.api_url, csv_path)
    
    if not result:
        sys.exit(1)
    
    job_id = result["job_id"]
    
    # Monitor progress (unless skipped)
    if not args.skip_progress:
        monitor_progress(args.api_url, job_id)
    else:
        print(f"\n⏭️  Skipping progress monitoring")
        print(f"   Monitor manually at: {args.api_url}/api/progress/{job_id}")


if __name__ == "__main__":
    main()

