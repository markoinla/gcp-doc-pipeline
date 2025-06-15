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
from urllib.parse import urlparse
import time

@functions_framework.http
def process_pdf(request):
    """Main function to process PDF with Document AI and upload to R2"""
    try:
        # Parse request
        request_json = request.get_json()
        
        # Validate required parameters
        if not request_json:
            return {"status": "error", "error": "No JSON body provided"}, 400
            
        required_fields = ['pdfUrl', 'r2Config']
        for field in required_fields:
            if field not in request_json:
                return {"status": "error", "error": f"Missing required field: {field}"}, 400
        
        pdf_url = request_json['pdfUrl']
        callback_url = request_json.get('callbackUrl')  # Optional (legacy)
        webhook_url = request_json.get('webhookUrl')    # New webhook parameter
        r2_config = request_json['r2Config']
        
        # New parameters for project organization
        project_id = request_json.get('projectID')
        project_file_id = request_json.get('projectFileID')
        
        # Use projectFileID as document_id if provided, otherwise generate one
        if project_file_id:
            document_id = project_file_id
        else:
            document_id = f"doc_{int(time.time())}"
        
        # Use our configured processor
        processor_id = "fa7abbc0ea6541c5"
        location = "us"
        gcp_project_id = "ladders-doc-pipeline-462921"
        
        print(f"Starting PDF processing for document ID: {document_id}")
        print(f"PDF URL: {pdf_url}")
        if project_id:
            print(f"App Project ID: {project_id}")
        if project_file_id:
            print(f"App Project File ID: {project_file_id}")
        if webhook_url:
            print(f"Webhook URL: {webhook_url}")
        
        # Process PDF
        result = process_pdf_document(
            pdf_url=pdf_url,
            document_id=document_id,
            processor_id=processor_id,
            project_id=gcp_project_id,
            location=location,
            r2_config=r2_config,
            app_project_id=project_id,
            webhook_url=webhook_url
        )
        
        # Send legacy callback if provided
        if callback_url:
            send_callback(callback_url, result)
        
        return {"status": "success", "document_id": document_id, "result": result}
        
    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")
        return {"status": "error", "error": str(e)}, 500

def process_pdf_document(pdf_url, document_id, processor_id, project_id, location, r2_config, app_project_id=None, webhook_url=None):
    """Process PDF by chunking into 15-page segments for Document AI"""
    start_time = datetime.now()
    
    print(f"Processing PDF document: {document_id}")
    
    # Download PDF to temporary location
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    
    try:
        # Extract PDF metadata first
        pdf_metadata = extract_pdf_metadata(temp_pdf_path, pdf_url)
        print(f"Extracted PDF metadata: {pdf_metadata['file_info']['filename']}")
        
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
        processing_result = extract_and_process_data(combined_doc, document_id, pdf_url, start_time, pdf_metadata)
        
        # Upload to R2
        upload_result = upload_to_r2(processing_result, r2_config, document_id, app_project_id)
        
        processing_time = datetime.now() - start_time
        
        result = {
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
        
        # Send webhook notification if provided
        if webhook_url:
            send_webhook_notification(webhook_url, result, r2_config, app_project_id)
        
        return result
        
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

def extract_and_process_data(doc, document_id, pdf_url, start_time, pdf_metadata):
    """Extract patterns and words with search-optimized structure"""
    
    print("Extracting patterns and words with search-optimized structure...")
    
    # Extract both patterns and words with bounding boxes
    items = extract_items_with_bounding_boxes(doc)
    
    # Calculate confidence scores
    avg_confidence = calculate_average_confidence(doc)
    
    # Extract page-level metadata
    pages_metadata = extract_page_metadata(doc)
    
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
        "document_metadata": pdf_metadata,
        "pages_metadata": pages_metadata,
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
        "document_info": {
            "filename": pdf_metadata["file_info"]["filename"],
            "title": pdf_metadata["document_info"].get("title"),
            "total_pages": pdf_metadata["file_info"]["total_pages"],
            "file_size_bytes": pdf_metadata["file_info"]["file_size_bytes"]
        },
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
    # Paint patterns: PT-1, PT1, P1, P-1, etc.
    if (pattern_text.startswith('PT') or 
        (pattern_text.startswith('P') and len(pattern_text) >= 2 and 
         (pattern_text[1].isdigit() or pattern_text[1] == '-'))):
        return "painting"
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

def upload_to_r2(processing_result, r2_config, document_id, app_project_id=None):
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
    
    # Organize files by project if provided
    if app_project_id:
        base_path = f"projects/{app_project_id}"
        print(f"Organizing files under project: {app_project_id}")
    else:
        base_path = ""
        print("Using default file organization")
    
    # Upload main document
    if base_path:
        main_key = f"{base_path}/documents/{document_id}.json"
    else:
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
    if base_path:
        summary_key = f"{base_path}/summaries/{document_id}.json"
    else:
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

def extract_pdf_metadata(pdf_path, pdf_url):
    """Extract comprehensive PDF metadata using PyPDF2"""
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Get basic document info
            metadata = {
                "file_info": {
                    "filename": os.path.basename(urlparse(pdf_url).path) or "unknown.pdf",
                    "source_url": pdf_url,
                    "file_size_bytes": os.path.getsize(pdf_path),
                    "total_pages": len(pdf_reader.pages)
                },
                "document_info": {},
                "security_info": {
                    "is_encrypted": pdf_reader.is_encrypted,
                    "metadata_encrypted": False
                }
            }
            
            # Extract document metadata if available
            if pdf_reader.metadata:
                doc_info = pdf_reader.metadata
                metadata["document_info"] = {
                    "title": str(doc_info.get('/Title', '')).strip() if doc_info.get('/Title') else None,
                    "author": str(doc_info.get('/Author', '')).strip() if doc_info.get('/Author') else None,
                    "subject": str(doc_info.get('/Subject', '')).strip() if doc_info.get('/Subject') else None,
                    "creator": str(doc_info.get('/Creator', '')).strip() if doc_info.get('/Creator') else None,
                    "producer": str(doc_info.get('/Producer', '')).strip() if doc_info.get('/Producer') else None,
                    "creation_date": str(doc_info.get('/CreationDate', '')).strip() if doc_info.get('/CreationDate') else None,
                    "modification_date": str(doc_info.get('/ModDate', '')).strip() if doc_info.get('/ModDate') else None,
                    "keywords": str(doc_info.get('/Keywords', '')).strip() if doc_info.get('/Keywords') else None
                }
                
                # Clean up empty values
                metadata["document_info"] = {k: v for k, v in metadata["document_info"].items() if v}
            
            return metadata
            
    except Exception as e:
        print(f"Error extracting PDF metadata: {str(e)}")
        return {
            "file_info": {
                "filename": os.path.basename(urlparse(pdf_url).path) or "unknown.pdf",
                "source_url": pdf_url,
                "file_size_bytes": 0,
                "total_pages": 0
            },
            "document_info": {},
            "security_info": {
                "is_encrypted": False,
                "metadata_encrypted": False
            },
            "extraction_error": str(e)
        }

def extract_page_metadata(doc):
    """Extract page-level metadata from Document AI results"""
    pages_metadata = []
    
    for page_num, page in enumerate(doc.pages, 1):
        page_meta = {
            "page_number": page_num,
            "dimensions": {},
            "layout_info": {},
            "content_stats": {}
        }
        
        # Extract page dimensions from Document AI
        if hasattr(page, 'dimension'):
            page_meta["dimensions"] = {
                "width": page.dimension.width,
                "height": page.dimension.height,
                "unit": page.dimension.unit if hasattr(page.dimension, 'unit') else "pixels"
            }
        
        # Extract layout information
        if hasattr(page, 'layout'):
            layout = page.layout
            if hasattr(layout, 'bounding_poly') and layout.bounding_poly.vertices:
                vertices = layout.bounding_poly.vertices
                page_meta["layout_info"]["content_bounds"] = {
                    "top_left": {"x": vertices[0].x, "y": vertices[0].y},
                    "top_right": {"x": vertices[1].x, "y": vertices[1].y},
                    "bottom_right": {"x": vertices[2].x, "y": vertices[2].y},
                    "bottom_left": {"x": vertices[3].x, "y": vertices[3].y}
                }
            
            if hasattr(layout, 'orientation'):
                page_meta["layout_info"]["orientation"] = layout.orientation
        
        # Count content elements
        content_stats = {
            "tokens": 0,
            "paragraphs": 0,
            "lines": 0,
            "blocks": 0,
            "tables": 0,
            "form_fields": 0
        }
        
        # Count tokens
        if hasattr(page, 'tokens'):
            content_stats["tokens"] = len(page.tokens)
        
        # Count paragraphs
        if hasattr(page, 'paragraphs'):
            content_stats["paragraphs"] = len(page.paragraphs)
        
        # Count lines
        if hasattr(page, 'lines'):
            content_stats["lines"] = len(page.lines)
        
        # Count blocks
        if hasattr(page, 'blocks'):
            content_stats["blocks"] = len(page.blocks)
        
        # Count tables
        if hasattr(page, 'tables'):
            content_stats["tables"] = len(page.tables)
        
        # Count form fields
        if hasattr(page, 'form_fields'):
            content_stats["form_fields"] = len(page.form_fields)
        
        page_meta["content_stats"] = content_stats
        
        # Calculate text density (characters per square unit)
        if hasattr(page, 'dimension') and content_stats["tokens"] > 0:
            area = page.dimension.width * page.dimension.height
            if area > 0:
                page_meta["text_density"] = content_stats["tokens"] / area
        
        pages_metadata.append(page_meta)
    
    return pages_metadata

def send_callback(callback_url, result):
    """Send callback to Cloudflare Worker (legacy)"""
    try:
        print(f"Sending callback to: {callback_url}")
        response = requests.post(callback_url, json=result, timeout=30)
        response.raise_for_status()
        print("Callback sent successfully")
    except Exception as e:
        print(f"Callback failed: {e}")
        # Don't fail the whole operation if callback fails

def send_webhook_notification(webhook_url, processing_result, r2_config, app_project_id=None):
    """Send webhook notification with processing results and file URLs"""
    try:
        print(f"Sending webhook notification to: {webhook_url}")
        
        # Build the base URL for R2 files
        r2_endpoint = r2_config.get('endpoint', '')
        bucket_name = r2_config.get('bucketName', '')
        
        # Extract the domain from the endpoint (remove protocol and path)
        if r2_endpoint.startswith('https://'):
            r2_domain = r2_endpoint.replace('https://', '').split('/')[0]
        else:
            r2_domain = r2_endpoint.split('/')[0]
        
        # Build public URLs for the uploaded files
        uploaded_files = processing_result.get('uploaded_files', {})
        file_urls = {}
        
        for file_type, file_path in uploaded_files.items():
            # Build public URL: https://pub-{account_hash}.r2.dev/{file_path}
            # We'll use a generic public URL format - adjust based on your R2 setup
            public_url = f"https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/{file_path}"
            file_urls[file_type] = public_url
        
        # Create webhook payload
        webhook_payload = {
            "event": "pdf_processing_complete",
            "timestamp": datetime.now().isoformat(),
            "projectID": app_project_id,
            "projectFileID": processing_result.get('document_id'),
            "status": processing_result.get('status'),
            "processing_stats": {
                "total_pages": processing_result.get('total_pages'),
                "items_found": processing_result.get('items_found'),
                "unique_items": processing_result.get('unique_items'),
                "patterns_found": processing_result.get('patterns_found'),
                "words_found": processing_result.get('words_found'),
                "processing_time": processing_result.get('processing_time')
            },
            "files": {
                "document_url": file_urls.get('main_document'),
                "summary_url": file_urls.get('summary')
            },
            "r2_paths": uploaded_files
        }
        
        # Send webhook
        response = requests.post(webhook_url, json=webhook_payload, timeout=30)
        response.raise_for_status()
        print("Webhook notification sent successfully")
        
    except Exception as e:
        print(f"Webhook notification failed: {e}")
        # Don't fail the whole operation if webhook fails 