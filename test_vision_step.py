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
        
        # Test on first 3 pages to start
        test_pages = min(3, len(page_images))
        print(f"🔍 Testing on first {test_pages} pages")
        
        all_results = []
        
        for i, image in enumerate(page_images[:test_pages]):
            print(f"\n📄 Processing page {i+1}/{test_pages}...")
            
            start_time = time.time()
            
            # Convert image to bytes for Vision API
            image_bytes = pdf_processor.image_to_bytes(image)
            
            # Process with Vision API
            vision_result = vision_processor.process_image_with_vision(image_bytes)
            
            processing_time = time.time() - start_time
            
            # Extract patterns
            patterns = pattern_extractor.extract_patterns(vision_result)
            
            print(f"⏱️  Vision API time: {processing_time:.2f}s")
            print(f"📝 Text blocks found: {len(vision_result.get('text_annotations', []))}")
            print(f"🎯 Patterns found: {len(patterns)}")
            
            # Show pattern summary
            pattern_types = {}
            for pattern in patterns:
                pattern_type = pattern.get('type', 'unknown')
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
        
        # Summary
        total_patterns = sum(len(result['patterns']) for result in all_results)
        avg_time = sum(result['processing_time'] for result in all_results) / len(all_results)
        
        print(f"\n🎉 Vision API Test Results:")
        print(f"📊 Total patterns found: {total_patterns}")
        print(f"⏱️  Average time per page: {avg_time:.2f}s")
        print(f"🎯 Pattern detection rate: {total_patterns/test_pages:.1f} patterns/page")
        
        # Look for PT1 specifically
        pt1_count = 0
        for result in all_results:
            for pattern in result['patterns']:
                if 'PT1' in pattern.get('text', '').upper():
                    pt1_count += 1
        
        print(f"🔍 PT1 patterns found: {pt1_count}")
        
        if pt1_count > 0:
            print("✅ SUCCESS: Found PT1 patterns! Vision API is working.")
        else:
            print("⚠️  No PT1 patterns found. May need to check more pages or adjust detection.")
        
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