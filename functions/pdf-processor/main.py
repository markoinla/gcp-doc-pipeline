import os
import json
import tempfile
import uuid
from datetime import datetime
import re
import boto3
from botocore.config import Config
from google.cloud import secretmanager
from google.cloud import storage
from google.cloud import documentai
import requests
import functions_framework
import PyPDF2
import io

@functions_framework.http
def process_pdf(request):
    """Main function to process PDF with Document AI and upload to R2"""
    try:
        # Parse request
        request_json = request.get_json()
        
        # Validate required parameters
        if not request_json:
            return {"status": "error", "error": "No JSON body provided"}, 400
            
        required_fields = ['pdfUrl', 'callbackUrl', 'r2Config']
        for field in required_fields:
            if field not in request_json:
                return {"status": "error", "error": f"Missing required field: {field}"}, 400
        
        pdf_url = request_json['pdfUrl']
        callback_url = request_json['callbackUrl']
        r2_config = request_json['r2Config']
        
        # Use our configured processor
        processor_id = "fa7abbc0ea6541c5"
        location = "us"
        project_id = "ladders-doc-pipeline-462921"
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        print(f"Starting PDF processing for document ID: {document_id}")
        print(f"PDF URL: {pdf_url}")
        
        # Process PDF
        result = process_pdf_document(
            pdf_url=pdf_url,
            document_id=document_id,
            processor_id=processor_id,
            project_id=project_id,
            location=location,
            r2_config=r2_config
        )
        
        # Send callback
        send_callback(callback_url, result)
        
        return {"status": "success", "document_id": document_id, "result": result}
        
    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")
        return {"status": "error", "error": str(e)}, 500

def process_pdf_document(pdf_url, document_id, processor_id, project_id, location, r2_config):
    """Process PDF by chunking into 15-page segments for Document AI"""
    start_time = datetime.now()
    
    print(f"Processing PDF document: {document_id}")
    
    # Download PDF to temporary location
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    
    try:
        # Check PDF page count and split if necessary
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            
        print(f"PDF has {total_pages} pages")
        
        if total_pages <= 15:
            # Process normally if under page limit
            print("PDF is under 15 pages, processing normally")
            doc = process_single_pdf_chunk(temp_pdf_path, processor_id, project_id, location)
            all_pages = doc.pages
            combined_text = doc.text
        else:
            # Split into chunks and process each
            print(f"PDF has {total_pages} pages, splitting into chunks")
            chunks = split_pdf_into_chunks(temp_pdf_path, max_pages=15)
            
            all_pages = []
            combined_text = ""
            page_offset = 0
            
            for i, chunk_path in enumerate(chunks):
                try:
                    print(f"Processing chunk {i+1}/{len(chunks)}")
                    chunk_doc = process_single_pdf_chunk(chunk_path, processor_id, project_id, location)
                    
                    # Adjust page numbers for chunks
                    for page in chunk_doc.pages:
                        # Update page number to reflect position in original document
                        page.page_number = page.page_number + page_offset
                    
                    all_pages.extend(chunk_doc.pages)
                    combined_text += chunk_doc.text + "\n"
                    page_offset += len(chunk_doc.pages)
                    
                finally:
                    # Clean up chunk file
                    if os.path.exists(chunk_path):
                        os.unlink(chunk_path)
        
        # Create a combined document object
        combined_doc = create_combined_document(all_pages, combined_text, total_pages)
        
        print(f"Combined document has {len(all_pages)} pages")
        
        # Extract and process data
        processing_result = extract_and_process_data(combined_doc, document_id, pdf_url, start_time)
        
        # Upload to R2
        upload_result = upload_to_r2(processing_result, r2_config, document_id)
        
        processing_time = datetime.now() - start_time
        
        return {
            "document_id": document_id,
            "status": "success",
            "uploaded_files": upload_result,
            "items_found": processing_result['summary']['total_items'],
            "unique_items": processing_result['summary']['unique_items'],
            "patterns_found": processing_result['summary']['item_breakdown']['patterns'],
            "words_found": processing_result['summary']['item_breakdown']['words'],
            "total_pages": processing_result['main_document']['total_pages'],
            "processing_time": str(processing_time)
        }
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)

def split_pdf_into_chunks(pdf_path, max_pages=15):
    """Split PDF into chunks of max_pages or less"""
    chunks = []
    
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        
        for start_page in range(0, total_pages, max_pages):
            end_page = min(start_page + max_pages, total_pages)
            
            # Create a new PDF with the chunk
            pdf_writer = PyPDF2.PdfWriter()
            
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Save chunk to temporary file
            chunk_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            pdf_writer.write(chunk_file)
            chunk_file.close()
            
            chunks.append(chunk_file.name)
            print(f"Created chunk {len(chunks)}: pages {start_page+1}-{end_page}")
    
    return chunks

def process_single_pdf_chunk(pdf_path, processor_id, project_id, location):
    """Process a single PDF chunk with Document AI"""
    client = documentai.DocumentProcessorServiceClient()
    
    # Read PDF file
    with open(pdf_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
    
    print(f"Chunk file size: {len(pdf_content)} bytes")
    
    # Configure Document AI request
    processor_name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    
    # Process document
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )
    )
    
    print("Sending chunk to Document AI...")
    result = client.process_document(request=request)
    print("Document AI chunk processing complete")
    
    return result.document

def create_combined_document(all_pages, combined_text, total_pages):
    """Create a combined document object from processed chunks"""
    # Create a mock document object with the combined data
    class CombinedDocument:
        def __init__(self, pages, text):
            self.pages = pages
            self.text = text
            self.entities = []  # Empty for now
    
    return CombinedDocument(all_pages, combined_text)

def extract_and_process_data(doc, document_id, pdf_url, start_time):
    """Extract patterns and words with search-optimized structure"""
    
    print("Extracting patterns and words with search-optimized structure...")
    
    # Extract both patterns and words with bounding boxes
    items = extract_items_with_bounding_boxes(doc)
    
    # Calculate confidence scores
    avg_confidence = calculate_average_confidence(doc)
    
    # Create search indexes
    search_indexes = create_search_indexes(items)
    
    # Generate statistics
    statistics = generate_statistics(items)
    
    # Count totals
    total_items = sum(item["total_count"] for item in items.values())
    unique_items = len(items)
    pages_with_content = set()
    
    for item in items.values():
        for location in item["locations"]:
            pages_with_content.add(location["page"])
    
    # Create main search-optimized document
    main_document = {
        "document_id": document_id,
        "source_url": pdf_url,
        "processed_at": datetime.now().isoformat(),
        "total_pages": len(doc.pages),
        "processing_metadata": {
            "processing_time": str(datetime.now() - start_time),
            "ocr_confidence": avg_confidence,
            "total_items": total_items,
            "unique_items": unique_items,
            "pages_with_content": sorted(list(pages_with_content))
        },
        "items": items,
        "search_indexes": search_indexes,
        "statistics": statistics
    }
    
    # Create simplified summary for quick overview
    summary = {
        "document_id": document_id,
        "total_items": total_items,
        "unique_items": unique_items,
        "pages_with_content": len(pages_with_content),
        "confidence_score": avg_confidence,
        "item_breakdown": {
            "patterns": statistics["item_counts_by_type"]["pattern"],
            "words": statistics["item_counts_by_type"]["word"]
        },
        "top_categories": dict(list(statistics["items_by_category"].items())[:5])
    }
    
    print(f"Extracted {total_items} total items ({unique_items} unique) across {len(pages_with_content)} pages")
    
    return {
        "main_document": main_document,
        "summary": summary
    }

def create_search_indexes(items):
    """Create search indexes for efficient querying"""
    by_page = {}
    by_type = {"pattern": [], "word": []}
    by_category = {}
    
    for item_key, item_data in items.items():
        # Index by type
        by_type[item_data["type"]].append(item_key)
        
        # Index by category
        category = item_data["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(item_key)
        
        # Index by page
        for location in item_data["locations"]:
            page = str(location["page"])
            if page not in by_page:
                by_page[page] = []
            if item_key not in by_page[page]:
                by_page[page].append(item_key)
    
    return {
        "by_page": by_page,
        "by_type": by_type,
        "by_category": by_category
    }

def generate_statistics(items):
    """Generate statistics about the extracted items"""
    
    # Count by type
    item_counts_by_type = {"pattern": 0, "word": 0}
    
    # Count by category
    items_by_category = {}
    
    # Pattern type analysis
    pattern_types = {}
    
    # Word frequency
    word_frequency = {}
    
    # Page density
    page_density = {}
    
    for item_key, item_data in items.items():
        item_type = item_data["type"]
        category = item_data["category"]
        count = item_data["total_count"]
        
        # Count by type
        item_counts_by_type[item_type] += count
        
        # Count by category
        if category not in items_by_category:
            items_by_category[category] = 0
        items_by_category[category] += count
        
        # Pattern type analysis
        if item_type == "pattern":
            prefix = item_key.split('-')[0] if '-' in item_key else item_key[:2]
            if prefix not in pattern_types:
                pattern_types[prefix] = 0
            pattern_types[prefix] += count
        
        # Word frequency (top words only)
        if item_type == "word":
            word_frequency[item_key] = count
        
        # Page density
        for location in item_data["locations"]:
            page = location["page"]
            if page not in page_density:
                page_density[page] = 0
            page_density[page] += 1
    
    # Sort and limit results
    items_by_category = dict(sorted(items_by_category.items(), key=lambda x: x[1], reverse=True))
    pattern_types = dict(sorted(pattern_types.items(), key=lambda x: x[1], reverse=True))
    word_frequency = dict(sorted(word_frequency.items(), key=lambda x: x[1], reverse=True)[:20])  # Top 20 words
    pages_by_density = [{"page": page, "item_count": count} for page, count in sorted(page_density.items(), key=lambda x: x[1], reverse=True)]
    
    return {
        "item_counts_by_type": item_counts_by_type,
        "items_by_category": items_by_category,
        "pattern_types": pattern_types,
        "word_frequency": word_frequency,
        "pages_by_density": pages_by_density
    }

def extract_items_with_bounding_boxes(doc):
    """Extract both patterns and words with bounding boxes from Document AI tokens"""
    items = {}
    
    # Define pattern regex - matching PT-1, PT1, M1, M-1, etc.
    pattern_regex = re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE)
    
    # Define word regex - meaningful words (3+ chars, not purely numeric)
    word_regex = re.compile(r'\b[A-Za-z][A-Za-z\s]{2,}\b')
    
    print("Extracting patterns and words from Document AI tokens...")
    
    # Extract from each page's tokens
    for page_num, page in enumerate(doc.pages, 1):
        if hasattr(page, 'tokens'):
            for token in page.tokens:
                # Get the text content of the token
                token_text = ""
                if hasattr(token, 'layout') and hasattr(token.layout, 'text_anchor'):
                    text_segments = token.layout.text_anchor.text_segments
                    for segment in text_segments:
                        start_idx = getattr(segment, 'start_index', 0)
                        end_idx = getattr(segment, 'end_index', len(doc.text))
                        token_text += doc.text[start_idx:end_idx]
                
                if not token_text.strip():
                    continue
                
                # Extract bounding box and confidence
                bounding_box = None
                confidence = 0.95
                
                if hasattr(token, 'layout') and hasattr(token.layout, 'bounding_poly'):
                    vertices = []
                    if hasattr(token.layout.bounding_poly, 'vertices'):
                        for vertex in token.layout.bounding_poly.vertices:
                            vertices.append({
                                "x": getattr(vertex, 'x', 0),
                                "y": getattr(vertex, 'y', 0)
                            })
                        bounding_box = {
                            "vertices": vertices
                        }
                
                if hasattr(token, 'layout') and hasattr(token.layout, 'confidence'):
                    confidence = token.layout.confidence
                
                # Check if token is a pattern
                if pattern_regex.match(token_text):
                    item_key = token_text.upper().strip()
                    item_type = "pattern"
                    category = categorize_pattern(item_key)
                
                # Check if token is a meaningful word
                elif word_regex.match(token_text) and len(token_text.strip()) >= 3:
                    item_key = token_text.lower().strip()
                    item_type = "word"
                    category = categorize_word(item_key)
                else:
                    continue
                
                # Add to items collection
                if item_key not in items:
                    items[item_key] = {
                        "type": item_type,
                        "category": category,
                        "total_count": 0,
                        "locations": []
                    }
                
                # Check for duplicates on same page
                existing_on_page = False
                for existing_loc in items[item_key]["locations"]:
                    if existing_loc["page"] == page_num:
                        # If very close coordinates, consider it duplicate
                        if bounding_box and existing_loc.get("bounding_box"):
                            existing_on_page = True
                            break
                
                if not existing_on_page:
                    items[item_key]["locations"].append({
                        "page": page_num,
                        "bounding_box": bounding_box,
                        "confidence": confidence
                    })
                    items[item_key]["total_count"] += 1
        
        # Also check blocks for additional patterns/words (fallback)
        if hasattr(page, 'blocks'):
            for block in page.blocks:
                if hasattr(block, 'layout') and hasattr(block.layout, 'text_anchor'):
                    text_segments = block.layout.text_anchor.text_segments
                    block_text = ""
                    for segment in text_segments:
                        start_idx = getattr(segment, 'start_index', 0)
                        end_idx = getattr(segment, 'end_index', len(doc.text))
                        block_text += doc.text[start_idx:end_idx]
                    
                    # Extract bounding box from block
                    block_bounding_box = None
                    block_confidence = 0.85
                    
                    if hasattr(block, 'layout') and hasattr(block.layout, 'bounding_poly'):
                        vertices = []
                        if hasattr(block.layout.bounding_poly, 'vertices'):
                            for vertex in block.layout.bounding_poly.vertices:
                                vertices.append({
                                    "x": getattr(vertex, 'x', 0),
                                    "y": getattr(vertex, 'y', 0)
                                })
                            block_bounding_box = {
                                "vertices": vertices
                            }
                    
                    if hasattr(block, 'layout') and hasattr(block.layout, 'confidence'):
                        block_confidence = block.layout.confidence
                    
                    # Find patterns in block text
                    pattern_matches = pattern_regex.finditer(block_text)
                    for match in pattern_matches:
                        item_key = match.group().upper().strip()
                        
                        if item_key not in items:
                            items[item_key] = {
                                "type": "pattern",
                                "category": categorize_pattern(item_key),
                                "total_count": 0,
                                "locations": []
                            }
                        
                        # Check if we already have this on this page
                        existing_on_page = any(loc["page"] == page_num for loc in items[item_key]["locations"])
                        
                        if not existing_on_page:
                            items[item_key]["locations"].append({
                                "page": page_num,
                                "bounding_box": block_bounding_box,
                                "confidence": block_confidence
                            })
                            items[item_key]["total_count"] += 1
    
    print(f"Found {len(items)} unique items")
    pattern_count = sum(1 for item in items.values() if item["type"] == "pattern")
    word_count = sum(1 for item in items.values() if item["type"] == "word")
    print(f"Patterns: {pattern_count}, Words: {word_count}")
    
    return items

def categorize_pattern(pattern_text):
    """Categorize technical patterns"""
    if pattern_text.startswith('PT'):
        return "plumbing_technical"
    elif pattern_text.startswith('M'):
        return "mechanical"
    elif pattern_text.startswith('E'):
        return "electrical"
    elif pattern_text.startswith('A'):
        return "architectural"
    elif pattern_text.startswith('S'):
        return "structural"
    else:
        return "technical_code"

def categorize_word(word_text):
    """Categorize words by type"""
    architectural_elements = {'door', 'window', 'wall', 'roof', 'floor', 'ceiling', 'beam', 'column'}
    room_types = {'bathroom', 'kitchen', 'bedroom', 'office', 'lobby', 'hallway', 'closet', 'storage'}
    materials = {'concrete', 'steel', 'wood', 'brick', 'glass', 'aluminum', 'copper'}
    dimensions = {'length', 'width', 'height', 'depth', 'diameter', 'thickness'}
    
    word_lower = word_text.lower()
    
    if word_lower in architectural_elements:
        return "architectural_element"
    elif word_lower in room_types:
        return "room_type"
    elif word_lower in materials:
        return "material"
    elif word_lower in dimensions:
        return "dimension"
    else:
        return "general_text"

def upload_to_r2(processing_result, r2_config, document_id):
    """Upload all JSON files directly to R2"""
    print("Uploading results to R2...")
    
    # Get R2 credentials from Secret Manager
    client = secretmanager.SecretManagerServiceClient()
    project_id = "ladders-doc-pipeline-462921"
    
    try:
        access_key = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-access-key/versions/latest"}
        ).payload.data.decode("UTF-8")
        
        secret_key = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-secret-key/versions/latest"}
        ).payload.data.decode("UTF-8")
        
        endpoint = client.access_secret_version(
            request={"name": f"projects/{project_id}/secrets/r2-endpoint/versions/latest"}
        ).payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error retrieving R2 credentials: {e}")
        # Fallback to provided config
        access_key = r2_config.get('accessKey')
        secret_key = r2_config.get('secretKey') 
        endpoint = r2_config.get('endpoint')
    
    # Configure R2 client
    r2_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    bucket_name = r2_config['bucketName']
    uploaded_files = {}
    
    # Upload main document
    main_key = f"documents/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=main_key,
        Body=json.dumps(processing_result['main_document'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['main_document'] = main_key
    print(f"Uploaded main document: {main_key}")
    
    # Upload summary
    summary_key = f"summaries/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=summary_key,
        Body=json.dumps(processing_result['summary'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['summary'] = summary_key
    print(f"Uploaded summary: {summary_key}")
    
    return uploaded_files

def download_pdf_to_temp(pdf_url):
    """Download PDF to temporary file"""
    print(f"Downloading PDF from: {pdf_url}")
    
    response = requests.get(pdf_url, timeout=60)
    response.raise_for_status()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(response.content)
        print(f"Downloaded PDF to: {temp_file.name}")
        return temp_file.name

def get_context_around_match(text, match_text, match_start, context_length=30):
    """Get context around a pattern match"""
    start = max(0, match_start - context_length)
    end = min(len(text), match_start + len(match_text) + context_length)
    
    return text[start:end].strip()

def calculate_average_confidence(doc):
    """Calculate average confidence score"""
    confidences = []
    
    # Try to extract confidence from entities
    if hasattr(doc, 'entities'):
        for entity in doc.entities:
            if hasattr(entity, 'confidence'):
                confidences.append(entity.confidence)
    
    # If no entities with confidence, try pages
    if not confidences:
        for page in doc.pages:
            for paragraph in page.paragraphs:
                if hasattr(paragraph, 'confidence'):
                    confidences.append(paragraph.confidence)
    
    return sum(confidences) / len(confidences) if confidences else 0.95

def send_callback(callback_url, result):
    """Send callback to Cloudflare Worker"""
    try:
        print(f"Sending callback to: {callback_url}")
        response = requests.post(callback_url, json=result, timeout=30)
        response.raise_for_status()
        print("Callback sent successfully")
    except Exception as e:
        print(f"Callback failed: {e}")
        # Don't fail the whole operation if callback fails 