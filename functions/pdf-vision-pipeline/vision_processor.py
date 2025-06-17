from google.cloud import vision
import time
import logging

from config import RETRY_ATTEMPTS, RETRY_DELAY, VISION_TIMEOUT
import pdf_processor
import pattern_extractor
import storage_handler
from client_manager import client_manager

logger = logging.getLogger(__name__)

def process_page_chunk(page_images, start_page_num, project_id, file_id, bucket):
    """Process a chunk of pages with retry logic"""
    results = []
    
    for idx, page_image in enumerate(page_images):
        page_num = start_page_num + idx
        logger.info(f"Processing page {page_num}")
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                start_time = time.time()
                
                # Convert image to bytes
                image_bytes = pdf_processor.image_to_bytes(page_image)
                
                # Vision API processing
                vision_result = call_vision_api(image_bytes)
                
                # Extract patterns
                patterns = pattern_extractor.extract_patterns_from_vision(vision_result, page_num)
                
                processing_time = time.time() - start_time
                
                # Store data for batch upload (no individual uploads)
                results.append({
                    "page": page_num,
                    "success": True,
                    "image_bytes": image_bytes,  # Store for batch upload
                    "patterns": patterns,
                    "pattern_count": len(patterns),
                    "processing_time": processing_time
                })
                
                logger.info(f"Page {page_num} completed successfully in {processing_time:.2f}s - found {len(patterns)} patterns")
                break  # Success, exit retry loop
                
            except Exception as e:
                logger.warning(f"Page {page_num} attempt {attempt + 1} failed: {str(e)}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    results.append({
                        "page": page_num,
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(f"Page {page_num} failed after {RETRY_ATTEMPTS} attempts")
    
    return results

def process_page_chunk_with_urls(page_images_with_urls, start_page_num, project_id, file_id, bucket):
    """Process a chunk of pages with URL preservation and retry logic"""
    results = []
    
    for idx, page_data in enumerate(page_images_with_urls):
        page_num = start_page_num + idx
        page_image = page_data['image']
        original_url = page_data['original_url']
        
        logger.info(f"Processing page {page_num} with original URL: {original_url}")
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                start_time = time.time()
                
                # Convert image to bytes
                image_bytes = pdf_processor.image_to_bytes(page_image)
                
                # Vision API processing
                vision_result = call_vision_api(image_bytes)
                
                # Extract patterns
                patterns = pattern_extractor.extract_patterns_from_vision(vision_result, page_num)
                
                processing_time = time.time() - start_time
                
                # Generate correct page URL with /pages/ instead of /images/
                page_url = generate_page_url(project_id, file_id, page_num, original_url)
                
                # Store data for batch upload (no individual uploads)
                results.append({
                    "page": page_num,
                    "success": True,
                    "image_bytes": image_bytes,  # Store for batch upload
                    "patterns": patterns,
                    "pattern_count": len(patterns),
                    "processing_time": processing_time,
                    "original_url": original_url,
                    "page_url": page_url  # Use correct /pages/ URL
                })
                
                logger.info(f"Page {page_num} completed successfully in {processing_time:.2f}s - found {len(patterns)} patterns")
                break  # Success, exit retry loop
                
            except Exception as e:
                logger.warning(f"Page {page_num} attempt {attempt + 1} failed: {str(e)}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    results.append({
                        "page": page_num,
                        "success": False,
                        "error": str(e),
                        "original_url": original_url
                    })
                    logger.error(f"Page {page_num} failed after {RETRY_ATTEMPTS} attempts")
    
    return results

def generate_page_url(project_id, file_id, page_num, original_url):
    """Generate the correct page URL with /pages/ path"""
    from config import R2_BASE_URL
    
    # If we have an original URL, use it as-is (it's already correct)
    if original_url:
        return original_url
    
    # For base64 images, generate a placeholder URL with /pages/
    return f"{R2_BASE_URL}/projects/{project_id}/files/{file_id}/pages/page-{page_num:03d}.jpg"

def call_vision_api(image_bytes):
    """Call Google Cloud Vision API using singleton client"""
    # Use singleton client instead of creating new one each time
    client = client_manager.get_vision_client()
    
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    
    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")
        
    logger.debug(f"Vision API returned {len(response.text_annotations)} text annotations")
    return response 