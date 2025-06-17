#!/bin/bash

# Quick API Test - Simple one-liner style test
echo "🚀 Quick API Test - $(date)"

curl -X POST "https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/pdf-vision-pipeline" \
  -H "Content-Type: application/json" \
  -d '{
    "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf",
    "projectID": "quick-test",
    "fileID": "test-'$(date +%s)'",
    "chunkSize": 2,
    "parallelWorkers": 15
  }' \
  --max-time 180 | python3 -m json.tool

echo ""
echo "✅ Quick test completed - $(date)" 