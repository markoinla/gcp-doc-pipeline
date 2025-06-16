#!/bin/bash

# Test the complete PDF processing pipeline with real R2 credentials
set -e

PROJECT_ID="ladders-doc-pipeline-462921"
WORKFLOW_NAME="pdf-processing-workflow"
REGION="us-central1"
R2_BUCKET="ladders-1"

echo "🚀 Testing Complete PDF Processing Pipeline"
echo "==========================================="
echo "Project: ${PROJECT_ID}"
echo "Workflow: ${WORKFLOW_NAME}"
echo "R2 Bucket: ${R2_BUCKET}"
echo ""

# Set the active project
gcloud config set project ${PROJECT_ID}

# Test with the Firehouse Subs PDF (our known test document)
echo "📄 Testing with Firehouse Subs PDF (24 pages, expected patterns: 8×PT-1, 4×M1, 4×M-1)"
echo "📋 R2 credentials will be loaded automatically by the function from Secret Manager"
echo ""

TEST_PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf",
  "r2Config": {
    "bucketName": "${R2_BUCKET}"
  },
  "callbackUrl": "https://test-callback.example.com/webhook"
}
EOF
)

echo "🔄 Starting workflow execution..."
echo ""

# Execute the workflow
EXECUTION_OUTPUT=$(gcloud workflows run ${WORKFLOW_NAME} \
  --location=${REGION} \
  --data="${TEST_PAYLOAD}" \
  --format="value(name)")

EXECUTION_ID=$(echo "${EXECUTION_OUTPUT}" | rev | cut -d'/' -f1 | rev)

echo "📊 Workflow execution started!"
echo "Execution ID: ${EXECUTION_ID}"
echo "⏱️  Expected processing time: 2-5 minutes"
echo ""

# Monitor execution with detailed progress
echo "🔍 Monitoring execution progress..."
echo ""

# Poll for completion with longer timeout for PDF processing
for i in {1..20}; do
  echo "📋 Checking execution status (${i}/20)..."
  
  EXECUTION_STATE=$(gcloud workflows executions describe ${EXECUTION_ID} \
    --workflow=${WORKFLOW_NAME} \
    --location=${REGION} \
    --format="value(state)")
  
  echo "   Current state: ${EXECUTION_STATE}"
  
  if [[ "${EXECUTION_STATE}" == "SUCCEEDED" ]]; then
    echo ""
    echo "🎉 SUCCESS! PDF processing completed successfully!"
    echo "============================================="
    
    # Get the detailed result
    RESULT=$(gcloud workflows executions describe ${EXECUTION_ID} \
      --workflow=${WORKFLOW_NAME} \
      --location=${REGION} \
      --format="value(result)")
    
    echo ""
    echo "📄 Execution Result:"
    echo "${RESULT}" | jq .
    
    # Parse key metrics from result
    DOCUMENT_ID=$(echo "${RESULT}" | jq -r '.document_id // "unknown"')
    PROCESSING_TIME=$(echo "${RESULT}" | jq -r '.processing_time // "unknown"')
    
    echo ""
    echo "📊 Key Metrics:"
    echo "   Document ID: ${DOCUMENT_ID}"
    echo "   Processing Time: ${PROCESSING_TIME} seconds"
    
    # Check if result contains R2 upload information
    if echo "${RESULT}" | jq -e '.result.uploaded_files' > /dev/null; then
      echo ""
      echo "☁️  R2 Upload Results:"
      echo "${RESULT}" | jq -r '.result.uploaded_files | to_entries[] | "   \(.key): \(.value)"'
      
      echo ""
      echo "🔗 Generated Files in R2:"
      echo "   Main Document: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/documents/${DOCUMENT_ID}.json"
      echo "   Search Index:  https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/search/${DOCUMENT_ID}.json"
      echo "   Pattern Summary: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/patterns/${DOCUMENT_ID}.json"
    fi
    
    break
    
  elif [[ "${EXECUTION_STATE}" == "FAILED" ]]; then
    echo ""
    echo "❌ FAILED! Workflow execution failed."
    echo "================================="
    
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
    echo "🔍 Checking Cloud Function logs for additional details..."
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
echo "🔗 Cloud Console Links:"
echo "   Workflow Execution: https://console.cloud.google.com/workflows/workflow/${REGION}/${WORKFLOW_NAME}/execution/${EXECUTION_ID}?project=${PROJECT_ID}"
echo "   Cloud Function: https://console.cloud.google.com/functions/details/${REGION}/pdf-processor?project=${PROJECT_ID}"
echo "   Document AI: https://console.cloud.google.com/ai/document-ai/processors?project=${PROJECT_ID}"

echo ""
echo "🏁 Pipeline test completed!"

# Optional: Test pattern extraction expectations
if [[ "${EXECUTION_STATE}" == "SUCCEEDED" ]]; then
  echo ""
  echo "📝 Expected vs Actual Pattern Analysis:"
  echo "   Expected: 8×PT-1, 4×M1, 4×M-1 patterns"
  echo "   Actual: Check the pattern summary JSON for detailed results"
  echo ""
  echo "   To verify patterns manually:"
  echo "   curl -s https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/patterns/${DOCUMENT_ID}.json | jq '.pattern_counts'"
fi 