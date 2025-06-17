#!/bin/bash

# Test Production PDF Vision Pipeline
# Tests the deployed Cloud Function with real PDF processing

set -e

echo "🧪 TESTING PRODUCTION PDF VISION PIPELINE"
echo "=========================================="

# Configuration
FUNCTION_URL="https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/pdf-vision-pipeline"
TEST_PDF_URL="https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
PROJECT_ID="prod-test-$(date +%s)"
FILE_ID="test-file-$(date +%s)"

echo "📋 Test Configuration:"
echo "   🔗 Function URL: $FUNCTION_URL"
echo "   📄 PDF URL: $TEST_PDF_URL"
echo "   📁 Project ID: $PROJECT_ID"
echo "   📋 File ID: $FILE_ID"
echo ""

# Create test payload
TEST_PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "$TEST_PDF_URL",
  "projectID": "$PROJECT_ID",
  "fileID": "$FILE_ID",
  "chunkSize": 2
}
EOF
)

echo "🚀 Starting production test..."
echo "⏱️  Start time: $(date)"
START_TIME=$(date +%s)

# Make the request
echo ""
echo "📤 Sending request to Cloud Function..."
TEMP_FILE=$(mktemp)
HTTP_CODE=$(curl -s -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d "$TEST_PAYLOAD" \
  -w "%{http_code}" \
  -o "$TEMP_FILE")

RESPONSE_BODY=$(cat "$TEMP_FILE")
rm "$TEMP_FILE"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "📊 PRODUCTION TEST RESULTS:"
echo "=========================="
echo "⏱️  Total time: ${DURATION}s"
echo "🌐 HTTP Status: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ SUCCESS! Function executed successfully"
    echo ""
    echo "📋 Response Details:"
    echo "$RESPONSE_BODY" | python3 -m json.tool
    
    # Extract key metrics from response
    echo ""
    echo "🎯 KEY METRICS:"
    TOTAL_PAGES=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_pages', 'N/A'))")
    PROCESSED_PAGES=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('processed_pages', 'N/A'))")
    PROCESSING_TIME=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('processing_time_seconds', 'N/A'))")
    
    echo "   📄 Total pages: $TOTAL_PAGES"
    echo "   ✅ Processed pages: $PROCESSED_PAGES"
    echo "   ⚡ Processing time: ${PROCESSING_TIME}s"
    echo "   🚀 Pages per second: $(python3 -c "print(round($PROCESSED_PAGES / $PROCESSING_TIME, 2) if '$PROCESSING_TIME' != 'N/A' and float('$PROCESSING_TIME') > 0 else 'N/A')")"
    
    # Test R2 URLs
    echo ""
    echo "🔗 Testing R2 URLs..."
    FINAL_JSON_URL=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('final_json_url', ''))")
    if [ -n "$FINAL_JSON_URL" ]; then
        echo "   📄 Final JSON URL: $FINAL_JSON_URL"
        if curl -s -I "$FINAL_JSON_URL" | grep -q "200 OK"; then
            echo "   ✅ Final JSON accessible"
        else
            echo "   ❌ Final JSON not accessible"
        fi
    fi
    
    echo ""
    echo "🏆 PRODUCTION PIPELINE: ✅ SUCCESS!"
    
else
    echo "❌ FAILED! HTTP Status: $HTTP_CODE"
    echo ""
    echo "📋 Error Response:"
    echo "$RESPONSE_BODY"
    echo ""
    echo "🏆 PRODUCTION PIPELINE: ❌ FAILED!"
fi

echo ""
echo "⏱️  End time: $(date)" 