#!/bin/bash

# Quick Test Script for Image Direct Pipeline
# Tests the deployed image-vision-pipeline endpoint with real examples

set -e

echo "🧪 Quick Image Pipeline Test"
echo "============================"

# Configuration
ENDPOINT="https://us-central1-ladders-doc-pipeline-462921.cloudfunctions.net/image-vision-pipeline"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Testing endpoint: $ENDPOINT${NC}"
echo ""

# Test 1: Single Image Test
echo -e "${YELLOW}Test 1: Single Image URL${NC}"
echo "Making request..."

response1=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {
        "url": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/images/page-1-53fca0cf-ab0e-49ba-87ca-711329f1c823.jpg",
        "pageNumber": 1
      }
    ],
    "projectID": "quick-test",
    "fileID": "single-image-test"
  }' \
  "$ENDPOINT")

http_status1=$(echo "$response1" | grep "HTTP_STATUS:" | cut -d: -f2)
response_body1=$(echo "$response1" | sed '/HTTP_STATUS:/d')

echo "Status: $http_status1"
if [[ "$http_status1" == "200" ]]; then
  echo -e "${GREEN}✅ Single image test PASSED${NC}"
  echo "Response excerpt: $(echo "$response_body1" | jq -r '.success, .total_images, .processed_images' 2>/dev/null || echo "JSON parsing failed")"
else
  echo -e "${RED}❌ Single image test FAILED${NC}"
  echo "Response: $response_body1"
fi

echo ""

# Test 2: Multiple Images Test
echo -e "${YELLOW}Test 2: Multiple Images (Parallel Processing)${NC}"
echo "Making request with 3 images..."

response2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {
        "url": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/images/page-10-8351711d-d9f0-42b4-a093-fd3a0dcd27cb.jpg",
        "pageNumber": 1
      },
      {
        "url": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/images/page-15-a7634d1e-c8ef-40d9-a739-cad4c28d531e.jpg", 
        "pageNumber": 2
      },
      {
        "url": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/images/page-17-5928593c-9d42-49d6-b717-e6e609f18ac6.jpg",
        "pageNumber": 3
      }
    ],
    "projectID": "02-quick-test",
    "fileID": "multi-image-test",
    "parallelWorkers": 15
  }' \
  "$ENDPOINT")

http_status2=$(echo "$response2" | grep "HTTP_STATUS:" | cut -d: -f2)
response_body2=$(echo "$response2" | sed '/HTTP_STATUS:/d')

echo "Status: $http_status2"
if [[ "$http_status2" == "200" ]]; then
  echo -e "${GREEN}✅ Multiple images test PASSED${NC}"
  echo "Response excerpt: $(echo "$response_body2" | jq -r '.success, .total_images, .processed_images, .processing_time_seconds' 2>/dev/null || echo "JSON parsing failed")"
else
  echo -e "${RED}❌ Multiple images test FAILED${NC}"
  echo "Response: $response_body2"
fi

echo ""

# Test 3: Error Handling Test
echo -e "${YELLOW}Test 3: Error Handling (Empty Images Array)${NC}"
echo "Making request with invalid payload..."

response3=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "images": [],
    "projectID": "quick-test"
  }' \
  "$ENDPOINT")

http_status3=$(echo "$response3" | grep "HTTP_STATUS:" | cut -d: -f2)
response_body3=$(echo "$response3" | sed '/HTTP_STATUS:/d')

echo "Status: $http_status3"
if [[ "$http_status3" == "400" ]] || [[ "$http_status3" == "500" ]]; then
  echo -e "${GREEN}✅ Error handling test PASSED${NC}"
  echo "Error message: $(echo "$response_body3" | jq -r '.error' 2>/dev/null || echo "$response_body3")"
else
  echo -e "${RED}❌ Error handling test FAILED${NC}"
  echo "Response: $response_body3"
fi

echo ""
echo "🏁 Quick Test Complete!"

# Summary
passed=0
total=3

if [[ "$http_status1" == "200" ]]; then ((passed++)); fi
if [[ "$http_status2" == "200" ]]; then ((passed++)); fi
if [[ "$http_status3" == "400" ]] || [[ "$http_status3" == "500" ]]; then ((passed++)); fi

echo ""
echo "📊 Results: $passed/$total tests passed"

if [ $passed -eq $total ]; then
    echo -e "${GREEN}🎉 All tests passed! Your image pipeline is working correctly.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Check the responses above.${NC}"
    exit 1
fi 