# GCP Document Processing Pipeline - Integration Guide

**Version**: 1.0  
**Last Updated**: 2025-01-14  
**API Base URL**: `https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions`

## 🎯 Overview

The GCP Document Processing Pipeline is a cloud-based service that processes PDF documents using Google Cloud's Document AI for OCR and pattern extraction. It automatically extracts text, identifies technical patterns, and uploads structured results to Cloudflare R2 storage.

### Key Features
- **OCR Processing**: Extract text from PDF documents using Google Document AI
- **Pattern Recognition**: Identify technical patterns like `PT-1`, `M1`, `M-1`, and other alphanumeric codes
- **Multi-format Output**: Generate optimized JSON files for documents, search, and patterns
- **Cloud Storage**: Direct upload to Cloudflare R2 with public access URLs
- **Scalable Processing**: Handle large PDFs by automatically chunking into 15-page segments
- **Webhook Support**: Real-time notifications when processing completes

---

## 🚀 Quick Start

### 1. Basic PDF Processing Request

```bash
curl -X POST \
  "https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "argument": {
      "pdfUrl": "https://example.com/document.pdf",
      "r2Config": {
        "bucketName": "your-bucket-name"
      }
    }
  }'
```

### 2. Response Format

```json
{
  "name": "projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions/12345678-1234-5678-9012-123456789012",
  "state": "ACTIVE"
}
```

---

## 📋 API Reference

### Authentication

The API uses Google Cloud authentication. You have two options:

#### Option 1: Service Account (Recommended for Production)
```bash
# Authenticate with service account
gcloud auth activate-service-account --key-file=path/to/service-account.json

# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token)
```

#### Option 2: User Account (Development)
```bash
# Authenticate with user account
gcloud auth application-default login

# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token)
```

### Endpoints

#### Start Processing Job
- **Method**: `POST`
- **URL**: `https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions`
- **Headers**: 
  - `Authorization: Bearer {ACCESS_TOKEN}`
  - `Content-Type: application/json`

#### Check Job Status
- **Method**: `GET`
- **URL**: `https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions/{EXECUTION_ID}`
- **Headers**: 
  - `Authorization: Bearer {ACCESS_TOKEN}`

---

## 📝 Request Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `pdfUrl` | string | HTTPS URL to the PDF file (must end with `.pdf`) |
| `r2Config` | object | R2 bucket configuration |
| `r2Config.bucketName` | string | Target R2 bucket name |

### Optional Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `projectID` | string | Your application's project identifier |
| `projectFileID` | string | Your application's file identifier (used as document ID) |
| `webhookUrl` | string | URL to receive processing completion notifications |
| `callbackUrl` | string | Legacy callback URL (deprecated, use webhookUrl) |

### Example Request Payloads

#### Minimal Request
```json
{
  "argument": {
    "pdfUrl": "https://example.com/document.pdf",
    "r2Config": {
      "bucketName": "my-documents"
    }
  }
}
```

#### Full Request with Optional Parameters
```json
{
  "argument": {
    "pdfUrl": "https://example.com/construction-plan.pdf",
    "r2Config": {
      "bucketName": "construction-docs"
    },
    "projectID": "project-123",
    "projectFileID": "file-456",
    "webhookUrl": "https://your-app.com/api/processing-complete"
  }
}
```

---

## 📤 Response Formats

### Processing Job Started Response

```json
{
  "name": "projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions/abc123def456",
  "state": "ACTIVE",
  "startTime": "2025-01-14T10:30:00.123456Z"
}
```

### Job Status Response (In Progress)

```json
{
  "name": "projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions/abc123def456",
  "state": "ACTIVE",
  "startTime": "2025-01-14T10:30:00.123456Z"
}
```

### Job Completion Response

```json
{
  "name": "projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions/abc123def456",
  "state": "SUCCEEDED",
  "startTime": "2025-01-14T10:30:00.123456Z",
  "endTime": "2025-01-14T10:32:15.789012Z",
  "result": {
    "status": "success",
    "document_id": "doc_1705235400",
    "processing_time": "2 minutes 15 seconds",
    "result": {
      "document_id": "doc_1705235400",
      "status": "success",
      "uploaded_files": {
        "main_document": "documents/doc_1705235400.json",
        "search_index": "search/doc_1705235400.json",
        "pattern_summary": "patterns/doc_1705235400.json"
      },
      "items_found": 156,
      "unique_items": 47,
      "patterns_found": 12,
      "words_found": 35,
      "total_pages": 24,
      "processing_time": "0:02:15.123456"
    }
  }
}
```

---

## 🔔 Webhook Notifications

When you provide a `webhookUrl`, the system will send a POST request to your endpoint when processing completes.

### Webhook Payload

```json
{
  "document_id": "doc_1705235400",
  "status": "success",
  "processing_time": "0:02:15.123456",
  "uploaded_files": {
    "main_document": "documents/doc_1705235400.json",
    "search_index": "search/doc_1705235400.json",
    "pattern_summary": "patterns/doc_1705235400.json"
  },
  "items_found": 156,
  "unique_items": 47,
  "patterns_found": 12,
  "words_found": 35,
  "total_pages": 24,
  "r2_urls": {
    "main_document": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/documents/doc_1705235400.json",
    "search_index": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/search/doc_1705235400.json",
    "pattern_summary": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/patterns/doc_1705235400.json"
  }
}
```

### Webhook Endpoint Requirements

Your webhook endpoint should:
- Accept POST requests
- Return HTTP 200 status for successful processing
- Handle JSON payloads
- Be accessible via HTTPS

Example webhook handler (Node.js/Express):

```javascript
app.post('/api/processing-complete', (req, res) => {
  const { document_id, status, uploaded_files, r2_urls } = req.body;
  
  if (status === 'success') {
    // Process successful completion
    console.log(`Document ${document_id} processed successfully`);
    
    // Download and process the results
    const mainDocUrl = r2_urls.main_document;
    // ... your processing logic
    
    res.status(200).json({ received: true });
  } else {
    // Handle processing failure
    console.error(`Document ${document_id} processing failed`);
    res.status(200).json({ received: true });
  }
});
```

---

## 📁 Output File Formats

The pipeline generates three types of JSON files in your R2 bucket:

### 1. Main Document (`documents/{document_id}.json`)

Contains the complete document analysis:

```json
{
  "document_id": "doc_1705235400",
  "processing_info": {
    "timestamp": "2025-01-14T10:30:00.123456Z",
    "processing_time": "0:02:15.123456",
    "document_ai_confidence": 0.95
  },
  "source_info": {
    "pdf_url": "https://example.com/document.pdf",
    "total_pages": 24,
    "file_size": 2048576
  },
  "extracted_text": "Full OCR text content...",
  "pages": [
    {
      "page_number": 1,
      "text": "Page 1 text content...",
      "patterns_found": ["PT-1", "M1"],
      "words_found": ["specification", "material"]
    }
  ],
  "all_items": [
    {
      "text": "PT-1",
      "type": "pattern",
      "category": "Paint/Coating",
      "page_number": 1,
      "confidence": 0.98,
      "bounding_box": {
        "x": 100,
        "y": 200,
        "width": 50,
        "height": 20
      },
      "context": "...surrounding text for PT-1 reference..."
    }
  ]
}
```

### 2. Search Index (`search/{document_id}.json`)

Optimized for search functionality:

```json
{
  "document_id": "doc_1705235400",
  "searchable_items": [
    {
      "id": "item_001",
      "text": "PT-1",
      "type": "pattern",
      "category": "Paint/Coating",
      "page": 1,
      "context": "Apply PT-1 coating to all exposed surfaces",
      "search_terms": ["PT-1", "PT1", "paint", "coating"]
    }
  ],
  "page_summaries": [
    {
      "page": 1,
      "summary": "Foundation specifications with PT-1 coating requirements",
      "key_terms": ["foundation", "PT-1", "coating", "specifications"]
    }
  ]
}
```

### 3. Pattern Summary (`patterns/{document_id}.json`)

Statistical analysis of found patterns:

```json
{
  "document_id": "doc_1705235400",
  "summary": {
    "total_items": 156,
    "unique_items": 47,
    "pattern_count": 12,
    "word_count": 35
  },
  "pattern_counts": {
    "PT-1": 8,
    "M1": 4,
    "M-1": 4,
    "R1": 2
  },
  "word_counts": {
    "specification": 15,
    "material": 12,
    "coating": 8
  },
  "categories": {
    "Paint/Coating": 12,
    "Material": 8,
    "Technical": 27
  }
}
```

---

## 🔧 Integration Examples

### Node.js/Express Integration

```javascript
const axios = require('axios');
const { GoogleAuth } = require('google-auth-library');

class DocumentProcessor {
  constructor() {
    this.auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform']
    });
    this.baseUrl = 'https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow';
  }

  async processDocument(pdfUrl, options = {}) {
    const accessToken = await this.auth.getAccessToken();
    
    const payload = {
      argument: {
        pdfUrl,
        r2Config: {
          bucketName: options.bucketName || 'default-bucket'
        },
        projectID: options.projectId,
        projectFileID: options.fileId,
        webhookUrl: options.webhookUrl
      }
    };

    const response = await axios.post(`${this.baseUrl}/executions`, payload, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    return this.extractExecutionId(response.data.name);
  }

  async checkStatus(executionId) {
    const accessToken = await this.auth.getAccessToken();
    
    const response = await axios.get(`${this.baseUrl}/executions/${executionId}`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });

    return response.data;
  }

  async waitForCompletion(executionId, timeoutMs = 300000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeoutMs) {
      const status = await this.checkStatus(executionId);
      
      if (status.state === 'SUCCEEDED') {
        return status.result;
      } else if (status.state === 'FAILED') {
        throw new Error(`Processing failed: ${status.error?.message}`);
      }
      
      // Wait 10 seconds before checking again
      await new Promise(resolve => setTimeout(resolve, 10000));
    }
    
    throw new Error('Processing timeout');
  }

  extractExecutionId(executionName) {
    return executionName.split('/').pop();
  }
}

// Usage example
async function processDocumentExample() {
  const processor = new DocumentProcessor();
  
  try {
    const executionId = await processor.processDocument(
      'https://example.com/construction-plan.pdf',
      {
        bucketName: 'construction-docs',
        projectId: 'project-123',
        fileId: 'file-456',
        webhookUrl: 'https://your-app.com/api/webhook'
      }
    );
    
    console.log(`Processing started. Execution ID: ${executionId}`);
    
    const result = await processor.waitForCompletion(executionId);
    console.log('Processing completed:', result);
    
  } catch (error) {
    console.error('Error processing document:', error);
  }
}
```

### Python Integration

```python
import asyncio
import aiohttp
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import json

class DocumentProcessor:
    def __init__(self, service_account_file=None):
        if service_account_file:
            self.credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        else:
            # Use default credentials
            from google.auth import default
            self.credentials, _ = default(
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        
        self.base_url = 'https://workflowexecutions-us-central1.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow'

    def get_access_token(self):
        self.credentials.refresh(Request())
        return self.credentials.token

    async def process_document(self, pdf_url, **options):
        access_token = self.get_access_token()
        
        payload = {
            "argument": {
                "pdfUrl": pdf_url,
                "r2Config": {
                    "bucketName": options.get('bucket_name', 'default-bucket')
                }
            }
        }
        
        # Add optional parameters
        if 'project_id' in options:
            payload['argument']['projectID'] = options['project_id']
        if 'file_id' in options:
            payload['argument']['projectFileID'] = options['file_id']
        if 'webhook_url' in options:
            payload['argument']['webhookUrl'] = options['webhook_url']

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.base_url}/executions',
                json=payload,
                headers=headers
            ) as response:
                data = await response.json()
                return data['name'].split('/')[-1]  # Extract execution ID

    async def check_status(self, execution_id):
        access_token = self.get_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{self.base_url}/executions/{execution_id}',
                headers=headers
            ) as response:
                return await response.json()

    async def wait_for_completion(self, execution_id, timeout_seconds=300):
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError("Processing timeout")
            
            status = await self.check_status(execution_id)
            
            if status['state'] == 'SUCCEEDED':
                return status['result']
            elif status['state'] == 'FAILED':
                error_msg = status.get('error', {}).get('message', 'Unknown error')
                raise Exception(f"Processing failed: {error_msg}")
            
            await asyncio.sleep(10)  # Wait 10 seconds

# Usage example
async def main():
    processor = DocumentProcessor()
    
    try:
        execution_id = await processor.process_document(
            'https://example.com/construction-plan.pdf',
            bucket_name='construction-docs',
            project_id='project-123',
            file_id='file-456',
            webhook_url='https://your-app.com/api/webhook'
        )
        
        print(f"Processing started. Execution ID: {execution_id}")
        
        result = await processor.wait_for_completion(execution_id)
        print("Processing completed:", json.dumps(result, indent=2))
        
    except Exception as error:
        print(f"Error processing document: {error}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ❌ Error Handling

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input parameters |
| 401 | Unauthorized - Invalid or missing authentication |
| 403 | Forbidden - Insufficient permissions |
| 408 | Timeout - Processing took too long |
| 500 | Internal Server Error |

### Error Response Format

```json
{
  "error": {
    "code": 400,
    "message": "Missing required fields: pdfUrl and r2Config are required",
    "status": "INVALID_ARGUMENT"
  }
}
```

### Common Error Scenarios

#### Invalid PDF URL
```json
{
  "error": {
    "code": 400,
    "message": "Invalid PDF URL: URL must be HTTPS and end with .pdf"
  }
}
```

#### Processing Timeout
```json
{
  "error": {
    "code": 408,
    "message": "PDF processing timed out - document may be too large or complex"
  }
}
```

#### Authentication Error
```json
{
  "error": {
    "code": 401,
    "message": "Request had invalid authentication credentials"
  }
}
```

#### R2 Upload Failed
```json
{
  "error": {
    "code": 500,
    "message": "R2 upload failed - check bucket name and permissions"
  }
}
```

---

## ⚡ Performance Guidelines

### Processing Times
- **Small PDFs (1-5 pages)**: 30-60 seconds
- **Medium PDFs (6-20 pages)**: 1-3 minutes
- **Large PDFs (21-50 pages)**: 3-8 minutes
- **Very Large PDFs (50+ pages)**: 8-15 minutes

### Optimization Tips

1. **Use Webhooks**: Instead of polling, use webhooks for real-time notifications
2. **Batch Processing**: Process multiple documents concurrently
3. **File Size**: Optimize PDF file sizes before processing
4. **Retry Logic**: Implement exponential backoff for failed requests
5. **Caching**: Cache results to avoid reprocessing the same documents

### Rate Limits
- **Concurrent Executions**: 10 simultaneous workflow executions
- **Request Rate**: No specific rate limits, but avoid excessive polling
- **File Size**: Maximum 100MB per PDF file

---

## 🔒 Security Best Practices

### Authentication
- Use service accounts for production environments
- Regularly rotate service account keys
- Store credentials securely (environment variables, secret managers)
- Use principle of least privilege for IAM roles

### Data Privacy
- PDFs are temporarily stored in Google Cloud Storage (auto-deleted after 1 day)
- Processed results are stored in your specified R2 bucket
- No data is retained by the pipeline after processing
- Use HTTPS URLs for all PDF sources

### Webhook Security
- Use HTTPS endpoints for webhooks
- Validate webhook payloads
- Implement proper authentication for webhook endpoints
- Consider using webhook signatures for verification

---

## 🐛 Troubleshooting

### Common Issues

#### "Invalid PDF URL" Error
**Cause**: PDF URL doesn't meet format requirements
**Solution**: Ensure URL is HTTPS and ends with `.pdf`

#### "Processing Timeout" Error
**Cause**: Document is too large or complex
**Solution**: 
- Reduce PDF file size
- Split large documents into smaller parts
- Contact support for processing limits

#### "Authentication Failed" Error
**Cause**: Invalid or expired access token
**Solution**:
- Refresh your access token
- Check service account permissions
- Verify project access

#### "R2 Upload Failed" Error
**Cause**: R2 bucket configuration issues
**Solution**:
- Verify bucket name and permissions
- Check R2 credentials in Secret Manager
- Ensure bucket exists and is accessible

### Debug Information

Enable debug logging by checking the workflow execution details:

```bash
gcloud workflows executions describe EXECUTION_ID \
  --workflow=pdf-processing-workflow \
  --location=us-central1 \
  --format="value(error)"
```

---

## 📞 Support

### Resources
- **Documentation**: This integration guide
- **Test Scripts**: Available in `/scripts/` directory
- **Example PDFs**: Test with provided sample documents

### Getting Help
1. Check the troubleshooting section above
2. Review workflow execution logs in Google Cloud Console
3. Test with the provided sample documents
4. Contact your system administrator

### Sample Test Document
Use this document for testing your integration:
```
URL: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf
Expected patterns: 8×"PT-1", 4×"M1", 4×"M-1"
Pages: 24
Expected processing time: 2-3 minutes
```

---

## 🔄 Changelog

### Version 1.0 (2025-01-14)
- Initial release
- Core PDF processing functionality
- Pattern recognition for technical documents
- R2 storage integration
- Webhook support
- Comprehensive error handling

---

*This integration guide covers the complete functionality of the GCP Document Processing Pipeline. For additional technical details, refer to the source code in the repository.* 