from google.cloud import vision
import time
import logging

from config import RETRY_ATTEMPTS, RETRY_DELAY, VISION_TIMEOUT
import pdf_processor
import pattern_extractor
import storage_handler

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
                
                # Upload image to R2
                image_url = storage_handler.upload_page_image(image_bytes, project_id, file_id, page_num, bucket)
                
                # Upload page JSON to R2  
                page_json_url = storage_handler.upload_page_json(patterns, project_id, file_id, page_num, bucket)
                
                processing_time = time.time() - start_time
                
                results.append({
                    "page": page_num,
                    "success": True,
                    "image_url": image_url,
                    "page_json_url": page_json_url,
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

def call_vision_api(image_bytes):
    """Call Google Cloud Vision API"""
    client = vision.ImageAnnotatorClient()
    
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    
    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")
        
    logger.debug(f"Vision API returned {len(response.text_annotations)} text annotations")
    return response 