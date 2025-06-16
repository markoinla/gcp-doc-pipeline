import time
import logging
from datetime import datetime
from collections import defaultdict

from config import PARALLEL_WORKERS, IMAGE_DPI

logger = logging.getLogger(__name__)

def compile_final_json(page_results, project_id, file_id):
    """Compile search-optimized final JSON"""
    
    start_time = time.time()
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
            "processing_time_seconds": time.time() - start_time,
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

def calculate_pattern_counts(patterns):
    """Calculate pattern counts by type"""
    if not patterns:
        return {}
    
    counts = defaultdict(int)
    for pattern in patterns:
        counts[pattern['pattern_type']] += 1
    
    return dict(counts)

def create_search_index(all_patterns, pages_data):
    """Create optimized search index"""
    
    # Extract unique pattern types
    unique_patterns = list(set(p['pattern_type'] for p in all_patterns))
    
    # Get pages that have patterns
    pages_with_patterns = sorted(list(set(p['page_number'] for p in all_patterns)))
    
    # Create pattern count by page mapping
    patterns_by_page = {}
    for page in pages_data:
        if page['patterns']:
            patterns_by_page[str(page['page_number'])] = len(page['patterns'])
    
    return {
        "unique_patterns": unique_patterns,
        "pages_with_patterns": pages_with_patterns,
        "total_pattern_count": len(all_patterns),
        "patterns_by_page": patterns_by_page
    }

def aggregate_pattern_statistics(all_patterns):
    """Aggregate pattern statistics for quick access"""
    
    if not all_patterns:
        return {}
    
    # Group patterns by type
    pattern_groups = defaultdict(list)
    for pattern in all_patterns:
        pattern_groups[pattern['pattern_type']].append(pattern)
    
    # Create aggregated statistics
    aggregated = {}
    for pattern_type, patterns in pattern_groups.items():
        pages = sorted(list(set(p['page_number'] for p in patterns)))
        aggregated[pattern_type] = {
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