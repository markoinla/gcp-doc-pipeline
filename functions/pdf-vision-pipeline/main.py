import functions_framework
import concurrent.futures
import time
import uuid
import json
import logging
from datetime import datetime

from config import *
import pdf_processor
import vision_processor
import storage_handler
import result_aggregator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@functions_framework.http
def pdf_vision_pipeline(request):
    """Main pipeline orchestrator"""
    try:
        # 1. Validate input
        request_data = validate_request(request)
        pdf_url = request_data['pdfUrl']  # Required
        project_id = request_data.get('projectID', 'default')
        file_id = request_data.get('fileID', generate_file_id())
        webhook = request_data.get('webhook')
        chunk_size = request_data.get('chunkSize', DEFAULT_CHUNK_SIZE)
        bucket = request_data.get('bucket', DEFAULT_R2_BUCKET)
        
        logger.info(f"Starting processing for project={project_id}, file={file_id}, PDF={pdf_url}")
        
        # 2. Download and split PDF
        page_images = pdf_processor.split_pdf_to_images(pdf_url)
        
        if len(page_images) > MAX_PAGES:
            return {"error": f"PDF exceeds {MAX_PAGES} page limit"}, 400
            
        # 3. Process pages in parallel chunks
        page_results = process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size)
        
        # 4. Aggregate results
        final_result = result_aggregator.compile_final_json(page_results, project_id, file_id)
        
        # 5. Upload final JSON
        final_json_url = storage_handler.upload_final_json(final_result, project_id, file_id, bucket)
        
        # 6. Send webhook if provided
        if webhook:
            send_webhook_notification(webhook, final_result)
        
        # 7. Return response
        response = {
            "success": True,
            "project_id": project_id,
            "file_id": file_id,
            "total_pages": len(page_images),
            "processed_pages": len([r for r in page_results if r['success']]),
            "failed_pages": [r['page'] for r in page_results if not r['success']],
            "final_json_url": final_json_url,
            "image_urls": [r['image_url'] for r in page_results if r['success']],
            "processing_time_seconds": final_result['processing_metadata']['processing_time_seconds']
        }
        
        logger.info(f"Processing completed successfully: {response['processed_pages']}/{response['total_pages']} pages")
        return response
        
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        return {"error": str(e)}, 500

def validate_request(request):
    """Validate and parse the incoming request"""
    if not request.is_json:
        raise ValueError("Request must be JSON")
    
    data = request.get_json()
    if not data.get('pdfUrl'):
        raise ValueError("pdfUrl is required")
    
    # Validate chunk size
    chunk_size = data.get('chunkSize', DEFAULT_CHUNK_SIZE)
    if not isinstance(chunk_size, int) or chunk_size < 1 or chunk_size > 15:
        raise ValueError("chunkSize must be between 1 and 15")
    
    return data

def generate_file_id():
    """Generate a unique file ID"""
    return f"file-{str(uuid.uuid4())[:8]}"

def process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size):
    """Process pages using ThreadPoolExecutor with chunking"""
    results = []
    
    # Create chunks of pages for each worker
    page_chunks = [page_images[i:i + chunk_size] for i in range(0, len(page_images), chunk_size)]
    
    logger.info(f"Processing {len(page_images)} pages in {len(page_chunks)} chunks of size {chunk_size}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        # Submit chunk processing tasks
        future_to_chunk = {
            executor.submit(vision_processor.process_page_chunk, chunk, chunk_idx * chunk_size + 1, project_id, file_id, bucket): chunk_idx
            for chunk_idx, chunk in enumerate(page_chunks)
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_idx = future_to_chunk[future]
            try:
                chunk_results = future.result()
                results.extend(chunk_results)
                logger.info(f"Completed chunk {chunk_idx + 1}/{len(page_chunks)}")
            except Exception as e:
                logger.error(f"Chunk {chunk_idx} failed: {str(e)}")
                # If chunk fails, create error results for all pages in chunk
                start_page = chunk_idx * chunk_size + 1
                for i in range(len(page_chunks[chunk_idx])):
                    results.append({
                        "page": start_page + i,
                        "success": False,
                        "error": str(e)
                    })
    
    return sorted(results, key=lambda x: x.get('page', 0))

def send_webhook_notification(webhook_url, final_result):
    """Send webhook notification on completion"""
    try:
        import requests
        
        webhook_data = {
            "status": "completed",
            "project_id": final_result["project_id"],
            "file_id": final_result["file_id"],
            "total_pages": final_result["processing_metadata"]["total_pages"],
            "processed_pages": final_result["processing_metadata"]["processed_pages"],
            "processing_time_seconds": final_result["processing_metadata"]["processing_time_seconds"],
            "timestamp": final_result["processing_metadata"]["timestamp"]
        }
        
        response = requests.post(webhook_url, json=webhook_data, timeout=10)
        logger.info(f"Webhook sent successfully: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to send webhook: {str(e)}") 