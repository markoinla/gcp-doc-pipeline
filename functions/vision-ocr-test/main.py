import functions_framework
import json
import re
from google.cloud import vision
import requests

@functions_framework.http
def vision_ocr_test(request):
    """Test Google Cloud Vision API OCR on architectural drawing"""
    
    try:
        # Get the image URL from request
        request_json = request.get_json()
        if not request_json:
            return {"error": "No JSON body provided"}, 400
            
        image_url = request_json.get('imageUrl')
        if not image_url:
            return {"error": "imageUrl is required"}, 400
            
        print(f"Testing Vision API OCR on image: {image_url}")
        print("Expected results: PT1=8 matches, PT2=22 matches")
        
        # Initialize Vision API client
        client = vision.ImageAnnotatorClient()
        
        # Download image from URL
        response = requests.get(image_url)
        if response.status_code != 200:
            return {"error": f"Failed to download image: {response.status_code}"}, 400
            
        image_content = response.content
        print(f"Downloaded image: {len(image_content)} bytes")
        
        # Create Vision API image object
        image = vision.Image(content=image_content)
        
        # Perform text detection with detailed response
        response = client.text_detection(image=image)
        
        if response.error.message:
            return {"error": f"Vision API error: {response.error.message}"}, 500
            
        texts = response.text_annotations
        print(f"Vision API found {len(texts)} text annotations")
        
        # Analyze results
        results = analyze_vision_results(texts)
        
        # Return comprehensive results
        return {
            "success": True,
            "image_url": image_url,
            "total_text_annotations": len(texts),
            "analysis": results,
            "raw_text_sample": texts[0].description[:500] if texts else "No text found"
        }
        
    except Exception as e:
        print(f"Error in vision_ocr_test: {str(e)}")
        return {"error": str(e)}, 500

def analyze_vision_results(texts):
    """Analyze Vision API results for PT patterns"""
    
    if not texts:
        return {
            "pt1_matches": 0,
            "pt2_matches": 0,
            "error": "No text detected by Vision API"
        }
    
    # Get full text (first annotation contains all text)
    full_text = texts[0].description
    print(f"Full text length: {len(full_text)} characters")
    
    # Define comprehensive PT pattern regex
    pt_patterns = [
        re.compile(r'\bPT1\b', re.IGNORECASE),           # Exact PT1
        re.compile(r'\bPT-1\b', re.IGNORECASE),          # PT-1
        re.compile(r'\bPT\s*1\b', re.IGNORECASE),        # PT 1, PT  1
        re.compile(r'\bPT\.1\b', re.IGNORECASE),         # PT.1
        re.compile(r'\bPT_1\b', re.IGNORECASE),          # PT_1
        re.compile(r'\bPT2\b', re.IGNORECASE),           # Exact PT2
        re.compile(r'\bPT-2\b', re.IGNORECASE),          # PT-2
        re.compile(r'\bPT\s*2\b', re.IGNORECASE),        # PT 2, PT  2
        re.compile(r'\bPT\.2\b', re.IGNORECASE),         # PT.2
        re.compile(r'\bPT_2\b', re.IGNORECASE),          # PT_2
    ]
    
    # Find all PT1 and PT2 matches
    pt1_matches = []
    pt2_matches = []
    all_matches = []
    
    # Search individual text annotations for precise locations
    for i, text in enumerate(texts[1:], 1):  # Skip first (full text)
        text_content = text.description.strip()
        
        # Check for PT1 patterns
        for pattern in pt_patterns[:5]:  # First 5 are PT1 patterns
            if pattern.search(text_content):
                match_info = {
                    "text": text_content,
                    "confidence": getattr(text, 'confidence', 0.0),
                    "bounding_box": extract_bounding_box(text),
                    "pattern_type": "PT1"
                }
                pt1_matches.append(match_info)
                all_matches.append(match_info)
                print(f"PT1 match: '{text_content}' (confidence: {match_info['confidence']:.3f})")
                break
                
        # Check for PT2 patterns
        for pattern in pt_patterns[5:]:  # Last 5 are PT2 patterns
            if pattern.search(text_content):
                match_info = {
                    "text": text_content,
                    "confidence": getattr(text, 'confidence', 0.0),
                    "bounding_box": extract_bounding_box(text),
                    "pattern_type": "PT2"
                }
                pt2_matches.append(match_info)
                all_matches.append(match_info)
                print(f"PT2 match: '{text_content}' (confidence: {match_info['confidence']:.3f})")
                break
    
    # Also search full text for additional matches
    pt1_full_text_matches = []
    pt2_full_text_matches = []
    
    for pattern in pt_patterns[:5]:
        matches = list(pattern.finditer(full_text))
        pt1_full_text_matches.extend([m.group() for m in matches])
        
    for pattern in pt_patterns[5:]:
        matches = list(pattern.finditer(full_text))
        pt2_full_text_matches.extend([m.group() for m in matches])
    
    print(f"=== VISION API RESULTS ===")
    print(f"PT1 individual annotations: {len(pt1_matches)}")
    print(f"PT2 individual annotations: {len(pt2_matches)}")
    print(f"PT1 in full text: {len(set(pt1_full_text_matches))}")
    print(f"PT2 in full text: {len(set(pt2_full_text_matches))}")
    print(f"Expected: PT1=8, PT2=22")
    
    return {
        "pt1_matches": len(pt1_matches),
        "pt2_matches": len(pt2_matches),
        "pt1_full_text_count": len(set(pt1_full_text_matches)),
        "pt2_full_text_count": len(set(pt2_full_text_matches)),
        "expected_pt1": 8,
        "expected_pt2": 22,
        "success_rate_pt1": len(pt1_matches) / 8 * 100 if len(pt1_matches) <= 8 else 100,
        "success_rate_pt2": len(pt2_matches) / 22 * 100 if len(pt2_matches) <= 22 else 100,
        "detailed_matches": {
            "pt1": pt1_matches,
            "pt2": pt2_matches
        },
        "confidence_stats": calculate_confidence_stats(all_matches)
    }

def extract_bounding_box(text_annotation):
    """Extract bounding box coordinates from Vision API text annotation"""
    if hasattr(text_annotation, 'bounding_poly') and text_annotation.bounding_poly:
        vertices = []
        for vertex in text_annotation.bounding_poly.vertices:
            vertices.append({
                "x": vertex.x,
                "y": vertex.y
            })
        return {"vertices": vertices}
    return None

def calculate_confidence_stats(matches):
    """Calculate confidence statistics for matches"""
    if not matches:
        return {"average": 0, "min": 0, "max": 0, "count": 0}
        
    confidences = [m.get('confidence', 0) for m in matches]
    return {
        "average": sum(confidences) / len(confidences),
        "min": min(confidences),
        "max": max(confidences),
        "count": len(confidences)
    } 