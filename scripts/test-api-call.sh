#!/bin/bash

# Simple Production API Test
# Mimics the actual API call your application would make

set -e

echo "🧪 PRODUCTION API TEST"
echo "====================="

# Configuration - modify these for your actual use case
FUNCTION_URL="https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/pdf-vision-pipeline"
PDF_URL="https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/ebGames%20-%20White%20Oaks(ARCH).pdf"
PROJECT_ID="my-project-123"
FILE_ID="document-$(date +%s)"
CHUNK_SIZE=3
PARALLEL_WORKERS=15

echo "📋 API Call Configuration:"
echo "   🔗 Endpoint: $FUNCTION_URL"
echo "   📄 PDF: $PDF_URL"
echo "   📁 Project: $PROJECT_ID"
echo "   📋 File ID: $FILE_ID"
echo "   📦 Chunk Size: $CHUNK_SIZE (OPTIMIZED ⚡)"
echo "   👥 Parallel Workers: $PARALLEL_WORKERS (OPTIMIZED ⚡)"
echo "   🚀 Client Pooling: ENABLED (Connection Reuse)"
echo ""

# Create the API payload
API_PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "$PDF_URL",
  "projectID": "$PROJECT_ID",
  "fileID": "$FILE_ID",
  "chunkSize": $CHUNK_SIZE,
  "parallelWorkers": $PARALLEL_WORKERS
}
EOF
)

echo "📤 API Request Payload:"
echo "$API_PAYLOAD" | python3 -m json.tool
echo ""

echo "🚀 Making API call..."
echo "⏱️  Start: $(date)"
START_TIME=$(date +%s)

# Make the API call
RESPONSE=$(curl -s -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyApp/1.0" \
  -d "$API_PAYLOAD" \
  --max-time 300 \
  --connect-timeout 10)

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "⏱️  End: $(date)"
echo "⏱️  Duration: ${DURATION}s"
echo ""

# Parse and display response
echo "📋 API Response:"
echo "==============="

# Check if response is valid JSON
if echo "$RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "✅ Valid JSON response received"
    echo ""
    
    # Pretty print the response
    echo "$RESPONSE" | python3 -m json.tool
    echo ""
    
    # Extract key metrics
    echo "🎯 KEY RESULTS:"
    echo "==============="
    
    SUCCESS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null || echo "false")
    TOTAL_PAGES=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_pages', 'N/A'))" 2>/dev/null || echo "N/A")
    PROCESSED_PAGES=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('processed_pages', 'N/A'))" 2>/dev/null || echo "N/A")
    FAILED_PAGES=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('failed_pages', [])))" 2>/dev/null || echo "N/A")
    FINAL_JSON_URL=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('final_json_url', ''))" 2>/dev/null || echo "")
    
    echo "   ✅ Success: $SUCCESS"
    echo "   📄 Total Pages: $TOTAL_PAGES"
    echo "   ✅ Processed: $PROCESSED_PAGES"
    echo "   ❌ Failed: $FAILED_PAGES"
    echo "   🔗 Final JSON: $FINAL_JSON_URL"
    echo ""
    
    # Test final JSON accessibility
    if [ -n "$FINAL_JSON_URL" ] && [ "$FINAL_JSON_URL" != "null" ]; then
        echo "🔍 Testing Final JSON Access:"
        if curl -s -I "$FINAL_JSON_URL" | grep -q "200 OK"; then
            echo "   ✅ Final JSON is accessible"
            
            # Get pattern count from final JSON
            PATTERN_COUNT=$(curl -s "$FINAL_JSON_URL" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total = data['processing_metadata']['statistics']['total_patterns_found']
    print(total)
except:
    print('N/A')
" 2>/dev/null || echo "N/A")
            
            echo "   🎯 Total Patterns Found: $PATTERN_COUNT"
        else
            echo "   ❌ Final JSON not accessible"
        fi
    fi
    
    echo ""
    if [ "$SUCCESS" = "True" ] || [ "$SUCCESS" = "true" ]; then
        echo "🏆 API TEST: ✅ SUCCESS!"
    else
        echo "🏆 API TEST: ❌ FAILED!"
    fi
    
else
    echo "❌ Invalid JSON response or error occurred"
    echo ""
    echo "Raw Response:"
    echo "$RESPONSE"
    echo ""
    echo "🏆 API TEST: ❌ FAILED!"
fi

echo ""
echo "📊 SUMMARY:"
echo "==========="
echo "   ⏱️  Total API call time: ${DURATION}s"
echo "   🔗 Endpoint tested: $FUNCTION_URL"
echo "   📄 Document processed: $(basename "$PDF_URL")"
echo "   📁 Project: $PROJECT_ID"
echo "   📋 File: $FILE_ID" 