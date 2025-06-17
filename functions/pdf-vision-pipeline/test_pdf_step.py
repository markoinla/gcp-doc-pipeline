#!/usr/bin/env python3
"""
Test PDF processing step: Download PDF and convert to images
This tests the first step in our pipeline workflow.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import pdf_processor
import time

def test_pdf_processing():
    """Test PDF download and image conversion"""
    print("📄 Testing PDF Processing Step...")
    
    # Use your actual PDF for testing
    test_pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks%28BidSet%29.pdf"
    
    try:
        print(f"🔗 PDF URL: {test_pdf_url}")
        
        start_time = time.time()
        
        # Test PDF download and conversion
        print("⬇️  Downloading and converting PDF...")
        page_images = pdf_processor.split_pdf_to_images(test_pdf_url)
        
        download_time = time.time() - start_time
        
        print(f"✅ Success! Converted to {len(page_images)} images")
        print(f"⏱️  Processing time: {download_time:.2f} seconds")
        
        # Test image properties
        if page_images:
            first_image = page_images[0]
            print(f"🖼️  First image: {first_image.size} pixels ({first_image.mode})")
            
            # Test image to bytes conversion
            image_bytes = pdf_processor.image_to_bytes(first_image)
            print(f"📦 Image bytes: {len(image_bytes)} bytes")
            
            # Calculate average per page
            print(f"📊 Average per page: {download_time/len(page_images):.2f}s, {len(image_bytes)/1024:.1f}KB")
        
        # Verify we got the expected number of pages (21 for your PDF)
        expected_pages = 21
        if len(page_images) == expected_pages:
            print(f"✅ Page count matches expected: {expected_pages}")
        else:
            print(f"⚠️  Page count mismatch. Expected: {expected_pages}, Got: {len(page_images)}")
        
        print(f"\n🎉 PDF Processing test PASSED!")
        print(f"📋 Ready for next step: Vision API processing")
        
        return True, page_images
        
    except Exception as e:
        print(f"❌ PDF Processing test FAILED: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, images = test_pdf_processing()
    
    if success:
        print(f"\n💡 Next test: Vision API on page images")
        print(f"   Run: python test_vision_step.py")
    
    sys.exit(0 if success else 1) 