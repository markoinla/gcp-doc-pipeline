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
    
    logger.info(f"Page {page_num}: Processing {len(vision_response.text_annotations)-1} text annotations")
    logger.info(f"Page {page_num}: Using regex patterns: {PATTERN_REGEXES}")
    
    annotations = vision_response.text_annotations[1:]  # Skip first (full text)
    
    # Method 1: Process individual annotations (for patterns that aren't split)
    for annotation in annotations:
        text = annotation.description.strip()
        logger.debug(f"Page {page_num}: Processing text annotation: '{text}'")
        
        for i, regex in enumerate(compiled_regexes):
            match = regex.search(text)
            if match:
                matched_text = match.group()
                logger.info(f"Page {page_num}: ✅ Pattern {i+1} '{PATTERN_REGEXES[i]}' matched '{matched_text}' in text '{text}'")
                pattern = create_pattern_object(
                    matched_text, annotation, page_num, pattern_id_counter
                )
                patterns.append(pattern)
                pattern_id_counter += 1
                break
    
    # Method 2: Reconstruct split patterns by combining adjacent annotations
    logger.info(f"Page {page_num}: Attempting to reconstruct split patterns from {len(annotations)} annotations")
    reconstructed_patterns = reconstruct_split_patterns(annotations, page_num, pattern_id_counter, compiled_regexes)
    patterns.extend(reconstructed_patterns)
    
    logger.info(f"Page {page_num}: Extracted {len(patterns)} total patterns ({len(reconstructed_patterns)} reconstructed)")
    if len(patterns) == 0:
        logger.warning(f"Page {page_num}: No patterns found! Check if Vision API detected the right text.")
    
    return patterns

def reconstruct_split_patterns(annotations, page_num, pattern_id_counter, compiled_regexes):
    """Reconstruct patterns that were split across multiple annotations by Vision API"""
    
    reconstructed_patterns = []
    
    # Sort annotations by position (left to right, top to bottom)
    sorted_annotations = sorted(annotations, key=lambda a: (
        a.bounding_poly.vertices[0].y,  # Top edge (y coordinate)
        a.bounding_poly.vertices[0].x   # Left edge (x coordinate)
    ))
    
    # Look for patterns formed by combining 2-3 adjacent annotations
    for i in range(len(sorted_annotations) - 1):
        current = sorted_annotations[i]
        next_ann = sorted_annotations[i + 1]
        
        # Check if annotations are close enough to be part of the same pattern
        if are_annotations_adjacent(current, next_ann):
            current_text = current.description.strip()
            next_text = next_ann.description.strip()
            
            # Try 2-part combinations: "A" + "-" + "1" or "AB" + "-" + "1"
            combined_2 = current_text + next_text
            
            # Check if 2-part combination matches any pattern
            for regex_idx, regex in enumerate(compiled_regexes):
                if regex.search(combined_2):
                    logger.info(f"Page {page_num}: 🔗 Reconstructed 2-part pattern '{combined_2}' from '{current_text}' + '{next_text}'")
                    
                    # Create pattern using combined bounding boxes
                    pattern = create_pattern_object_combined(
                        combined_2, [current, next_ann], page_num, pattern_id_counter + len(reconstructed_patterns)
                    )
                    reconstructed_patterns.append(pattern)
                    break
            
            # Try 3-part combinations if we have a third annotation
            if i + 2 < len(sorted_annotations):
                third_ann = sorted_annotations[i + 2]
                if are_annotations_adjacent(next_ann, third_ann):
                    third_text = third_ann.description.strip()
                    combined_3 = current_text + next_text + third_text
                    
                    # Check if 3-part combination matches any pattern
                    for regex_idx, regex in enumerate(compiled_regexes):
                        if regex.search(combined_3):
                            logger.info(f"Page {page_num}: 🔗 Reconstructed 3-part pattern '{combined_3}' from '{current_text}' + '{next_text}' + '{third_text}'")
                            
                            # Create pattern using combined bounding boxes
                            pattern = create_pattern_object_combined(
                                combined_3, [current, next_ann, third_ann], page_num, pattern_id_counter + len(reconstructed_patterns)
                            )
                            reconstructed_patterns.append(pattern)
                            break
    
    return reconstructed_patterns

def are_annotations_adjacent(ann1, ann2, max_distance=50):
    """Check if two annotations are close enough to be part of the same pattern"""
    
    # Get bounding boxes
    box1 = ann1.bounding_poly.vertices
    box2 = ann2.bounding_poly.vertices
    
    # Calculate centers
    center1_x = sum(v.x for v in box1) / len(box1)
    center1_y = sum(v.y for v in box1) / len(box1)
    center2_x = sum(v.x for v in box2) / len(box2)
    center2_y = sum(v.y for v in box2) / len(box2)
    
    # Calculate distance
    distance = ((center2_x - center1_x) ** 2 + (center2_y - center1_y) ** 2) ** 0.5
    
    # Check if they're on roughly the same line (similar y-coordinates)
    y_diff = abs(center2_y - center1_y)
    same_line = y_diff < 20  # Allow some vertical tolerance
    
    return distance < max_distance and same_line

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

def create_pattern_object_combined(text, annotations, page_num, pattern_id):
    """Create pattern object with combined bounding boxes from multiple annotations"""
    
    # Combine all bounding boxes to create a unified bounding box
    all_vertices = []
    for annotation in annotations:
        all_vertices.extend(annotation.bounding_poly.vertices)
    
    # Calculate the bounding box that encompasses all annotations
    min_x = min(v.x for v in all_vertices)
    min_y = min(v.y for v in all_vertices)
    max_x = max(v.x for v in all_vertices)
    max_y = max(v.y for v in all_vertices)
    
    width = max_x - min_x
    height = max_y - min_y
    
    # Calculate average confidence
    confidences = [getattr(ann, 'confidence', 0.0) for ann in annotations]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    pattern_type = text.upper().strip()
    
    logger.debug(f"Page {page_num}: Combined bounding box for '{text}': ({min_x}, {min_y}) {width}x{height} from {len(annotations)} annotations")
    
    return {
        "pattern_id": f"{pattern_type.lower()}_page{page_num}_{pattern_id:03d}",
        "pattern_type": pattern_type,
        "text": text,
        "page_number": page_num,
        "coordinates": {
            "x": min_x,
            "y": min_y, 
            "width": width,
            "height": height
        },
        "confidence": avg_confidence
    } 