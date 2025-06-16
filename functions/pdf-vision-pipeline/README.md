# PDF Vision Pipeline

High-performance PDF processing pipeline using Google Cloud Vision API with parallel processing and R2 storage.

## Overview

This function processes PDFs by:
1. Converting PDFs to 150 DPI JPEG images
2. Processing pages in parallel using Vision API
3. Extracting technical patterns (PT1, M1, E1, etc.)
4. Uploading images and JSON to R2 storage
5. Returning search-optimized aggregated results

## API Parameters

- **pdfUrl** (required): URL of the PDF to process
- **projectID** (optional): Project identifier for organization
- **fileID** (optional): File identifier for organization  
- **webhook** (optional): URL to send completion notification
- **chunkSize** (optional, default 5): Number of pages per worker chunk (1-15)
- **bucket** (optional, default 'ladders-1'): R2 bucket for storage

## Example Request

```json
{
  "pdfUrl": "https://example.com/document.pdf",
  "projectID": "my-project",
  "fileID": "doc-123",
  "chunkSize": 3,
  "bucket": "my-bucket"
}
```

## Performance

- **50 pages**: 15-25 seconds
- **95%+ pattern accuracy** (Vision API)
- **15 parallel workers** with configurable chunk sizes
- **Individual page retry** logic

## Storage Structure

```
bucket/
├── projects/{projectID}/
│   └── files/{fileID}/
│       ├── images/
│       │   ├── page-001.jpg
│       │   └── ...
│       └── json/
│           ├── page-001.json
│           ├── final-results.json
│           └── ...
```

## Setup Requirements

✅ **R2 credentials in Secret Manager** - Using existing secrets:
- `projects/ladders-doc-pipeline-462921/secrets/r2-access-key`
- `projects/ladders-doc-pipeline-462921/secrets/r2-secret-key`  
- `projects/ladders-doc-pipeline-462921/secrets/r2-endpoint`

✅ **Vision API enabled** - Already enabled in project

✅ **R2 configuration** - Using same setup as existing pdf-processor

### Test Connection
Run `python test_r2_connection.py` to verify R2 access

## Deployment

```bash
gcloud functions deploy pdf-vision-pipeline \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=3600 \
  --memory=8GB \
  --max-instances=10
``` 