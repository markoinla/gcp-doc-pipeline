import re
import logging

from config import PATTERN_REGEXES

logger = logging.getLogger(__name__)

def extract_patterns_from_vision(vision_response, page_num):
    """Extract all paragraph groupings from Vision API response"""
    
    if not vision_response.text_annotations:
        logger.info(f"Page {page_num}: No text annotations found")
        return []
    
    patterns = []
    pattern_id_counter = 1
    
    # Check if we have full_text_annotation with paragraph structure
    if hasattr(vision_response, 'full_text_annotation') and vision_response.full_text_annotation:
        logger.info(f"Page {page_num}: Using paragraph-based extraction")
        patterns = extract_from_paragraphs(vision_response.full_text_annotation, page_num, pattern_id_counter)
    else:
        # Fallback to individual text annotations if no paragraph structure
        logger.info(f"Page {page_num}: No paragraph structure found, using individual text annotations")
        patterns = extract_from_text_annotations(vision_response.text_annotations, page_num, pattern_id_counter)
    
    logger.info(f"Page {page_num}: Extracted {len(patterns)} text elements from paragraphs")
    if len(patterns) == 0:
        logger.warning(f"Page {page_num}: No text found! Check if Vision API detected any text.")
    
    return patterns

def extract_from_paragraphs(full_text_annotation, page_num, pattern_id_counter):
    """Extract all text from paragraph groupings"""
    patterns = []
    
    # Navigate the hierarchy: pages -> blocks -> paragraphs
    for page in full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                # Extract text from all words in the paragraph
                paragraph_text = ""
                word_vertices = []
                word_confidences = []
                
                for word in paragraph.words:
                    word_text = ""
                    for symbol in word.symbols:
                        word_text += symbol.text
                        # Collect confidence scores
                        if hasattr(symbol, 'confidence'):
                            word_confidences.append(symbol.confidence)
                    
                    paragraph_text += word_text
                    
                    # Add space after word if it doesn't end the paragraph
                    if hasattr(word.symbols[-1], 'property') and word.symbols[-1].property:
                        if hasattr(word.symbols[-1].property, 'detected_break'):
                            break_type = word.symbols[-1].property.detected_break.type_
                            if break_type in [1, 3]:  # SPACE or LINE_BREAK
                                paragraph_text += " "
                    else:
                        paragraph_text += " "  # Default to adding space
                    
                    # Collect word bounding boxes for paragraph bounding box calculation
                    if word.bounding_box and word.bounding_box.vertices:
                        word_vertices.extend(word.bounding_box.vertices)
                
                # Clean up text
                paragraph_text = paragraph_text.strip()
                
                if paragraph_text:  # Only create pattern if we have text
                    # Calculate average confidence
                    avg_confidence = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0
                    
                    # Create pattern object
                    pattern = create_pattern_object_from_paragraph(
                        paragraph_text, paragraph, word_vertices, avg_confidence, page_num, pattern_id_counter
                    )
                    patterns.append(pattern)
                    pattern_id_counter += 1
                    
                    logger.debug(f"Page {page_num}: Extracted paragraph text: '{paragraph_text}'")
    
    return patterns

def extract_from_text_annotations(text_annotations, page_num, pattern_id_counter):
    """Fallback: extract from individual text annotations if no paragraph structure"""
    patterns = []
    
    # Skip the first annotation (full text) and process individual annotations
    annotations = text_annotations[1:] if len(text_annotations) > 1 else []
    
    for annotation in annotations:
        text = annotation.description.strip()
        if text:  # Only create pattern if we have text
            pattern = create_pattern_object(
                text, annotation, page_num, pattern_id_counter
            )
            patterns.append(pattern)
            pattern_id_counter += 1
            
            logger.debug(f"Page {page_num}: Extracted annotation text: '{text}'")
    
    return patterns

def create_pattern_object_from_paragraph(text, paragraph, word_vertices, confidence, page_num, pattern_id):
    """Create pattern object from paragraph data"""
    
    # Use paragraph bounding box if available, otherwise calculate from word vertices
    if paragraph.bounding_box and paragraph.bounding_box.vertices:
        vertices = paragraph.bounding_box.vertices
    elif word_vertices:
        # Calculate bounding box from all word vertices
        min_x = min(v.x for v in word_vertices if hasattr(v, 'x'))
        min_y = min(v.y for v in word_vertices if hasattr(v, 'y'))
        max_x = max(v.x for v in word_vertices if hasattr(v, 'x'))
        max_y = max(v.y for v in word_vertices if hasattr(v, 'y'))
        
        # Create mock vertices for bounding box calculation
        class MockVertex:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        
        vertices = [
            MockVertex(min_x, min_y),
            MockVertex(max_x, min_y),
            MockVertex(max_x, max_y),
            MockVertex(min_x, max_y)
        ]
    else:
        # Fallback to default coordinates
        vertices = [MockVertex(0, 0), MockVertex(100, 0), MockVertex(100, 20), MockVertex(0, 20)]
    
    # Extract coordinates
    x = min(v.x for v in vertices)
    y = min(v.y for v in vertices)
    width = max(v.x for v in vertices) - x
    height = max(v.y for v in vertices) - y
    
    return {
        "text": text,
        "page_number": page_num,
        "coordinates": {
            "x": x,
            "y": y, 
            "width": width,
            "height": height
        },
        "confidence": confidence
    }

def create_pattern_object(text, annotation, page_num, pattern_id):
    """Create search-optimized pattern object from text annotation"""
    
    # Extract coordinates
    vertices = annotation.bounding_poly.vertices
    x = min(v.x for v in vertices)
    y = min(v.y for v in vertices)
    width = max(v.x for v in vertices) - x
    height = max(v.y for v in vertices) - y
    
    return {
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

# Keep these functions for backward compatibility (though they're no longer used)
def reconstruct_split_patterns(annotations, page_num, pattern_id_counter, compiled_regexes):
    """Legacy function - no longer used with paragraph extraction"""
    return []

def are_annotations_adjacent(ann1, ann2, max_distance=50):
    """Legacy function - no longer used with paragraph extraction"""
    return False

def create_pattern_object_combined(text, annotations, page_num, pattern_id):
    """Legacy function - no longer used with paragraph extraction"""
    return create_pattern_object(text, annotations[0], page_num, pattern_id) 