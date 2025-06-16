import os

# Processing Configuration
MAX_PAGES = 50
PARALLEL_WORKERS = 15
DEFAULT_CHUNK_SIZE = 5  # Pages per worker chunk
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
    r'\bPT\d+\b',           # PT1, PT2, etc.
    r'\bM\d+\b',            # M1, M2, etc.
    r'\bE\d+\b',            # E1, E2, etc.
    r'\b[A-Z]-?\d+\b'       # General patterns like A1, S-1, etc.
] 