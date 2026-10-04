"""
Scan history - stores only the analysis RESULT per scan, never the raw
uploaded file. That keeps storage trivially small (a few hundred bytes per
row) regardless of whether someone uploaded a 100MB video, and sidesteps
privacy concerns around holding onto people's uploaded content.

Each user is capped at MAX_STORED_PER_USER rows - storage is cheap at this
size, but a cap still avoids unbounded growth over a long-running demo.
"""
import json
from datetime import datetime, timezone

from app.db import get_connection

MAX_STORED_PER_USER = 50
DEFAULT_HISTORY_LIMIT = 10


def save_scan(
    user_id: int, media_type: str, label: str, result: dict, thumbnail: str | None = None
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    sentences = result.get("sentences")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scans
                (user_id, media_type, label, ai_probability, confidence, components, risk_flags, thumbnail, sentences, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                media_type,
                label,
                result["ai_probability"],
                result["confidence"],
                json.dumps(result.get("components", {})),
                json.dumps(result.get("risk_flags", [])),
                thumbnail,
                json.dumps(sentences) if sentences is not None else None,
                now,
            ),
        )
        conn.commit()
        scan_id = cursor.lastrowid

        # Prune anything beyond the cap for this user, oldest first
        conn.execute(
            """
            DELETE FROM scans WHERE user_id = ? AND id NOT IN (
                SELECT id FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
            )
            """,
            (user_id, user_id, MAX_STORED_PER_USER),
        )
        conn.commit()

    return scan_id


def get_recent_scans(user_id: int, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]


def get_scan_by_id(user_id: int, scan_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scans WHERE id = ? AND user_id = ?",
            (scan_id, user_id),
        ).fetchone()
        return _row_to_dict(row) if row else None


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["components"] = json.loads(d["components"]) if d["components"] else {}
    d["risk_flags"] = json.loads(d["risk_flags"]) if d["risk_flags"] else []
    d["sentences"] = json.loads(d["sentences"]) if d.get("sentences") else None
    return d
