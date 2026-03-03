"""
Job State Store
===============
SQLite-backed persistent job storage.
Replaces the old in-memory dict so jobs survive server restarts.

Also provides a backward-compatible `jobs_db` shim for minimal migration.
"""

import os
import json
import sqlite3
import asyncio
import aiosqlite
from datetime import datetime, timezone
from typing import Dict, Optional, List

# Database file path (lives next to the backend code)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs.db")


class JobStore:
    """
    Async SQLite-backed job store.
    
    Usage:
        store = JobStore()
        await store.init()
        await store.create_job("abc-123", state="queued", progress=0, ...)
        job = await store.get_job("abc-123")
        await store.update_job("abc-123", progress=50, message="Working...")
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._initialized = False

    async def init(self):
        """Create the jobs table if it doesn't exist."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    caption TEXT DEFAULT '',
                    message TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.commit()

        self._initialized = True

    async def create_job(self, job_id: str, **fields) -> dict:
        """Insert a new job record."""
        await self.init()

        now = datetime.now(timezone.utc).isoformat()
        job = {
            "job_id": job_id,
            "state": fields.get("state", "queued"),
            "progress": fields.get("progress", 0),
            "caption": fields.get("caption", ""),
            "message": fields.get("message", "Job queued."),
            "created_at": fields.get("createdAt", now),
            "updated_at": now,
        }

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO jobs 
                    (job_id, state, progress, caption, message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job["job_id"], job["state"], job["progress"],
                job["caption"], job["message"],
                job["created_at"], job["updated_at"]
            ))
            await db.commit()

        return self._to_compat_dict(job)

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID. Returns None if not found."""
        await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return self._to_compat_dict(dict(row))

    async def update_job(self, job_id: str, **fields) -> None:
        """Update specific fields of a job."""
        await self.init()

        if not fields:
            return

        # Map compatibility keys
        field_map = {
            "state": "state",
            "progress": "progress",
            "caption": "caption",
            "message": "message",
        }

        set_clauses = []
        values = []
        for key, value in fields.items():
            col = field_map.get(key, key)
            if col in ("state", "progress", "caption", "message"):
                set_clauses.append(f"{col} = ?")
                values.append(value)

        if not set_clauses:
            return

        set_clauses.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(job_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE jobs SET {', '.join(set_clauses)} WHERE job_id = ?",
                values
            )
            await db.commit()

    async def list_jobs(self) -> List[dict]:
        """List all jobs, ordered by creation time (newest first)."""
        await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._to_compat_dict(dict(row)) for row in rows]

    @staticmethod
    def _to_compat_dict(row: dict) -> dict:
        """Convert DB row to the dict format the rest of the codebase expects."""
        return {
            "state": row.get("state", "unknown"),
            "progress": row.get("progress", 0),
            "caption": row.get("caption", ""),
            "message": row.get("message", ""),
            "createdAt": row.get("created_at", ""),
        }


# =============================================
# Backward-Compatible Shim
# =============================================
# The old codebase uses `jobs_db[job_id]` as a plain dict.
# This shim provides dict-like access backed by synchronous SQLite
# so queue_manager.py changes are minimal.

class _JobsDBShim:
    """
    Dict-like wrapper around synchronous SQLite.
    Provides `jobs_db[job_id]`, `jobs_db[job_id] = {...}`, `job_id in jobs_db`, etc.
    
    NOTE: Uses synchronous sqlite3 since it's called from sync code paths.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_table()

    def _ensure_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    caption TEXT DEFAULT '',
                    message TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def __contains__(self, job_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
            )
            return cursor.fetchone() is not None

    def __getitem__(self, job_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"Job {job_id} not found")
            
            # Return a _MutableJobRow that auto-syncs changes back to DB
            return _MutableJobRow(dict(row), job_id, self.db_path)

    def __setitem__(self, job_id: str, value: dict):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs 
                    (job_id, state, progress, caption, message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                value.get("state", "queued"),
                value.get("progress", 0),
                value.get("caption", ""),
                value.get("message", ""),
                value.get("createdAt", now),
                now,
            ))
            conn.commit()

    def items(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [
                (row["job_id"], JobStore._to_compat_dict(dict(row)))
                for row in rows
            ]


class _MutableJobRow(dict):
    """
    A dict subclass that writes changes back to SQLite on __setitem__.
    This makes `jobs_db[job_id]["progress"] = 50` work transparently.
    """

    def __init__(self, row: dict, job_id: str, db_path: str):
        # Convert DB column names to compat keys
        compat = JobStore._to_compat_dict(row)
        super().__init__(compat)
        self._job_id = job_id
        self._db_path = db_path

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._sync_to_db()

    def update(self, other=None, **kwargs):
        if other:
            super().update(other)
        if kwargs:
            super().update(kwargs)
        self._sync_to_db()

    def _sync_to_db(self):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                UPDATE jobs SET 
                    state = ?, progress = ?, caption = ?, message = ?, updated_at = ?
                WHERE job_id = ?
            """, (
                self.get("state", "unknown"),
                self.get("progress", 0),
                self.get("caption", ""),
                self.get("message", ""),
                now,
                self._job_id,
            ))
            conn.commit()


# =============================================
# Global instance — drop-in replacement for the old `jobs_db: Dict = {}`
# =============================================
jobs_db = _JobsDBShim()
