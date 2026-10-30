"""
SQLite Database module for persistent storage of multi-agent research sessions and chat history.

Stores complete research runs, including:
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
from datetime import datetime
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
    """Initializes the SQLite schema for research history sessions."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    model TEXT,
                    final_report TEXT NOT NULL,
                    duration TEXT,
                    sub_questions TEXT,      -- JSON list of sub-questions
                    worker_results TEXT,     -- JSON list of worker findings
                    paper_summaries TEXT,    -- JSON list of VeritasCore paper summaries
                    evidence_dna TEXT,       -- JSON list of VeritasCore evidence DNA
                    audit_report TEXT,       -- JSON object of VeritasCore claim audit
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON research_sessions(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_query ON research_sessions(query);")
    finally:
        conn.close()


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
                    query, model, final_report, duration,
                    sub_questions, worker_results, paper_summaries,
                    evidence_dna, audit_report, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (
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


def get_all_sessions(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves session summaries for the history sidebar."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, query, model, duration, created_at,
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


def delete_session(session_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a single research session."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def clear_all_sessions(db_path: Optional[str] = None) -> bool:
    """Clears all session history."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM research_sessions")
            return True
    finally:
        conn.close()


# Ensure DB is created on import
init_db()

