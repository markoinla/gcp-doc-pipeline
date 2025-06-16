import boto3
import json
import logging
from datetime import datetime
from google.cloud import secretmanager
from botocore.config import Config

from config import R2_BASE_URL

logger = logging.getLogger(__name__)

def get_r2_client():
    """Initialize R2 client with credentials from Secret Manager"""
    try:
        # Get R2 credentials from Secret Manager (same as existing pdf-processor)
        client = secretmanager.SecretManagerServiceClient()
        project_id = "ladders-doc-pipeline-462921"
        
        access_key = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-access-key/versions/latest"}
        ).payload.data.decode("UTF-8")
        
        secret_key = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-secret-key/versions/latest"}
        ).payload.data.decode("UTF-8")
        
        endpoint = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-endpoint/versions/latest"}
        ).payload.data.decode("UTF-8")
        
        # Configure R2 client (same as existing pdf-processor)
        r2_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        
        return r2_client
        
    except Exception as e:
        logger.error(f"Failed to initialize R2 client: {str(e)}")
        raise

def upload_page_image(image_bytes, project_id, file_id, page_num, bucket):
    """Upload page image to R2"""
    client = get_r2_client()
    
    key = f"projects/{project_id}/files/{file_id}/images/page-{page_num:03d}.jpg"
    
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_bytes,
            ContentType='image/jpeg',
            CacheControl='public, max-age=31536000'  # 1 year cache
        )
        
        url = f"{R2_BASE_URL}/{key}"
        logger.info(f"Uploaded image for page {page_num}: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Failed to upload image for page {page_num}: {str(e)}")
        raise

def upload_page_json(patterns, project_id, file_id, page_num, bucket):
    """Upload page JSON to R2"""
    client = get_r2_client()
    
    page_data = {
        "page_number": page_num,
        "patterns": patterns,
        "pattern_count": {
            pattern_type: len([p for p in patterns if p['pattern_type'] == pattern_type])
            for pattern_type in set(p['pattern_type'] for p in patterns)
        } if patterns else {},
        "total_patterns": len(patterns),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    key = f"projects/{project_id}/files/{file_id}/json/page-{page_num:03d}.json"
    
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(page_data, indent=2),
            ContentType='application/json'
        )
        
        url = f"{R2_BASE_URL}/{key}"
        logger.info(f"Uploaded JSON for page {page_num}: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Failed to upload JSON for page {page_num}: {str(e)}")
        raise

def upload_final_json(final_result, project_id, file_id, bucket):
    """Upload aggregated final JSON"""
    client = get_r2_client()
    
    key = f"projects/{project_id}/files/{file_id}/json/final-results.json"
    
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(final_result, indent=2),
            ContentType='application/json'
        )
        
        url = f"{R2_BASE_URL}/{key}"
        logger.info(f"Uploaded final JSON: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Failed to upload final JSON: {str(e)}")
        raise 