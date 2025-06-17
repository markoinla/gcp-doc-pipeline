#!/bin/bash

# Deploy Image Vision Pipeline ONLY to Google Cloud Functions
# This script deploys just the image-direct processing pipeline

set -e

echo "🚀 DEPLOYING IMAGE VISION PIPELINE ONLY"
echo "======================================="

# Configuration
PROJECT_ID="ladders-doc-pipeline-462921"
FUNCTION_NAME="image-vision-pipeline"
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
echo "🔗 Function URL: https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME"

echo ""
echo "🧪 Test Image Pipeline:"
echo "curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"images\": [{\"url\": \"YOUR_IMAGE_URL\", \"pageNumber\": 1}], \"projectID\": \"test\", \"fileID\": \"test-file\"}'"

echo ""
echo "🎯 Quick test with real image:"
echo "./scripts/quick-image-test.sh" 