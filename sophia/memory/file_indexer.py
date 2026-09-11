"""
Filesystem Deep Indexer & Search Engine
Continuously indexes user files, extracts metadata and text, and provides
instant full-text search (SQLite FTS5) across documents, code, and media.
"""

import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from sophia.config import CACHE_DIR

logger = logging.getLogger("SophiaFileIndexer")

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".swift", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".html", ".css", ".sh", ".zsh",
    ".c", ".cpp", ".h", ".rs", ".go", ".sql", ".env"
}


class FileIndexer:
    """Indexes and queries files across macOS directories."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (CACHE_DIR / "file_index.db")
        self._init_db()

    def _init_db(self):
        """Initializes SQLite tables with FTS5 full-text indexing."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    extension TEXT,
                    size_bytes INTEGER,
                    mtime REAL,
                    content_preview TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    path UNINDEXED,
                    filename,
                    content_preview
                )
            """)
            conn.commit()

    def index_file(self, file_path: Path) -> bool:
        """Indexes a single file into SQLite and FTS."""
        try:
            stat = file_path.stat()
            ext = file_path.suffix.lower()
            preview = ""

            if ext in TEXT_EXTENSIONS and stat.st_size < 2_000_000:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        preview = f.read(10_000)
                except Exception:
                    pass

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO files (path, filename, extension, size_bytes, mtime, content_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (str(file_path), file_path.name, ext, stat.st_size, stat.st_mtime, preview))

                conn.execute("DELETE FROM files_fts WHERE path = ?", (str(file_path),))
                if preview:
                    conn.execute("""
                        INSERT INTO files_fts (path, filename, content_preview)
                        VALUES (?, ?, ?)
                    """, (str(file_path), file_path.name, preview))

                conn.commit()
            return True
        except Exception as e:
            logger.debug("Failed to index %s: %s", file_path, e)
            return False

    async def scan_directory(self, root_dir: Path, max_files: int = 5000):
        """Asynchronously scans and indexes a directory tree."""
        logger.info("Scanning directory: %s", root_dir)
        count = 0
        loop = asyncio.get_running_loop()

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Skip hidden and cache folders
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", ".git", ".build", "__pycache__", "venv", ".venv")]

            for filename in filenames:
                if filename.startswith("."):
                    continue
                file_path = Path(dirpath) / filename
                await loop.run_in_executor(None, self.index_file, file_path)
                count += 1
                if count >= max_files:
                    logger.info("Reached file limit (%d) for scan.", max_files)
                    return count
        logger.info("Indexed %d files in %s", count, root_dir)
        return count

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Performs full-text search over indexed file contents and filenames."""
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # FTS search first
            try:
                cursor.execute("""
                    SELECT f.path, f.filename, f.extension, f.size_bytes, f.content_preview
                    FROM files_fts s
                    JOIN files f ON s.path = f.path
                    WHERE files_fts MATCH ?
                    LIMIT ?
                """, (query, limit))
                rows = cursor.fetchall()
            except Exception:
                rows = []

            # Fallback to LIKE if FTS had syntax or returned 0
            if not rows:
                pattern = f"%{query}%"
                cursor.execute("""
                    SELECT path, filename, extension, size_bytes, content_preview
                    FROM files
                    WHERE filename LIKE ? OR content_preview LIKE ?
                    LIMIT ?
                """, (pattern, pattern, limit))
                rows = cursor.fetchall()

            for row in rows:
                results.append({
                    "path": row[0],
                    "filename": row[1],
                    "extension": row[2],
                    "size_bytes": row[3],
                    "preview": (row[4] or "")[:300],
                })
        return results


# Singleton instance
file_indexer = FileIndexer()
