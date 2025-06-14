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
            "status": "completed",
            "uploaded_files": upload_result,
            "patterns_found": processing_result['pattern_summary']['total_patterns'],
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
    """Extract patterns with bounding boxes - no full text needed"""
    
    print("Extracting patterns and processing data...")
    
    # Extract patterns with bounding boxes from Document AI tokens
    patterns = extract_patterns_with_context(doc)
    
    # Calculate confidence scores
    avg_confidence = calculate_average_confidence(doc)
    
    # Create pattern summary with counts
    pattern_counts = {}
    total_patterns = 0
    pages_with_patterns = set()
    
    for pattern_type, instances in patterns.items():
        pattern_counts[pattern_type] = len(instances)
        total_patterns += len(instances)
        for instance in instances:
            pages_with_patterns.add(instance['page'])
    
    # Create main results JSON - only patterns and metadata
    main_document = {
        "document_id": document_id,
        "source_url": pdf_url,
        "processed_at": datetime.now().isoformat(),
        "total_pages": len(doc.pages),
        "patterns": patterns,
        "processing_metadata": {
            "processing_time": str(datetime.now() - start_time),
            "ocr_confidence": avg_confidence,
            "total_patterns": total_patterns,
            "pages_with_patterns": sorted(list(pages_with_patterns))
        }
    }
    
    # Create pattern summary JSON for quick lookup
    pattern_summary = {
        "document_id": document_id,
        "pattern_counts": pattern_counts,
        "total_patterns": total_patterns,
        "pages_with_patterns": sorted(list(pages_with_patterns)),
        "confidence_score": avg_confidence
    }
    
    print(f"Extracted {total_patterns} patterns across {len(pages_with_patterns)} pages")
    
    return {
        "main_document": main_document,
        "pattern_summary": pattern_summary
    }

def extract_patterns_with_context(doc):
    """Extract technical patterns with bounding boxes from Document AI tokens"""
    patterns = {}
    
    # Define pattern regex - matching PT-1, PT1, M1, M-1, etc.
    pattern_regex = re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE)
    
    print("Extracting patterns from Document AI tokens...")
    
    # Extract patterns from each page's tokens
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
                
                # Check if token matches our pattern
                if pattern_regex.match(token_text):
                    pattern_text = token_text.upper().strip()
                    
                    if pattern_text not in patterns:
                        patterns[pattern_text] = []
                    
                    # Extract bounding box
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
                    
                    # Get confidence if available
                    if hasattr(token, 'layout') and hasattr(token.layout, 'confidence'):
                        confidence = token.layout.confidence
                    
                    patterns[pattern_text].append({
                        "page": page_num,
                        "text": token_text.strip(),
                        "confidence": confidence,
                        "bounding_box": bounding_box
                    })
        
        # Also check blocks for patterns (fallback)
        if hasattr(page, 'blocks'):
            for block in page.blocks:
                if hasattr(block, 'layout') and hasattr(block.layout, 'text_anchor'):
                    text_segments = block.layout.text_anchor.text_segments
                    block_text = ""
                    for segment in text_segments:
                        start_idx = getattr(segment, 'start_index', 0)
                        end_idx = getattr(segment, 'end_index', len(doc.text))
                        block_text += doc.text[start_idx:end_idx]
                    
                    # Find patterns in block text
                    matches = pattern_regex.finditer(block_text)
                    for match in matches:
                        pattern_text = match.group().upper()
                        
                        if pattern_text not in patterns:
                            patterns[pattern_text] = []
                        
                        # Extract bounding box from block
                        bounding_box = None
                        confidence = 0.90
                        
                        if hasattr(block, 'layout') and hasattr(block.layout, 'bounding_poly'):
                            vertices = []
                            if hasattr(block.layout.bounding_poly, 'vertices'):
                                for vertex in block.layout.bounding_poly.vertices:
                                    vertices.append({
                                        "x": getattr(vertex, 'x', 0),
                                        "y": getattr(vertex, 'y', 0)
                                    })
                                bounding_box = {
                                    "vertices": vertices
                                }
                        
                        # Get confidence if available
                        if hasattr(block, 'layout') and hasattr(block.layout, 'confidence'):
                            confidence = block.layout.confidence
                        
                        # Check if we already have this exact pattern on this page
                        existing_pattern = False
                        for existing in patterns[pattern_text]:
                            if existing["page"] == page_num and existing["text"] == match.group().strip():
                                existing_pattern = True
                                break
                        
                        if not existing_pattern:
                            patterns[pattern_text].append({
                                "page": page_num,
                                "text": match.group().strip(),
                                "confidence": confidence,
                                "bounding_box": bounding_box
                            })
    
    print(f"Found patterns: {dict((k, len(v)) for k, v in patterns.items())}")
    return patterns

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
    
    bucket_name = r2_config['bucket']
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
    
    # Upload pattern summary
    pattern_key = f"patterns/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=pattern_key,
        Body=json.dumps(processing_result['pattern_summary'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['pattern_summary'] = pattern_key
    print(f"Uploaded pattern summary: {pattern_key}")
    
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