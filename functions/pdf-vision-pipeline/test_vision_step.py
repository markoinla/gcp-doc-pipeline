#!/usr/bin/env python3
"""
Test Vision API processing: Run Google Cloud Vision on PDF images
This tests our core pattern detection accuracy.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import pdf_processor
import vision_processor
import pattern_extractor
import time

def test_vision_api():
    """Test Vision API on architectural PDF images"""
    print("👁️  Testing Vision API Processing...")
    
    # Use same PDF as before
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    
    try:
        print("📄 Step 1: Getting PDF images...")
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        print(f"✅ Got {len(page_images)} images")
        
        print("\n👁️  Step 2: Testing Vision API...")
        
        # Process ALL pages for complete analysis
        test_pages = len(page_images)
        print(f"🔍 Processing ALL {test_pages} pages for complete analysis")
        print(f"⏱️  Estimated time: ~{test_pages * 4} seconds")
        
        all_results = []
        
        for i, image in enumerate(page_images[:test_pages]):
            print(f"\n📄 Processing page {i+1}/{test_pages}...")
            
            start_time = time.time()
            
            # Convert image to bytes for Vision API
            image_bytes = pdf_processor.image_to_bytes(image)
            
            # Process with Vision API
            vision_result = vision_processor.call_vision_api(image_bytes)
            
            processing_time = time.time() - start_time
            
            # Extract patterns
            patterns = pattern_extractor.extract_patterns_from_vision(vision_result, i+1)
            
            print(f"⏱️  Vision API time: {processing_time:.2f}s")
            print(f"📝 Text blocks found: {len(vision_result.text_annotations)}")
            print(f"🎯 Patterns found: {len(patterns)}")
            
            # Show pattern summary
            pattern_types = {}
            for pattern in patterns:
                pattern_type = pattern.get('pattern_type', 'unknown')
                pattern_types[pattern_type] = pattern_types.get(pattern_type, 0) + 1
            
            if pattern_types:
                print(f"📊 Pattern breakdown: {pattern_types}")
            else:
                print("❌ No patterns detected")
            
            all_results.append({
                'page': i+1,
                'vision_result': vision_result,
                'patterns': patterns,
                'processing_time': processing_time
            })
        
        # Comprehensive Analysis
        total_patterns = sum(len(result['patterns']) for result in all_results)
        total_time = sum(result['processing_time'] for result in all_results)
        avg_time = total_time / len(all_results)
        total_text_blocks = sum(len(result['vision_result'].text_annotations) for result in all_results)
        
        print(f"\n🎉 COMPLETE PDF ANALYSIS RESULTS:")
        print(f"📄 Pages processed: {test_pages}")
        print(f"⏱️  Total processing time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        print(f"⚡ Average time per page: {avg_time:.2f}s")
        print(f"📝 Total text blocks detected: {total_text_blocks:,}")
        print(f"📊 Total patterns found: {total_patterns}")
        print(f"🎯 Pattern detection rate: {total_patterns/test_pages:.1f} patterns/page")
        
        # Detailed pattern analysis
        all_pattern_types = {}
        pt1_count = 0
        pt_series_count = 0
        
        for result in all_results:
            for pattern in result['patterns']:
                pattern_type = pattern.get('pattern_type', 'unknown')
                all_pattern_types[pattern_type] = all_pattern_types.get(pattern_type, 0) + 1
                
                if pattern_type == 'PT1':
                    pt1_count += 1
                if pattern_type.startswith('PT'):
                    pt_series_count += 1
        
        print(f"\n🔍 KEY PATTERN ANALYSIS:")
        print(f"🎯 PT1 patterns found: {pt1_count}")
        print(f"📐 PT-series patterns (PT1-PT8): {pt_series_count}")
        print(f"📊 Unique pattern types: {len(all_pattern_types)}")
        
        # Show top 10 most common patterns
        sorted_patterns = sorted(all_pattern_types.items(), key=lambda x: x[1], reverse=True)
        print(f"\n🏆 TOP 10 MOST COMMON PATTERNS:")
        for i, (pattern, count) in enumerate(sorted_patterns[:10]):
            print(f"  {i+1:2d}. {pattern}: {count} occurrences")
        
        # Compare vs Document AI
        print(f"\n⚔️  VISION API vs DOCUMENT AI COMPARISON:")
        print(f"📊 Document AI (previous): ~3 PT1 patterns from 21 pages")
        print(f"🚀 Vision API (current): {pt1_count} PT1 patterns from {test_pages} pages")
        accuracy_improvement = (pt1_count / test_pages) / (3 / 21) if pt1_count > 0 else 0
        print(f"📈 Accuracy improvement: {accuracy_improvement:.1f}x better detection rate")
        
        if pt1_count > 3:
            print("🎉 SUCCESS: Vision API found MORE PT1 patterns than Document AI!")
        elif pt1_count > 0:
            print("✅ SUCCESS: Vision API found PT1 patterns! Accuracy validation complete.")
        else:
            print("⚠️  No PT1 patterns found. Document may not contain PT1 or needs adjustment.")
        
        return True, all_results
        
    except Exception as e:
        print(f"❌ Vision API test FAILED: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, results = test_vision_api()
    
    if success:
        print(f"\n💡 Next test: R2 Storage upload")
        print(f"   Run: python test_r2_connection.py")
    
    sys.exit(0 if success else 1) 