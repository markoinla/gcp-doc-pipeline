import fitz  # PyMuPDF
import requests
import io
import logging
from PIL import Image

from config import IMAGE_DPI, IMAGE_FORMAT

logger = logging.getLogger(__name__)

def split_pdf_to_images(pdf_url):
    """Download PDF and convert to images using PyMuPDF"""
    
    logger.info(f"Downloading PDF from: {pdf_url}")
    
    # Download PDF
    response = requests.get(pdf_url, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to download PDF: {response.status_code}")
    
    pdf_bytes = response.content
    logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")
    
    # Open PDF with PyMuPDF
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    
    # Convert each page to image
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        
        # Calculate zoom factor for desired DPI (default 72 DPI)
        zoom = IMAGE_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("jpeg")
        image = Image.open(io.BytesIO(img_data))
        images.append(image)
    
    pdf_document.close()
    
    logger.info(f"Converted PDF to {len(images)} page images at {IMAGE_DPI} DPI")
    return images

def image_to_bytes(pil_image):
    """Convert PIL image to bytes for Vision API"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=IMAGE_FORMAT, quality=85)
    return img_byte_arr.getvalue() 