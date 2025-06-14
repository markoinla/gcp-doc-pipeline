# Google Cloud PDF Processing Pipeline - Implementation Plan

## Project Overview

This implementation plan details the creation of a Google Cloud Workflow that processes PDF documents using Document AI Toolbox for OCR and pattern extraction, with direct upload to Cloudflare R2 storage.

### Key Design Decisions
- **Single Project**: All components in `ladders-doc-pipeline-462921` 
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

**Project ID**: `ladders-doc-pipeline-462921`
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
gcloud projects add-iam-policy-binding ladders-doc-pipeline-462921 \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline-462921.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding ladders-doc-pipeline-462921 \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline-462921.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ladders-doc-pipeline-462921 \
  --member="serviceAccount:pdf-processor-sa@ladders-doc-pipeline-462921.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 1.2 Storage Setup

#### Temporary GCS Bucket (for PDF downloads only)
```bash
# Create bucket for temporary PDF storage
gcloud storage buckets create gs://temp-pdfs-ladders-doc-pipeline-462921 \
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

gcloud storage buckets update gs://temp-pdfs-ladders-doc-pipeline-462921 \
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

## Implementation Phases

### Phase 2: Cloud Function Development
### Phase 3: Workflow Implementation  
### Phase 4: Integration Configuration
### Phase 5: Testing and Deployment
### Phase 6: Monitoring and Optimization

## Success Criteria

1. **Functionality**: Successfully processes 50+ page image-based PDFs
2. **Accuracy**: Extracts patterns with >95% accuracy compared to manual review
3. **Performance**: Completes processing within 5 minutes for typical documents
4. **Reliability**: Handles errors gracefully with proper cleanup
5. **Integration**: Seamlessly integrates with Cloudflare Worker callbacks
6. **Scalability**: Supports concurrent executions without conflicts