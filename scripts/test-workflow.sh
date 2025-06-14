#!/bin/bash

# Test the Google Cloud Workflow with a sample PDF
set -e

PROJECT_ID="ladders-doc-pipeline-462921"
WORKFLOW_NAME="pdf-processing-workflow"
REGION="us-central1"

echo "🧪 Testing Google Cloud Workflow..."
echo "Project: ${PROJECT_ID}"
echo "Workflow: ${WORKFLOW_NAME}"
echo "Region: ${REGION}"
echo ""

# Set the active project
gcloud config set project ${PROJECT_ID}

# Test with a simple validation request first
echo "1. Testing workflow with validation error (should fail)..."
echo ""

gcloud workflows run ${WORKFLOW_NAME} \
  --location=${REGION} \
  --data='{"invalid": "request"}' \
  --format="json" > /tmp/test-result-1.json

echo "✅ Validation test completed. Check result:"
cat /tmp/test-result-1.json | jq -r '.error.message // .result.status'
echo ""

# Test with valid structure but test R2 config
echo "2. Testing workflow with valid structure..."
echo ""

# Note: This will likely fail at R2 upload since we don't have real R2 credentials
# but it should validate the workflow structure and Cloud Function integration
TEST_PAYLOAD='{
  "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf",
  "r2Config": {
    "bucket": "test-bucket",
    "accessKey": "test-access-key",
    "secretKey": "test-secret-key",
    "endpoint": "https://test.r2.cloudflarestorage.com"
  },
  "callbackUrl": "https://test-callback.example.com/webhook"
}'

# Execute the workflow
EXECUTION_ID=$(gcloud workflows run ${WORKFLOW_NAME} \
  --location=${REGION} \
  --data="${TEST_PAYLOAD}" \
  --format="value(name)" | cut -d'/' -f6)

echo "🔄 Workflow execution started with ID: ${EXECUTION_ID}"
echo "Monitoring execution..."
echo ""

# Wait for completion and get result
sleep 5

# Poll for completion
for i in {1..12}; do
  echo "Checking execution status (attempt ${i}/12)..."
  
  EXECUTION_STATE=$(gcloud workflows executions describe ${EXECUTION_ID} \
    --workflow=${WORKFLOW_NAME} \
    --location=${REGION} \
    --format="value(state)")
  
  echo "Current state: ${EXECUTION_STATE}"
  
  if [[ "${EXECUTION_STATE}" == "SUCCEEDED" ]]; then
    echo "✅ Workflow execution succeeded!"
    
    # Get the result
    echo ""
    echo "Execution result:"
    gcloud workflows executions describe ${EXECUTION_ID} \
      --workflow=${WORKFLOW_NAME} \
      --location=${REGION} \
      --format="value(result)" | jq .
    break
  elif [[ "${EXECUTION_STATE}" == "FAILED" ]]; then
    echo "❌ Workflow execution failed."
    
    # Get the error
    echo ""
    echo "Execution error:"
    gcloud workflows executions describe ${EXECUTION_ID} \
      --workflow=${WORKFLOW_NAME} \
      --location=${REGION} \
      --format="value(error)" | jq .
    break
  elif [[ "${EXECUTION_STATE}" == "ACTIVE" ]]; then
    echo "⏳ Still running... waiting 30 seconds"
    sleep 30
  else
    echo "🤔 Unknown state: ${EXECUTION_STATE}"
    break
  fi
done

echo ""
echo "🔗 View execution in Cloud Console:"
echo "https://console.cloud.google.com/workflows/workflow/${REGION}/${WORKFLOW_NAME}/execution/${EXECUTION_ID}?project=${PROJECT_ID}"

# Cleanup
rm -f /tmp/test-result-1.json

echo ""
echo "�� Test completed!" 