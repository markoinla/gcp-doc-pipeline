#!/bin/bash

# Test script for the Cloudflare Worker API Proxy
set -e

PROJECT_ID="ladders-doc-pipeline-462921"
WORKFLOW_NAME="pdf-processing-workflow"
REGION="us-central1"
API_ENDPOINT="https://cf-api-proxy.m-6bb.workers.dev/"

echo "🚀 Cloudflare Worker API Proxy Test"
echo "===================================="
echo ""

# Prompt for inputs with defaults
echo "📋 Please provide the following information:"
echo ""

read -p "PDF URL: " PDF_URL
if [[ -z "$PDF_URL" ]]; then
    echo "❌ PDF URL is required!"
    exit 1
fi

read -p "Project ID (optional): " INPUT_PROJECT_ID
PROJECT_ID_VALUE=${INPUT_PROJECT_ID:-"test-project"}

read -p "File ID (optional): " INPUT_FILE_ID
FILE_ID_VALUE=${INPUT_FILE_ID:-"test-file-$(date +%s)"}

read -p "Webhook URL (optional, press Enter to skip): " WEBHOOK_URL

echo ""
echo "📊 Test Configuration:"
echo "   PDF URL: ${PDF_URL}"
echo "   Project ID: ${PROJECT_ID_VALUE}"
echo "   File ID: ${FILE_ID_VALUE}"
echo "   Webhook URL: ${WEBHOOK_URL:-"(none)"}"
echo "   API Endpoint: ${API_ENDPOINT}"
echo ""

# Prepare the JSON payload
if [[ -n "$WEBHOOK_URL" ]]; then
    PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "${PDF_URL}",
  "projectId": "${PROJECT_ID_VALUE}",
  "fileId": "${FILE_ID_VALUE}",
  "webhookUrl": "${WEBHOOK_URL}"
}
EOF
)
else
    PAYLOAD=$(cat <<EOF
{
  "pdfUrl": "${PDF_URL}",
  "projectId": "${PROJECT_ID_VALUE}",
  "fileId": "${FILE_ID_VALUE}"
}
EOF
)
fi

echo "🔄 Calling API proxy..."
echo ""

# Call the API and capture response
RESPONSE=$(curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" \
  -w "\nHTTP_STATUS:%{http_code}")

# Split response and status code
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")

echo "📡 API Response:"
echo "   HTTP Status: ${HTTP_CODE}"
echo "   Response Body: ${RESPONSE_BODY}"
echo ""

# Check if the API call was successful
if [[ "$HTTP_CODE" == "200" ]]; then
    echo "✅ API call successful!"
    
    # Extract execution ID from response
    EXECUTION_ID=$(echo "$RESPONSE_BODY" | jq -r '.executionId // empty')
    
    if [[ -n "$EXECUTION_ID" && "$EXECUTION_ID" != "null" ]]; then
        echo "   Execution ID: ${EXECUTION_ID}"
        echo ""
        
        # Set the active project for gcloud commands
        gcloud config set project ${PROJECT_ID} --quiet
        
        echo "🔍 Monitoring workflow execution..."
        echo "   Expected processing time: 2-5 minutes for typical PDFs"
        echo ""
        
        # Monitor execution status
        for i in {1..20}; do
            echo "📋 Checking execution status (${i}/20)..."
            
            EXECUTION_STATE=$(gcloud workflows executions describe ${EXECUTION_ID} \
                --workflow=${WORKFLOW_NAME} \
                --location=${REGION} \
                --format="value(state)" 2>/dev/null || echo "ERROR")
            
            if [[ "$EXECUTION_STATE" == "ERROR" ]]; then
                echo "   ❌ Failed to get execution status"
                break
            fi
            
            echo "   Current state: ${EXECUTION_STATE}"
            
            if [[ "${EXECUTION_STATE}" == "SUCCEEDED" ]]; then
                echo ""
                echo "🎉 SUCCESS! PDF processing completed successfully!"
                echo "============================================="
                
                # Get the detailed result
                RESULT=$(gcloud workflows executions describe ${EXECUTION_ID} \
                    --workflow=${WORKFLOW_NAME} \
                    --location=${REGION} \
                    --format="value(result)" 2>/dev/null || echo "{}")
                
                echo ""
                echo "📄 Execution Result:"
                echo "${RESULT}" | jq . 2>/dev/null || echo "${RESULT}"
                
                # Parse key metrics from result if available
                if echo "${RESULT}" | jq . >/dev/null 2>&1; then
                    DOCUMENT_ID=$(echo "${RESULT}" | jq -r '.document_id // "unknown"')
                    PROCESSING_TIME=$(echo "${RESULT}" | jq -r '.processing_time // "unknown"')
                    
                    echo ""
                    echo "📊 Key Metrics:"
                    echo "   Document ID: ${DOCUMENT_ID}"
                    echo "   Processing Time: ${PROCESSING_TIME} seconds"
                    
                    # Check if result contains R2 upload information
                    if echo "${RESULT}" | jq -e '.result.uploaded_files' > /dev/null 2>&1; then
                        echo ""
                        echo "☁️  R2 Upload Results:"
                        echo "${RESULT}" | jq -r '.result.uploaded_files | to_entries[] | "   \(.key): \(.value)"' 2>/dev/null || echo "   Upload info not available"
                        
                        echo ""
                        echo "🔗 Generated Files in R2:"
                        echo "   Main Document: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/documents/${DOCUMENT_ID}.json"
                        echo "   Search Index:  https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/search/${DOCUMENT_ID}.json"
                        echo "   Pattern Summary: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/patterns/${DOCUMENT_ID}.json"
                    fi
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
                    --format="value(error)" 2>/dev/null || echo "Error details not available")
                
                echo ""
                echo "🚨 Error Details:"
                echo "${ERROR}"
                
                break
                
            elif [[ "${EXECUTION_STATE}" == "ACTIVE" ]]; then
                echo "   ⏳ Still processing... waiting 15 seconds"
                sleep 15
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
        
    else
        echo "⚠️  API call successful but no execution ID returned"
        echo "   This might indicate an issue with the response format"
    fi
    
else
    echo "❌ API call failed!"
    echo "   HTTP Status: ${HTTP_CODE}"
    echo "   Response: ${RESPONSE_BODY}"
    
    # Try to parse error message if it's JSON
    if echo "$RESPONSE_BODY" | jq . >/dev/null 2>&1; then
        ERROR_MSG=$(echo "$RESPONSE_BODY" | jq -r '.error // .message // "Unknown error"')
        echo "   Error: ${ERROR_MSG}"
    fi
fi

echo ""
echo "🏁 Test completed!"
echo ""
echo "💡 Tips:"
echo "   - Use the Firehouse Subs PDF for testing: https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Firehouse%20Subs%20-%20London(BidSet).pdf"
echo "   - Expected patterns in Firehouse PDF: 8×PT-1, 4×M1, 4×M-1"
echo "   - Check Cloudflare Worker logs: cd cf-api-proxy && wrangler tail --format=pretty"
echo "   - Monitor function logs: gcloud functions logs read pdf-processor --region=us-central1 --limit=10" 