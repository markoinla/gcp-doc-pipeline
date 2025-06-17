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
import batch_storage
from client_manager import client_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@functions_framework.http
def pdf_vision_pipeline(request):
    """Main pipeline orchestrator"""
    try:
        # Track total pipeline processing time
        pipeline_start_time = time.time()
        
        # 1. Validate input
        request_data = validate_request(request)
        pdf_url = request_data['pdfUrl']  # Required
        project_id = request_data.get('projectID', 'default')
        file_id = request_data.get('fileID', generate_file_id())
        webhook = request_data.get('webhook')
        chunk_size = request_data.get('chunkSize', DEFAULT_CHUNK_SIZE)
        parallel_workers = request_data.get('parallelWorkers', PARALLEL_WORKERS)
        bucket = request_data.get('bucket', DEFAULT_R2_BUCKET)
        
        logger.info(f"Starting processing for project={project_id}, file={file_id}, PDF={pdf_url}")
        logger.info(f"Configuration: chunk_size={chunk_size}, parallel_workers={parallel_workers}")
        
        # Initialize singleton clients (connection pooling optimization)
        client_init_start = time.time()
        client_manager.get_vision_client()  # Pre-initialize Vision API client
        client_manager.get_r2_client()      # Pre-initialize R2 client
        client_init_time = time.time() - client_init_start
        logger.info(f"Client initialization completed in {client_init_time:.2f}s")
        
        # 2. Download and split PDF
        page_images = pdf_processor.split_pdf_to_images(pdf_url)
        
        if len(page_images) > MAX_PAGES:
            return {"error": f"PDF exceeds {MAX_PAGES} page limit"}, 400
            
        # 3. Process pages in parallel chunks (Vision API + pattern extraction only)
        page_results = process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size, parallel_workers)
        
        # 4. Batch upload all storage operations in parallel (OPTIMIZATION)
        batch_upload_start = time.time()
        page_results = batch_storage.batch_upload_page_results(page_results, project_id, file_id, bucket)
        batch_upload_time = time.time() - batch_upload_start
        logger.info(f"Batch storage completed in {batch_upload_time:.2f}s")
        
        # 5. Aggregate results (pass actual processing time)
        actual_processing_time = time.time() - pipeline_start_time
        final_result = result_aggregator.compile_final_json(page_results, project_id, file_id, actual_processing_time)
        
        # 6. Upload final JSON (optimized)
        final_json_url = batch_storage.upload_final_json_optimized(final_result, project_id, file_id, bucket)
        
        # 7. Send webhook if provided
        if webhook:
            send_webhook_notification(webhook, final_result)
        
        # 8. Return response
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
    
    # Validate parallel workers
    parallel_workers = data.get('parallelWorkers', PARALLEL_WORKERS)
    if not isinstance(parallel_workers, int) or parallel_workers < 1 or parallel_workers > 50:
        raise ValueError("parallelWorkers must be between 1 and 50")
    
    return data

def generate_file_id():
    """Generate a unique file ID"""
    return f"file-{str(uuid.uuid4())[:8]}"

def process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size, parallel_workers):
    """Process pages using ThreadPoolExecutor with chunking"""
    results = []
    
    # Create chunks of pages for each worker
    page_chunks = [page_images[i:i + chunk_size] for i in range(0, len(page_images), chunk_size)]
    
    logger.info(f"Processing {len(page_images)} pages in {len(page_chunks)} chunks of size {chunk_size}")
    logger.info(f"Using {parallel_workers} parallel workers")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
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

def process_pages_parallel_with_urls(page_images_with_urls, project_id, file_id, bucket, chunk_size, parallel_workers):
    """Process pages with URL preservation using ThreadPoolExecutor with chunking"""
    results = []
    
    # Create chunks of pages for each worker
    page_chunks = [page_images_with_urls[i:i + chunk_size] for i in range(0, len(page_images_with_urls), chunk_size)]
    
    logger.info(f"Processing {len(page_images_with_urls)} pages in {len(page_chunks)} chunks of size {chunk_size}")
    logger.info(f"Using {parallel_workers} parallel workers")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        # Submit chunk processing tasks
        future_to_chunk = {
            executor.submit(vision_processor.process_page_chunk_with_urls, chunk, chunk_idx * chunk_size + 1, project_id, file_id, bucket): chunk_idx
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

# ============ NEW IMAGE DIRECT PIPELINE ENDPOINT ============

@functions_framework.http
def image_vision_pipeline(request):
    """Direct image processing pipeline (bypasses PDF conversion)"""
    try:
        # Track total pipeline processing time
        pipeline_start_time = time.time()
        
        # 1. Validate input
        request_data = validate_image_request(request)
        images = request_data['images']  # Required
        project_id = request_data.get('projectID', 'default')
        file_id = request_data.get('fileID', generate_file_id())
        webhook = request_data.get('webhook')
        chunk_size = request_data.get('chunkSize', DEFAULT_CHUNK_SIZE)
        parallel_workers = request_data.get('parallelWorkers', PARALLEL_WORKERS)
        bucket = request_data.get('bucket', DEFAULT_R2_BUCKET)
        
        logger.info(f"Starting image processing for project={project_id}, file={file_id}, images={len(images)}")
        logger.info(f"Configuration: chunk_size={chunk_size}, parallel_workers={parallel_workers}")
        
        # Initialize singleton clients (connection pooling optimization)
        client_init_start = time.time()
        client_manager.get_vision_client()  # Pre-initialize Vision API client
        client_manager.get_r2_client()      # Pre-initialize R2 client
        client_init_time = time.time() - client_init_start
        logger.info(f"Client initialization completed in {client_init_time:.2f}s")
        
        # 2. Process images using the new parallel pipeline
        page_results = process_images_pipeline(images, project_id, file_id, bucket, chunk_size, parallel_workers)
        
        # 3. Process results (skip image uploads - already stored)
        batch_upload_start = time.time()
        page_results = batch_storage.batch_upload_image_results_json_only(page_results, project_id, file_id, bucket)
        batch_upload_time = time.time() - batch_upload_start
        logger.info(f"Image result processing completed in {batch_upload_time:.2f}s")
        
        # 4. Aggregate results with image metadata
        actual_processing_time = time.time() - pipeline_start_time
        final_result = result_aggregator.compile_final_json_images(page_results, project_id, file_id, actual_processing_time, len(images))
        
        # 5. Upload final JSON (optimized)
        final_json_url = batch_storage.upload_final_json_optimized(final_result, project_id, file_id, bucket)
        
        # 6. Send webhook if provided
        if webhook:
            send_webhook_notification(webhook, final_result)
        
        # 7. Return response
        response = {
            "success": True,
            "project_id": project_id,
            "file_id": file_id,
            "total_pages": len(images),
            "processed_pages": len([r for r in page_results if r['success']]),
            "failed_pages": [r['page'] for r in page_results if not r['success']],
            "final_json_url": final_json_url,
            "page_urls": [r.get('page_url', r.get('original_url', '')) for r in page_results if r['success']],
            "processing_time_seconds": final_result['processing_metadata']['processing_time_seconds']
        }
        
        logger.info(f"Image processing completed successfully: {response['processed_pages']}/{response['total_pages']} pages")
        return response
        
    except Exception as e:
        logger.error(f"Image pipeline error: {str(e)}")
        return {"error": str(e)}, 500

def validate_image_request(request):
    """Validate and parse the incoming image request"""
    if not request.is_json:
        raise ValueError("Request must be JSON")
    
    data = request.get_json()
    if not data.get('images'):
        raise ValueError("images array is required")
    
    images = data.get('images')
    if not isinstance(images, list):
        raise ValueError("images must be an array")
    
    if len(images) == 0:
        raise ValueError("images array cannot be empty")
    
    if len(images) > MAX_IMAGES:
        raise ValueError(f"Too many images: {len(images)} (max: {MAX_IMAGES})")
    
    # Validate each image spec
    for idx, image_spec in enumerate(images):
        if not isinstance(image_spec, dict):
            raise ValueError(f"Image {idx + 1}: must be an object")
        
        if 'url' not in image_spec and 'data' not in image_spec:
            raise ValueError(f"Image {idx + 1}: must have 'url' or 'data' field")
        
        if 'url' in image_spec and 'data' in image_spec:
            raise ValueError(f"Image {idx + 1}: cannot have both 'url' and 'data' fields")
    
    # Validate chunk size
    chunk_size = data.get('chunkSize', DEFAULT_CHUNK_SIZE)
    if not isinstance(chunk_size, int) or chunk_size < 1 or chunk_size > 15:
        raise ValueError("chunkSize must be between 1 and 15")
    
    # Validate parallel workers
    parallel_workers = data.get('parallelWorkers', PARALLEL_WORKERS)
    if not isinstance(parallel_workers, int) or parallel_workers < 1 or parallel_workers > 50:
        raise ValueError("parallelWorkers must be between 1 and 50")
    
    return data

def process_images_pipeline(image_specs, project_id, file_id, bucket, chunk_size, parallel_workers):
    """Process images with same parallel strategy as PDF pipeline"""
    
    # Phase 1: Download all images in parallel (NEW)
    download_start = time.time()
    page_images_with_urls = pdf_processor.download_images_parallel_with_urls(image_specs, parallel_workers)
    download_time = time.time() - download_start
    logger.info(f"Downloaded {len(page_images_with_urls)} images in {download_time:.2f}s using {parallel_workers} workers")
    
    if len(page_images_with_urls) == 0:
        raise Exception("No images were successfully downloaded")
    
    # Phase 2: Process images using modified parallel chunk processing that preserves URLs
    page_results = process_pages_parallel_with_urls(page_images_with_urls, project_id, file_id, bucket, chunk_size, parallel_workers)
    
    return page_results 