# api/main.py
# FastAPI backend for AI-powered local file search

from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import application components
from config.config import API_HOST, API_PORT, WATCH_PATHS
from config.logger import get_logger

from embeddings.embedder import Embedder
from indexer.faiss_index import FAISSIndex
from indexer.bm25_index import BM25Index
from indexer.metadata import MetadataStore
from search.query_engine import QueryEngine
from watcher.crawler import Crawler
from watcher.file_watcher import FileWatcher

logger = get_logger(__name__)

# ==============================================================================
# Global State (initialized on startup)
# ==============================================================================

# Global instances for the application
embedder: Optional[Embedder] = None
faiss: Optional[FAISSIndex] = None
bm25: Optional[BM25Index] = None
metadata: Optional[MetadataStore] = None
query_engine: Optional[QueryEngine] = None
crawler: Optional[Crawler] = None
file_watcher: Optional[FileWatcher] = None


# ==============================================================================
# Pydantic Request/Response Models
# ==============================================================================


class IndexRequest(BaseModel):
    """Request model for triggering indexing."""

    paths: Optional[List[Path]] = None  # Optional list of paths to index
    recrawl: bool = Field(default=False, description="Re-crawl all files")


class IndexResponse(BaseModel):
    """Response model for indexing operation."""

    status: str
    message: str
    files_indexed: int = 0


class SearchRequest(BaseModel):
    """Request model for search."""

    query: str = Field(..., min_length=1, description="Search query")
    top_k: Optional[int] = Field(default=20, ge=1, le=100, description="Max results")
    alpha: Optional[float] = Field(
        default=0.6, ge=0.0, le=1.0, description="Semantic weight"
    )


class SearchResultModel(BaseModel):
    """Single search result."""

    path: str
    file_name: str
    snippet: str = Field(..., description="Text snippet from result")
    semantic_score: float
    keyword_score: float
    fuzzy_score: float
    recency_score: float
    final_score: float
    file_type: str


class SearchResponse(BaseModel):
    """Response model for search results."""

    query: str
    total_results: int
    results: List[SearchResultModel]


class PreviewRequest(BaseModel):
    """Request model for file preview."""

    path: str = Field(..., description="File path to preview")


class PreviewResponse(BaseModel):
    """Response model for file preview."""

    path: str
    content: str = Field(..., description="File content (truncated)")
    file_type: str
    size: int
    modified: float


class StatusResponse(BaseModel):
    """Response model for system status."""

    status: str
    index_count: int
    faiss_count: int
    bm25_count: int
    cache_stats: dict
    watch_paths: List[str]


class FilesResponse(BaseModel):
    """Response model for indexed files list."""

    files: List[dict]


# ==============================================================================
# FastAPI Application
# ==============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Initializes all components on startup and cleans up on shutdown.
    """
    global embedder, faiss, bm25, metadata, query_engine, crawler, file_watcher

    logger.info("Starting Smart Search API...")

    try:
        # Initialize embedding component
        embedder = Embedder(use_cache=True)

        # Initialize indexers
        faiss = FAISSIndex()
        bm25 = BM25Index()
        metadata = MetadataStore()

        # Initialize query engine for hybrid search
        query_engine = QueryEngine(faiss, bm25, metadata, embedder)

        # Initialize crawler for indexing files
        crawler = Crawler(embedder, faiss, bm25, metadata)

        # Initialize file watcher (but don't start yet)
        def on_file_create(path):
            logger.info(f"File created: {path}")
            crawler.index_file(path)

        def on_file_modify(path):
            logger.info(f"File modified: {path}")
            crawler.reindex_file(path)

        def on_file_delete(path):
            logger.info(f"File deleted: {path}")
            crawler.remove_file(path)

        file_watcher = FileWatcher(
            on_create=on_file_create,
            on_modify=on_file_modify,
            on_delete=on_file_delete,
            watch_paths=WATCH_PATHS,
        )

        logger.info("Smart Search API started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down Smart Search API...")
    if file_watcher:
        file_watcher.stop()


# Create FastAPI app
app = FastAPI(
    title="Smart Search API",
    description="AI-powered local file search with semantic and keyword search",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for Electron frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local Electron app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# API Endpoints
# ==============================================================================


@app.post("/index", response_model=IndexResponse)
async def index_files(request: IndexRequest):
    """
    Trigger indexing of files.

    Can index specific paths or trigger full crawl of watched directories.
    """
    try:
        files_indexed = 0

        if request.paths:
            # Index specific paths
            for path in request.paths:
                if path.exists():
                    crawler.index_file(path)
                    files_indexed += 1
        else:
            # Full crawl of watched directories
            crawler.crawl_all()
            files_indexed = faiss.get_count()

        return IndexResponse(
            status="success",
            message=f"Indexed {files_indexed} files",
            files_indexed=files_indexed,
        )

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Perform hybrid search combining semantic and keyword search.
    """
    try:
        results = query_engine.search(
            query=request.query,
            top_k=request.top_k,
            alpha=request.alpha,
        )

        # Convert results to response model
        search_results = []
        for r in results:
            # Determine file type from extension
            ext = Path(r.path).suffix.lower()

            # Truncate snippet
            snippet = r.text[:200] + "..." if len(r.text) > 200 else r.text

            search_results.append(
                SearchResultModel(
                    path=r.path,
                    file_name=r.file_name,
                    snippet=snippet,
                    semantic_score=round(r.semantic_score, 3),
                    keyword_score=round(r.keyword_score, 3),
                    fuzzy_score=round(r.fuzzy_score, 3),
                    recency_score=round(r.recency_score, 3),
                    final_score=round(r.final_score, 3),
                    file_type=ext,
                )
            )

        return SearchResponse(
            query=request.query,
            total_results=len(search_results),
            results=search_results,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/preview", response_model=PreviewResponse)
async def preview_file(request: PreviewRequest):
    """
    Get a preview of a file's content.
    """
    try:
        path = Path(request.path)

        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Get file metadata
        stat = path.stat()
        file_type = path.suffix.lower()
        size = stat.st_size
        modified = stat.st_mtime

        # Try to read content based on file type
        content = ""
        try:
            if file_type in (
                ".txt",
                ".md",
                ".py",
                ".js",
                ".ts",
                ".html",
                ".css",
                ".json",
                ".yaml",
                ".yml",
            ):
                # Read text files directly
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(5000)  # First 5000 chars
            else:
                # For other files, return a placeholder message
                content = f"[Binary file: {file_type}]"
        except Exception as e:
            content = f"[Error reading file: {e}]"

        return PreviewResponse(
            path=str(path),
            content=content,
            file_type=file_type,
            size=size,
            modified=modified,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get the current status of the search engine.
    """
    try:
        # Get cache stats
        cache_stats = embedder.get_cache_stats() if embedder else {}

        return StatusResponse(
            status="running",
            index_count=metadata.get_all_paths().__len__() if metadata else 0,
            faiss_count=faiss.get_count() if faiss else 0,
            bm25_count=len(bm25.doc_ids) if bm25 else 0,
            cache_stats=cache_stats,
            watch_paths=[str(p) for p in WATCH_PATHS],
        )

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files", response_model=FilesResponse)
async def list_files(limit: int = Query(default=100, ge=1, le=1000)):
    """
    List all indexed files.
    """
    try:
        all_paths = metadata.get_all_paths() if metadata else []

        files = []
        for path_str in all_paths[:limit]:
            path = Path(path_str)
            try:
                if path.exists():
                    stat = path.stat()
                    files.append(
                        {
                            "path": path_str,
                            "name": path.name,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        }
                    )
            except OSError:
                continue

        return FilesResponse(files=files)

    except Exception as e:
        logger.error(f"List files failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/watch/start")
async def start_watcher():
    """Start the file watcher."""
    try:
        if file_watcher:
            file_watcher.start()
            return {"status": "success", "message": "Watcher started"}
        else:
            raise HTTPException(status_code=500, detail="Watcher not initialized")
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/watch/stop")
async def stop_watcher():
    """Stop the file watcher."""
    try:
        if file_watcher:
            file_watcher.stop()
            return {"status": "success", "message": "Watcher stopped"}
        else:
            raise HTTPException(status_code=500, detail="Watcher not initialized")
    except Exception as e:
        logger.error(f"Failed to stop watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main():
    """Run the FastAPI server."""
    logger.info(f"Starting API server at {API_HOST}:{API_PORT}")

    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,  # Set to True for development
        log_level="info",
    )


if __name__ == "__main__":
    main()
