import fitz  # PyMuPDF
import requests
import io
import logging
import base64
import concurrent.futures
from PIL import Image

from config import IMAGE_DPI, IMAGE_FORMAT, SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE_MB, IMAGE_DOWNLOAD_TIMEOUT

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

# ============ NEW IMAGE DIRECT PROCESSING FUNCTIONS ============

def download_images_parallel(image_specs, parallel_workers):
    """Download all image URLs in parallel using ThreadPoolExecutor"""
    logger.info(f"Starting parallel download of {len(image_specs)} images using {parallel_workers} workers")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        # Submit all download tasks
        future_to_spec = {
            executor.submit(download_single_image, spec, idx + 1): (spec, idx)
            for idx, spec in enumerate(image_specs)
        }
        
        # Collect results maintaining order
        images = [None] * len(image_specs)
        for future in concurrent.futures.as_completed(future_to_spec):
            spec, idx = future_to_spec[future]
            try:
                images[idx] = future.result()
                logger.info(f"Downloaded image {idx + 1}/{len(image_specs)}")
            except Exception as e:
                logger.error(f"Failed to download image {idx + 1}: {str(e)}")
                images[idx] = None
    
    # Filter out failed downloads
    successful_images = [img for img in images if img is not None]
    failed_count = len(images) - len(successful_images)
    
    if failed_count > 0:
        logger.warning(f"{failed_count} images failed to download")
    
    logger.info(f"Successfully downloaded {len(successful_images)}/{len(image_specs)} images")
    return successful_images

def download_images_parallel_with_urls(image_specs, parallel_workers):
    """Download all image URLs in parallel and preserve original URLs"""
    logger.info(f"Starting parallel download of {len(image_specs)} images using {parallel_workers} workers")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        # Submit all download tasks
        future_to_spec = {
            executor.submit(download_single_image_with_url, spec, idx + 1): (spec, idx)
            for idx, spec in enumerate(image_specs)
        }
        
        # Collect results maintaining order
        images_with_urls = [None] * len(image_specs)
        for future in concurrent.futures.as_completed(future_to_spec):
            spec, idx = future_to_spec[future]
            try:
                images_with_urls[idx] = future.result()
                logger.info(f"Downloaded image {idx + 1}/{len(image_specs)}")
            except Exception as e:
                logger.error(f"Failed to download image {idx + 1}: {str(e)}")
                images_with_urls[idx] = None
    
    # Filter out failed downloads
    successful_images = [img for img in images_with_urls if img is not None]
    failed_count = len(images_with_urls) - len(successful_images)
    
    if failed_count > 0:
        logger.warning(f"{failed_count} images failed to download")
    
    logger.info(f"Successfully downloaded {len(successful_images)}/{len(image_specs)} images")
    return successful_images

def download_single_image_with_url(image_spec, page_num):
    """Download or decode a single image and preserve original URL/metadata"""
    try:
        if 'url' in image_spec:
            image = download_image_from_url(image_spec['url'])
            original_url = image_spec['url']
        elif 'data' in image_spec:
            image = decode_base64_image(image_spec['data'])
            original_url = None  # No URL for base64 data
        else:
            raise ValueError(f"Image {page_num}: No URL or data provided")
        
        # Return tuple of (image, original_url, page_number)
        return {
            'image': image,
            'original_url': original_url,
            'page_number': image_spec.get('pageNumber', page_num)
        }
        
    except Exception as e:
        logger.error(f"Error processing image {page_num}: {str(e)}")
        raise

def download_single_image(image_spec, page_num):
    """Download or decode a single image"""
    try:
        if 'url' in image_spec:
            return download_image_from_url(image_spec['url'])
        elif 'data' in image_spec:
            return decode_base64_image(image_spec['data'])
        else:
            raise ValueError(f"Image {page_num}: No URL or data provided")
    except Exception as e:
        logger.error(f"Error processing image {page_num}: {str(e)}")
        raise

def download_image_from_url(image_url):
    """Download image from URL and convert to PIL Image"""
    logger.debug(f"Downloading image from: {image_url}")
    
    response = requests.get(image_url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
    if response.status_code != 200:
        raise Exception(f"Failed to download image: HTTP {response.status_code}")
    
    image_bytes = response.content
    
    # Validate image size
    if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise Exception(f"Image too large: {len(image_bytes)} bytes (max: {MAX_IMAGE_SIZE_MB}MB)")
    
    # Convert to PIL Image
    image = Image.open(io.BytesIO(image_bytes))
    
    # Validate image format
    validate_image_format(image)
    
    logger.debug(f"Downloaded image: {image.size} pixels, format: {image.format}")
    return image

def decode_base64_image(base64_data):
    """Decode base64 image data to PIL Image"""
    logger.debug("Decoding base64 image data")
    
    try:
        # Remove data URL prefix if present (data:image/jpeg;base64,...)
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        image_bytes = base64.b64decode(base64_data)
        
        # Validate image size
        if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise Exception(f"Image too large: {len(image_bytes)} bytes (max: {MAX_IMAGE_SIZE_MB}MB)")
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Validate image format
        validate_image_format(image)
        
        logger.debug(f"Decoded base64 image: {image.size} pixels, format: {image.format}")
        return image
        
    except Exception as e:
        raise Exception(f"Failed to decode base64 image: {str(e)}")

def validate_image_format(image):
    """Validate image format and size"""
    if image.format not in SUPPORTED_IMAGE_FORMATS:
        raise Exception(f"Unsupported image format: {image.format}. Supported: {SUPPORTED_IMAGE_FORMATS}")
    
    # Check image dimensions (reasonable limits)
    width, height = image.size
    if width < 10 or height < 10:
        raise Exception(f"Image too small: {width}x{height} pixels")
    
    if width > 10000 or height > 10000:
        raise Exception(f"Image too large: {width}x{height} pixels (max: 10000x10000)")
    
    logger.debug(f"Image validation passed: {width}x{height}, format: {image.format}") 