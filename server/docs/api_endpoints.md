# API Endpoints Documentation

## Upload Endpoint

### POST `/api/upload`

Upload a CSV file for asynchronous import processing.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: CSV file with field name `file`

**Required CSV Headers:**
- `sku` (required): Product SKU identifier
- `name` (required): Product name
- `description` (optional): Product description
- `active` (optional): Boolean (true/false, yes/no, 1/0)

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "sse_url": "/api/progress/550e8400-e29b-41d4-a716-446655440000",
  "message": "CSV upload accepted. Processing 1000 rows in background."
}
```

**Error Responses:**

400 Bad Request - Invalid file or validation errors:
```json
{
  "detail": {
    "message": "CSV validation failed",
    "errors": [
      "Missing required headers: name",
      "Row 5, field 'sku': Field required"
    ]
  }
}
```

413 Request Entity Too Large - File exceeds size limit:
```json
{
  "detail": "File size (600.00 MB) exceeds maximum allowed size (512 MB)"
}
```

500 Internal Server Error - Server error during processing:
```json
{
  "detail": "Failed to process upload: <error message>"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@products.csv" \
  -H "Accept: application/json"
```

**Example with Python:**
```python
import requests

with open('products.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/upload',
        files={'file': ('products.csv', f, 'text/csv')}
    )

if response.status_code == 202:
    data = response.json()
    job_id = data['job_id']
    sse_url = data['sse_url']
    print(f"Job created: {job_id}")
    print(f"Track progress at: {sse_url}")
else:
    print(f"Error: {response.json()}")
```

---

## Progress Endpoint (SSE)

### GET `/api/progress/{job_id}`

Stream real-time progress updates for an import job via Server-Sent Events.

**Request:**
- Method: `GET`
- Path Parameter: `job_id` (UUID)
- Headers: `Accept: text/event-stream` (optional but recommended)

**Response (200 OK):**
- Content-Type: `text/event-stream`
- Stream of SSE events with progress updates

**SSE Event Format:**
```
data: {"job_id": "...", "status": "importing", "stage": "batch_5", "processed_rows": 5000, "total_rows": 10000, "progress_percent": 50.0}

data: {"job_id": "...", "status": "done", "stage": "completed", "processed_rows": 10000, "total_rows": 10000, "progress_percent": 100.0}

data: {"event": "close", "job_id": "..."}
```

**Progress Status Values:**
- `queued`: Job is waiting to be processed
- `uploading`: File is being uploaded (rarely seen in SSE)
- `parsing`: CSV is being parsed
- `importing`: Data is being inserted into database
- `done`: Import completed successfully
- `failed`: Import failed with error

**Error Responses:**

404 Not Found - Job doesn't exist:
```json
{
  "detail": "Import job not found: 550e8400-e29b-41d4-a716-446655440000"
}
```

**Example with curl:**
```bash
# Stream progress updates
curl -N http://localhost:8000/api/progress/550e8400-e29b-41d4-a716-446655440000 \
  -H "Accept: text/event-stream"
```

**Example with Python:**
```python
import requests
import json

job_id = "550e8400-e29b-41d4-a716-446655440000"
url = f"http://localhost:8000/api/progress/{job_id}"

with requests.get(url, stream=True, headers={"Accept": "text/event-stream"}) as response:
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data:'):
                data_json = line.replace('data:', '').strip()
                try:
                    event = json.loads(data_json)
                    print(f"Status: {event.get('status')}, Progress: {event.get('progress_percent', 0):.1f}%")
                    
                    # Check if import is complete
                    if event.get('status') in ('done', 'failed'):
                        print(f"Import finished: {event.get('status')}")
                        break
                except json.JSONDecodeError:
                    pass
```

**Example with JavaScript (Browser):**
```javascript
const jobId = "550e8400-e29b-41d4-a716-446655440000";
const eventSource = new EventSource(`/api/progress/${jobId}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Status: ${data.status}, Progress: ${data.progress_percent}%`);
  
  // Update UI with progress
  if (data.progress_percent) {
    document.getElementById('progress-bar').style.width = `${data.progress_percent}%`;
  }
  
  // Close connection when done
  if (data.status === 'done' || data.status === 'failed') {
    eventSource.close();
    console.log('Import complete');
  }
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

---

## Complete Workflow Example

### 1. Upload CSV File
```bash
RESPONSE=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@products.csv" \
  -s)

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"
```

### 2. Monitor Progress
```bash
curl -N "http://localhost:8000/api/progress/$JOB_ID" \
  -H "Accept: text/event-stream"
```

### 3. Or monitor with Python
```python
import requests
import json
import time

# Step 1: Upload CSV
with open('products.csv', 'rb') as f:
    upload_response = requests.post(
        'http://localhost:8000/api/upload',
        files={'file': ('products.csv', f, 'text/csv')}
    )

if upload_response.status_code != 202:
    print(f"Upload failed: {upload_response.json()}")
    exit(1)

job_id = upload_response.json()['job_id']
print(f"Job created: {job_id}")

# Step 2: Stream progress
url = f"http://localhost:8000/api/progress/{job_id}"
print(f"Streaming progress from {url}...")

with requests.get(url, stream=True, headers={"Accept": "text/event-stream"}) as response:
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data:'):
                data_json = line.replace('data:', '').strip()
                try:
                    event = json.loads(data_json)
                    
                    # Skip close events
                    if event.get('event') == 'close':
                        continue
                    
                    status = event.get('status', 'unknown')
                    progress = event.get('progress_percent', 0)
                    processed = event.get('processed_rows', 0)
                    total = event.get('total_rows', 0)
                    
                    print(f"[{status.upper()}] {processed}/{total} rows ({progress:.1f}%)")
                    
                    # Handle completion
                    if status == 'done':
                        print("✓ Import completed successfully!")
                        break
                    elif status == 'failed':
                        error = event.get('error_message', 'Unknown error')
                        print(f"✗ Import failed: {error}")
                        break
                        
                except json.JSONDecodeError:
                    pass

print("Stream closed")
```

---

## Product CRUD Operations

### GET `/api/products`

List products with filtering and pagination.

**Request:**
- Method: `GET`
- Query Parameters:
  - `sku` (optional): Filter by SKU (partial match, case-insensitive)
  - `name` (optional): Filter by name (partial match, case-insensitive)
  - `description` (optional): Filter by description (partial match, case-insensitive)
  - `active` (optional): Filter by active status (true/false)
  - `page` (optional): Page number (default: 1, minimum: 1)
  - `page_size` (optional): Items per page (default: 20, minimum: 1, maximum: 100)

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "sku": "PROD-001",
      "name": "Example Product",
      "description": "Product description",
      "active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

**Example with curl:**
```bash
curl "http://localhost:8000/api/products?page=1&page_size=20&active=true" \
  -H "Accept: application/json"
```

**Example with Python:**
```python
import requests

response = requests.get(
    'http://localhost:8000/api/products',
    params={
        'sku': 'PROD',
        'active': True,
        'page': 1,
        'page_size': 20
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total']} products")
    for product in data['items']:
        print(f"{product['sku']}: {product['name']}")
```

---

### POST `/api/products`

Create a new product.

**Request:**
- Method: `POST`
- Content-Type: `application/json`
- Body:
```json
{
  "sku": "PROD-001",
  "name": "Example Product",
  "description": "Product description (optional)",
  "active": true
}
```

**Required Fields:**
- `sku` (required): Unique stock keeping unit identifier (1-255 characters)
- `name` (required): Display name for the product (1-255 characters)

**Optional Fields:**
- `description`: Optional marketing copy
- `active`: Indicates if the product is sellable (default: true)

**Response (201 Created):**
```json
{
  "id": 1,
  "sku": "PROD-001",
  "name": "Example Product",
  "description": "Product description",
  "active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses:**

409 Conflict - SKU already exists:
```json
{
  "detail": "Product with SKU 'PROD-001' already exists"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "sku": "PROD-001",
    "name": "Example Product",
    "description": "Product description",
    "active": true
  }'
```

---

### GET `/api/products/{product_id}`

Get a single product by its database ID.

**Request:**
- Method: `GET`
- Path Parameter: `product_id` (integer)

**Response (200 OK):**
```json
{
  "id": 1,
  "sku": "PROD-001",
  "name": "Example Product",
  "description": "Product description",
  "active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses:**

404 Not Found - Product doesn't exist:
```json
{
  "detail": "Product with ID 1 not found"
}
```

**Example with curl:**
```bash
curl http://localhost:8000/api/products/1 \
  -H "Accept: application/json"
```

---

### PUT `/api/products/{product_id}`

Update a product by ID. All fields are optional - only provided fields will be updated.

**Request:**
- Method: `PUT`
- Path Parameter: `product_id` (integer)
- Content-Type: `application/json`
- Body (all fields optional):
```json
{
  "sku": "PROD-001-UPDATED",
  "name": "Updated Product Name",
  "description": "Updated description",
  "active": false
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "sku": "PROD-001-UPDATED",
  "name": "Updated Product Name",
  "description": "Updated description",
  "active": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

**Error Responses:**

404 Not Found - Product doesn't exist:
```json
{
  "detail": "Product with ID 1 not found"
}
```

409 Conflict - SKU already exists:
```json
{
  "detail": "SKU already exists (case-insensitive)"
}
```

**Example with curl:**
```bash
curl -X PUT http://localhost:8000/api/products/1 \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "name": "Updated Product Name",
    "active": false
  }'
```

---

### DELETE `/api/products/{product_id}`

Delete a product by ID.

**Request:**
- Method: `DELETE`
- Path Parameter: `product_id` (integer)

**Response (204 No Content):**
- Empty response body

**Error Responses:**

404 Not Found - Product doesn't exist:
```json
{
  "detail": "Product with ID 1 not found"
}
```

**Example with curl:**
```bash
curl -X DELETE http://localhost:8000/api/products/1 \
  -H "Accept: application/json"
```

---

## Bulk Delete

### POST `/api/products/bulk-delete`

Initiates an asynchronous bulk deletion of all products in the database. Returns immediately with job_id and SSE URL for progress tracking. Products are deleted in batches to ensure efficient processing.

**Request:**
- Method: `POST`

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "sse_url": "/api/progress/550e8400-e29b-41d4-a716-446655440000",
  "message": "Bulk delete operation initiated. All products will be deleted in the background."
}
```

**Progress Tracking:**
- Use the returned `sse_url` to monitor progress via Server-Sent Events (same format as import progress)
- Progress stages: `preparing → deleting → done/failed`
- Progress updates include `processed_rows` (deleted count) and `total_rows` (total products)

**Error Responses:**

500 Internal Server Error - Server error during processing:
```json
{
  "detail": "Failed to initiate bulk delete: <error message>"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/products/bulk-delete \
  -H "Accept: application/json"
```

**Example with Python:**
```python
import requests
import json

# Step 1: Initiate bulk delete
response = requests.post('http://localhost:8000/api/products/bulk-delete')

if response.status_code == 202:
    data = response.json()
    job_id = data['job_id']
    sse_url = data['sse_url']
    print(f"Bulk delete job created: {job_id}")
    print(f"Track progress at: {sse_url}")
    
    # Step 2: Monitor progress (same as import progress)
    progress_url = f"http://localhost:8000{sse_url}"
    with requests.get(progress_url, stream=True, headers={"Accept": "text/event-stream"}) as stream:
        for line in stream.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    event = json.loads(line.replace('data:', '').strip())
                    if event.get('event') == 'close':
                        continue
                    print(f"Status: {event.get('status')}, Deleted: {event.get('processed_rows')}/{event.get('total_rows')}")
                    if event.get('status') in ('done', 'failed'):
                        break
else:
    print(f"Error: {response.json()}")
```

---

## Webhook Configuration

### GET `/api/webhooks`

List all configured webhooks.

**Request:**
- Method: `GET`

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "url": "https://example.com/webhook",
    "events": ["product.created", "product.updated"],
    "enabled": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

**Example with curl:**
```bash
curl http://localhost:8000/api/webhooks \
  -H "Accept: application/json"
```

---

### POST `/api/webhooks`

Create a new webhook configuration.

**Request:**
- Method: `POST`
- Content-Type: `application/json`
- Body:
```json
{
  "url": "https://example.com/webhook",
  "events": ["product.created", "product.updated", "product.deleted"],
  "enabled": true
}
```

**Required Fields:**
- `url` (required): Webhook URL to receive POST requests (must start with http:// or https://)
- `events` (required): List of event types to subscribe to (non-empty list)

**Optional Fields:**
- `enabled`: Whether the webhook is active (default: true)

**Supported Event Types:**
- `product.created`: Fired when a product is created
- `product.updated`: Fired when a product is updated
- `product.deleted`: Fired when a product is deleted
- `product.bulk_deleted`: Fired when bulk delete operation completes
- `import.completed`: Fired when CSV import completes
- `import.failed`: Fired when CSV import fails

**Response (201 Created):**
```json
{
  "id": 1,
  "url": "https://example.com/webhook",
  "events": ["product.created", "product.updated", "product.deleted"],
  "enabled": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses:**

400 Bad Request - Invalid URL or empty events:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "url"],
      "msg": "URL must start with http:// or https://"
    }
  ]
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "url": "https://example.com/webhook",
    "events": ["product.created", "product.updated"],
    "enabled": true
  }'
```

---

### GET `/api/webhooks/{webhook_id}`

Get a single webhook by its database ID.

**Request:**
- Method: `GET`
- Path Parameter: `webhook_id` (integer)

**Response (200 OK):**
```json
{
  "id": 1,
  "url": "https://example.com/webhook",
  "events": ["product.created", "product.updated"],
  "enabled": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses:**

404 Not Found - Webhook doesn't exist:
```json
{
  "detail": "Webhook with ID 1 not found"
}
```

**Example with curl:**
```bash
curl http://localhost:8000/api/webhooks/1 \
  -H "Accept: application/json"
```

---

### PUT `/api/webhooks/{webhook_id}`

Update a webhook by ID. All fields are optional - only provided fields will be updated.

**Request:**
- Method: `PUT`
- Path Parameter: `webhook_id` (integer)
- Content-Type: `application/json`
- Body (all fields optional):
```json
{
  "url": "https://new-url.com/webhook",
  "events": ["product.created"],
  "enabled": false
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "url": "https://new-url.com/webhook",
  "events": ["product.created"],
  "enabled": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

**Error Responses:**

404 Not Found - Webhook doesn't exist:
```json
{
  "detail": "Webhook with ID 1 not found"
}
```

**Example with curl:**
```bash
curl -X PUT http://localhost:8000/api/webhooks/1 \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "enabled": false
  }'
```

---

### DELETE `/api/webhooks/{webhook_id}`

Delete a webhook by ID.

**Request:**
- Method: `DELETE`
- Path Parameter: `webhook_id` (integer)

**Response (204 No Content):**
- Empty response body

**Error Responses:**

404 Not Found - Webhook doesn't exist:
```json
{
  "detail": "Webhook with ID 1 not found"
}
```

**Example with curl:**
```bash
curl -X DELETE http://localhost:8000/api/webhooks/1 \
  -H "Accept: application/json"
```

---

### POST `/api/webhooks/{webhook_id}/test`

Send a test event to the webhook URL synchronously. Returns the response code, response time, and response body (truncated to 1000 characters).

**Request:**
- Method: `POST`
- Path Parameter: `webhook_id` (integer)

**Response (200 OK):**
```json
{
  "success": true,
  "response_code": 200,
  "response_time_ms": 45,
  "response_body": "OK",
  "error": null
}
```

**Error Responses:**

404 Not Found - Webhook doesn't exist:
```json
{
  "detail": "Webhook with ID 1 not found"
}
```

**Example Response (Timeout):**
```json
{
  "success": false,
  "response_code": null,
  "response_time_ms": 10000,
  "response_body": "Webhook request timed out after 10s",
  "error": "Webhook request timed out after 10s"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/webhooks/1/test \
  -H "Accept: application/json"
```

---

### GET `/api/webhooks/{webhook_id}/deliveries`

Get delivery history for a webhook with pagination.

**Request:**
- Method: `GET`
- Path Parameter: `webhook_id` (integer)
- Query Parameters:
  - `page` (optional): Page number (default: 1, minimum: 1)
  - `page_size` (optional): Items per page (default: 50, minimum: 1, maximum: 100)

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "webhook_id": 1,
    "event_type": "product.created",
    "status": "success",
    "response_code": 200,
    "response_time_ms": 45,
    "attempted_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:00:00.045Z"
  },
  {
    "id": 2,
    "webhook_id": 1,
    "event_type": "product.updated",
    "status": "failed",
    "response_code": 500,
    "response_time_ms": 120,
    "attempted_at": "2024-01-01T01:00:00Z",
    "completed_at": "2024-01-01T01:00:00.120Z"
  }
]
```

**Delivery Status Values:**
- `pending`: Delivery is queued but not yet attempted
- `success`: Delivery succeeded (HTTP 2xx response)
- `failed`: Delivery failed (non-2xx response or timeout/error)

**Error Responses:**

404 Not Found - Webhook doesn't exist:
```json
{
  "detail": "Webhook with ID 1 not found"
}
```

**Example with curl:**
```bash
curl "http://localhost:8000/api/webhooks/1/deliveries?page=1&page_size=50" \
  -H "Accept: application/json"
```

---

## Health Check

### GET `/health`

Simple health endpoint for load balancers and monitoring.

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

## Error Handling

All endpoints follow standard HTTP status codes:

- **200 OK**: Request successful (GET endpoints)
- **202 Accepted**: Request accepted for async processing (POST /upload)
- **400 Bad Request**: Invalid request or validation errors
- **404 Not Found**: Resource not found
- **413 Request Entity Too Large**: File size exceeds limit
- **500 Internal Server Error**: Unexpected server error

Error responses include a `detail` field with human-readable error messages.

---

## Rate Limiting & Performance

- **Max file size**: 512 MB (configurable via `MAX_UPLOAD_SIZE_MB`)
- **Concurrent imports**: Supports 10+ concurrent imports
- **SSE connection timeout**: Connections remain open until job completes or client disconnects
- **Heartbeat**: SSE streams send heartbeat comments every few seconds to keep connection alive

---

## CORS Configuration

The API is configured to accept requests from any origin (`allow_origins=["*"]`). 
For production, update the CORS configuration in `app/main.py` to restrict origins.

---

## Webhook Event Payloads

When webhooks are triggered, they receive POST requests with the following payload formats:

### Product Events

**product.created / product.updated / product.deleted:**
```json
{
  "event": "product.created",
  "data": {
    "id": 1,
    "sku": "PROD-001",
    "name": "Example Product",
    "description": "Product description",
    "active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

**product.bulk_deleted:**
```json
{
  "event": "product.bulk_deleted",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "done",
    "deleted_count": 5000,
    "total_products": 5000
  }
}
```

### Import Events

**import.completed / import.failed:**
```json
{
  "event": "import.completed",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "done",
    "processed_rows": 10000,
    "total_rows": 10000
  }
}
```

---

## Next Steps

- Add structured logging with job_id correlation
- Configure Dead Letter Queue for failed tasks
- Add monitoring endpoints for Celery worker health
- Implement webhook retry mechanism with exponential backoff

