# AGENTS.md

This file provides guidelines for agentic coding agents operating in this repository.

## Project Overview

AI-powered local file search engine for Windows. Uses Gemini embeddings for semantic search, BM25 for keyword search, FAISS for vector indexing, and SQLite for file metadata.

## Build/Lint/Test Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Linting (project uses ruff)
ruff check .
ruff check --fix .

# Type checking
ruff check --select=ANN .

# Running all tests
pytest

# Running a single test
pytest tests/test_filename.py::test_function_name

# Running tests with coverage
pytest --cov=src --cov-report=term-missing
```

## Code Style Guidelines

### Imports

- Use absolute imports: `from config import logger` (not `from .config import logger`)
- Group imports in order: standard library, third-party, local
- Sort within each group alphabetically
- Use `import module` for modules, `from module import Class` for classes

```python
# Correct
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from config import logger
from src.indexer import FileIndexer
```

### Formatting

- Maximum line length: 100 characters
- Use 4 spaces for indentation (no tabs)
- Use Black-style formatting: spaces around operators, after commas
- One blank line between top-level definitions

### Types

- Use type hints on all function signatures and return types
- Prefer `typing.Optional` over `None` in type annotations
- Use concrete types when possible (e.g., `list[str]` over `List[str]`)

```python
def search(query: str, top_k: int = 20) -> list[SearchResult]:
    ...
```

### Naming Conventions

- `snake_case` for variables, functions, methods
- `PascalCase` for classes, types
- `SCREAMING_SNAKE_CASE` for constants
- Prefix private members with underscore: `_private_method()`

### Error Handling

- Use specific exceptions: catch `FileNotFoundError`, not `Exception`
- Log errors before re-raising: `logger.error("Failed to read file", exc_info=True)`
- Never silently swallow exceptions without logging

```python
try:
    result = load_index(path)
except FileNotFoundError:
    logger.warning(f"Index not found at {path}, building new index")
    result = None
except PermissionError as e:
    logger.error(f"Permission denied accessing {path}", exc_info=True)
    raise
```

### Logging

- Use the logger from `config.logger`: `logger = get_logger(__name__)`
- Use appropriate log levels: DEBUG for verbose, INFO for normal, WARNING for issues, ERROR for failures
- Include context in log messages: `logger.info(f"Indexed {count} files")`

### Configuration

- All paths use `pathlib.Path` (not raw strings)
- Configuration lives in `config/config.py`
- Load secrets from environment variables via `os.getenv`
- Never hardcode paths or credentials

### Testing

- Tests go in `tests/` directory
- Name test files: `test_<module>.py`
- Name test functions: `test_<description>`
- Use fixtures for common setup
- Mock external APIs (Gemini, file system)

### Git Conventions

- Commit messages: imperative mood, 50 chars max for subject
- Branch naming: `feature/description`, `fix/description`
- No force pushes to main
- Run lint before committing

## File Structure

```
project/
├── config/           # Configuration modules
├── src/              # Main application code
├── tests/            # Test files
├── data/             # Runtime data (indexes, DB)
├── logs/             # Application logs
├── cache/            # Cache files
├── .env.example      # Environment template
└── AGENTS.md         # This file
```
