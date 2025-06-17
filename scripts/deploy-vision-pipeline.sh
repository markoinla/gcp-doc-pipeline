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

echo "✅ PDF Pipeline deployment completed!"
echo "🔗 Function URL: https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME"

# Deploy Image Direct Pipeline
echo ""
echo "🚀 DEPLOYING IMAGE DIRECT PIPELINE"
echo "=================================="

IMAGE_FUNCTION_NAME="image-vision-pipeline"

echo "🔧 Deploying function: $IMAGE_FUNCTION_NAME"

gcloud functions deploy $IMAGE_FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=image_vision_pipeline \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=8Gi \
  --cpu=4 \
  --max-instances=10 \
  --concurrency=1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=ladders-doc-pipeline-462921,DEFAULT_R2_BUCKET=ladders-1"

echo "✅ Image Pipeline deployment completed!"
echo "🔗 Function URL: https://$REGION-$PROJECT_ID.cloudfunctions.net/$IMAGE_FUNCTION_NAME"

echo ""
echo "📋 DEPLOYMENT SUMMARY"
echo "===================="
echo "PDF Pipeline: https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME"
echo "Image Pipeline: https://$REGION-$PROJECT_ID.cloudfunctions.net/$IMAGE_FUNCTION_NAME"

echo ""
echo "🧪 Test PDF Pipeline:"
echo "curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"pdfUrl\": \"YOUR_PDF_URL\", \"projectID\": \"test\", \"fileID\": \"test-file\"}'"

echo ""
echo "🧪 Test Image Pipeline:"
echo "curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/$IMAGE_FUNCTION_NAME \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"images\": [{\"url\": \"YOUR_IMAGE_URL\", \"pageNumber\": 1}], \"projectID\": \"test\", \"fileID\": \"test-file\"}'" 