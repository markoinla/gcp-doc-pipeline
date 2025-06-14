# Google Cloud Workflow for PDF Document Processing - AI Agent Prompt

## Project Overview

You are tasked with creating a Google Cloud Workflow that processes PDF documents using Document AI for OCR and pattern extraction. This workflow will be deployed in a separate Google Cloud project from the Cloudflare Workers and will handle the heavy document processing workload.

## Architecture Context

### Current Setup
- **Cloudflare Workers Project**: `cf-pdf-workers` - Handles API layer, user interfaces, R2 storage, D1 indexing
- **Google Cloud Project**: `document-processing-workflows` (NEW) - Handles PDF processing workflows
- **Existing Document AI Processor**: Enterprise OCR processor (ID: `5aa847e724b9d72`) in project `ladders-ai`

### Integration Flow
```
User uploads PDF → Cloudflare Worker → Triggers Google Cloud Workflow → 
PDF Processing (splitting, OCR, pattern extraction) → 
Structured JSON output → Cloudflare Worker retrieves results → 
Stores in R2 + indexes in D1
```

## Technical Requirements

### 1. PDF Processing Constraints
- **Image-based PDFs**: Many PDFs are scanned documents or CAD exports with no text layer
- **OCR Required**: Must use Document AI Enterprise OCR for all pages
- **Page Limit**: Document AI has 15-page limit per request
- **Target Size**: Support PDFs up to 50+ pages
- **Solution**: Split PDFs into 15-page chunks and process in parallel

### 2. Pattern Extraction Requirements
Extract specific technical patterns with bounding boxes:
- `PT-1`, `PT1` (paint/coating specifications)
- `M1`, `M-1` (material specifications)  
- `[A-Z]\d+`, `[A-Z]-\d+` (general technical codes)

### 3. Output Requirements
Generate structured JSON optimized for search and indexing:
```json
{
  "document_id": "uuid",
  "source_url": "original-pdf-url",
  "processed_at": "2025-06-14T21:00:00Z",
  "total_pages": 47,
  "chunks_processed": 4,
  "patterns": [
    {
      "pattern_type": "PT-1",
      "instances": [
        {
          "page": 8,
          "text": "PT-1",
          "confidence": 0.987,
          "bounding_box": {
            "vertices": [{"x": 2002, "y": 729}, {"x": 2018, "y": 739}],
            "normalized": [{"x": 0.817, "y": 0.446}, {"x": 0.824, "y": 0.453}]
          },
          "context": "PAINTED PT-1 STEEL FRAME",
          "chunk_id": 1,
          "token_details": [
            {"text": "PT", "confidence": 0.987, "bounding_box": {...}},
            {"text": "-", "confidence": 0.977, "bounding_box": {...}},
            {"text": "1", "confidence": 0.970, "bounding_box": {...}}
          ]
        }
      ]
    }
  ],
  "search_index": {
    "full_text": "searchable text from all pages",
    "pattern_locations": {...},
    "page_summaries": [...]
  },
  "processing_metadata": {
    "chunks": 4,
    "total_tokens": 15420,
    "processing_time": "45s",
    "ocr_quality": "high",
    "workflow_execution_id": "workflow-uuid"
  }
}
```

## Workflow Implementation Requirements

### 1. Main Workflow Structure
Create a workflow named `pdf-ocr-pipeline` with these steps:

#### Input Parameters
```yaml
params: [input]
# Expected input:
# {
#   "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/file.pdf",
#   "outputBucket": "gs://processed-results",
#   "callbackUrl": "https://document-ai-worker.m-6bb.workers.dev/workflow-callback",
#   "processorId": "5aa847e724b9d72",
#   "projectId": "ladders-ai",
#   "location": "us"
# }
```

#### Step 1: Download and Validate PDF
- Download PDF from the provided URL
- Validate it's a valid PDF file
- Get page count and basic metadata
- Store temporarily in GCS bucket

#### Step 2: PDF Splitting
- Split PDF into chunks of maximum 15 pages each
- Maintain page numbering metadata for each chunk
- Upload each chunk to GCS with unique identifiers

#### Step 3: Parallel Document AI Processing
- Process all chunks simultaneously using parallel steps
- Use Document AI Enterprise OCR processor
- Handle retries and error cases for each chunk
- Collect all OCR results

#### Step 4: Pattern Extraction and Analysis
- Merge OCR results from all chunks
- Extract patterns using regex: `/^(PT-?\d+|M\d+|[A-Z]\d+|[A-Z]-\d+)$/i`
- Map patterns to their token-level bounding boxes
- Calculate confidence scores and context

#### Step 5: JSON Structure Creation
- Create the structured JSON output format
- Include search optimization data
- Add processing metadata and timing information

#### Step 6: Result Storage and Callback
- Store final JSON in GCS output bucket
- Call the Cloudflare Worker callback URL with results
- Clean up temporary files

### 2. Error Handling Requirements
- Implement retry logic for Document AI calls (exponential backoff)
- Handle partial failures (some chunks succeed, others fail)
- Provide detailed error information in callbacks
- Clean up resources on failure

### 3. Performance Requirements
- Process chunks in parallel for speed
- Optimize memory usage for large PDFs
- Target completion time: <2 minutes for 50-page PDFs
- Support concurrent workflow executions

## Google Cloud Services to Use

### Required Services
1. **Workflows** - Main orchestration
2. **Document AI** - OCR processing (existing processor in `ladders-ai` project)
3. **Cloud Storage** - Temporary file storage and results
4. **Cloud Functions** (if needed) - Custom processing logic
5. **Cloud Logging** - Execution monitoring

### Service Configuration
- **Region**: `us-central1` (same as Document AI processor)
- **Storage Buckets**: 
  - `temp-pdfs-processing` (temporary PDF chunks)
  - `processed-results` (final JSON outputs)
- **IAM Roles**: Document AI API User, Storage Admin, Workflows Invoker

## Integration Specifications

### Authentication
- Use service account with cross-project permissions
- Document AI processor is in `ladders-ai` project
- Workflow runs in `document-processing-workflows` project

### Callback Interface
The workflow must call the Cloudflare Worker callback URL with:
```json
{
  "execution_id": "workflow-execution-uuid",
  "status": "completed|failed|processing",
  "result_location": "gs://processed-results/document-uuid.json",
  "patterns_found": 42,
  "total_pages": 47,
  "processing_time": "45s",
  "error_message": "optional error details"
}
```

### Monitoring and Logging
- Log all major steps and timing information
- Include execution IDs for traceability
- Monitor Document AI API quotas and usage

## Testing Requirements

### Test Cases
1. **Small PDF** (1-5 pages) - Basic functionality test
2. **Medium PDF** (15-30 pages) - Chunking and parallel processing
3. **Large PDF** (50+ pages) - Full scale test
4. **Image-heavy PDF** - OCR quality test
5. **Error scenarios** - Network failures, invalid PDFs, API limits

### Sample Test PDF
Use the Firehouse Subs architectural drawings PDF that has been successfully tested:
- URL: `https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf`
- 24 pages of architectural drawings
- Contains multiple PT-1, M1, and M-1 patterns
- Image-based PDF requiring OCR

## Deliverables

### 1. Workflow Definition
- `workflows/pdf-ocr-pipeline.yaml` - Main workflow definition
- Complete YAML with all steps and error handling

### 2. Supporting Functions (if needed)
- Cloud Functions for PDF splitting, pattern extraction, or JSON formatting
- Include deployment scripts and requirements

### 3. Configuration Files
- IAM roles and permissions setup
- GCS bucket configuration
- Environment variables and secrets

### 4. Documentation
- Deployment instructions
- API documentation for the workflow
- Troubleshooting guide

### 5. Testing Scripts
- Test workflow with sample PDFs
- Validation scripts for output format
- Performance benchmarking

## Success Criteria

1. **Functionality**: Successfully processes 50+ page image-based PDFs
2. **Accuracy**: Extracts patterns with >95% accuracy compared to manual review
3. **Performance**: Completes processing within 2 minutes for typical documents
4. **Reliability**: Handles errors gracefully with proper cleanup
5. **Integration**: Seamlessly integrates with Cloudflare Worker callbacks
6. **Scalability**: Supports concurrent executions without conflicts

## Additional Context

### Existing Implementation Reference
The current Cloudflare Worker implementation successfully:
- Processes PDFs via Document AI Enterprise OCR
- Extracts patterns with bounding boxes
- Handles GCS integration for large files
- Uses base64-encoded service account authentication

### Pattern Extraction Success
Previous testing found these patterns in the Firehouse Subs PDF:
- 8 instances of "PT-1" across multiple pages
- 4 instances of "M1" 
- 4 instances of "M-1"
- 61 total tokens with precise bounding boxes

Use this as validation data for testing the workflow implementation.

---

**Note**: This workflow will be the foundation for a scalable document processing pipeline that can handle architectural drawings, technical specifications, and other image-based PDFs with high accuracy and performance. 