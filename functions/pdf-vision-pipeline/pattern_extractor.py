import re
import logging

from config import PATTERN_REGEXES

logger = logging.getLogger(__name__)

def extract_patterns_from_vision(vision_response, page_num):
    """Extract and structure patterns for search optimization"""
    
    if not vision_response.text_annotations:
        logger.info(f"Page {page_num}: No text annotations found")
        return []
    
    patterns = []
    pattern_id_counter = 1
    
    # Compile regex patterns
    compiled_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERN_REGEXES]
    
    # Process individual text annotations  
    for annotation in vision_response.text_annotations[1:]:  # Skip first (full text)
        text = annotation.description.strip()
        
        for regex in compiled_regexes:
            if regex.match(text):
                pattern = create_pattern_object(
                    text, annotation, page_num, pattern_id_counter
                )
                patterns.append(pattern)
                pattern_id_counter += 1
                break
    
    logger.info(f"Page {page_num}: Extracted {len(patterns)} patterns")
    return patterns

def create_pattern_object(text, annotation, page_num, pattern_id):
    """Create search-optimized pattern object"""
    
    # Extract coordinates
    vertices = annotation.bounding_poly.vertices
    x = min(v.x for v in vertices)
    y = min(v.y for v in vertices)
    width = max(v.x for v in vertices) - x
    height = max(v.y for v in vertices) - y
    
    pattern_type = text.upper().strip()
    
    return {
        "pattern_id": f"{pattern_type.lower()}_page{page_num}_{pattern_id:03d}",
        "pattern_type": pattern_type,
        "text": text,
        "page_number": page_num,
        "coordinates": {
            "x": x,
            "y": y, 
            "width": width,
            "height": height
        },
        "confidence": getattr(annotation, 'confidence', 0.0)
    } 