"""
SQLite Database module for persistent storage of multi-agent research sessions,
chat history, user authentication, profile settings, and 7-day free trial tracking.

Stores:
- User accounts (email, hashed password, name, avatar, 7-day free trial timestamp, Pro status)
- Research runs linked to user accounts:
  - User queries & LLM models
  - Orchestrator sub-questions
  - Worker findings & retrieved source citations
  - VeritasCore Paper Intelligence summaries
  - Final synthesized Markdown reports
  - VeritasCore Evidence DNA mappings
  - VeritasCore Claim-Level Verification Audits & Integrity Scores
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DEFAULT_DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "research_history.db")


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None):
    """Initializes the SQLite schema for users, trial tracking, and research sessions."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            # 1. Users table (Authentication, Profile & 7-Day Free Trial)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    avatar_url TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    trial_ends_at TIMESTAMP NOT NULL,
                    is_pro BOOLEAN DEFAULT 0,
                    razorpay_payment_id TEXT DEFAULT NULL
                );
            """)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);")

            # 2. Research Sessions Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER DEFAULT NULL,
                    query TEXT NOT NULL,
                    model TEXT,
                    final_report TEXT NOT NULL,
                    duration TEXT,
                    sub_questions TEXT,      -- JSON list of sub-questions
                    worker_results TEXT,     -- JSON list of worker findings
                    paper_summaries TEXT,    -- JSON list of VeritasCore paper summaries
                    evidence_dna TEXT,       -- JSON list of VeritasCore evidence DNA
                    audit_report TEXT,       -- JSON object of VeritasCore claim audit
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                );
            """)
            # Automatic Schema Migration: Ensure user_id column exists if table was previously created
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(research_sessions);")
            columns = [row[1] for row in cursor.fetchall()]
            if "user_id" not in columns:
                conn.execute("ALTER TABLE research_sessions ADD COLUMN user_id INTEGER DEFAULT NULL;")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON research_sessions(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_query ON research_sessions(query);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON research_sessions(user_id);")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# User Authentication & Profile Database Functions
# ---------------------------------------------------------------------------

def create_user(
    email: str,
    password_hash: str,
    name: str,
    avatar_url: Optional[str] = None,
    trial_days: int = 7,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers a new user account with an automatic 7-day free trial.
    Returns the user data dictionary (excluding password_hash).
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    
    clean_email = email.strip().lower()
    clean_name = name.strip() or "Researcher"
    avatar = avatar_url or ""
    
    # Compute 7-day free trial expiration timestamp
    now = datetime.utcnow()
    trial_ends_at = (now + timedelta(days=trial_days)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (
                    email, password_hash, name, avatar_url, trial_ends_at, is_pro
                ) VALUES (?, ?, ?, ?, ?, 0)
            """, (clean_email, password_hash, clean_name, avatar, trial_ends_at))
            user_id = cursor.lastrowid
            
        return {
            "id": user_id,
            "email": clean_email,
            "name": clean_name,
            "avatar_url": avatar,
            "trial_ends_at": trial_ends_at,
            "is_pro": False,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S")
        }
    finally:
        conn.close()


def get_user_by_email(email: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves full user record by email, including password_hash for verification."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    clean_email = email.strip().lower()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves user profile data by ID (excluding password_hash)."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, name, avatar_url, created_at, trial_ends_at, is_pro, razorpay_payment_id
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["is_pro"] = bool(data["is_pro"])
        return data
    finally:
        conn.close()


def update_user_profile(
    user_id: int,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Updates user display name and/or avatar picture URL."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if avatar_url is not None:
        updates.append("avatar_url = ?")
        params.append(avatar_url.strip())
        
    if not updates:
        return False
        
    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))
            return cursor.rowcount > 0
    finally:
        conn.close()


def upgrade_user_to_pro(user_id: int, payment_id: str, db_path: Optional[str] = None) -> bool:
    """Upgrades a user to Pro after a successful Razorpay payment verification."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET is_pro = 1, razorpay_payment_id = ?
                WHERE id = ?
            """, (payment_id, user_id))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_user_trial_status(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes real-time 7-day free trial status and countdown metrics.
    Returns:
    - status: 'pro' | 'trial' | 'expired'
    - is_active: bool (True if user can run queries)
    - days_left: int
    - hours_left: int
    - message: human-readable status text
    """
    if user.get("is_pro"):
        return {
            "status": "pro",
            "is_active": True,
            "is_pro": True,
            "days_left": 9999,
            "hours_left": 9999,
            "trial_ends_at": user.get("trial_ends_at"),
            "message": "Pro Member — Unlimited Access"
        }

    raw_ends = user.get("trial_ends_at")
    if not raw_ends:
        return {
            "status": "expired",
            "is_active": False,
            "is_pro": False,
            "days_left": 0,
            "hours_left": 0,
            "trial_ends_at": None,
            "message": "Trial Expired"
        }

    try:
        # Parse timestamp
        trial_end = datetime.strptime(str(raw_ends)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        trial_end = datetime.utcnow()

    now = datetime.utcnow()
    if trial_end > now:
        diff = trial_end - now
        days_left = diff.days
        hours_left = int(diff.seconds // 3600)
        return {
            "status": "trial",
            "is_active": True,
            "is_pro": False,
            "days_left": days_left,
            "hours_left": hours_left,
            "trial_ends_at": str(raw_ends),
            "message": f"{days_left}d {hours_left}h remaining on Free Trial"
        }
    else:
        return {
            "status": "expired",
            "is_active": False,
            "is_pro": False,
            "days_left": 0,
            "hours_left": 0,
            "trial_ends_at": str(raw_ends),
            "message": "7-Day Free Trial Expired — Upgrade to Pro"
        }


# ---------------------------------------------------------------------------
# Research Sessions Database Functions
# ---------------------------------------------------------------------------

def save_session(
    query: str,
    final_report: str,
    model: Optional[str] = None,
    duration: Optional[str] = None,
    sub_questions: Optional[List[str]] = None,
    worker_results: Optional[List[Dict[str, Any]]] = None,
    paper_summaries: Optional[List[Dict[str, Any]]] = None,
    evidence_dna: Optional[List[Dict[str, Any]]] = None,
    audit_report: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> int:
    """Saves a complete research session into SQLite database and returns the generated ID."""
    init_db(db_path)
    conn = get_db_connection(db_path)

    sub_q_str = json.dumps(sub_questions or [])
    workers_str = json.dumps(worker_results or [])
    papers_str = json.dumps(paper_summaries or [])
    dna_str = json.dumps(evidence_dna or [])
    audit_str = json.dumps(audit_report or {})

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO research_sessions (
                    user_id, query, model, final_report, duration,
                    sub_questions, worker_results, paper_summaries,
                    evidence_dna, audit_report, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (
                user_id,
                query,
                model or "default",
                final_report,
                duration or "00:00.0",
                sub_q_str,
                workers_str,
                papers_str,
                dna_str,
                audit_str
            ))
            return cursor.lastrowid
    finally:
        conn.close()


def get_all_sessions(
    limit: int = 50,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves session summaries for history. Filters by user_id if provided."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("""
                SELECT 
                    id, user_id, query, model, duration, created_at,
                    substr(final_report, 1, 150) AS preview,
                    length(final_report) AS report_len
                FROM research_sessions
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT 
                    id, user_id, query, model, duration, created_at,
                    substr(final_report, 1, 150) AS preview,
                    length(final_report) AS report_len
                FROM research_sessions
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "query": r["query"],
                "model": r["model"],
                "duration": r["duration"],
                "created_at": r["created_at"],
                "preview": r["preview"],
                "report_len": r["report_len"]
            })
        return results
    finally:
        conn.close()


def get_session_by_id(session_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves full session data by ID with parsed JSON structures."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM research_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "query": row["query"],
            "model": row["model"],
            "final_report": row["final_report"],
            "duration": row["duration"],
            "sub_questions": json.loads(row["sub_questions"] or "[]"),
            "worker_results": json.loads(row["worker_results"] or "[]"),
            "paper_summaries": json.loads(row["paper_summaries"] or "[]"),
            "evidence_dna": json.loads(row["evidence_dna"] or "[]"),
            "audit_report": json.loads(row["audit_report"] or "{}"),
            "created_at": row["created_at"]
        }
    finally:
        conn.close()


def delete_session(session_id: int, user_id: Optional[int] = None, db_path: Optional[str] = None) -> bool:
    """Deletes a research session. Verifies user ownership if user_id is provided."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute("DELETE FROM research_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
            else:
                cursor.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def clear_all_sessions(user_id: Optional[int] = None, db_path: Optional[str] = None) -> bool:
    """Clears session history. Clears only the user's sessions if user_id is given."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            if user_id is not None:
                conn.execute("DELETE FROM research_sessions WHERE user_id = ?", (user_id,))
            else:
                conn.execute("DELETE FROM research_sessions")
            return True
    finally:
        conn.close()


# Ensure DB is created on import
init_db()
