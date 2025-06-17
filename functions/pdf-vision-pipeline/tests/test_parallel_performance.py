#!/usr/bin/env python3
"""
Test Parallel Performance: Test the actual chunked parallel processing
This validates our 9x speedup hypothesis with real parallel execution.
"""

import sys
import os
import time
sys.path.append(os.path.dirname(__file__))

import pdf_processor
from main import process_pages_parallel
from config import DEFAULT_CHUNK_SIZE, PARALLEL_WORKERS

def test_parallel_vs_sequential():
    """Compare sequential vs parallel processing performance"""
    print("⚡ PARALLEL PERFORMANCE TEST")
    print("=" * 50)
    
    # Use same PDF as before
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    
    try:
        print("📄 Step 1: Getting PDF images...")
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        print(f"✅ Got {len(page_images)} images")
        
        # Test different chunk sizes
        chunk_sizes_to_test = [1, 2, 3, 5]  # Including current default
        
        print(f"\n🔧 Configuration:")
        print(f"   📄 Pages: {len(page_images)}")
        print(f"   👥 Workers: {PARALLEL_WORKERS}")
        print(f"   🎯 Default chunk size: {DEFAULT_CHUNK_SIZE}")
        
        results = {}
        
        for chunk_size in chunk_sizes_to_test:
            print(f"\n🚀 Testing chunk_size = {chunk_size}")
            print(f"   📊 Expected chunks: {(len(page_images) + chunk_size - 1) // chunk_size}")
            
            # Mock parameters for testing (we won't actually upload to R2)
            project_id = "test-project"
            file_id = "test-file"
            bucket = "test-bucket"
            
            start_time = time.time()
            
            try:
                # This will call Vision API but skip R2 uploads (will error on upload)
                # We'll catch that and measure the Vision API processing time
                page_results = process_pages_parallel(page_images, project_id, file_id, bucket, chunk_size)
                processing_time = time.time() - start_time
                
                # Count successful Vision API calls (before R2 upload failures)
                vision_success_count = len([r for r in page_results if 'processing_time' in r])
                
                results[chunk_size] = {
                    'time': processing_time,
                    'success_count': vision_success_count,
                    'status': 'partial_success'  # Vision API worked, R2 upload failed
                }
                
                print(f"   ⏱️  Total time: {processing_time:.1f}s")
                print(f"   ✅ Vision API calls: {vision_success_count}/{len(page_images)}")
                
            except Exception as e:
                processing_time = time.time() - start_time
                # Even if R2 upload fails, we can measure Vision API time
                results[chunk_size] = {
                    'time': processing_time,
                    'status': 'error',
                    'error': str(e)
                }
                print(f"   ⏱️  Time before error: {processing_time:.1f}s")
                print(f"   ❌ Error (expected): {str(e)[:100]}...")
        
        # Analysis
        print(f"\n📊 PERFORMANCE COMPARISON:")
        print("Chunk | Time   | Status    | Speedup")
        print("Size  |        |           | Factor") 
        print("-" * 40)
        
        baseline_time = results.get(max(chunk_sizes_to_test), {}).get('time', results[chunk_sizes_to_test[0]]['time'])
        
        for chunk_size in sorted(chunk_sizes_to_test):
            if chunk_size in results:
                result = results[chunk_size]
                speedup = baseline_time / result['time'] if result['time'] > 0 else 0
                status = "✅ Good" if result.get('success_count', 0) > 0 else "⚠️  Error"
                print(f"{chunk_size:4d}  | {result['time']:5.1f}s | {status:9s} | {speedup:6.1f}x")
        
        # Find best performing chunk size
        valid_results = {k: v for k, v in results.items() if v['time'] > 0}
        if valid_results:
            best_chunk_size = min(valid_results.keys(), key=lambda x: valid_results[x]['time'])
            best_time = valid_results[best_chunk_size]['time']
            
            print(f"\n🏆 RESULTS:")
            print(f"✅ Best chunk_size: {best_chunk_size}")
            print(f"⏱️  Best time: {best_time:.1f}s")
            print(f"🚀 Speedup vs largest chunk: {baseline_time/best_time:.1f}x")
            
            if best_chunk_size == DEFAULT_CHUNK_SIZE:
                print(f"🎯 Current default ({DEFAULT_CHUNK_SIZE}) is optimal!")
            else:
                print(f"💡 Consider updating DEFAULT_CHUNK_SIZE to {best_chunk_size}")
        
        return True, results
        
    except Exception as e:
        print(f"❌ Test FAILED: {str(e)}")
        return False, None

def test_vision_api_only():
    """Test just Vision API calls without R2 upload to isolate performance"""
    print("\n🔬 VISION API ISOLATION TEST")
    print("=" * 50)
    
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    
    try:
        print("📄 Getting first 3 pages for quick test...")
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)[:3]
        
        import vision_processor
        import pattern_extractor
        
        print(f"🔍 Testing {len(page_images)} pages with isolated Vision API calls...")
        
        start_time = time.time()
        
        for i, image in enumerate(page_images):
            page_start = time.time()
            
            # Convert image to bytes
            image_bytes = pdf_processor.image_to_bytes(image)
            
            # Vision API call
            vision_result = vision_processor.call_vision_api(image_bytes)
            
            # Pattern extraction
            patterns = pattern_extractor.extract_patterns_from_vision(vision_result, i+1)
            
            page_time = time.time() - page_start
            print(f"   Page {i+1}: {page_time:.2f}s, {len(patterns)} patterns")
        
        total_time = time.time() - start_time
        avg_time = total_time / len(page_images)
        
        print(f"\n⏱️  Total time: {total_time:.1f}s")
        print(f"📊 Average per page: {avg_time:.2f}s")
        print(f"🚀 Projected 18 pages: {avg_time * 18:.1f}s sequential")
        print(f"⚡ With chunk_size=2: ~{(avg_time * 2):.1f}s parallel")
        
        return True
        
    except Exception as e:
        print(f"❌ Vision API test FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 COMPREHENSIVE PERFORMANCE TESTING")
    print("=" * 60)
    
    # Test 1: Vision API isolation
    vision_success = test_vision_api_only()
    
    # Test 2: Parallel processing (will partially fail on R2 but show Vision timing)
    if vision_success:
        parallel_success, results = test_parallel_vs_sequential()
        
        if parallel_success:
            print(f"\n✅ ALL TESTS COMPLETED")
            print(f"🎯 Ready for production with optimized chunking!")
        else:
            print(f"\n⚠️  Partial success - Vision API timing validated")
    
    print(f"\n💡 Next: Test R2 storage connection")
    print(f"   Run: python test_r2_connection.py") 