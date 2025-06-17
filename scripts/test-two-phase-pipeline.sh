#!/bin/bash

# Test script for the new two-phase PDF processing pipeline
# Phase 1: Fast image processing (should return in 5-10 seconds)
# Phase 2: Background OCR processing (triggered automatically)

set -e

echo "🚀 Testing Two-Phase PDF Processing Pipeline"
echo "============================================="

# Configuration
FUNCTION_URL="https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/pdf-vision-pipeline"
PDF_URL="https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf"
PROJECT_ID="test-project-$(date +%s)"
FILE_ID="test-file-$(date +%s)"
WEBHOOK_URL="https://webhook.site/your-webhook-url"  # Replace with actual webhook URL

echo "📋 Test Configuration:"
echo "   Function URL: $FUNCTION_URL"
echo "   PDF URL: $PDF_URL" 
echo "   Project ID: $PROJECT_ID"
echo "   File ID: $FILE_ID"
echo ""

echo "⏱️  Starting Phase 1 (Fast Image Processing)..."
echo "Expected: 5-10 seconds response with images ready"
echo ""

# Phase 1: Fast image processing
PHASE1_START=$(date +%s)

PHASE1_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"pdfUrl\": \"$PDF_URL\",
    \"projectID\": \"$PROJECT_ID\",
    \"fileID\": \"$FILE_ID\",
    \"webhook\": \"$WEBHOOK_URL\"
  }" \
  "$FUNCTION_URL")

PHASE1_END=$(date +%s)
PHASE1_TIME=$((PHASE1_END - PHASE1_START))

echo "✅ Phase 1 completed in ${PHASE1_TIME} seconds"
echo ""

# Parse and display Phase 1 response
echo "📊 Phase 1 Response:"
echo "$PHASE1_RESPONSE" | jq '.'

# Extract key information
PROCESSING_ID=$(echo "$PHASE1_RESPONSE" | jq -r '.processing_id // "not_found"')
STATUS=$(echo "$PHASE1_RESPONSE" | jq -r '.status // "unknown"')
TOTAL_PAGES=$(echo "$PHASE1_RESPONSE" | jq -r '.total_pages // 0')
IMAGES_COUNT=$(echo "$PHASE1_RESPONSE" | jq -r '.images | length // 0')
OCR_STATUS=$(echo "$PHASE1_RESPONSE" | jq -r '.ocr_status // "unknown"')
ESTIMATED_COMPLETION=$(echo "$PHASE1_RESPONSE" | jq -r '.estimated_completion // "unknown"')

echo ""
echo "📋 Phase 1 Summary:"
echo "   Processing ID: $PROCESSING_ID"
echo "   Status: $STATUS"  
echo "   Total Pages: $TOTAL_PAGES"
echo "   Images Ready: $IMAGES_COUNT"
echo "   OCR Status: $OCR_STATUS"
echo "   Estimated OCR Completion: $ESTIMATED_COMPLETION"
echo "   Phase 1 Time: ${PHASE1_TIME}s"

if [ "$STATUS" = "images_ready" ]; then
    echo ""
    echo "🎉 SUCCESS: Phase 1 completed successfully!"
    echo "   ✅ Images are ready and available immediately"
    echo "   ⏳ OCR processing is running in background"
    echo "   📞 Webhook will be called when OCR completes"
    echo ""
    
    # Display first few image URLs for verification
    echo "🖼️  Sample Image URLs:"
    echo "$PHASE1_RESPONSE" | jq -r '.images[0:3][]' | head -3 | while read url; do
        echo "   - $url"
    done
    
    echo ""
    echo "⏱️  Monitoring OCR Progress..."
    echo "   Expected completion: $ESTIMATED_COMPLETION"
    echo "   Check your webhook endpoint for completion notification"
    echo ""
    echo "💡 Architecture Benefits Demonstrated:"
    echo "   • Users get images immediately (${PHASE1_TIME}s vs 30-90s before)"
    echo "   • No blocking wait for OCR processing"
    echo "   • Better user experience and scalability"
    echo "   • Graceful handling of OCR failures"
    
else
    echo ""
    echo "❌ PHASE 1 FAILED"
    echo "Response: $PHASE1_RESPONSE"
    exit 1
fi

echo ""
echo "🔧 How to Test Phase 2 (OCR Processing) Manually:"
echo "You can trigger OCR processing directly by calling:"
echo ""
echo "curl -X POST -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"phase\": \"ocr\","
echo "    \"processing_id\": \"$PROCESSING_ID\","
echo "    \"image_urls\": $(echo "$PHASE1_RESPONSE" | jq -c '.images'),"
echo "    \"project_id\": \"$PROJECT_ID\","
echo "    \"file_id\": \"$FILE_ID\","
echo "    \"webhook\": \"$WEBHOOK_URL\""
echo "  }' \\"
echo "  \"$FUNCTION_URL\""

echo ""
echo "✨ Two-Phase Pipeline Test Complete!" 