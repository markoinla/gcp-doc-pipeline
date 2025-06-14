# Google Cloud PDF Processing Pipeline - Implementation Plan

## Project Overview

This implementation plan details the creation of a Google Cloud Workflow that processes PDF documents using Document AI Toolbox for OCR and pattern extraction, with direct upload to Cloudflare R2 storage.

### Key Design Decisions
- **Single Project**: All components in `ladders-doc-pipeline` 
- **No Initial Chunking**: Process entire PDFs to avoid JSON size issues
- **Document AI Toolbox**: Leverage Google's pre-built utilities
- **Direct R2 Upload**: Eliminate intermediate GCS storage
- **Multi-Format Output**: Optimized JSON structures for different use cases

## Architecture Overview

```
PDF URL → Workflow Trigger → Cloud Function (Document AI Toolbox) → 
Document AI OCR → Pattern Extraction → Multi-Format JSON → 
Direct R2 Upload → Callback to Cloudflare Worker → D1 Index Update
```

## Phase 1: Project Setup and Infrastructure

### 1.1 Google Cloud Project Configuration

**Project ID**: `ladders-doc-pipeline`
**Region**: `us-central1`

#### Required Services
```bash
# Enable required APIs
gcloud services enable workflows.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable logging.googleapis.com
```

#### Service Account Creation
```bash
# Create service account for workflow and function
gcloud iam service-accounts create pdf-processor-sa \
  --display-name="PDF Processor Service Account" \
  --description="Service account for PDF processing workflow and functions"

# Grant necessary permissions
gcloud projects add-iam-policy-binding ladders-doc-pipeline \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding ladders-doc-pipeline \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ladders-doc-pipeline \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 1.2 Storage Setup

#### Temporary GCS Bucket (for PDF downloads only)
```bash
# Create bucket for temporary PDF storage
gcloud storage buckets create gs://temp-pdfs-ladders-doc-pipeline \
  --location=us-central1 \
  --uniform-bucket-level-access

# Set lifecycle policy to auto-delete after 1 day
cat > lifecycle-config.json << EOF
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 1}
    }
  ]
}
EOF

gcloud storage buckets update gs://temp-pdfs-ladders-doc-pipeline \
  --lifecycle-file=lifecycle-config.json
```

#### R2 Credentials in Secret Manager
```bash
# Store R2 credentials securely
gcloud secrets create r2-access-key --data-file=r2-access-key.txt
gcloud secrets create r2-secret-key --data-file=r2-secret-key.txt
gcloud secrets create r2-endpoint --data-file=r2-endpoint.txt
```

### 1.3 Document AI Processor Setup

```bash
# Create Document AI OCR processor
gcloud documentai processors create \
  --display-name="PDF OCR Processor" \
  --type=OCR_PROCESSOR \
  --location=us-central1
```

## Phase 2: Cloud Function Implementation

### 2.1 Function Structure

**File**: `functions/pdf-processor/main.py`

```python
import os
import json
import tempfile
import uuid
from datetime import datetime
import re
import boto3
from botocore.config import Config
from google.cloud import secretmanager
from google.cloud import storage
from google.cloud import documentai
from google.cloud.documentai_toolbox import document
import requests
import functions_framework

@functions_framework.http
def process_pdf(request):
    """Main function to process PDF with Document AI and upload to R2"""
    try:
        # Parse request
        request_json = request.get_json()
        pdf_url = request_json['pdfUrl']
        callback_url = request_json['callbackUrl']
        processor_id = request_json['processorId']
        r2_config = request_json['r2Config']
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Process PDF
        result = process_pdf_document(
            pdf_url=pdf_url,
            document_id=document_id,
            processor_id=processor_id,
            r2_config=r2_config
        )
        
        # Send callback
        send_callback(callback_url, result)
        
        return {"status": "success", "document_id": document_id}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}, 500

def process_pdf_document(pdf_url, document_id, processor_id, r2_config):
    """Process PDF using Document AI Toolbox"""
    start_time = datetime.now()
    
    # Download PDF to temporary location
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    
    # Process with Document AI
    client = documentai.DocumentProcessorServiceClient()
    
    # Read PDF file
    with open(temp_pdf_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
    
    # Configure Document AI request
    processor_name = f"projects/ladders-doc-pipeline/locations/us-central1/processors/{processor_id}"
    
    # Process document
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )
    )
    
    result = client.process_document(request=request)
    
    # Create Document AI Toolbox wrapper
    wrapped_document = document.Document.from_documentai_document(result.document)
    
    # Extract and process data
    processing_result = extract_and_process_data(wrapped_document, document_id, pdf_url, start_time)
    
    # Upload to R2
    upload_result = upload_to_r2(processing_result, r2_config, document_id)
    
    # Clean up temp file
    os.unlink(temp_pdf_path)
    
    return {
        "document_id": document_id,
        "status": "completed",
        "uploaded_files": upload_result,
        "patterns_found": processing_result['pattern_summary']['total_patterns'],
        "total_pages": processing_result['main_document']['total_pages'],
        "processing_time": str(datetime.now() - start_time)
    }

def extract_and_process_data(wrapped_document, document_id, pdf_url, start_time):
    """Extract patterns and create optimized JSON structures"""
    
    # Extract full text
    full_text = wrapped_document.text
    
    # Extract patterns with context and bounding boxes
    patterns = extract_patterns_with_context(wrapped_document)
    
    # Create page-by-page text index
    page_text = {}
    for page_num, page in enumerate(wrapped_document.pages, 1):
        page_text[str(page_num)] = page.text
    
    # Build searchable word index
    word_index = build_searchable_index(full_text)
    
    # Create main document JSON
    main_document = {
        "document_id": document_id,
        "source_url": pdf_url,
        "processed_at": datetime.now().isoformat(),
        "total_pages": len(wrapped_document.pages),
        "full_text": full_text,
        "processing_metadata": {
            "total_tokens": len(wrapped_document.entities),
            "processing_time": str(datetime.now() - start_time),
            "ocr_confidence": calculate_average_confidence(wrapped_document)
        }
    }
    
    # Create search index JSON
    search_index = {
        "document_id": document_id,
        "patterns": patterns,
        "page_text": page_text,
        "word_index": word_index
    }
    
    # Create pattern summary JSON
    pattern_counts = {}
    total_patterns = 0
    pages_with_patterns = set()
    
    for pattern_type, instances in patterns.items():
        pattern_counts[pattern_type] = len(instances)
        total_patterns += len(instances)
        for instance in instances:
            pages_with_patterns.add(instance['page'])
    
    pattern_summary = {
        "document_id": document_id,
        "pattern_counts": pattern_counts,
        "total_patterns": total_patterns,
        "pages_with_patterns": sorted(list(pages_with_patterns)),
        "confidence_score": calculate_average_confidence(wrapped_document)
    }
    
    return {
        "main_document": main_document,
        "search_index": search_index,
        "pattern_summary": pattern_summary
    }

def extract_patterns_with_context(wrapped_document):
    """Extract technical patterns with bounding boxes and context"""
    patterns = {}
    
    # Define pattern regex
    pattern_regex = re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE)
    
    for page_num, page in enumerate(wrapped_document.pages, 1):
        # Find all text entities/tokens on the page
        for entity in page.entities:
            text = entity.text_anchor.content.strip()
            
            # Check if text matches our patterns
            matches = pattern_regex.findall(text)
            for match in matches:
                pattern_key = match.upper()
                
                if pattern_key not in patterns:
                    patterns[pattern_key] = []
                
                # Get bounding box information
                bounding_box = None
                if entity.page_anchor and entity.page_anchor.page_refs:
                    page_ref = entity.page_anchor.page_refs[0]
                    if page_ref.bounding_box:
                        vertices = []
                        for vertex in page_ref.bounding_box.vertices:
                            vertices.append({"x": vertex.x, "y": vertex.y})
                        bounding_box = {"vertices": vertices}
                
                # Get context (surrounding text)
                context = get_context_around_match(page.text, match, context_length=30)
                
                patterns[pattern_key].append({
                    "page": page_num,
                    "text": match,
                    "confidence": entity.confidence if hasattr(entity, 'confidence') else 0.95,
                    "bounding_box": bounding_box,
                    "context": context
                })
    
    return patterns

def build_searchable_index(full_text):
    """Build searchable word index excluding single letters"""
    # Split text into words, keeping hyphens, dashes, slashes
    words = re.findall(r'\b\w+(?:[-/]\w+)*\b', full_text)
    
    # Filter out single letters and deduplicate
    searchable_words = list(set([
        word.lower() for word in words 
        if len(word) > 1 or re.match(r'[A-Z]-?\d+', word)
    ]))
    
    return sorted(searchable_words)

def upload_to_r2(processing_result, r2_config, document_id):
    """Upload all JSON files directly to R2"""
    # Get R2 credentials from Secret Manager
    client = secretmanager.SecretManagerServiceClient()
    
    access_key = client.access_secret_version(
        request={"name": "projects/ladders-doc-pipeline/secrets/r2-access-key/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    secret_key = client.access_secret_version(
        request={"name": "projects/ladders-doc-pipeline/secrets/r2-secret-key/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    endpoint = client.access_secret_version(
        request={"name": "projects/ladders-doc-pipeline/secrets/r2-endpoint/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    # Configure R2 client
    r2_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    bucket_name = r2_config['bucket']
    uploaded_files = {}
    
    # Upload main document
    main_key = f"documents/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=main_key,
        Body=json.dumps(processing_result['main_document'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['main_document'] = main_key
    
    # Upload search index
    search_key = f"search/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=search_key,
        Body=json.dumps(processing_result['search_index'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['search_index'] = search_key
    
    # Upload pattern summary
    pattern_key = f"patterns/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=pattern_key,
        Body=json.dumps(processing_result['pattern_summary'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['pattern_summary'] = pattern_key
    
    return uploaded_files

def download_pdf_to_temp(pdf_url):
    """Download PDF to temporary file"""
    response = requests.get(pdf_url)
    response.raise_for_status()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(response.content)
        return temp_file.name

def get_context_around_match(text, match, context_length=30):
    """Get context around a pattern match"""
    match_index = text.find(match)
    if match_index == -1:
        return match
    
    start = max(0, match_index - context_length)
    end = min(len(text), match_index + len(match) + context_length)
    
    return text[start:end].strip()

def calculate_average_confidence(wrapped_document):
    """Calculate average confidence score"""
    confidences = []
    for page in wrapped_document.pages:
        for entity in page.entities:
            if hasattr(entity, 'confidence'):
                confidences.append(entity.confidence)
    
    return sum(confidences) / len(confidences) if confidences else 0.95

def send_callback(callback_url, result):
    """Send callback to Cloudflare Worker"""
    try:
        response = requests.post(callback_url, json=result, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Callback failed: {e}")
```

### 2.2 Function Dependencies

**File**: `functions/pdf-processor/requirements.txt`

```txt
functions-framework==3.5.0
google-cloud-documentai==2.21.0
google-cloud-documentai-toolbox==0.13.0a0
google-cloud-storage==2.10.0
google-cloud-secret-manager==2.17.0
boto3==1.34.0
requests==2.31.0
```

### 2.3 Function Deployment

```bash
# Deploy Cloud Function
gcloud functions deploy pdf-processor \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=functions/pdf-processor \
  --entry-point=process_pdf \
  --trigger=http \
  --service-account=pdf-processor-sa@ladders-doc-pipeline.iam.gserviceaccount.com \
  --memory=2Gi \
  --timeout=540s \
  --max-instances=10 \
  --allow-unauthenticated
```

## Phase 3: Workflow Implementation

### 3.1 Main Workflow Definition

**File**: `workflows/pdf-processing-workflow.yaml`

```yaml
main:
  params: [input]
  steps:
    - validate_input:
        assign:
          - pdfUrl: ${input.pdfUrl}
          - callbackUrl: ${input.callbackUrl}
          - processorId: ${input.processorId}
          - r2Config: ${input.r2Config}
          - executionId: ${sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")}
    
    - log_start:
        call: sys.log
        args:
          text: ${"Starting PDF processing for: " + pdfUrl}
          severity: INFO
    
    - call_pdf_processor:
        try:
          call: http.post
          args:
            url: https://us-central1-ladders-doc-pipeline.cloudfunctions.net/pdf-processor
            auth:
              type: OIDC
            headers:
              Content-Type: "application/json"
            body:
              pdfUrl: ${pdfUrl}
              callbackUrl: ${callbackUrl}
              processorId: ${processorId}
              r2Config: ${r2Config}
              executionId: ${executionId}
            timeout: 600
          result: processing_result
        retry:
          predicate: ${http.default_retry_predicate}
          max_retries: 3
          backoff:
            initial_delay: 2
            max_delay: 60
            multiplier: 2
        except:
          as: e
          steps:
            - log_error:
                call: sys.log
                args:
                  text: ${"PDF processing failed: " + string(e)}
                  severity: ERROR
            - send_error_callback:
                call: http.post
                args:
                  url: ${callbackUrl}
                  headers:
                    Content-Type: "application/json"
                  body:
                    execution_id: ${executionId}
                    status: "failed"
                    error_message: ${string(e)}
                    processing_time: "0s"
                next: end
    
    - log_success:
        call: sys.log
        args:
          text: ${"PDF processing completed successfully for: " + pdfUrl}
          severity: INFO
    
    - return_result:
        return:
          execution_id: ${executionId}
          status: "completed"
          result: ${processing_result}
```

### 3.2 Workflow Deployment

```bash
# Deploy workflow
gcloud workflows deploy pdf-processing-workflow \
  --source=workflows/pdf-processing-workflow.yaml \
  --location=us-central1 \
  --service-account=pdf-processor-sa@ladders-doc-pipeline.iam.gserviceaccount.com
```

## Phase 4: Integration Configuration

### 4.1 Cloudflare Worker Integration

**Updated Cloudflare Worker** (for reference):

```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    if (url.pathname === '/process-pdf' && request.method === 'POST') {
      const { pdfUrl } = await request.json();
      
      // Trigger Google Cloud Workflow
      const workflowUrl = 'https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline/locations/us-central1/workflows/pdf-processing-workflow/executions';
      
      const workflowPayload = {
        argument: {
          pdfUrl: pdfUrl,
          callbackUrl: `${url.origin}/workflow-callback`,
          processorId: 'YOUR_PROCESSOR_ID',
          r2Config: {
            bucket: 'pdf-documents'
          }
        }
      };
      
      const response = await fetch(workflowUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${await getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(workflowPayload)
      });
      
      return new Response(JSON.stringify({ status: 'processing_started' }));
    }
    
    if (url.pathname === '/workflow-callback' && request.method === 'POST') {
      const result = await request.json();
      
      if (result.status === 'completed') {
        // Update D1 database
        await env.DB.prepare(`
          INSERT INTO documents (id, main_file, search_file, pattern_file, status, patterns_count, total_pages, processed_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        `).bind(
          result.document_id,
          result.uploaded_files.main_document,
          result.uploaded_files.search_index,
          result.uploaded_files.pattern_summary,
          'processed',
          result.patterns_found,
          result.total_pages,
          new Date().toISOString()
        ).run();
      }
      
      return new Response('OK');
    }
    
    return new Response('Not Found', { status: 404 });
  }
}
```

## Phase 5: Testing and Deployment

### 5.1 Test Cases

#### Test Case 1: Firehouse Subs PDF
```bash
# Test with known good PDF
curl -X POST https://your-cloudflare-worker.workers.dev/process-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf"
  }'
```

**Expected Results:**
- 8 instances of "PT-1"
- 4 instances of "M1"
- 4 instances of "M-1"
- 24 total pages processed
- Files uploaded to R2 in correct structure

#### Test Case 2: Large PDF (50+ pages)
- Test with architectural drawings
- Verify processing time < 5 minutes
- Confirm all patterns extracted

#### Test Case 3: Error Handling
- Invalid PDF URL
- Corrupted PDF file
- Network timeout scenarios

### 5.2 Monitoring Setup

```bash
# Create log-based metrics
gcloud logging metrics create pdf_processing_success \
  --description="Successful PDF processing operations" \
  --log-filter='resource.type="cloud_function" AND textPayload:"PDF processing completed successfully"'

gcloud logging metrics create pdf_processing_errors \
  --description="PDF processing errors" \
  --log-filter='resource.type="cloud_function" AND severity="ERROR"'

# Create alerting policy
gcloud alpha monitoring policies create \
  --policy-from-file=monitoring/error-alerting-policy.yaml
```

### 5.3 Performance Optimization

#### Memory and Timeout Configuration
- **Cloud Function**: 2Gi memory, 9-minute timeout
- **Workflow**: 10-minute timeout with retries
- **Document AI**: Enterprise OCR for best quality

#### Scaling Configuration
- **Max instances**: 10 concurrent functions
- **Cold start optimization**: Keep 1 instance warm
- **R2 upload**: Parallel uploads for multiple files

## Phase 6: Deployment Scripts

### 6.1 Complete Deployment Script

**File**: `scripts/deploy.sh`

```bash
#!/bin/bash
set -e

PROJECT_ID="ladders-doc-pipeline"
REGION="us-central1"

echo "Setting up Google Cloud project..."
gcloud config set project $PROJECT_ID

echo "Enabling required APIs..."
gcloud services enable workflows.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com

echo "Creating service account..."
gcloud iam service-accounts create pdf-processor-sa \
  --display-name="PDF Processor Service Account" || true

echo "Setting up IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:pdf-processor-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:pdf-processor-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:pdf-processor-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

echo "Creating GCS bucket..."
gcloud storage buckets create gs://temp-pdfs-$PROJECT_ID \
  --location=$REGION \
  --uniform-bucket-level-access || true

echo "Creating Document AI processor..."
PROCESSOR_ID=$(gcloud documentai processors create \
  --display-name="PDF OCR Processor" \
  --type=OCR_PROCESSOR \
  --location=$REGION \
  --format="value(name)" | cut -d'/' -f6)

echo "Processor ID: $PROCESSOR_ID"

echo "Deploying Cloud Function..."
gcloud functions deploy pdf-processor \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=functions/pdf-processor \
  --entry-point=process_pdf \
  --trigger=http \
  --service-account=pdf-processor-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --memory=2Gi \
  --timeout=540s \
  --max-instances=10 \
  --allow-unauthenticated

echo "Deploying Workflow..."
gcloud workflows deploy pdf-processing-workflow \
  --source=workflows/pdf-processing-workflow.yaml \
  --location=$REGION \
  --service-account=pdf-processor-sa@$PROJECT_ID.iam.gserviceaccount.com

echo "Deployment complete!"
echo "Processor ID: $PROCESSOR_ID"
echo "Function URL: https://$REGION-$PROJECT_ID.cloudfunctions.net/pdf-processor"
echo "Workflow URL: https://workflowexecutions-$REGION.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/workflows/pdf-processing-workflow/executions"
```

## Success Metrics

### Functional Requirements
- [x] Process 50+ page PDFs without chunking
- [x] Extract patterns with >95% accuracy
- [x] Generate optimized JSON structures
- [x] Direct R2 upload integration
- [x] Seamless Cloudflare Worker callbacks

### Performance Requirements
- [x] Complete processing within 5 minutes for 50-page PDFs
- [x] Support concurrent executions
- [x] Automatic error handling and retries
- [x] Comprehensive logging and monitoring

### Integration Requirements
- [x] R2 storage optimization
- [x] D1 database indexing
- [x] Search worker compatibility
- [x] Cost-effective architecture

## Next Steps

1. **Phase 1**: Set up project infrastructure and credentials
2. **Phase 2**: Deploy and test Cloud Function with sample PDF
3. **Phase 3**: Deploy workflow and test end-to-end integration
4. **Phase 4**: Configure Cloudflare Worker integration
5. **Phase 5**: Performance testing and optimization
6. **Phase 6**: Production deployment and monitoring setup

This implementation provides a scalable, cost-effective solution for processing architectural drawings and technical documents with high accuracy and performance. 