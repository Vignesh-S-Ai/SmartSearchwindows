# config/config.py
# Phase 1: Project Structure & Configuration
# This file defines all configuration settings for the AI-powered local file search engine.
# It uses pathlib.Path for all paths, loads environment variables, and creates necessary directories.

# Import required standard library modules
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# This allows users to set configuration via environment variables
load_dotenv()

# ==============================================================================
# Directory Configuration
# ==============================================================================
# BASE_DIR is the root directory of the project (parent of config directory)
BASE_DIR = Path(__file__).resolve().parent.parent

# DATA_DIR stores persistent data: indexes, database, cache
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# LOG_DIR stores application logs
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# CACHE_DIR stores temporary cache files
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# Gemini API Configuration
# ==============================================================================
# GEMINI_API_KEY: Read from environment variable for security
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# GEMINI_MODEL: The embedding model to use for semantic search
GEMINI_MODEL = "models/gemini-embedding-001"

# EMBEDDING_DIM: Dimension of the embedding vector (3072 for gemini-embedding-001)
EMBEDDING_DIM = 3072

# EMBED_BATCH_SIZE: Number of documents to process in each embedding batch
EMBED_BATCH_SIZE = 32

# EMBED_MAX_RETRIES: Maximum number of retry attempts for API calls
EMBED_MAX_RETRIES = 3

# EMBED_RETRY_DELAY: Delay in seconds between retry attempts
EMBED_RETRY_DELAY = 2.0

# ==============================================================================
# File Watching Configuration
# ==============================================================================
# DEFAULT_WATCH_PATHS: Default directories to monitor for file changes
DEFAULT_WATCH_PATHS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
]

# WATCH_PATHS: Directories to watch, read from environment variable (semicolon-separated for Windows)
# Fall back to DEFAULT_WATCH_PATHS if not set in environment
_watch_paths_env = os.getenv("WATCH_PATHS", "")
if _watch_paths_env.strip():
    # Parse semicolon-separated paths from environment
    WATCH_PATHS = [Path(p.strip()) for p in _watch_paths_env.split(";") if p.strip()]
else:
    WATCH_PATHS = DEFAULT_WATCH_PATHS

# ==============================================================================
# File Type Filtering Configuration
# ==============================================================================
# SUPPORTED_EXTENSIONS: Set of file extensions to index (text and binary formats)
SUPPORTED_EXTENSIONS = {
    # Documents
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".xlsx",
    ".csv",
    # Code - Python
    ".py",
    # Code - JavaScript/TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    # Code - Java
    ".java",
    # Code - C/C++
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cc",
    ".cxx",
    # Code - C#/.NET
    ".cs",
    # Code - Go
    ".go",
    # Code - Rust
    ".rs",
    # Code - Ruby
    ".rb",
    # Code - PHP
    ".php",
    # Code - Swift
    ".swift",
    # Code - Kotlin
    ".kt",
    ".kts",
    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    # Data formats
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".toml",
    # Config
    ".ini",
    ".cfg",
    ".conf",
    # Shell/ Scripts
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".ps1",
    ".cmd",
    # Other
    ".log",
    ".sql",
    # Images (metadata only)
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
}

# IGNORE_DIRS: Directory names to skip during indexing (common non-relevant dirs)
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "$RECYCLE.BIN",
}

# ==============================================================================
# Text Chunking Configuration
# ==============================================================================
# CHUNK_SIZE: Maximum number of characters per text chunk when splitting documents
CHUNK_SIZE = 512

# CHUNK_OVERLAP: Number of overlapping characters between consecutive chunks
CHUNK_OVERLAP = 64

# ==============================================================================
# Index and Storage Paths
# ==============================================================================
# FAISS_INDEX_PATH: Path to the FAISS vector index file (for semantic search)
FAISS_INDEX_PATH = DATA_DIR / "faiss_index.bin"

# FAISS_META_PATH: Path to the FAISS metadata file (stores chunk info)
FAISS_META_PATH = DATA_DIR / "faiss_meta.json"

# BM25_INDEX_PATH: Path to the BM25 index file (for keyword search)
BM25_INDEX_PATH = DATA_DIR / "bm25_index.pkl"

# SQLITE_PATH: Path to the SQLite database (stores file metadata)
SQLITE_PATH = DATA_DIR / "file_index.db"

# SQLITE_TIMEOUT: Timeout in seconds for SQLite database operations
SQLITE_TIMEOUT = 30

# ==============================================================================
# Search Ranking Configuration
# ==============================================================================
# ALPHA: Weight for semantic search vs keyword search (0.6 = 60% semantic, 40% keyword)
ALPHA = 0.6

# RECENCY_BOOST: Additional weight given to recently modified files
RECENCY_BOOST = 0.1

# TOP_K: Number of top results to return from search
TOP_K = 20

# ==============================================================================
# API Server Configuration
# ==============================================================================
# API_HOST: Host address for the API server
API_HOST = "127.0.0.1"

# API_PORT: Port number for the API server
API_PORT = 8765

# ==============================================================================
# Logging Configuration
# ==============================================================================
# LOG_LEVEL: Logging level from environment variable, default to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# LOG_FILE: Path to the log file inside LOG_DIR
LOG_FILE = LOG_DIR / "app.log"
