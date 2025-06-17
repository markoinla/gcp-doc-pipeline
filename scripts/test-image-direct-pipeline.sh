#!/bin/bash

# Test script for Image Direct Pipeline
# Tests various scenarios for the new image processing endpoint

set -e

echo "🚀 Testing Image Direct Pipeline"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOCAL_FUNCTION_URL="http://localhost:8080"
CLOUD_FUNCTION_URL="https://us-central1-my-project.cloudfunctions.net/image-vision-pipeline"

# Use local by default, cloud if --cloud flag is passed
FUNCTION_URL="$LOCAL_FUNCTION_URL"
if [[ "$*" == *"--cloud"* ]]; then
    FUNCTION_URL="$CLOUD_FUNCTION_URL"
    echo "Testing against Cloud Function: $FUNCTION_URL"
else
    echo "Testing against Local Function: $FUNCTION_URL"
fi

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local json_payload="$2"
    local expected_pattern="$3"
    
    echo -e "\n${YELLOW}Test: $test_name${NC}"
    echo "Payload: $json_payload"
    
    # Make request and capture response
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$FUNCTION_URL" 2>/dev/null)
    
    # Extract HTTP status and body
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo "HTTP Status: $http_status"
    echo "Response: $response_body"
    
    # Check if test passed
    if [[ "$http_status" == "200" ]] && [[ "$response_body" == *"$expected_pattern"* ]]; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAILED${NC}"
        ((TESTS_FAILED++))
    fi
}

run_error_test() {
    local test_name="$1"
    local json_payload="$2"
    local expected_error="$3"
    
    echo -e "\n${YELLOW}Error Test: $test_name${NC}"
    echo "Payload: $json_payload"
    
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$FUNCTION_URL" 2>/dev/null)
    
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    response_body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo "HTTP Status: $http_status"
    echo "Response: $response_body"
    
    if [[ "$http_status" == "400" ]] || [[ "$http_status" == "500" ]] && [[ "$response_body" == *"$expected_error"* ]]; then
        echo -e "${GREEN}✅ PASSED (Error handled correctly)${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAILED (Expected error not returned)${NC}"
        ((TESTS_FAILED++))
    fi
}

echo -e "\n${YELLOW}=== BASIC FUNCTIONALITY TESTS ===${NC}"

# Test 1: Single Image URL
run_test "1. Single Image URL" \
'{
  "images": [
    {
      "url": "https://example.com/sample-document.jpg",
      "pageNumber": 1
    }
  ],
  "projectID": "test-project",
  "fileID": "test-single-image"
}' \
'"success"'

# Test 2: Multiple Image URLs (Parallel Processing)
run_test "2. Multiple Image URLs" \
'{
  "images": [
    {
      "url": "https://example.com/doc-page1.jpg",
      "pageNumber": 1
    },
    {
      "url": "https://example.com/doc-page2.jpg", 
      "pageNumber": 2
    },
    {
      "url": "https://example.com/doc-page3.jpg",
      "pageNumber": 3
    }
  ],
  "projectID": "test-project",
  "fileID": "test-multiple-images",
  "parallelWorkers": 10
}' \
'"total_images": 3'

# Test 3: Base64 Image Data
run_test "3. Base64 Image Data" \
'{
  "images": [
    {
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/8A",
      "pageNumber": 1
    }
  ],
  "projectID": "test-project",
  "fileID": "test-base64-image"
}' \
'"success"'

# Test 4: Mixed URL and Base64
run_test "4. Mixed URL and Base64" \
'{
  "images": [
    {
      "url": "https://example.com/doc-page1.jpg",
      "pageNumber": 1
    },
    {
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/8A",
      "pageNumber": 2
    }
  ],
  "projectID": "test-project",
  "fileID": "test-mixed-input"
}' \
'"total_images": 2'

# Test 5: Custom Configuration
run_test "5. Custom Configuration" \
'{
  "images": [
    {
      "url": "https://example.com/doc.jpg",
      "pageNumber": 1
    }
  ],
  "projectID": "test-project",
  "fileID": "test-custom-config",
  "chunkSize": 3,
  "parallelWorkers": 20,
  "bucket": "custom-bucket"
}' \
'"success"'

echo -e "\n${YELLOW}=== ERROR HANDLING TESTS ===${NC}"

# Error Test 1: Missing images array
run_error_test "E1. Missing images array" \
'{
  "projectID": "test-project"
}' \
"images array is required"

# Error Test 2: Empty images array  
run_error_test "E2. Empty images array" \
'{
  "images": [],
  "projectID": "test-project"
}' \
"images array cannot be empty"

# Error Test 3: Invalid image spec
run_error_test "E3. Invalid image spec" \
'{
  "images": [
    {
      "pageNumber": 1
    }
  ],
  "projectID": "test-project"
}' \
"must have"

# Error Test 4: Too many images
run_error_test "E4. Too many images" \
'{
  "images": '$(python3 -c "
import json
images = [{'url': f'https://example.com/page{i}.jpg', 'pageNumber': i} for i in range(1, 52)]
print(json.dumps(images))
")',
  "projectID": "test-project"
}' \
"Too many images"

# Error Test 5: Invalid chunk size
run_error_test "E5. Invalid chunk size" \
'{
  "images": [{"url": "https://example.com/test.jpg", "pageNumber": 1}],
  "chunkSize": 20
}' \
"chunkSize must be between"

# Error Test 6: Invalid parallel workers
run_error_test "E6. Invalid parallel workers" \
'{
  "images": [{"url": "https://example.com/test.jpg", "pageNumber": 1}],
  "parallelWorkers": 100
}' \
"parallelWorkers must be between"

echo -e "\n${YELLOW}=== PERFORMANCE TESTS ===${NC}"

# Performance Test: Large batch processing
echo -e "\n${YELLOW}Performance Test: Processing 10 images${NC}"
start_time=$(date +%s)

curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"url": "https://example.com/p1.jpg", "pageNumber": 1},
      {"url": "https://example.com/p2.jpg", "pageNumber": 2},
      {"url": "https://example.com/p3.jpg", "pageNumber": 3},
      {"url": "https://example.com/p4.jpg", "pageNumber": 4},
      {"url": "https://example.com/p5.jpg", "pageNumber": 5},
      {"url": "https://example.com/p6.jpg", "pageNumber": 6},
      {"url": "https://example.com/p7.jpg", "pageNumber": 7},
      {"url": "https://example.com/p8.jpg", "pageNumber": 8},
      {"url": "https://example.com/p9.jpg", "pageNumber": 9},
      {"url": "https://example.com/p10.jpg", "pageNumber": 10}
    ],
    "projectID": "performance-test",
    "parallelWorkers": 30
  }' \
  "$FUNCTION_URL" > /dev/null

end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Performance test completed in ${duration} seconds"

echo -e "\n${YELLOW}=== TEST SUMMARY ===${NC}"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}💥 Some tests failed!${NC}"
    exit 1
fi 