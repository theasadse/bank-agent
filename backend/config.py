import os
from pathlib import Path
from dotenv import load_dotenv

# Base directories
BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

# Load .env from root and backend directory
load_dotenv(BASE_DIR / ".env", override=True)
load_dotenv(BACKEND_DIR / ".env", override=True)

# Server configuration
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "127.0.0.1")

# Storage paths
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
UPLOADS_DIR = DATA_DIR / "uploads"
SAMPLE_DATA_DIR = BASE_DIR / "backend" / "sample_data"

# Vector Store & Embedding Model
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CHROMA_COLLECTION_NAME = "bank_soc_documents"

# LLM Providers Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_DEFAULT_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "openai/gpt-oss-120b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_DEFAULT_MODEL = os.getenv("GEMINI_DEFAULT_MODEL", "gemini-1.5-flash")

# Default tax rates for calculations
DEFAULT_FED_RATE = 16.0  # 16% Federal Excise Duty / Provincial Sales Tax
DEFAULT_FILER_WHT = 0.6  # 0.6% Withholding Tax for cash withdrawals > threshold
DEFAULT_NON_FILER_WHT = 1.2 # 1.2% Withholding Tax for Non-Filers
DEFAULT_INTL_MARKUP = 3.5 # 3.5% Foreign transaction markup

# Create necessary directories
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
SAMPLE_DATA_DIR.mkdir(exist_ok=True)
