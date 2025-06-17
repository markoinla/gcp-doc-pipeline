#!/usr/bin/env python3
"""
End-to-End Test: Complete pipeline with R2 uploads
Tests the full workflow: PDF → Images → Vision API → Pattern Extraction → R2 Upload
"""

import sys
import os
import time
sys.path.append(os.path.dirname(__file__))

import pdf_processor
from main import process_pages_parallel
from config import DEFAULT_CHUNK_SIZE, PARALLEL_WORKERS
import storage_handler

def test_end_to_end_pipeline():
    """Test the complete pipeline with R2 uploads"""
    print("🧪 END-TO-END PIPELINE TEST")
    print("=" * 60)
    
    # Test configuration
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    project_id = "test-project-e2e"
    file_id = f"test-file-{int(time.time())}"
    bucket = "ladders-1"
    
    print(f"🔧 Configuration:")
    print(f"   📄 PDF URL: {test_pdf_url}")
    print(f"   📁 Project ID: {project_id}")
    print(f"   📋 File ID: {file_id}")
    print(f"   🪣 Bucket: {bucket}")
    print(f"   📦 Chunk Size: {DEFAULT_CHUNK_SIZE}")
    print(f"   👥 Workers: {PARALLEL_WORKERS}")
    
    try:
        # Step 1: PDF Processing
        print(f"\n📄 Step 1: Processing PDF...")
        start_time = time.time()
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        pdf_time = time.time() - start_time
        print(f"✅ PDF processed: {len(page_images)} pages in {pdf_time:.1f}s")
        
        # Step 2: Parallel Vision API + R2 Upload
        print(f"\n⚡ Step 2: Parallel Vision API processing with R2 uploads...")
        pipeline_start = time.time()
        
        # Process with our optimized chunk size
        page_results = process_pages_parallel(
            page_images=page_images,
            project_id=project_id,
            file_id=file_id,
            bucket=bucket,
            chunk_size=DEFAULT_CHUNK_SIZE
        )
        
        pipeline_time = time.time() - pipeline_start
        print(f"✅ Pipeline completed in {pipeline_time:.1f}s")
        
        # Step 3: Analyze Results
        print(f"\n📊 Step 3: Analyzing Results...")
        successful_pages = [r for r in page_results if r.get('success', False)]
        failed_pages = [r for r in page_results if not r.get('success', False)]
        
        total_patterns = sum(len(r.get('patterns', [])) for r in successful_pages)
        pt1_patterns = sum(len([p for p in r.get('patterns', []) if p.get('pattern_type') == 'PT1']) for r in successful_pages)
        
        # URLs uploaded
        image_urls = [r.get('image_url') for r in successful_pages if r.get('image_url')]
        json_urls = [r.get('json_url') for r in successful_pages if r.get('json_url')]
        
        print(f"   📄 Total pages: {len(page_images)}")
        print(f"   ✅ Successful: {len(successful_pages)}")
        print(f"   ❌ Failed: {len(failed_pages)}")
        print(f"   🎯 Total patterns: {total_patterns}")
        print(f"   🏷️  PT1 patterns: {pt1_patterns}")
        print(f"   🖼️  Images uploaded: {len(image_urls)}")
        print(f"   📋 JSON files uploaded: {len(json_urls)}")
        
        # Step 4: Performance Summary
        print(f"\n⚡ Step 4: Performance Summary...")
        total_time = pdf_time + pipeline_time
        avg_page_time = pipeline_time / len(successful_pages) if successful_pages else 0
        
        print(f"   📄 PDF processing: {pdf_time:.1f}s")
        print(f"   ⚡ Vision + Upload: {pipeline_time:.1f}s")
        print(f"   🕒 Total time: {total_time:.1f}s")
        print(f"   📊 Avg per page: {avg_page_time:.2f}s")
        
        # Calculate speedup vs sequential
        sequential_estimate = len(page_images) * 4.2  # From our previous tests
        speedup = sequential_estimate / pipeline_time
        print(f"   🚀 Speedup vs sequential: {speedup:.1f}x")
        
        # Step 5: Verify R2 URLs
        print(f"\n🔍 Step 5: Verifying uploaded files...")
        if image_urls:
            print(f"   🖼️  Sample image URL: {image_urls[0]}")
        if json_urls:
            print(f"   📋 Sample JSON URL: {json_urls[0]}")
        
        # Success criteria
        success_rate = len(successful_pages) / len(page_images) if page_images else 0
        performance_good = pipeline_time < (len(page_images) * 2)  # Under 2s per page
        patterns_found = total_patterns > 0
        uploads_working = len(image_urls) > 0 and len(json_urls) > 0
        
        print(f"\n🎯 Success Criteria:")
        print(f"   📊 Success rate: {success_rate:.1%} {'✅' if success_rate > 0.8 else '❌'}")
        print(f"   ⚡ Performance: {'✅' if performance_good else '❌'} (<2s/page)")
        print(f"   🔍 Patterns found: {'✅' if patterns_found else '❌'}")
        print(f"   📤 R2 uploads: {'✅' if uploads_working else '❌'}")
        
        overall_success = success_rate > 0.8 and performance_good and patterns_found and uploads_working
        
        if overall_success:
            print(f"\n🎉 END-TO-END TEST: ✅ SUCCESS")
            print(f"   🚀 Pipeline ready for production!")
            print(f"   ⚡ {speedup:.1f}x faster than sequential processing")
            print(f"   🎯 {pt1_patterns} PT1 patterns detected")
        else:
            print(f"\n❌ END-TO-END TEST: FAILED")
            if not success_rate > 0.8:
                print(f"   📊 Low success rate: {success_rate:.1%}")
            if not performance_good:
                print(f"   ⚡ Performance issue: {pipeline_time:.1f}s for {len(page_images)} pages")
            if not patterns_found:
                print(f"   🔍 No patterns detected")
            if not uploads_working:
                print(f"   📤 R2 upload issues")
        
        # Show any errors
        if failed_pages:
            print(f"\n❌ Failed Pages Details:")
            for failed in failed_pages[:3]:  # Show first 3 failures
                page_num = failed.get('page', 'unknown')
                error = failed.get('error', 'unknown error')
                print(f"   Page {page_num}: {error}")
        
        return overall_success, {
            'total_time': total_time,
            'pipeline_time': pipeline_time,
            'success_rate': success_rate,
            'total_patterns': total_patterns,
            'pt1_patterns': pt1_patterns,
            'speedup': speedup,
            'image_urls': image_urls,
            'json_urls': json_urls
        }
        
    except Exception as e:
        print(f"❌ End-to-end test FAILED: {str(e)}")
        return False, None

def test_single_page_upload():
    """Test single page processing and upload"""
    print(f"\n🧪 SINGLE PAGE UPLOAD TEST")
    print("=" * 40)
    
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    project_id = "test-single"
    file_id = f"single-{int(time.time())}"
    bucket = "ladders-1"
    
    try:
        # Get first page only
        print("📄 Getting first page...")
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)[:1]
        print(f"✅ Got {len(page_images)} page")
        
        # Process single page
        start_time = time.time()
        page_results = process_pages_parallel(
            page_images=page_images,
            project_id=project_id,
            file_id=file_id,
            bucket=bucket,
            chunk_size=1
        )
        processing_time = time.time() - start_time
        
        if page_results and page_results[0].get('success'):
            result = page_results[0]
            print(f"✅ Single page processed in {processing_time:.2f}s")
            print(f"   🎯 Patterns found: {len(result.get('patterns', []))}")
            print(f"   🖼️  Image URL: {result.get('image_url', 'None')}")
            print(f"   📋 JSON URL: {result.get('json_url', 'None')}")
            return True
        else:
            error = page_results[0].get('error') if page_results else 'Unknown error'
            print(f"❌ Single page test failed: {error}")
            return False
        
    except Exception as e:
        print(f"❌ Single page test FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 COMPREHENSIVE END-TO-END TESTING")
    print("=" * 70)
    
    # Test 1: Single page upload
    single_success = test_single_page_upload()
    
    # Test 2: Full pipeline (only if single page works)
    if single_success:
        print(f"\n" + "="*70)
        e2e_success, results = test_end_to_end_pipeline()
        
        if e2e_success and results:
            print(f"\n🎊 ALL TESTS PASSED!")
            print(f"📈 Performance achieved: {results['speedup']:.1f}x speedup")
            print(f"🎯 Pattern detection: {results['pt1_patterns']} PT1 patterns")
            print(f"📤 R2 integration: {len(results['image_urls'])} images + {len(results['json_urls'])} JSON files")
            print(f"\n🚀 READY FOR PRODUCTION DEPLOYMENT!")
        else:
            print(f"\n❌ End-to-end test failed")
    else:
        print(f"\n❌ Skipping full test due to single page failure")
    
    sys.exit(0 if (single_success and e2e_success if 'e2e_success' in locals() else single_success) else 1) 