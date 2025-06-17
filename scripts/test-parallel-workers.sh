#!/bin/bash

# Test script to compare different parallelWorkers values (CONCURRENT VERSION)
# Usage: ./scripts/test-parallel-workers.sh

set -e

FUNCTION_URL="https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/pdf-vision-pipeline"
PDF_URL="https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"

echo "🧪 TESTING PARALLEL WORKERS PARAMETER (CONCURRENT LOAD TEST)"
echo "============================================================"
echo "📄 PDF: Boathouse - WhiteOaks (18 pages)"
echo "🔗 Function: pdf-vision-pipeline"
echo "🚀 Running ALL tests concurrently to test load handling"
echo ""

# Test configurations
declare -a WORKER_CONFIGS=(
    "15:2"
)

# Create temp directory for storing results
TEMP_DIR=$(mktemp -d)
declare -a PIDS=()
declare -a TEST_NAMES=()

echo "🚀 Starting all tests concurrently at $(date '+%H:%M:%S')"
echo ""

# Start all tests in background
for i in "${!WORKER_CONFIGS[@]}"; do
    config="${WORKER_CONFIGS[$i]}"
    IFS=':' read -r workers chunk_size <<< "$config"
    
    test_name="workers-${workers}_chunk-${chunk_size}"
    TEST_NAMES+=("$test_name")
    
    echo "🔧 Starting: ${workers} workers, chunk_size ${chunk_size}"
    
    # Run test in background, storing results to temp file
    {
        start_time=$(date +%s)
        
        # Make API call with specific worker configuration
        response=$(curl -s -X POST "$FUNCTION_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"pdfUrl\": \"$PDF_URL\",
                \"projectID\": \"test-workers-${workers}\",
                \"fileID\": \"test-$(date +%s)-${workers}w\",
                \"parallelWorkers\": $workers,
                \"chunkSize\": $chunk_size
            }")
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        # Store results in temp file
        echo "{
            \"workers\": $workers,
            \"chunk_size\": $chunk_size,
            \"start_time\": $start_time,
            \"end_time\": $end_time,
            \"duration\": $duration,
            \"response\": $response
        }" > "$TEMP_DIR/${test_name}.json"
        
    } &
    
    PIDS+=($!)
done

echo "⏳ Waiting for all ${#WORKER_CONFIGS[@]} tests to complete..."
echo ""

# Wait for all background processes to complete
for pid in "${PIDS[@]}"; do
    wait "$pid"
done

overall_end_time=$(date +%s)
echo "🏁 All tests completed at $(date '+%H:%M:%S')"
echo ""

# Display results
echo "📊 CONCURRENT TEST RESULTS:"
echo "=========================="

for test_name in "${TEST_NAMES[@]}"; do
    if [ -f "$TEMP_DIR/${test_name}.json" ]; then
        # Parse test results
        test_data=$(cat "$TEMP_DIR/${test_name}.json")
        workers=$(echo "$test_data" | jq -r '.workers')
        chunk_size=$(echo "$test_data" | jq -r '.chunk_size')
        duration=$(echo "$test_data" | jq -r '.duration')
        response=$(echo "$test_data" | jq -r '.response')
        
        # Parse API response
        success=$(echo "$response" | jq -r '.success // false')
        processing_time=$(echo "$response" | jq -r '.processing_time_seconds // 0')
        total_pages=$(echo "$response" | jq -r '.total_pages // 0')
        processed_pages=$(echo "$response" | jq -r '.processed_pages // 0')
        
        echo "🔧 Config: ${workers} workers, chunk_size ${chunk_size}"
        if [ "$success" = "true" ]; then
            echo "   ✅ SUCCESS: ${processed_pages}/${total_pages} pages processed"
            echo "   ⏱️  Total time: ${duration}s (API response time)"
            echo "   🔄 Processing time: ${processing_time}s (internal processing)"
            if [ "$total_pages" -gt 0 ]; then
                avg_per_page=$(echo "scale=2; $processing_time / $total_pages" | bc)
                echo "   📊 Average per page: ${avg_per_page}s"
            fi
        else
            echo "   ❌ FAILED"
            error_msg=$(echo "$response" | jq -r '.error // "Unknown error"')
            echo "   Error: $error_msg"
        fi
        echo ""
    else
        echo "❌ Missing results for $test_name"
        echo ""
    fi
done

echo "📈 LOAD TEST SUMMARY:"
echo "- Ran ${#WORKER_CONFIGS[@]} concurrent API calls to test function load handling"
echo "- All tests started simultaneously to create realistic load conditions"
echo "- Compare both individual performance and system behavior under load"
echo "- Previous optimal: 15 workers + chunk_size 2"
echo ""

# Cleanup temp directory
rm -rf "$TEMP_DIR"

echo "🧹 Cleanup completed!" 