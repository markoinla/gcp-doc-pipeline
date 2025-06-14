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
# from google.cloud.documentai_toolbox import document  # Commented out for now
import requests
import functions_framework

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
    """Process PDF using Document AI Toolbox"""
    start_time = datetime.now()
    
    print(f"Processing PDF document: {document_id}")
    
    # Download PDF to temporary location
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    
    try:
        # Process with Document AI
        client = documentai.DocumentProcessorServiceClient()
        
        # Read PDF file
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        
        print(f"PDF file size: {len(pdf_content)} bytes")
        
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
        
        print("Sending document to Document AI...")
        result = client.process_document(request=request)
        print("Document AI processing complete")
        
        # Work directly with Document AI result
        doc = result.document
        
        print(f"Document has {len(doc.pages)} pages")
        
        # Extract and process data
        processing_result = extract_and_process_data(doc, document_id, pdf_url, start_time)
        
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

def extract_and_process_data(doc, document_id, pdf_url, start_time):
    """Extract patterns and create optimized JSON structures"""
    
    print("Extracting patterns and processing data...")
    
    # Extract full text
    full_text = doc.text
    
    # Extract patterns with context and bounding boxes
    patterns = extract_patterns_with_context(doc)
    
    # Create page-by-page text index
    page_text = {}
    for page_num, page in enumerate(doc.pages, 1):
        # Extract text from page
        page_text_content = ""
        for paragraph in page.paragraphs:
            for word in paragraph.words:
                for symbol in word.symbols:
                    page_text_content += symbol.text
                page_text_content += " "
            page_text_content += "\n"
        page_text[str(page_num)] = page_text_content
    
    # Build searchable word index
    word_index = build_searchable_index(full_text)
    
    # Calculate confidence scores
    avg_confidence = calculate_average_confidence(doc)
    
    # Create main document JSON
    main_document = {
        "document_id": document_id,
        "source_url": pdf_url,
        "processed_at": datetime.now().isoformat(),
        "total_pages": len(doc.pages),
        "full_text": full_text,
        "processing_metadata": {
            "total_entities": len(doc.entities) if hasattr(doc, 'entities') else 0,
            "processing_time": str(datetime.now() - start_time),
            "ocr_confidence": avg_confidence
        }
    }
    
    # Create search index JSON
    search_index = {
        "document_id": document_id,
        "patterns": patterns,
        "page_text": page_text,
        "word_index": word_index
    }
    
    # Create pattern summary JSON
    pattern_counts = {}
    total_patterns = 0
    pages_with_patterns = set()
    
    for pattern_type, instances in patterns.items():
        pattern_counts[pattern_type] = len(instances)
        total_patterns += len(instances)
        for instance in instances:
            pages_with_patterns.add(instance['page'])
    
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
        "search_index": search_index,
        "pattern_summary": pattern_summary
    }

def extract_patterns_with_context(doc):
    """Extract technical patterns with bounding boxes and context"""
    patterns = {}
    
    # Define pattern regex - matching PT-1, PT1, M1, M-1, etc.
    pattern_regex = re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE)
    
    print("Extracting patterns from document...")
    
    # Use full document text for pattern matching
    full_text = doc.text
    matches = pattern_regex.finditer(full_text)
    
    for match in matches:
        pattern_text = match.group().upper()
        
        if pattern_text not in patterns:
            patterns[pattern_text] = []
        
        # Get context around the match
        context = get_context_around_match(full_text, match.group(), match.start(), context_length=30)
        
        # For simplicity, assign to page 1 unless we can determine the actual page
        # In a full implementation, we'd map the character position to the specific page
        page_num = 1
        
        patterns[pattern_text].append({
            "page": page_num,
            "text": match.group(),
            "confidence": 0.95,  # Default confidence
            "bounding_box": None,  # Would need more complex logic to extract from Document AI tokens
            "context": context
        })
    
    print(f"Found patterns: {dict((k, len(v)) for k, v in patterns.items())}")
    return patterns

def build_searchable_index(full_text):
    """Build searchable word index excluding single letters"""
    # Split text into words, keeping hyphens, dashes, slashes
    words = re.findall(r'\b\w+(?:[-/]\w+)*\b', full_text)
    
    # Filter out single letters and deduplicate, but keep technical patterns
    searchable_words = list(set([
        word.lower() for word in words 
        if len(word) > 1 or re.match(r'[A-Z]-?\d+', word, re.IGNORECASE)
    ]))
    
    return sorted(searchable_words)

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
    
    # Upload search index
    search_key = f"search/{document_id}.json"
    r2_client.put_object(
        Bucket=bucket_name,
        Key=search_key,
        Body=json.dumps(processing_result['search_index'], indent=2),
        ContentType='application/json'
    )
    uploaded_files['search_index'] = search_key
    print(f"Uploaded search index: {search_key}")
    
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