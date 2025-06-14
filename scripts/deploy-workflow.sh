#!/bin/bash

# Deploy Google Cloud Workflow for PDF Processing Pipeline
set -e

PROJECT_ID="ladders-doc-pipeline-462921"
WORKFLOW_NAME="pdf-processing-workflow"
REGION="us-central1"
SERVICE_ACCOUNT="pdf-processor-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🚀 Deploying Google Cloud Workflow..."
echo "Project: ${PROJECT_ID}"
echo "Workflow: ${WORKFLOW_NAME}"
echo "Region: ${REGION}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""

# Set the active project
echo "Setting project context..."
gcloud config set project ${PROJECT_ID}

# Deploy the workflow
echo "Deploying workflow from YAML..."
gcloud workflows deploy ${WORKFLOW_NAME} \
  --source=workflows/pdf-processing-workflow.yaml \
  --location=${REGION} \
  --service-account=${SERVICE_ACCOUNT}

# Check deployment status
echo ""
echo "✅ Workflow deployed successfully!"
echo ""

# Get workflow details
echo "Workflow details:"
gcloud workflows describe ${WORKFLOW_NAME} \
  --location=${REGION} \
  --format="table(name,state,createTime,updateTime)"

echo ""
echo "🔗 Workflow execution endpoint:"
echo "https://workflowexecutions-${REGION}.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${WORKFLOW_NAME}/executions"

echo ""
echo "📝 To execute the workflow, use:"
echo "gcloud workflows run ${WORKFLOW_NAME} \\"
echo "  --location=${REGION} \\"
echo "  --data='{\"pdfUrl\":\"YOUR_PDF_URL\",\"r2Config\":{...}}'" 