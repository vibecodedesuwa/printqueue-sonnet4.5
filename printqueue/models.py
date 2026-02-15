"""
SQLite models for Print Queue Manager
Handles API keys, print job metadata, email mappings, and device mappings.
"""
import sqlite3
import hashlib
import secrets
import os
import json
from datetime import datetime, timedelta
from contextlib import contextmanager


class Database:
    """SQLite database manager"""

    def __init__(self, db_path='data/printqueue.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    permissions TEXT NOT NULL DEFAULT '["read"]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    request_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS print_job_meta (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cups_job_id INTEGER,
                    submitted_via TEXT NOT NULL DEFAULT 'ipp',
                    original_filename TEXT,
                    submitted_by TEXT,
                    claimed_by TEXT,
                    claimed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS email_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS known_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cups_username TEXT NOT NULL UNIQUE,
                    authentik_username TEXT NOT NULL,
                    auto_match BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    key_hash TEXT NOT NULL,
                    window_start TIMESTAMP NOT NULL,
                    request_count INTEGER DEFAULT 1,
                    PRIMARY KEY (key_hash, window_start)
                );
            ''')

    # ─── API Key Management ────────────────────────────────────────────

    def create_api_key(self, name, owner, permissions=None):
        """Create a new API key. Returns the raw key (only shown once)."""
        if permissions is None:
            permissions = ['read']
        raw_key = f"pq_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:10]

        with self.get_connection() as conn:
            conn.execute(
                'INSERT INTO api_keys (key_hash, key_prefix, name, owner, permissions) VALUES (?, ?, ?, ?, ?)',
                (key_hash, key_prefix, name, owner, json.dumps(permissions))
            )
        return raw_key

    def validate_api_key(self, raw_key):
        """Validate an API key. Returns key info dict or None."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1',
                (key_hash,)
            ).fetchone()
            if row:
                conn.execute(
                    'UPDATE api_keys SET last_used = CURRENT_TIMESTAMP, request_count = request_count + 1 WHERE key_hash = ?',
                    (key_hash,)
                )
                return dict(row)
        return None

    def list_api_keys(self):
        """List all API keys (without hashes)."""
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT id, key_prefix, name, owner, permissions, created_at, last_used, request_count, is_active FROM api_keys ORDER BY created_at DESC'
            ).fetchall()
            return [dict(r) for r in rows]

    def revoke_api_key(self, key_id):
        """Revoke an API key by ID."""
        with self.get_connection() as conn:
            conn.execute('UPDATE api_keys SET is_active = 0 WHERE id = ?', (key_id,))

    def delete_api_key(self, key_id):
        """Delete an API key by ID."""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))

    # ─── Rate Limiting ─────────────────────────────────────────────────

    def check_rate_limit(self, raw_key, limit=100):
        """Check if API key is within rate limit. Returns (allowed, remaining)."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = datetime.utcnow()
        window_start = now.replace(second=0, microsecond=0)

        with self.get_connection() as conn:
            # Clean old entries
            conn.execute(
                'DELETE FROM rate_limits WHERE window_start < ?',
                (window_start - timedelta(minutes=1),)
            )

            row = conn.execute(
                'SELECT request_count FROM rate_limits WHERE key_hash = ? AND window_start = ?',
                (key_hash, window_start)
            ).fetchone()

            if row:
                count = row['request_count']
                if count >= limit:
                    return False, 0
                conn.execute(
                    'UPDATE rate_limits SET request_count = request_count + 1 WHERE key_hash = ? AND window_start = ?',
                    (key_hash, window_start)
                )
                return True, limit - count - 1
            else:
                conn.execute(
                    'INSERT INTO rate_limits (key_hash, window_start, request_count) VALUES (?, ?, 1)',
                    (key_hash, window_start)
                )
                return True, limit - 1

    # ─── Print Job Metadata ────────────────────────────────────────────

    def create_job_meta(self, cups_job_id, submitted_via='ipp', original_filename=None, submitted_by=None):
        """Record metadata for a print job."""
        with self.get_connection() as conn:
            conn.execute(
                'INSERT INTO print_job_meta (cups_job_id, submitted_via, original_filename, submitted_by) VALUES (?, ?, ?, ?)',
                (cups_job_id, submitted_via, original_filename, submitted_by)
            )

    def get_job_meta(self, cups_job_id):
        """Get metadata for a CUPS job."""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM print_job_meta WHERE cups_job_id = ?', (cups_job_id,)
            ).fetchone()
            return dict(row) if row else None

    def claim_job(self, cups_job_id, username):
        """Claim an unclaimed job."""
        with self.get_connection() as conn:
            # Check if already claimed
            existing = conn.execute(
                'SELECT claimed_by FROM print_job_meta WHERE cups_job_id = ?', (cups_job_id,)
            ).fetchone()

            if existing and existing['claimed_by']:
                return False, f"Job already claimed by {existing['claimed_by']}"

            if existing:
                conn.execute(
                    'UPDATE print_job_meta SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP WHERE cups_job_id = ?',
                    (username, cups_job_id)
                )
            else:
                conn.execute(
                    'INSERT INTO print_job_meta (cups_job_id, submitted_via, claimed_by, claimed_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                    (cups_job_id, 'ipp', username)
                )
            return True, "Job claimed successfully"

    def get_unclaimed_jobs(self):
        """Get list of unclaimed job IDs."""
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT cups_job_id FROM print_job_meta WHERE claimed_by IS NULL AND submitted_via = ?',
                ('ipp',)
            ).fetchall()
            return [r['cups_job_id'] for r in rows]

    def get_claimed_owner(self, cups_job_id):
        """Get the claimed owner of a job, or None."""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT claimed_by FROM print_job_meta WHERE cups_job_id = ?', (cups_job_id,)
            ).fetchone()
            return row['claimed_by'] if row else None

    # ─── Email Mappings ────────────────────────────────────────────────

    def add_email_mapping(self, email, username):
        with self.get_connection() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO email_mappings (email, username) VALUES (?, ?)',
                (email.lower(), username)
            )

    def get_email_mapping(self, email):
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT username FROM email_mappings WHERE email = ?', (email.lower(),)
            ).fetchone()
            return row['username'] if row else None

    def list_email_mappings(self):
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM email_mappings ORDER BY email').fetchall()
            return [dict(r) for r in rows]

    def delete_email_mapping(self, email):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM email_mappings WHERE email = ?', (email.lower(),))

    # ─── Known Device Mappings ─────────────────────────────────────────

    def add_known_device(self, cups_username, authentik_username, auto_match=True):
        with self.get_connection() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO known_devices (cups_username, authentik_username, auto_match) VALUES (?, ?, ?)',
                (cups_username, authentik_username, auto_match)
            )

    def get_device_mapping(self, cups_username):
        """Find Authentik username for a CUPS username."""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT authentik_username FROM known_devices WHERE cups_username = ? AND auto_match = 1',
                (cups_username,)
            ).fetchone()
            return row['authentik_username'] if row else None

    def list_known_devices(self):
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM known_devices ORDER BY cups_username').fetchall()
            return [dict(r) for r in rows]

    def delete_known_device(self, device_id):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM known_devices WHERE id = ?', (device_id,))

    # ─── Cleanup ───────────────────────────────────────────────────────

    def cleanup_expired_unclaimed(self, timeout_hours=24):
        """Cancel unclaimed jobs older than timeout."""
        cutoff = datetime.utcnow() - timedelta(hours=timeout_hours)
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT cups_job_id FROM print_job_meta WHERE claimed_by IS NULL AND submitted_via = ? AND created_at < ?',
                ('ipp', cutoff)
            ).fetchall()
            expired_ids = [r['cups_job_id'] for r in rows]
            if expired_ids:
                placeholders = ','.join('?' * len(expired_ids))
                conn.execute(
                    f'DELETE FROM print_job_meta WHERE cups_job_id IN ({placeholders})',
                    expired_ids
                )
            return expired_ids
