import os

# Processing Configuration
MAX_PAGES = 50
PARALLEL_WORKERS = 30  # Default workers (can be overridden via API)
DEFAULT_CHUNK_SIZE = 2  # Pages per worker chunk (optimized for best performance)
IMAGE_DPI = 150
IMAGE_FORMAT = 'JPEG'
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Vision API Configuration
VISION_TIMEOUT = 30  # seconds

# Storage Configuration  
DEFAULT_R2_BUCKET = 'ladders-1'
R2_BASE_URL = 'https://pub-592c678931664039950f4a0846d0d9d1.r2.dev'

# Pattern Configuration - Regex patterns for matching
PATTERN_REGEXES = [
    r'\b[A-Za-z]-?\d+\b',       # General patterns like A1, S-1, a1, s-1, etc.
    r'\b[A-Za-z]{2}-\d+\b',     # Patterns like AB-123, XY-1, ab-123, xy-1, etc.
    r'\b[A-Za-z]{2}\d{1,3}\b',  # Patterns like AB12, XY99, ab12, xy99 (1-3 digits)
]

# Image Input Configuration
MAX_IMAGES = 50  # Same as MAX_PAGES
SUPPORTED_IMAGE_FORMATS = ['JPEG', 'PNG', 'WEBP', 'TIFF']
MAX_IMAGE_SIZE_MB = 10

# Parallel Processing Configuration (MAINTAINED FROM PDF PIPELINE)
IMAGE_DOWNLOAD_TIMEOUT = 15 # Timeout for individual image downloads 