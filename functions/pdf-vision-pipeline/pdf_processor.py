from pdf2image import convert_from_bytes
import requests
import io
import logging

from config import IMAGE_DPI, IMAGE_FORMAT

logger = logging.getLogger(__name__)

def split_pdf_to_images(pdf_url):
    """Download PDF and convert to images"""
    
    logger.info(f"Downloading PDF from: {pdf_url}")
    
    # Download PDF
    response = requests.get(pdf_url, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to download PDF: {response.status_code}")
    
    pdf_bytes = response.content
    logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")
    
    # Convert to images
    images = convert_from_bytes(
        pdf_bytes, 
        dpi=IMAGE_DPI,
        fmt=IMAGE_FORMAT.lower()
    )
    
    logger.info(f"Converted PDF to {len(images)} page images at {IMAGE_DPI} DPI")
    return images

def image_to_bytes(pil_image):
    """Convert PIL image to bytes for Vision API"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=IMAGE_FORMAT, quality=85)
    return img_byte_arr.getvalue() 