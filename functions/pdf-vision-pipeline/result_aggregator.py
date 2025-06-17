import time
import logging
from datetime import datetime
from collections import defaultdict

from config import PARALLEL_WORKERS, IMAGE_DPI

logger = logging.getLogger(__name__)

def compile_final_json(page_results, project_id, file_id, actual_processing_time=None):
    """Compile search-optimized final JSON"""
    
    compilation_start_time = time.time()
    successful_results = [r for r in page_results if r['success']]
    failed_results = [r for r in page_results if not r['success']]
    
    logger.info(f"Compiling results: {len(successful_results)} successful, {len(failed_results)} failed")
    
    # Aggregate all patterns
    all_patterns = []
    pages_data = []
    
    for result in successful_results:
        # Add page data
        page_data = {
            "page_number": result['page'],
            "image_url": result['image_url'],
            "patterns": result['patterns'],
            "pattern_count": calculate_pattern_counts(result['patterns'])
        }
        pages_data.append(page_data)
        
        # Collect patterns
        all_patterns.extend(result['patterns'])
    
    # Create search index
    search_index = create_search_index(all_patterns, pages_data)
    
    # Aggregate pattern statistics
    aggregated_patterns = aggregate_pattern_statistics(all_patterns)
    
    # Calculate processing statistics
    processing_stats = calculate_processing_statistics(page_results)
    
    final_result = {
        "project_id": project_id,
        "file_id": file_id,
        "processing_metadata": {
            "total_pages": len(page_results),
            "processed_pages": len(successful_results),
            "failed_pages": [{"page": r['page'], "error": r['error']} for r in failed_results],
            "processing_time_seconds": actual_processing_time if actual_processing_time else time.time() - compilation_start_time,
            "compilation_time_seconds": time.time() - compilation_start_time,
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "parallel_workers": PARALLEL_WORKERS,
                "image_dpi": IMAGE_DPI,
                "vision_api_version": "v1"
            },
            "statistics": processing_stats
        },
        "pages": pages_data,
        "aggregated_patterns": aggregated_patterns,
        "search_index": search_index
    }
    
    logger.info(f"Final result compiled: {len(all_patterns)} total patterns across {len(successful_results)} pages")
    return final_result

def compile_final_json_images(page_results, project_id, file_id, actual_processing_time=None, total_images=None):
    """Compile search-optimized final JSON for image processing"""
    
    compilation_start_time = time.time()
    successful_results = [r for r in page_results if r['success']]
    failed_results = [r for r in page_results if not r['success']]
    
    logger.info(f"Compiling image results: {len(successful_results)} successful, {len(failed_results)} failed")
    
    # Aggregate all patterns
    all_patterns = []
    images_data = []
    
    for result in successful_results:
        # Add page data (consistent with PDF pipeline structure)
        page_data = {
            "page_number": result['page'],
            "page_url": result.get('page_url', result.get('original_url', '')),  # Use correct page_url
            "patterns": result['patterns'],
            "pattern_count": calculate_pattern_counts(result['patterns'])
        }
        images_data.append(page_data)
        
        # Collect patterns
        all_patterns.extend(result['patterns'])
    
    # Create search index
    search_index = create_search_index_images(all_patterns, images_data)
    
    # Aggregate pattern statistics
    aggregated_patterns = aggregate_pattern_statistics(all_patterns)
    
    # Calculate processing statistics
    processing_stats = calculate_processing_statistics(page_results)
    
    final_result = {
        "project_id": project_id,
        "file_id": file_id,
        "processing_metadata": {
            "input_type": "images",  # Distinguish from PDF processing
            "total_pages": total_images or len(page_results),
            "processed_pages": len(successful_results),
            "failed_pages": [{"page": r['page'], "error": r['error']} for r in failed_results],
            "processing_time_seconds": actual_processing_time if actual_processing_time else time.time() - compilation_start_time,
            "compilation_time_seconds": time.time() - compilation_start_time,
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "parallel_workers": PARALLEL_WORKERS,
                "image_dpi": IMAGE_DPI,  # Still relevant for image processing
                "vision_api_version": "v1"
            },
            "statistics": processing_stats
        },
        "pages": images_data,  # Use 'pages' for consistency with PDF pipeline
        "aggregated_patterns": aggregated_patterns,
        "search_index": search_index
    }
    
    logger.info(f"Final image result compiled: {len(all_patterns)} total patterns across {len(successful_results)} pages")
    return final_result

def create_search_index_images(all_patterns, images_data):
    """Create optimized search index for image processing"""
    
    # Extract unique text values (instead of pattern types)
    unique_texts = list(set(p['text'] for p in all_patterns))
    
    # Get images that have patterns
    images_with_patterns = sorted(list(set(p['page_number'] for p in all_patterns)))
    
    # Create pattern count by page mapping
    patterns_by_page = {}
    for page in images_data:
        if page['patterns']:
            patterns_by_page[str(page['page_number'])] = len(page['patterns'])
    
    return {
        "unique_patterns": unique_texts,
        "pages_with_patterns": images_with_patterns,
        "total_pattern_count": len(all_patterns),
        "patterns_by_page": patterns_by_page
    }

def calculate_pattern_counts(patterns):
    """Calculate pattern counts by text content"""
    if not patterns:
        return {}
    
    counts = defaultdict(int)
    for pattern in patterns:
        # Group by text content instead of pattern_type
        text = pattern['text'].strip()
        counts[text] += 1
    
    return dict(counts)

def create_search_index(all_patterns, pages_data):
    """Create optimized search index"""
    
    # Extract unique text values (instead of pattern types)
    unique_texts = list(set(p['text'] for p in all_patterns))
    
    # Get pages that have patterns
    pages_with_patterns = sorted(list(set(p['page_number'] for p in all_patterns)))
    
    # Create pattern count by page mapping
    patterns_by_page = {}
    for page in pages_data:
        if page['patterns']:
            patterns_by_page[str(page['page_number'])] = len(page['patterns'])
    
    return {
        "unique_patterns": unique_texts,
        "pages_with_patterns": pages_with_patterns,
        "total_pattern_count": len(all_patterns),
        "patterns_by_page": patterns_by_page
    }

def aggregate_pattern_statistics(all_patterns):
    """Aggregate pattern statistics for quick access"""
    
    if not all_patterns:
        return {}
    
    # Group patterns by text content instead of pattern_type
    pattern_groups = defaultdict(list)
    for pattern in all_patterns:
        text = pattern['text'].strip()
        pattern_groups[text].append(pattern)
    
    # Create aggregated statistics
    aggregated = {}
    for text, patterns in pattern_groups.items():
        pages = sorted(list(set(p['page_number'] for p in patterns)))
        aggregated[text] = {
            "total_count": len(patterns),
            "pages": pages,
            "avg_confidence": sum(p['confidence'] for p in patterns) / len(patterns) if patterns else 0.0
        }
    
    return aggregated

def calculate_processing_statistics(page_results):
    """Calculate processing performance statistics"""
    
    successful_results = [r for r in page_results if r['success']]
    
    if not successful_results:
        return {
            "avg_processing_time_per_page": 0,
            "total_patterns_found": 0
        }
    
    processing_times = [r.get('processing_time', 0) for r in successful_results]
    total_patterns = sum(r.get('pattern_count', 0) for r in successful_results)
    
    return {
        "avg_processing_time_per_page": sum(processing_times) / len(processing_times),
        "min_processing_time": min(processing_times),
        "max_processing_time": max(processing_times),
        "total_patterns_found": total_patterns,
        "success_rate": len(successful_results) / len(page_results) * 100
    } 