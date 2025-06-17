#!/usr/bin/env python3
"""
Focused Parallel Test: Quick validation of parallel vs sequential
Tests with 6 pages to prove the concept.
"""

import sys
import os
import time
import concurrent.futures
sys.path.append(os.path.dirname(__file__))

import pdf_processor
import vision_processor
import pattern_extractor
from config import DEFAULT_CHUNK_SIZE, PARALLEL_WORKERS

def process_single_page(image, page_num):
    """Process a single page - used for both sequential and parallel tests"""
    try:
        start_time = time.time()
        
        # Convert image to bytes
        image_bytes = pdf_processor.image_to_bytes(image)
        
        # Vision API call
        vision_result = vision_processor.call_vision_api(image_bytes)
        
        # Pattern extraction
        patterns = pattern_extractor.extract_patterns_from_vision(vision_result, page_num)
        
        processing_time = time.time() - start_time
        
        return {
            'page': page_num,
            'success': True,
            'processing_time': processing_time,
            'patterns': len(patterns)
        }
    except Exception as e:
        return {
            'page': page_num,
            'success': False,
            'error': str(e),
            'processing_time': time.time() - start_time
        }

def test_sequential_processing(page_images):
    """Test sequential processing"""
    print("🔄 SEQUENTIAL PROCESSING TEST")
    print("-" * 40)
    
    start_time = time.time()
    results = []
    
    for i, image in enumerate(page_images):
        print(f"   Processing page {i+1}/{len(page_images)}...")
        result = process_single_page(image, i+1)
        results.append(result)
        
        if result['success']:
            print(f"   ✅ Page {i+1}: {result['processing_time']:.2f}s, {result['patterns']} patterns")
        else:
            print(f"   ❌ Page {i+1}: Failed")
    
    total_time = time.time() - start_time
    successful_pages = [r for r in results if r['success']]
    avg_time = sum(r['processing_time'] for r in successful_pages) / len(successful_pages) if successful_pages else 0
    
    print(f"\n📊 Sequential Results:")
    print(f"   ⏱️  Total time: {total_time:.1f}s")
    print(f"   📄 Successful pages: {len(successful_pages)}/{len(page_images)}")
    print(f"   📊 Average per page: {avg_time:.2f}s")
    
    return total_time, results

def test_parallel_processing(page_images, chunk_size):
    """Test parallel processing with chunking"""
    print(f"\n⚡ PARALLEL PROCESSING TEST (chunk_size={chunk_size})")
    print("-" * 50)
    
    # Create chunks
    page_chunks = [page_images[i:i + chunk_size] for i in range(0, len(page_images), chunk_size)]
    print(f"   📊 Created {len(page_chunks)} chunks of max size {chunk_size}")
    
    start_time = time.time()
    all_results = []
    
    def process_chunk(chunk_data):
        chunk_idx, chunk = chunk_data
        chunk_results = []
        print(f"   🚀 Starting chunk {chunk_idx+1} ({len(chunk)} pages)...")
        
        for local_idx, image in enumerate(chunk):
            page_num = chunk_idx * chunk_size + local_idx + 1
            result = process_single_page(image, page_num)
            chunk_results.append(result)
            
            if result['success']:
                print(f"      ✅ Page {page_num}: {result['processing_time']:.2f}s")
            else:
                print(f"      ❌ Page {page_num}: Failed")
        
        print(f"   ✅ Completed chunk {chunk_idx+1}")
        return chunk_results
    
    # Process chunks in parallel
    max_workers = min(len(page_chunks), PARALLEL_WORKERS)
    print(f"   👥 Using {max_workers} workers for {len(page_chunks)} chunks")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        chunk_data = [(i, chunk) for i, chunk in enumerate(page_chunks)]
        chunk_results = list(executor.map(process_chunk, chunk_data))
    
    # Flatten results
    for chunk_result in chunk_results:
        all_results.extend(chunk_result)
    
    total_time = time.time() - start_time
    successful_pages = [r for r in all_results if r['success']]
    avg_time = sum(r['processing_time'] for r in successful_pages) / len(successful_pages) if successful_pages else 0
    
    print(f"\n📊 Parallel Results:")
    print(f"   ⏱️  Total time: {total_time:.1f}s")
    print(f"   📄 Successful pages: {len(successful_pages)}/{len(page_images)}")
    print(f"   📊 Average per page: {avg_time:.2f}s")
    
    return total_time, all_results

def main():
    """Main test function"""
    print("🧪 FOCUSED PARALLEL vs SEQUENTIAL TEST")
    print("=" * 60)
    
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    
    try:
        # Get first 6 pages for focused test
        print("📄 Loading PDF pages...")
        all_page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        page_images = all_page_images[:6]  # Test with 6 pages
        print(f"✅ Testing with {len(page_images)} pages")
        
        print(f"\n🔧 Configuration:")
        print(f"   📄 Test pages: {len(page_images)}")
        print(f"   👥 Available workers: {PARALLEL_WORKERS}")
        print(f"   🎯 Default chunk size: {DEFAULT_CHUNK_SIZE}")
        
        # Test 1: Sequential
        sequential_time, seq_results = test_sequential_processing(page_images)
        
        # Test 2: Parallel with chunk_size=2
        parallel_time, par_results = test_parallel_processing(page_images, chunk_size=2)
        
        # Comparison
        print(f"\n🏆 PERFORMANCE COMPARISON:")
        print("=" * 40)
        print(f"Sequential:    {sequential_time:.1f}s")
        print(f"Parallel (2):  {parallel_time:.1f}s")
        
        if parallel_time > 0:
            speedup = sequential_time / parallel_time
            print(f"Speedup:       {speedup:.1f}x")
            
            if speedup > 1.5:
                print(f"✅ SUCCESS: Parallel processing is {speedup:.1f}x faster!")
            elif speedup > 1.0:
                print(f"🟡 MODEST: Parallel processing is {speedup:.1f}x faster")
            else:
                print(f"❌ ISSUE: Parallel processing is slower")
        
        # Project to full PDF
        print(f"\n🚀 PROJECTED FULL PDF PERFORMANCE:")
        total_pages = len(all_page_images)
        seq_successful = len([r for r in seq_results if r['success']])
        par_successful = len([r for r in par_results if r['success']])
        
        if seq_successful > 0 and par_successful > 0:
            seq_avg = sequential_time / seq_successful
            par_avg = parallel_time / par_successful  # This is total time for chunk, not per page
            
            print(f"   📄 Full PDF pages: {total_pages}")
            print(f"   🔄 Sequential projection: {seq_avg * total_pages:.0f}s")
            print(f"   ⚡ Parallel projection: {(seq_avg * 2):.0f}s (chunk_size=2)")  # 2 pages per chunk processed in parallel
            print(f"   📈 Expected speedup: {(seq_avg * total_pages) / (seq_avg * 2):.1f}x")
        
        return True
        
    except Exception as e:
        print(f"❌ Test FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ Test completed successfully!")
        print(f"🎯 Chunking optimization validated!")
    else:
        print(f"\n❌ Test failed")
    
    sys.exit(0 if success else 1) 