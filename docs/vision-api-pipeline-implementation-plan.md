# Vision API PDF Processing Pipeline - Implementation Plan

## Overview
Complete pipeline to process up to 50-page PDFs using Google Cloud Vision API with parallel processing, R2 storage, and search-optimized JSON output.

## Architecture Summary

```
PDF URL → pdf-vision-pipeline (Cloud Function) →
├── Download & Split PDF (pdf2image @ 150 DPI)
├── Parallel Processing (15 ThreadPoolExecutor workers)
│   ├── Page 1-15: Image → Vision API → Pattern Extraction → R2 Upload
│   ├── Page 16-30: Image → Vision API → Pattern Extraction → R2 Upload  
│   └── Page 31-50: Image → Vision API → Pattern Extraction → R2 Upload
├── Aggregate Results (search-optimized JSON)
├── Upload Final JSON to R2
└── Return Response (image URLs + final JSON URL)
```

## Performance Targets
- **Processing Time**: 15-25 seconds for 50 pages
- **Accuracy**: 95%+ pattern detection (proven with Vision API)
- **Reliability**: Individual page retry logic, job continues on page failures
- **Scalability**: Handles 1-50 pages efficiently

## Phase 1: Core Infrastructure Setup

### 1.1 Project Structure
```
functions/
├── pdf-vision-pipeline/
│   ├── main.py              # Main orchestration function
│   ├── pdf_processor.py     # PDF splitting and image conversion
│   ├── vision_processor.py  # Vision API integration
│   ├── pattern_extractor.py # Pattern analysis and extraction
│   ├── storage_handler.py   # R2 upload and URL management
│   ├── result_aggregator.py # JSON compilation and optimization
│   ├── requirements.txt     # Dependencies
│   └── config.py           # Configuration constants
├── tests/
│   ├── test_pdf_processor.py
│   ├── test_vision_processor.py
│   └── test_integration.py
└── docs/
    ├── api_documentation.md
    └── deployment_guide.md
```

### 1.2 Dependencies (requirements.txt)
```
functions-framework==3.5.0
google-cloud-vision==3.4.4
google-cloud-secret-manager==2.17.0
pdf2image==1.17.0
Pillow==10.1.0
boto3==1.34.0
requests==2.31.0
concurrent.futures
```

### 1.3 Configuration (config.py)
```python
import os

# Processing Configuration
MAX_PAGES = 50
PARALLEL_WORKERS = 15
DEFAULT_CHUNK_SIZE = 5  # Pages per worker chunk
IMAGE_DPI = 150
IMAGE_FORMAT = 'JPEG'
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Vision API Configuration
VISION_TIMEOUT = 30  # seconds

# Storage Configuration  
DEFAULT_R2_BUCKET = 'ladders-1'
R2_BASE_URL = 'https://pub-592c678931664039950f4a0846d0d9d1.r2.dev'
```

## Phase 2: API Interface & Configuration

### 2.1 API Parameters
The function accepts these parameters:
- **pdfUrl** (required): URL of the PDF to process
- **projectID** (optional): Project identifier for organization
- **fileID** (optional): File identifier for organization  
- **webhook** (optional): URL to send completion notification
- **chunkSize** (optional, default 5): Number of pages per worker chunk (min 1, max 15)
- **bucket** (optional, default 'ladders-1'): R2 bucket for storage

### 2.2 R2 Storage Structure
```
bucket/
├── projects/{projectID}/
│   └── files/{fileID}/
│       ├── images/
│       │   ├── page-001.jpg
│       │   ├── page-002.jpg
│       │   └── ...
│       └── json/
│           ├── page-001.json
│           ├── page-002.json
│           └── final-results.json
```

### 2.3 Search-Optimized JSON Structure
```json
{
  "project_id": "project-123",
  "file_id": "file-456",
  "processing_metadata": {
    "total_pages": 50,
    "processed_pages": 49,
    "failed_pages": [{"page": 23, "error": "vision_api_timeout"}],
    "processing_time_seconds": 18.5
  },
  "pages": [
    {
      "page_number": 1,
      "image_url": "https://r2-cdn.../projects/project-123/files/file-456/images/page-001.jpg",
      "patterns": [
        {
          "pattern_id": "pt1_page1_001",
          "pattern_type": "PT1", 
          "text": "PT1",
          "page_number": 1,
          "coordinates": {"x": 464, "y": 2853, "width": 30, "height": 13},
          "confidence": 0.95
        }
      ],
      "pattern_count": {"PT1": 8, "PT2": 22}
    }
  ],
  "aggregated_patterns": {
    "PT1": {"total_count": 156, "pages": [1, 2, 5, 8...]},
    "PT2": {"total_count": 89, "pages": [1, 3, 4, 7...]}
  },
  "search_index": {
    "unique_patterns": ["PT1", "PT2", "PT3"],
    "pages_with_patterns": [1, 2, 3, 5, 8, 10, 12...]
  }
}
```

## Phase 3: Core Components Implementation

### 3.1 Main Orchestration Function (main.py)
```python
@functions_framework.http
def pdf_vision_pipeline(request):
    """Main pipeline orchestrator"""
    try:
        # 1. Validate input
        request_data = validate_request(request)
        pdf_url = request_data['pdfUrl']  # Required
        project_id = request_data.get('projectID', 'default')
        file_id = request_data.get('fileID', generate_file_id())
        webhook = request_data.get('webhook')
        chunk_size = request_data.get('chunkSize', DEFAULT_CHUNK_SIZE)
        bucket = request_data.get('bucket', DEFAULT_R2_BUCKET)
        
        # 2. Download and split PDF
        page_images = pdf_processor.split_pdf_to_images(pdf_url)
        
        if len(page_images) > MAX_PAGES:
            return {"error": f"PDF exceeds {MAX_PAGES} page limit"}, 400
            
        # 3. Process pages in parallel chunks
        page_results = process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size)
        
        # 4. Aggregate results
        final_result = result_aggregator.compile_final_json(page_results, project_id, file_id)
        
        # 5. Upload final JSON
        final_json_url = storage_handler.upload_final_json(final_result, project_id, file_id, bucket)
        
        # 6. Send webhook if provided
        if webhook:
            send_webhook_notification(webhook, final_result)
        
        # 7. Return response
        return {
            "success": True,
            "project_id": project_id,
            "file_id": file_id,
            "total_pages": len(page_images),
            "processed_pages": len([r for r in page_results if r['success']]),
            "failed_pages": [r['page'] for r in page_results if not r['success']],
            "final_json_url": final_json_url,
            "image_urls": [r['image_url'] for r in page_results if r['success']],
            "processing_time_seconds": final_result['processing_metadata']['processing_time_seconds']
        }
        
    except Exception as e:
        return {"error": str(e)}, 500

def process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size):
    """Process pages using ThreadPoolExecutor with chunking"""
    results = []
    
    # Create chunks of pages for each worker
    page_chunks = [page_images[i:i + chunk_size] for i in range(0, len(page_images), chunk_size)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        # Submit chunk processing tasks
        future_to_chunk = {
            executor.submit(process_page_chunk, chunk, chunk_idx * chunk_size + 1, project_id, file_id, bucket): chunk_idx
            for chunk_idx, chunk in enumerate(page_chunks)
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_idx = future_to_chunk[future]
            try:
                chunk_results = future.result()
                results.extend(chunk_results)
            except Exception as e:
                # If chunk fails, create error results for all pages in chunk
                start_page = chunk_idx * chunk_size + 1
                for i in range(len(page_chunks[chunk_idx])):
                    results.append({
                        "page": start_page + i,
                        "success": False,
                        "error": str(e)
                    })
    
    return sorted(results, key=lambda x: x.get('page', 0))
```

### 3.2 PDF Processing (pdf_processor.py)
```python
from pdf2image import convert_from_bytes
import requests
import io

def split_pdf_to_images(pdf_url):
    """Download PDF and convert to images"""
    
    # Download PDF
    response = requests.get(pdf_url, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to download PDF: {response.status_code}")
    
    pdf_bytes = response.content
    print(f"Downloaded PDF: {len(pdf_bytes)} bytes")
    
    # Convert to images
    images = convert_from_bytes(
        pdf_bytes, 
        dpi=IMAGE_DPI,
        fmt=IMAGE_FORMAT.lower()
    )
    
    print(f"Converted PDF to {len(images)} page images")
    return images

def image_to_bytes(pil_image):
    """Convert PIL image to bytes for Vision API"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=IMAGE_FORMAT, quality=85)
    return img_byte_arr.getvalue()
```

### 3.3 Vision API Processing (vision_processor.py)
```python
from google.cloud import vision
import time

def process_page_chunk(page_images, start_page_num, project_id, file_id, bucket):
    """Process a chunk of pages with retry logic"""
    results = []
    
    for idx, page_image in enumerate(page_images):
        page_num = start_page_num + idx
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                start_time = time.time()
                
                # Convert image to bytes
                image_bytes = pdf_processor.image_to_bytes(page_image)
                
                # Vision API processing
                vision_result = call_vision_api(image_bytes)
                
                # Extract patterns
                patterns = pattern_extractor.extract_patterns_from_vision(vision_result, page_num)
                
                # Upload image to R2
                image_url = storage_handler.upload_page_image(image_bytes, project_id, file_id, page_num, bucket)
                
                # Upload page JSON to R2  
                page_json_url = storage_handler.upload_page_json(patterns, project_id, file_id, page_num, bucket)
                
                results.append({
                    "page": page_num,
                    "success": True,
                    "image_url": image_url,
                    "page_json_url": page_json_url,
                    "patterns": patterns,
                    "pattern_count": len(patterns),
                    "processing_time": time.time() - start_time
                })
                break  # Success, exit retry loop
                
            except Exception as e:
                print(f"Page {page_num} attempt {attempt + 1} failed: {str(e)}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    results.append({
                        "page": page_num,
                        "success": False,
                        "error": str(e)
                    })
    
    return results

def call_vision_api(image_bytes):
    """Call Google Cloud Vision API"""
    client = vision.ImageAnnotatorClient()
    
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    
    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")
        
    return response
```

### 3.4 Pattern Extraction (pattern_extractor.py)
```python
import re

def extract_patterns_from_vision(vision_response, page_num):
    """Extract and structure patterns for search optimization"""
    
    if not vision_response.text_annotations:
        return []
    
    patterns = []
    pattern_id_counter = 1
    
    # Define pattern regex
    pattern_regexes = [
        re.compile(r'\bPT\d+\b', re.IGNORECASE),     # PT1, PT2, etc.
        re.compile(r'\bM\d+\b', re.IGNORECASE),      # M1, M2, etc.
        re.compile(r'\bE\d+\b', re.IGNORECASE),      # E1, E2, etc.
        re.compile(r'\b[A-Z]-?\d+\b', re.IGNORECASE) # General patterns
    ]
    
    # Process individual text annotations  
    for annotation in vision_response.text_annotations[1:]:  # Skip first (full text)
        text = annotation.description.strip()
        
        for regex in pattern_regexes:
            if regex.match(text):
                pattern = create_pattern_object(
                    text, annotation, page_num, pattern_id_counter
                )
                patterns.append(pattern)
                pattern_id_counter += 1
                break
    
    return patterns

def create_pattern_object(text, annotation, page_num, pattern_id):
    """Create search-optimized pattern object"""
    
    # Extract coordinates
    vertices = annotation.bounding_poly.vertices
    x = min(v.x for v in vertices)
    y = min(v.y for v in vertices)
    width = max(v.x for v in vertices) - x
    height = max(v.y for v in vertices) - y
    
    pattern_type = text.upper().strip()
    
    return {
        "pattern_id": f"{pattern_type.lower()}_page{page_num}_{pattern_id:03d}",
        "pattern_type": pattern_type,
        "text": text,
        "page_number": page_num,
        "coordinates": {
            "x": x,
            "y": y, 
            "width": width,
            "height": height
        },
        "confidence": getattr(annotation, 'confidence', 0.0)
    }
```

### 3.5 Storage Handler (storage_handler.py)
```python
import boto3
import json
from datetime import datetime

def get_r2_client():
    """Initialize R2 client with credentials from Secret Manager"""
    # Implementation to get R2 credentials from Secret Manager
    # and return boto3 client configured for R2
    pass

def upload_page_image(image_bytes, project_id, file_id, page_num, bucket):
    """Upload page image to R2"""
    client = get_r2_client()
    
    key = f"projects/{project_id}/files/{file_id}/images/page-{page_num:03d}.jpg"
    
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=image_bytes,
        ContentType='image/jpeg',
        CacheControl='public, max-age=31536000'  # 1 year cache
    )
    
    return f"{R2_BASE_URL}/{key}"

def upload_page_json(patterns, project_id, file_id, page_num, bucket):
    """Upload page JSON to R2"""
    client = get_r2_client()
    
    page_data = {
        "page_number": page_num,
        "patterns": patterns,
        "pattern_count": {
            pattern_type: len([p for p in patterns if p['pattern_type'] == pattern_type])
            for pattern_type in set(p['pattern_type'] for p in patterns)
        },
        "total_patterns": len(patterns),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    key = f"projects/{project_id}/files/{file_id}/json/page-{page_num:03d}.json"
    
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(page_data, indent=2),
        ContentType='application/json'
    )
    
    return f"{R2_BASE_URL}/{key}"

def upload_final_json(final_result, project_id, file_id, bucket):
    """Upload aggregated final JSON"""
    client = get_r2_client()
    
    key = f"projects/{project_id}/files/{file_id}/json/final-results.json"
    
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(final_result, indent=2),
        ContentType='application/json'
    )
    
    return f"{R2_BASE_URL}/{key}"
```

### 3.6 Result Aggregator (result_aggregator.py)
```python
def compile_final_json(page_results, project_id, file_id):
    """Compile search-optimized final JSON"""
    
    start_time = time.time()
    successful_results = [r for r in page_results if r['success']]
    failed_results = [r for r in page_results if not r['success']]
    
    # Aggregate all patterns
    all_patterns = []
    pages_data = []
    
    for result in successful_results:
        # Add page data
        page_data = {
            "page_number": result['page'],
            "image_url": result['image_url'],
            "patterns": result['patterns'],
            "pattern_count": calculate_pattern_counts(result['patterns'])
        }
        pages_data.append(page_data)
        
        # Collect patterns
        all_patterns.extend(result['patterns'])
    
    # Create search index
    search_index = create_search_index(all_patterns, pages_data)
    
    # Aggregate pattern statistics
    aggregated_patterns = aggregate_pattern_statistics(all_patterns)
    
    final_result = {
        "project_id": project_id,
        "file_id": file_id,
        "processing_metadata": {
            "total_pages": len(page_results),
            "processed_pages": len(successful_results),
            "failed_pages": [{"page": r['page'], "error": r['error']} for r in failed_results],
            "processing_time_seconds": time.time() - start_time,
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "parallel_workers": PARALLEL_WORKERS,
                "image_dpi": IMAGE_DPI,
                "vision_api_version": "v1"
            }
        },
        "pages": pages_data,
        "aggregated_patterns": aggregated_patterns,
        "search_index": search_index,
        "statistics": calculate_document_statistics(all_patterns, pages_data)
    }
    
    return final_result

def create_search_index(all_patterns, pages_data):
    """Create optimized search index"""
    return {
        "unique_patterns": list(set(p['pattern_type'] for p in all_patterns)),
        "pages_with_patterns": sorted(list(set(p['pattern_id'].split('_page')[1].split('_')[0] for p in all_patterns))),
        "total_pattern_count": len(all_patterns),
        "patterns_by_page": {
            str(page['page_number']): len(page['patterns']) 
            for page in pages_data
        }
    }
```

## Phase 4: Deployment & Testing

### 4.1 Deployment Commands
```bash
# Deploy main function
gcloud functions deploy pdf-vision-pipeline \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --source=functions/pdf-vision-pipeline \
  --project=ladders-doc-pipeline-462921 \
  --region=us-central1 \
  --timeout=3600 \
  --memory=8GB \
  --max-instances=10

# Enable required APIs
gcloud services enable vision.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 4.2 Testing Strategy
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: End-to-end pipeline testing
3. **Load Tests**: 50-page PDF processing
4. **Error Handling Tests**: Network failures, API errors

### 4.3 Monitoring & Observability
- Cloud Function logs and metrics
- Custom metrics for pattern detection accuracy
- Performance monitoring (processing time per page)
- Error rate tracking and alerting

## Phase 5: Optimization & Production Readiness

### 5.1 Performance Optimizations
- Image compression optimization
- Memory usage optimization for large PDFs
- Vision API batch processing exploration
- Caching strategies for repeated documents

### 5.2 Error Handling & Resilience
- Comprehensive retry logic
- Circuit breaker patterns for external dependencies
- Graceful degradation on partial failures
- Dead letter queue for failed processing

### 5.3 Security Considerations
- R2 credentials management via Secret Manager
- Input validation and sanitization  
- Rate limiting and abuse prevention
- Audit logging for compliance

## Expected Outcomes

### Performance Metrics
- **Processing Time**: 15-25 seconds for 50-page PDF
- **Accuracy**: 95%+ pattern detection rate
- **Reliability**: 99.5% successful page processing
- **Scalability**: Support for concurrent document processing

### JSON Output Optimization
- **Search Performance**: Sub-second pattern queries
- **File Size**: Compressed JSON structure
- **Compatibility**: Standard JSON format for easy integration
- **Extensibility**: Schema supports additional pattern types

This implementation plan provides a robust, scalable solution optimized for architectural document processing with superior accuracy and performance. 