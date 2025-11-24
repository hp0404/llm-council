"""Configuration for the LLM Council."""

import os

from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Auth secret token - REQUIRED for security
SECRET_AUTH_TOKEN = os.getenv("SECRET_AUTH_TOKEN")

# Allowed CORS origins - comma-separated list
# Default: localhost for development
# Production: Set to your deployed frontend URL(s)
# Example: ALLOWED_ORIGINS=https://myapp.com,https://www.myapp.com
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://0.0.0.0:5173"
)

# Council members - list of OpenRouter model identifiers
# NOTE: These are fallback values. Primary defaults are in backend/models.py
# and can be configured per-conversation through the UI.
COUNCIL_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3-30b-a3b-thinking-2507",
    "qwen/qwen3-235b-a22b-thinking-2507",
]

# Chairman model - synthesizes final response
# NOTE: This is a fallback value. Primary default is in backend/models.py
# and can be configured per-conversation through the UI.
CHAIRMAN_MODEL = "openai/gpt-5-mini"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
