#!/usr/bin/env python3
"""
Test the PDF processing step of the pipeline
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pdf_processor import split_pdf_to_images, image_to_bytes

def test_pdf_processing():
    print("📄 Testing PDF Processing Step...")
    
    # Use the actual architectural PDF from the user
    pdf_url = "https://pub-592c678931664039950f4a0846d0d9d1.r2.dev/FLOORPLANS/Boathouse%20-%20WhiteOaks(BidSet).pdf"
    print(f"🔗 PDF URL: {pdf_url}")
    
    try:
        print("⬇️  Downloading and converting PDF...")
        images = split_pdf_to_images(pdf_url)
        
        print(f"✅ Successfully converted PDF to {len(images)} images")
        
        # Show sample image info
        if images:
            first_image = images[0]
            print(f"📊 Sample image: {first_image.size} pixels, format: {first_image.format}")
            
            # Test converting to bytes
            image_bytes = image_to_bytes(first_image)
            print(f"💾 Image data size: {len(image_bytes)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ PDF Processing test FAILED: {e}")
        return False

if __name__ == "__main__":
    success = test_pdf_processing()
    sys.exit(0 if success else 1) 