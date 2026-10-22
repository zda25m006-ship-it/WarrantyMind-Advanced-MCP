import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

RUNTIME_DIR = BASE_DIR / "runtime"
UPLOAD_DIR = Path(os.getenv("WM_STORAGE_DIR", str(RUNTIME_DIR / "uploads")))
DB_PATH = Path(os.getenv("WM_DB_PATH", str(RUNTIME_DIR / "warrantymind.db")))

ENABLE_OLLAMA = _env_bool("WM_ENABLE_OLLAMA", True)
OLLAMA_BASE_URL = os.getenv("WM_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
TEXT_MODEL = os.getenv("WM_TEXT_MODEL", "gemma4:e2b")
VISION_MODEL = os.getenv("WM_VISION_MODEL", "gemma4:e2b")
VISION_REQUEST_TIMEOUT = float(os.getenv("WM_VISION_REQUEST_TIMEOUT", "210"))
TEXT_REQUEST_TIMEOUT = float(os.getenv("WM_TEXT_REQUEST_TIMEOUT", "120"))
EMBED_MODEL = os.getenv("WM_EMBED_MODEL", "embeddinggemma-2:270m")
BRAVE_SEARCH_API_KEY = os.getenv("WM_BRAVE_SEARCH_API_KEY", "").strip()
BRAVE_SEARCH_BASE_URL = os.getenv("WM_BRAVE_SEARCH_BASE_URL", "https://api.search.brave.com/res/v1/web/search").strip()
RESEARCH_TIMEOUT_SECONDS = float(os.getenv("WM_RESEARCH_TIMEOUT_SECONDS", "12"))
RESEARCH_COUNTRY = os.getenv("WM_RESEARCH_COUNTRY", "IN").strip().upper()
ENVIRONMENT = os.getenv("WM_ENV", "local").strip().lower()
SECRET_KEY = os.getenv("WM_SECRET_KEY", "")
MAX_UPLOAD_BYTES = int(os.getenv("WM_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("WM_MAX_IMAGE_PIXELS", "40000000"))
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
