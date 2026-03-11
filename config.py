"""Central configuration for DarkWolf WOD Translator."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "logs" / "darkwolf_wod.log"
WOD_LOG = BASE_DIR / "data" / "wod_log.json"
PROMPTS_DIR = BASE_DIR / "prompts"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
(BASE_DIR / "logs").mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

# CrossFit
CROSSFIT_WOD_URL = "https://www.crossfit.com/wod"

# Claude API via AWS Bedrock
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLAUDE_MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"

# Site — now hosted under main site at /wod/
SITE_BASE_URL = "https://darkwolfmissionlog.com/wod"

# Main site repo for publishing
SITE_DIR = Path("C:/DarkWolfSite")
SITE_WOD_DIR = SITE_DIR / "wod"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds
