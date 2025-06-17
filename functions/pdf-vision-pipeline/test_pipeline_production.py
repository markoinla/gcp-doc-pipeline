#!/usr/bin/env python3
"""
Production Pipeline Test: Complete PDF → Vision API → R2 workflow
Tests the full production pipeline end-to-end.
"""

import sys
import os
import time
import json
sys.path.append(os.path.dirname(__file__))

import pdf_processor
from main import process_pages_parallel
import result_aggregator
import storage_handler
from config import DEFAULT_CHUNK_SIZE, PARALLEL_WORKERS

def test_production_pipeline():
    """Test the complete production pipeline"""
    print("🚀 PRODUCTION PIPELINE TEST")
    print("=" * 50)
    
    # Production configuration
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    project_id = "prod-pipeline-test"
    file_id = f"test-{int(time.time())}"
    bucket = "ladders-1"
    
    print(f"📄 PDF: {test_pdf_url}")
    print(f"📁 Project: {project_id}")
    print(f"📋 File: {file_id}")
    print(f"🪣 Bucket: {bucket}")
    
    total_start = time.time()
    
    try:
        # Step 1: Download and process PDF
        print(f"\n📥 Step 1: PDF Download & Processing...")
        pdf_start = time.time()
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        pdf_time = time.time() - pdf_start
        print(f"✅ PDF processed: {len(page_images)} pages in {pdf_time:.1f}s")
        
        # Step 2: Parallel Vision API processing with R2 uploads
        print(f"\n⚡ Step 2: Vision API + R2 Upload...")
        print(f"   📦 Chunk size: {DEFAULT_CHUNK_SIZE}")
        print(f"   👥 Workers: {PARALLEL_WORKERS}")
        
        vision_start = time.time()
        page_results = process_pages_parallel(
            page_images=page_images,
            project_id=project_id,
            file_id=file_id,
            bucket=bucket,
            chunk_size=DEFAULT_CHUNK_SIZE
        )
        vision_time = time.time() - vision_start
        print(f"✅ Vision processing completed in {vision_time:.1f}s")
        
        # Step 3: Compile and upload final results
        print(f"\n📋 Step 3: Final Results Compilation...")
        final_start = time.time()
        final_result = result_aggregator.compile_final_json(page_results, project_id, file_id)
        final_json_url = storage_handler.upload_final_json(final_result, project_id, file_id, bucket)
        final_time = time.time() - final_start
        print(f"✅ Final results uploaded in {final_time:.1f}s")
        
        # Step 4: Results Analysis
        total_time = time.time() - total_start
        successful_pages = [r for r in page_results if r.get('success', False)]
        failed_pages = [r for r in page_results if not r.get('success', False)]
        
        total_patterns = sum(len(r.get('patterns', [])) for r in successful_pages)
        pt1_patterns = sum(len([p for p in r.get('patterns', []) if p.get('pattern_type') == 'PT1']) for r in successful_pages)
        
        image_urls = [r.get('image_url') for r in successful_pages if r.get('image_url')]
        json_urls = [r.get('json_url') for r in successful_pages if r.get('json_url')]
        
        print(f"\n📊 PIPELINE RESULTS:")
        print(f"   ⏱️  Total time: {total_time:.1f}s")
        print(f"   📄 Pages processed: {len(successful_pages)}/{len(page_images)}")
        print(f"   ❌ Failed pages: {len(failed_pages)}")
        print(f"   🎯 Total patterns: {total_patterns}")
        print(f"   🏷️  PT1 patterns: {pt1_patterns}")
        print(f"   🖼️  Images uploaded: {len(image_urls)}")
        print(f"   📋 Page JSONs uploaded: {len(json_urls)}")
        print(f"   📄 Final JSON: {'✅' if final_json_url else '❌'}")
        
        # Performance metrics
        success_rate = len(successful_pages) / len(page_images) * 100
        avg_per_page = total_time / len(page_images)
        
        print(f"\n⚡ PERFORMANCE:")
        print(f"   📈 Success rate: {success_rate:.1f}%")
        print(f"   📊 Avg per page: {avg_per_page:.1f}s")
        print(f"   🚀 Processing rate: {len(page_images)/total_time:.1f} pages/second")
        
        # Show sample URLs
        print(f"\n🔗 SAMPLE URLS:")
        if image_urls:
            print(f"   🖼️  Image: {image_urls[0]}")
        if json_urls:
            print(f"   📋 Page JSON: {json_urls[0]}")
        if final_json_url:
            print(f"   📄 Final JSON: {final_json_url}")
        
        # Success criteria
        pipeline_success = (
            success_rate >= 90 and  # 90%+ success rate
            total_time <= 30 and    # Under 30 seconds total
            total_patterns > 0 and  # Found patterns
            len(image_urls) > 0 and # Images uploaded
            len(json_urls) > 0 and  # JSONs uploaded
            final_json_url is not None  # Final JSON uploaded
        )
        
        print(f"\n🏆 PIPELINE STATUS:")
        if pipeline_success:
            print(f"✅ PRODUCTION PIPELINE: SUCCESS!")
            print(f"   🎊 Ready for production deployment")
            print(f"   📈 {pt1_patterns} PT1 patterns detected")
            print(f"   ⚡ {total_time:.0f}s total processing time")
        else:
            print(f"❌ PRODUCTION PIPELINE: FAILED")
            if success_rate < 90:
                print(f"   📊 Low success rate: {success_rate:.1f}%")
            if total_time > 30:
                print(f"   ⏱️  Slow performance: {total_time:.1f}s")
            if total_patterns == 0:
                print(f"   🔍 No patterns detected")
            if not image_urls or not json_urls or not final_json_url:
                print(f"   📤 Upload issues detected")
        
        return pipeline_success
        
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 TESTING PRODUCTION PIPELINE")
    print("=" * 60)
    
    success = test_production_pipeline()
    
    if success:
        print(f"\n🎉 PIPELINE TEST PASSED!")
        print(f"🚀 Production pipeline is ready for deployment")
    else:
        print(f"\n❌ PIPELINE TEST FAILED!")
        print(f"🔧 Check logs above for issues")
    
    sys.exit(0 if success else 1) 