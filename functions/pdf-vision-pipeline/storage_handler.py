import boto3
import json
import logging
from datetime import datetime
from google.cloud import secretmanager
from botocore.config import Config

from config import R2_BASE_URL
from client_manager import client_manager

logger = logging.getLogger(__name__)

def get_r2_client():
    """Get R2 client using singleton pattern (DEPRECATED - use client_manager directly)"""
    # Legacy function maintained for compatibility
    return client_manager.get_r2_client()

def upload_page_image(image_bytes, project_id, file_id, page_num, bucket):
    """Upload page image to R2 using singleton client"""
    client = client_manager.get_r2_client()
    
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
    """Upload page JSON to R2 using singleton client"""
    client = client_manager.get_r2_client()
    
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
    """Upload aggregated final JSON using singleton client"""
    client = client_manager.get_r2_client()
    
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