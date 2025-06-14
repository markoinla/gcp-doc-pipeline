#!/bin/bash

echo "🧪 Testing PDF Chunking with Real R2 Config..."

# Real R2 configuration
gcloud workflows run pdf-processing-workflow \
  --location=us-central1 \
  --data='{
    "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf",
    "callbackUrl": "https://webhook.site/your-callback-url",
    "r2Config": {
      "bucket": "ladders-1",
      "endpoint": "https://6bbed442aa5feaffa4526109ffdb3629.r2.cloudflarestorage.com",
      "accessKey": "stored-in-secrets",
      "secretKey": "stored-in-secrets"
    }
  }'

echo "✅ Workflow started - check logs for results!"
echo "Expected patterns: PT-1: 8, M1: 13, M-1: 3" 