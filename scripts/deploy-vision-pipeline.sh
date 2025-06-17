#!/bin/bash

# Deploy PDF Vision Pipeline to Google Cloud Functions
# This script deploys the optimized Vision API pipeline

set -e

echo "🚀 DEPLOYING PDF VISION PIPELINE"
echo "================================="

# Configuration
PROJECT_ID="ladders-doc-pipeline-462921"
FUNCTION_NAME="pdf-vision-pipeline"
REGION="us-central1"
SOURCE_DIR="functions/pdf-vision-pipeline"

# Set project
echo "📋 Setting project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Deploy function
echo "🔧 Deploying function: $FUNCTION_NAME"
cd $SOURCE_DIR

gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=pdf_vision_pipeline \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=8Gi \
  --cpu=4 \
  --max-instances=10 \
  --concurrency=1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=ladders-doc-pipeline-462921,DEFAULT_R2_BUCKET=ladders-1"

echo "✅ Deployment completed!"
echo "🔗 Function URL: https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME"
echo ""
echo "🧪 Test with:"
echo "curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"pdfUrl\": \"YOUR_PDF_URL\", \"projectID\": \"test\", \"fileID\": \"test-file\"}'" 