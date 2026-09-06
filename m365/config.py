from pathlib import Path
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")

TOKEN_CACHE_FILE = PROJECT_ROOT / "token_cache.bin"

if not TENANT_ID:
    raise ValueError("TENANT_ID was not found in the .env file.")

if not CLIENT_ID:
    raise ValueError("CLIENT_ID was not found in the .env file.")

