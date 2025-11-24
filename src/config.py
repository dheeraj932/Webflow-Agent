"""
Configuration constants and settings
"""

import os
from pathlib import Path

# API Configuration
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.3"))

# Browser Configuration
BROWSER_STORAGE_PATH = os.getenv("BROWSER_STORAGE_PATH", "browser_storage")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "100"))

# Paths
SCREENSHOTS_DIR = Path("screenshots")
DATASET_DIR = Path("dataset")
DEBUG_HTML_DIR = Path("debug_html")

# Timeouts (in milliseconds)
CLICK_TIMEOUT = 5000
NAVIGATION_TIMEOUT = 30000
ELEMENT_WAIT_TIMEOUT = 5000

# Retry Configuration
MAX_RETRIES = 2
RETRY_DELAY = 0.5  # seconds

