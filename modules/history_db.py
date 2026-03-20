"""
PaperBrief — History Database
Tracks generated videos to prevent duplicates.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
DB_PATH = OUTPUT_DIR / "history.db"

def _get_connection():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database schema."""
    with _get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_papers (
                arxiv_id TEXT PRIMARY KEY,
                title TEXT,
                category TEXT,
                status TEXT,
                output_path TEXT,
                uploaded_yt BOOLEAN DEFAULT 0,
                uploaded_fb BOOLEAN DEFAULT 0,
                uploaded_tt BOOLEAN DEFAULT 0,
                created_at DATETIME
            )
        ''')
        conn.commit()

def is_processed(arxiv_id: str) -> bool:
    """Check if an arxiv_id has already been successfully processed."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM processed_papers WHERE arxiv_id = ? AND status = 'success'",
            (arxiv_id,)
        )
        return cursor.fetchone() is not None

def record_paper(arxiv_id: str, title: str, category: str, status: str, output_path: str = ""):
    """Record a paper's processing result in the database."""
    with _get_connection() as conn:
        conn.execute(
            '''
            INSERT OR REPLACE INTO processed_papers 
            (arxiv_id, title, category, status, output_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (arxiv_id, title, category, status, output_path, datetime.utcnow())
        )
        conn.commit()

def mark_uploaded(arxiv_id: str, platform: str):
    """Mark a specific platform as uploaded for a paper."""
    column_map = {
        "youtube": "uploaded_yt",
        "facebook": "uploaded_fb",
        "tiktok": "uploaded_tt"
    }
    
    column = column_map.get(platform.lower())
    if not column:
        raise ValueError(f"Unknown platform: {platform}")
        
    with _get_connection() as conn:
        conn.execute(
            f"UPDATE processed_papers SET {column} = 1 WHERE arxiv_id = ?",
            (arxiv_id,)
        )
        conn.commit()

def get_stats() -> dict:
    """Return statistics on processed papers."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processed_papers").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM processed_papers WHERE status = 'success'").fetchone()[0]
        uploaded_yt = conn.execute("SELECT COUNT(*) FROM processed_papers WHERE uploaded_yt = 1").fetchone()[0]
        
        return {
            "total_processed": total,
            "success": success,
            "uploaded_youtube": uploaded_yt
        }

def get_processed_ids() -> set:
    """Return a set of all successfully processed arxiv_ids."""
    with _get_connection() as conn:
        cursor = conn.execute("SELECT arxiv_id FROM processed_papers WHERE status = 'success'")
        return {row[0] for row in cursor.fetchall()}

# Auto-initialize the schema when module is imported
init_db()
