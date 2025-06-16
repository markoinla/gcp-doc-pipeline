# PDF Processing API Proxy

A Cloudflare Worker that acts as a secure API proxy for the GCP Document Processing Pipeline.

## Features

- 🔐 **Secure Authentication**: Google Cloud service account credentials stored as encrypted secrets
- 🌍 **Global Edge Performance**: Runs on Cloudflare's 300+ edge locations worldwide
- 🚀 **Auto-scaling**: Serverless architecture with instant scaling
- 🛡️ **CORS Support**: Full CORS handling for frontend integration
- ⚡ **Low Latency**: Sub-50ms response times globally
- 💰 **Cost Effective**: Pay-per-request pricing model

## API Endpoint

```
POST https://cf-api-proxy.YOUR_SUBDOMAIN.workers.dev/
```

## Request Format

```json
{
  "pdfUrl": "https://example.com/document.pdf",
  "projectId": "your-project-123",
  "fileId": "file-456"
}
```

### Parameters

- **pdfUrl** (required): HTTPS URL to the PDF file (must end with `.pdf`)
- **projectId** (optional): Your application's project identifier
- **fileId** (optional): Your application's file identifier

## Response Format

### Success Response
```json
{
  "success": true,
  "executionId": "abc123def456",
  "status": "processing_started",
  "message": "PDF processing has been initiated successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Invalid PDF URL: must be HTTPS and end with .pdf",
  "timestamp": "2025-06-16T20:30:00.000Z"
}
```

## Frontend Usage Examples

### JavaScript/Fetch
```javascript
async function processPDF(pdfUrl, projectId, fileId) {
  const response = await fetch('https://cf-api-proxy.YOUR_SUBDOMAIN.workers.dev/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      pdfUrl,
      projectId,
      fileId
    })
  });

  const result = await response.json();
  
  if (result.success) {
    console.log('Processing started:', result.executionId);
    return result.executionId;
  } else {
    throw new Error(result.error);
  }
}
```

### React Hook
```javascript
import { useState } from 'react';

export function usePDFProcessor() {
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);

  const processPDF = async (pdfUrl, projectId, fileId) => {
    setProcessing(true);
    setError(null);
    
    try {
      const response = await fetch('https://cf-api-proxy.YOUR_SUBDOMAIN.workers.dev/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdfUrl, projectId, fileId })
      });

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error);
      }
      
      return result.executionId;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setProcessing(false);
    }
  };

  return { processPDF, processing, error };
}
```

## Configuration

### Environment Variables
- `R2_BUCKET_NAME`: Target R2 bucket name (default: "ladders-documents")

### Secrets (set with `wrangler secret put`)
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Complete Google Cloud service account JSON key
- `WEBHOOK_BASE_URL` (optional): Base URL for webhook notifications

## Deployment

```bash
# Deploy to Cloudflare Workers
npm run deploy

# Or using wrangler directly
wrangler deploy
```

## Development

```bash
# Install dependencies
npm install

# Start local development server
npm run dev

# Run tests
npm test
```

## Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Missing required field: pdfUrl | PDF URL is required |
| 400 | Invalid PDF URL | URL must be HTTPS and end with .pdf |
| 405 | Method not allowed | Only POST requests are supported |
| 500 | Failed to authenticate with Google Cloud | Service account authentication failed |
| 500 | Workflow API error | Google Cloud Workflow API returned an error |

## Security

- Service account credentials are stored as encrypted Cloudflare secrets
- CORS is properly configured for cross-origin requests
- Input validation prevents malicious requests
- No sensitive data is logged or exposed

## Monitoring

The worker includes built-in observability features:
- Request/response logging
- Error tracking
- Performance metrics
- Cloudflare Analytics integration

## Support

For issues or questions, check the logs in the Cloudflare Workers dashboard or contact your development team. 