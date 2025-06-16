#!/bin/bash

# Interactive PDF Processing Test
# Allows user to input any PDF URL for testing
set -e

PROJECT_ID="ladders-doc-pipeline-462921"
WORKFLOW_NAME="pdf-processing-workflow"
REGION="us-central1"
R2_BUCKET="ladders-1"

# Mock project data for testing
MOCK_PROJECT_ID="test-project-$(date +%s)"
MOCK_PROJECT_FILE_ID="file-$(date +%s)"
MOCK_WEBHOOK_URL="https://webhook.site/$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -d'-' -f1)"

echo "🎯 Interactive PDF Processing Test"
echo "================================="
echo "Project: ${PROJECT_ID}"
echo "Test Project ID: ${MOCK_PROJECT_ID}"
echo "Test File ID: ${MOCK_PROJECT_FILE_ID}"
echo "Test Webhook: ${MOCK_WEBHOOK_URL}"
echo ""

# Get PDF URL from user
echo "📄 Enter the PDF URL to test:"
read -p "URL: " PDF_URL

if [[ -z "$PDF_URL" ]]; then
    echo "❌ Error: PDF URL cannot be empty"
    exit 1
fi

echo ""
echo "🔍 Testing with PDF: $PDF_URL"
echo ""

# Set the active project
gcloud config set project ${PROJECT_ID}

# Create test payload - R2 credentials will be loaded by the function from Secret Manager
TEST_PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "${PDF_URL}",
  "projectID": "${MOCK_PROJECT_ID}",
  "projectFileID": "${MOCK_PROJECT_FILE_ID}",
  "webhookUrl": "${MOCK_WEBHOOK_URL}",
  "r2Config": {
    "bucketName": "${R2_BUCKET}"
  }
}
EOF
)

echo "🚀 Starting test..."
echo "=================="

# Record start time
TEST_START_TIME=$(date +%s)

# Execute the workflow
echo "⏱️  Starting workflow execution..."
EXECUTION_OUTPUT=$(gcloud workflows run ${WORKFLOW_NAME} \
  --location=${REGION} \
  --data="${TEST_PAYLOAD}" \
  --format="value(name)")

EXECUTION_ID=$(echo "${EXECUTION_OUTPUT}" | rev | cut -d'/' -f1 | rev)

echo "📊 Workflow execution started!"
echo "Execution ID: ${EXECUTION_ID}"
echo ""

# Monitor execution
echo "🔍 Monitoring execution progress..."
echo ""

# Poll for completion
for i in {1..20}; do
  echo "📋 Checking execution status (${i}/20)..."
  
  EXECUTION_STATE=$(gcloud workflows executions describe ${EXECUTION_ID} \
    --workflow=${WORKFLOW_NAME} \
    --location=${REGION} \
    --format="value(state)")
  
  echo "   Current state: ${EXECUTION_STATE}"
  
  if [[ "${EXECUTION_STATE}" == "SUCCEEDED" ]]; then
    TEST_END_TIME=$(date +%s)
    TOTAL_TIME=$((TEST_END_TIME - TEST_START_TIME))
    
    echo ""
    echo "🎉 SUCCESS! Processing completed in ${TOTAL_TIME} seconds!"
    echo "=========================================="
    
    # Get the detailed result
    RESULT=$(gcloud workflows executions describe ${EXECUTION_ID} \
      --workflow=${WORKFLOW_NAME} \
      --location=${REGION} \
      --format="value(result)")
    
    echo ""
    echo "📄 Results Summary:"
    echo "=================="
    
    # Parse key metrics from result
    DOCUMENT_ID=$(echo "${RESULT}" | jq -r '.document_id // "unknown"')
    PROCESSING_TIME=$(echo "${RESULT}" | jq -r '.processing_time // "unknown"')
    
    echo "Document ID: ${DOCUMENT_ID}"
    echo "Processing Time: ${PROCESSING_TIME} seconds"
    echo "Total Time: ${TOTAL_TIME} seconds"
    
    # Check if result contains processing details
    if echo "${RESULT}" | jq -e '.result.result' > /dev/null; then
      ITEMS_FOUND=$(echo "${RESULT}" | jq -r '.result.result.items_found // 0')
      UNIQUE_ITEMS=$(echo "${RESULT}" | jq -r '.result.result.unique_items // 0')
      TOTAL_PAGES=$(echo "${RESULT}" | jq -r '.result.result.total_pages // 0')
      
      echo ""
      echo "📊 Processing Results:"
      echo "   Total Items: ${ITEMS_FOUND}"
      echo "   Unique Items: ${UNIQUE_ITEMS}"
      echo "   Total Pages: ${TOTAL_PAGES}"
    fi
    
    # Show file URLs
    echo ""
    echo "🔗 Generated Files:"
    echo "   📄 Main Document: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/projects/${MOCK_PROJECT_ID}/documents/${DOCUMENT_ID}.json"
    echo "   📋 Summary: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/projects/${MOCK_PROJECT_ID}/summaries/${DOCUMENT_ID}.json"
    echo "   🔔 Webhook: ${MOCK_WEBHOOK_URL}"
    
    break
    
  elif [[ "${EXECUTION_STATE}" == "FAILED" ]]; then
    echo ""
    echo "❌ FAILED! Workflow execution failed."
    echo "===================================="
    
    # Get the detailed error
    ERROR=$(gcloud workflows executions describe ${EXECUTION_ID} \
      --workflow=${WORKFLOW_NAME} \
      --location=${REGION} \
      --format="value(error)")
    
    echo ""
    echo "🚨 Error Details:"
    echo "${ERROR}"
    
    # Check Cloud Function logs for more details
    echo ""
    echo "🔍 Recent Cloud Function Logs:"
    echo "------------------------------"
    gcloud functions logs read pdf-processor --region=us-central1 --limit=10
    
    break
    
  elif [[ "${EXECUTION_STATE}" == "ACTIVE" ]]; then
    echo "   ⏳ Still processing... waiting 30 seconds"
    sleep 30
  else
    echo "   🤔 Unexpected state: ${EXECUTION_STATE}"
    sleep 10
  fi
done

echo ""
echo "🔗 Debugging Links:"
echo "=================="
echo "Workflow Execution: https://console.cloud.google.com/workflows/workflow/${REGION}/${WORKFLOW_NAME}/execution/${EXECUTION_ID}?project=${PROJECT_ID}"
echo "Cloud Function: https://console.cloud.google.com/functions/details/${REGION}/pdf-processor?project=${PROJECT_ID}"
echo "Function Logs: https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloud_function%22%20resource.labels.function_name%3D%22pdf-processor%22?project=${PROJECT_ID}"

echo ""
echo "🏁 Test completed!"
echo "" 