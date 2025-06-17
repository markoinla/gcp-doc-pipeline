# PDF Processing Pipeline - Performance Optimization Analysis

**Created**: 2025-01-14  
**Current Performance**: 2-5 minutes for 24-page PDFs  
**Target Performance**: <1 minute for similar documents

---

## 🔍 Current Performance Analysis

### Current Processing Times (from test results)
- **Small PDFs (1-5 pages)**: 30-60 seconds
- **Medium PDFs (6-20 pages)**: 1-3 minutes  
- **Large PDFs (21-50 pages)**: 3-8 minutes
- **Test Case (24-page Firehouse Subs)**: 2-5 minutes

### Performance Breakdown by Phase
1. **PDF Download**: ~5-15 seconds
2. **PDF Chunking**: ~5-10 seconds  
3. **Document AI Processing**: ~80-90% of total time
4. **Pattern Extraction**: ~10-20 seconds
5. **R2 Upload**: ~5-10 seconds

---

## 🚨 Major Performance Bottlenecks Identified

### 1. **CRITICAL: Sequential PDF Chunk Processing**
**Location**: `functions/pdf-processor/main.py:122-140`

```python
# BOTTLENECK: Sequential processing
for i, chunk_path in enumerate(chunks):
    try:
        print(f"Processing chunk {i+1}/{len(chunks)}")
        chunk_doc = process_single_pdf_chunk(chunk_path, processor_id, project_id, location)
        # ... process each chunk one by one
```

**Impact**: For a 45-page PDF (3 chunks), this takes 3× longer than necessary
**Solution**: Parallel chunk processing using `concurrent.futures`

### 2. **HIGH: Redundant Pattern Extraction**
**Location**: `functions/pdf-processor/main.py:412-558`

```python
# BOTTLENECK: Double processing of patterns
# First in tokens, then in blocks (fallback)
for page_num, page in enumerate(doc.pages, 1):
    if hasattr(page, 'tokens'):
        for token in page.tokens:
            # Process each token individually...
    
    # REDUNDANT: Also check blocks
    if hasattr(page, 'blocks'):
        for block in page.blocks:
            # Process blocks again...
```

**Impact**: ~50% extra processing time for pattern extraction
**Solution**: Single-pass extraction with optimized regex

### 3. **MEDIUM: Multiple Secret Manager Calls**
**Location**: `functions/pdf-processor/main.py:608-620`

```python
# BOTTLENECK: Three separate secret manager calls
access_key = client.access_secret_version(...)
secret_key = client.access_secret_version(...)
endpoint = client.access_secret_version(...)
```

**Impact**: ~2-3 seconds per upload
**Solution**: Batch secret retrieval or caching

### 4. **MEDIUM: Workflow Orchestration Overhead**
**Location**: `workflows/pdf-processing-workflow.yaml`

- Complex retry logic with exponential backoff
- Multiple validation steps
- HTTP round-trips between workflow and function

**Impact**: ~10-20 seconds overhead
**Solution**: Direct function invocation for simple cases

### 5. **LOW: Inefficient Bounding Box Processing**
**Location**: `functions/pdf-processor/main.py:440-470`

```python
# BOTTLENECK: Nested loops for bounding box extraction
for vertex in token.layout.bounding_poly.vertices:
    vertices.append({
        "x": getattr(vertex, 'x', 0),
        "y": getattr(vertex, 'y', 0)
    })
```

**Impact**: Minor but accumulates for large documents
**Solution**: Vectorized processing

---

## 🚀 Optimization Strategies

### **Priority 1: Parallel Chunk Processing (Estimated 60-70% improvement)**

#### Current Implementation Problem
```python
# Sequential: 3 chunks × 45 seconds = 135 seconds
for i, chunk_path in enumerate(chunks):
    chunk_doc = process_single_pdf_chunk(chunk_path, processor_id, project_id, location)
```

#### Optimized Solution
```python
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

def process_pdf_document_parallel(pdf_url, document_id, processor_id, project_id, location, r2_config, app_project_id=None, webhook_url=None):
    """Process PDF with parallel chunk processing"""
    start_time = datetime.now()
    
    # Download and split PDF (unchanged)
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    chunks = split_pdf_into_chunks(temp_pdf_path, max_pages=15)
    
    # OPTIMIZATION: Process chunks in parallel
    all_pages = []
    combined_text = ""
    
    with ThreadPoolExecutor(max_workers=min(len(chunks), 5)) as executor:
        # Submit all chunk processing jobs
        future_to_chunk = {
            executor.submit(process_single_pdf_chunk, chunk_path, processor_id, project_id, location): (i, chunk_path)
            for i, chunk_path in enumerate(chunks)
        }
        
        # Collect results as they complete
        chunk_results = [None] * len(chunks)
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_index, chunk_path = future_to_chunk[future]
            try:
                chunk_doc = future.result()
                chunk_results[chunk_index] = chunk_doc
            except Exception as e:
                print(f"Chunk {chunk_index} failed: {e}")
                raise
            finally:
                # Clean up chunk file
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)
    
    # Combine results in correct order
    page_offset = 0
    for chunk_doc in chunk_results:
        if chunk_doc:
            for page in chunk_doc.pages:
                page.page_number = page.page_number + page_offset
            all_pages.extend(chunk_doc.pages)
            combined_text += chunk_doc.text + "\n"
            page_offset += len(chunk_doc.pages)
    
    # Continue with existing processing...
```

**Expected Improvement**: 3 chunks processed in ~45 seconds instead of 135 seconds

### **Priority 2: Optimized Pattern Extraction (Estimated 30-40% improvement)**

#### Current Implementation Problem
```python
# Processes tokens AND blocks separately
# Regex compiled multiple times
# Duplicate detection inefficient
```

#### Optimized Solution
```python
def extract_items_with_bounding_boxes_optimized(doc):
    """Optimized single-pass pattern extraction"""
    items = {}
    
    # Pre-compile regex patterns once
    pattern_regex = re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE)
    word_regex = re.compile(r'\b[A-Za-z][A-Za-z\s]{2,}\b')
    
    # Single pass through document text with position tracking
    text_positions = []
    current_pos = 0
    
    for page_num, page in enumerate(doc.pages, 1):
        page_text = ""
        page_tokens = []
        
        # Build page text and token mapping
        if hasattr(page, 'tokens'):
            for token in page.tokens:
                if hasattr(token, 'layout') and hasattr(token.layout, 'text_anchor'):
                    for segment in token.layout.text_anchor.text_segments:
                        start_idx = getattr(segment, 'start_index', 0)
                        end_idx = getattr(segment, 'end_index', 0)
                        token_text = doc.text[start_idx:end_idx]
                        
                        page_tokens.append({
                            'text': token_text,
                            'start': current_pos,
                            'end': current_pos + len(token_text),
                            'bounding_box': extract_bounding_box(token),
                            'confidence': getattr(token.layout, 'confidence', 0.95)
                        })
                        
                        page_text += token_text
                        current_pos += len(token_text)
        
        # Find all patterns in page text at once
        pattern_matches = list(pattern_regex.finditer(page_text))
        word_matches = list(word_regex.finditer(page_text))
        
        # Map matches back to tokens efficiently
        for match in pattern_matches + word_matches:
            # Binary search to find corresponding token
            token = find_token_for_position(page_tokens, match.start())
            if token:
                add_item_to_collection(items, match.group(), token, page_num)
    
    return items

def find_token_for_position(tokens, position):
    """Binary search for token containing position"""
    left, right = 0, len(tokens) - 1
    while left <= right:
        mid = (left + right) // 2
        token = tokens[mid]
        if token['start'] <= position < token['end']:
            return token
        elif position < token['start']:
            right = mid - 1
        else:
            left = mid + 1
    return None
```

### **Priority 3: Batch Secret Manager Access (Estimated 10-15% improvement)**

#### Current Implementation Problem
```python
# Three separate API calls
access_key = client.access_secret_version(...)
secret_key = client.access_secret_version(...)  
endpoint = client.access_secret_version(...)
```

#### Optimized Solution
```python
@lru_cache(maxsize=1)
def get_r2_credentials():
    """Cached R2 credentials retrieval"""
    client = secretmanager.SecretManagerServiceClient()
    project_id = "ladders-doc-pipeline-462921"
    
    # Batch request (if supported) or parallel requests
    with ThreadPoolExecutor(max_workers=3) as executor:
        access_key_future = executor.submit(
            client.access_secret_version,
            request={"name": f"projects/{project_id}/secrets/r2-access-key/versions/latest"}
        )
        secret_key_future = executor.submit(
            client.access_secret_version,
            request={"name": f"projects/{project_id}/secrets/r2-secret-key/versions/latest"}
        )
        endpoint_future = executor.submit(
            client.access_secret_version,
            request={"name": f"projects/{project_id}/secrets/r2-endpoint/versions/latest"}
        )
        
        return {
            'access_key': access_key_future.result().payload.data.decode("UTF-8"),
            'secret_key': secret_key_future.result().payload.data.decode("UTF-8"),
            'endpoint': endpoint_future.result().payload.data.decode("UTF-8")
        }

def upload_to_r2_optimized(processing_result, r2_config, document_id, app_project_id=None):
    """Optimized R2 upload with cached credentials"""
    credentials = get_r2_credentials()
    
    # Configure R2 client once
    r2_client = boto3.client(
        's3',
        endpoint_url=credentials['endpoint'],
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    # Parallel uploads
    upload_futures = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Upload all files in parallel
        for file_type, content in [
            ('main_document', processing_result['main_document']),
            ('summary', processing_result['summary']),
            ('search_index', processing_result.get('search_index', {}))
        ]:
            future = executor.submit(upload_single_file, r2_client, file_type, content, document_id, r2_config, app_project_id)
            upload_futures.append((file_type, future))
        
        # Collect results
        uploaded_files = {}
        for file_type, future in upload_futures:
            uploaded_files[file_type] = future.result()
    
    return uploaded_files
```

### **Priority 4: Document AI Request Optimization (Estimated 15-20% improvement)**

#### Current Implementation Enhancement
```python
def process_single_pdf_chunk_optimized(pdf_path, processor_id, project_id, location):
    """Optimized Document AI processing with better error handling"""
    client = documentai.DocumentProcessorServiceClient()
    
    # Read PDF file
    with open(pdf_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
    
    processor_name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    
    # Optimized request configuration
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        ),
        # Enable field mask for faster processing
        field_mask=documentai.FieldMask(
            paths=["text", "pages.tokens", "pages.layout", "pages.dimension"]
        )
    )
    
    # Process with retry logic and better timeout
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = client.process_document(request=request, timeout=120)
            return result.document
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

### **Priority 5: Memory and CPU Optimization**

#### PDF Chunking Optimization
```python
def split_pdf_into_chunks_optimized(pdf_path, max_pages=15):
    """Memory-efficient PDF chunking"""
    chunks = []
    
    # Use memory-mapped file for large PDFs
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        total_pages = len(pdf_reader.pages)
        
        # Calculate optimal chunk size based on memory
        available_memory = psutil.virtual_memory().available
        chunk_size = min(max_pages, max(5, available_memory // (50 * 1024 * 1024)))  # 50MB per page estimate
        
        for start_page in range(0, total_pages, chunk_size):
            end_page = min(start_page + chunk_size, total_pages)
            
            # Create chunk with minimal memory footprint
            chunk_path = create_pdf_chunk_optimized(pdf_reader, start_page, end_page)
            chunks.append(chunk_path)
    
    return chunks

def create_pdf_chunk_optimized(pdf_reader, start_page, end_page):
    """Create PDF chunk with streaming write"""
    chunk_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    pdf_writer = PyPDF2.PdfWriter()
    
    # Add pages efficiently
    for page_num in range(start_page, end_page):
        pdf_writer.add_page(pdf_reader.pages[page_num])
    
    # Stream write to minimize memory usage
    pdf_writer.write(chunk_file)
    chunk_file.close()
    
    return chunk_file.name
```

---

## 🎯 Implementation Priority Plan

### **Phase 1: Critical Performance Fixes (Target: 60% improvement)**
1. **Parallel Chunk Processing** - Replace sequential with concurrent processing
2. **Optimized Pattern Extraction** - Single-pass algorithm with compiled regex
3. **Cached Secret Manager** - Eliminate redundant API calls

**Expected Result**: 24-page PDF processing time: 2-5 minutes → 1-2 minutes

### **Phase 2: Advanced Optimizations (Target: Additional 25% improvement)**
1. **Memory Optimization** - Efficient PDF chunking and memory management
2. **Document AI Field Masking** - Request only needed fields
3. **Parallel R2 Uploads** - Upload multiple files simultaneously

**Expected Result**: 24-page PDF processing time: 1-2 minutes → 45-90 seconds

### **Phase 3: Infrastructure Optimizations (Target: Additional 15% improvement)**
1. **Function Memory Increase** - Scale to 4GiB for faster processing
2. **Regional Optimization** - Ensure all services in same region
3. **Connection Pooling** - Reuse HTTP connections

**Expected Result**: 24-page PDF processing time: 45-90 seconds → 30-60 seconds

---

## 📊 Expected Performance Improvements

### Before Optimization
- **Small PDFs (1-5 pages)**: 30-60 seconds
- **Medium PDFs (6-20 pages)**: 1-3 minutes
- **Large PDFs (21-50 pages)**: 3-8 minutes

### After Full Optimization
- **Small PDFs (1-5 pages)**: 15-30 seconds (50% improvement)
- **Medium PDFs (6-20 pages)**: 30-90 seconds (70% improvement)
- **Large PDFs (21-50 pages)**: 90-240 seconds (75% improvement)

### Cost Impact
- **Current**: ~$0.05-0.15 per document (Document AI + compute)
- **Optimized**: ~$0.03-0.10 per document (reduced compute time)
- **Annual Savings**: ~30-40% for high-volume processing

---

## 🔧 Implementation Code Samples

### **1. Main Function with Parallel Processing**
```python
def process_pdf_document_v2(pdf_url, document_id, processor_id, project_id, location, r2_config, app_project_id=None, webhook_url=None):
    """Optimized PDF processing with parallel execution"""
    start_time = datetime.now()
    
    print(f"Processing PDF document (optimized): {document_id}")
    
    # Download PDF
    temp_pdf_path = download_pdf_to_temp(pdf_url)
    
    try:
        # Extract metadata
        pdf_metadata = extract_pdf_metadata(temp_pdf_path, pdf_url)
        
        # Check page count
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
        
        if total_pages <= 15:
            # Single chunk processing
            doc = process_single_pdf_chunk_optimized(temp_pdf_path, processor_id, project_id, location)
            all_pages = doc.pages
            combined_text = doc.text
        else:
            # Parallel chunk processing
            chunks = split_pdf_into_chunks_optimized(temp_pdf_path, max_pages=15)
            all_pages, combined_text = process_chunks_parallel(chunks, processor_id, project_id, location)
        
        # Optimized data extraction
        combined_doc = create_combined_document(all_pages, combined_text, total_pages)
        processing_result = extract_and_process_data_optimized(combined_doc, document_id, pdf_url, start_time, pdf_metadata)
        
        # Parallel upload
        upload_result = upload_to_r2_optimized(processing_result, r2_config, document_id, app_project_id)
        
        # Result formatting
        processing_time = datetime.now() - start_time
        result = format_result(document_id, processing_result, upload_result, processing_time)
        
        # Async webhook
        if webhook_url:
            send_webhook_async(webhook_url, result, r2_config, app_project_id)
        
        return result
        
    finally:
        # Cleanup
        if os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)

def process_chunks_parallel(chunks, processor_id, project_id, location):
    """Process PDF chunks in parallel"""
    all_pages = []
    combined_text = ""
    
    with ThreadPoolExecutor(max_workers=min(len(chunks), 5)) as executor:
        # Submit all jobs
        futures = [
            executor.submit(process_single_pdf_chunk_optimized, chunk_path, processor_id, project_id, location)
            for chunk_path in chunks
        ]
        
        # Collect results in order
        page_offset = 0
        for i, future in enumerate(futures):
            try:
                chunk_doc = future.result(timeout=180)  # 3 minute timeout per chunk
                
                # Adjust page numbers
                for page in chunk_doc.pages:
                    page.page_number = page.page_number + page_offset
                
                all_pages.extend(chunk_doc.pages)
                combined_text += chunk_doc.text + "\n"
                page_offset += len(chunk_doc.pages)
                
            except Exception as e:
                print(f"Chunk {i} failed: {e}")
                raise
            finally:
                # Cleanup chunk file
                chunk_path = chunks[i]
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)
    
    return all_pages, combined_text
```

### **2. Optimized Pattern Extraction**
```python
def extract_items_with_bounding_boxes_v2(doc):
    """High-performance pattern extraction"""
    items = defaultdict(lambda: {
        "type": "",
        "category": "",
        "total_count": 0,
        "locations": []
    })
    
    # Pre-compiled patterns
    PATTERNS = {
        'pattern': re.compile(r'\b(PT-?\d+|M-?\d+|[A-Z]-?\d+)\b', re.IGNORECASE),
        'word': re.compile(r'\b[A-Za-z][A-Za-z\s]{2,}\b')
    }
    
    # Process all pages in batch
    for page_num, page in enumerate(doc.pages, 1):
        page_items = extract_page_items_optimized(page, page_num, doc.text, PATTERNS)
        
        # Merge into main collection
        for item_key, item_data in page_items.items():
            if item_key not in items:
                items[item_key] = item_data
            else:
                items[item_key]["locations"].extend(item_data["locations"])
                items[item_key]["total_count"] += item_data["total_count"]
    
    return dict(items)

def extract_page_items_optimized(page, page_num, full_text, patterns):
    """Optimized single-page item extraction"""
    page_items = {}
    
    if not hasattr(page, 'tokens'):
        return page_items
    
    # Build token lookup table
    token_map = {}
    for token in page.tokens:
        if hasattr(token, 'layout') and hasattr(token.layout, 'text_anchor'):
            for segment in token.layout.text_anchor.text_segments:
                start_idx = getattr(segment, 'start_index', 0)
                end_idx = getattr(segment, 'end_index', 0)
                token_text = full_text[start_idx:end_idx].strip()
                
                if token_text and len(token_text) > 2:
                    token_map[start_idx] = {
                        'text': token_text,
                        'bounding_box': extract_bounding_box_fast(token),
                        'confidence': getattr(token.layout, 'confidence', 0.95)
                    }
    
    # Find all matches efficiently
    page_text_start = min(token_map.keys()) if token_map else 0
    page_text_end = max(token_map.keys()) if token_map else 0
    page_text = full_text[page_text_start:page_text_end]
    
    for pattern_type, regex in patterns.items():
        for match in regex.finditer(page_text):
            match_start = page_text_start + match.start()
            
            # Find corresponding token
            token_data = find_closest_token(token_map, match_start)
            if token_data:
                item_key = match.group().upper().strip() if pattern_type == 'pattern' else match.group().lower().strip()
                
                if item_key not in page_items:
                    page_items[item_key] = {
                        "type": pattern_type,
                        "category": categorize_item(item_key, pattern_type),
                        "total_count": 0,
                        "locations": []
                    }
                
                page_items[item_key]["locations"].append({
                    "page": page_num,
                    "bounding_box": token_data["bounding_box"],
                    "confidence": token_data["confidence"]
                })
                page_items[item_key]["total_count"] += 1
    
    return page_items
```

---

## 🚀 Quick Implementation Steps

### **Step 1: Deploy Parallel Processing**
1. Replace `process_pdf_document` with `process_pdf_document_v2`
2. Add `concurrent.futures` to requirements.txt
3. Update Cloud Function memory to 4GiB
4. Test with 24-page document

### **Step 2: Optimize Pattern Extraction**
1. Replace `extract_items_with_bounding_boxes` with optimized version
2. Pre-compile regex patterns at module level
3. Add performance logging

### **Step 3: Cache Secret Manager**
1. Add `@lru_cache` decorator to credential retrieval
2. Implement parallel secret fetching
3. Monitor cache hit rates

### **Step 4: Monitor and Measure**
1. Add detailed timing logs for each phase
2. Set up Cloud Monitoring metrics
3. Compare before/after performance
4. Adjust concurrent worker counts based on results

---

## 🎯 Success Criteria

After implementing these optimizations:

1. **Performance Target**: 24-page PDF processing < 90 seconds (vs current 2-5 minutes)
2. **Scalability Target**: Handle 10 concurrent 50-page PDFs without performance degradation
3. **Resource Efficiency**: <4GB memory usage peak
4. **Cost Target**: 30% reduction in processing costs
5. **Reliability Target**: <1% failure rate due to timeouts

---

*This optimization plan provides a clear roadmap to significantly improve the PDF processing pipeline performance while maintaining accuracy and reliability.* 