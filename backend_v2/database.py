import sqlite3
import json
import uuid
from datetime import datetime

DB_PATH = "cases.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id             TEXT PRIMARY KEY,
            user_id        TEXT NOT NULL DEFAULT 'default',
            crime_type     TEXT NOT NULL,
            scene_analysis TEXT NOT NULL,
            conversation   TEXT NOT NULL DEFAULT '[]',
            image_path     TEXT,
            created_at     TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'active'
        )
    """)
    # Add user_id column if it doesn't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id         TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    conn.close()


def create_session(crime_type: str, scene_analysis: dict,
                   image_path: str = None, user_id: str = "default") -> str:
    sid = str(uuid.uuid4())[:8].upper()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO sessions 
           (id, user_id, crime_type, scene_analysis, conversation, image_path, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sid,
            user_id,
            crime_type,
            json.dumps(scene_analysis),
            "[]",
            image_path,
            now,
            "active",
        ),
    )
    conn.commit()
    conn.close()
    return sid


def get_session(sid: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id":            row[0],
        "user_id":       row[1],
        "crime_type":    row[2],
        "scene_analysis": json.loads(row[3]),
        "conversation":  json.loads(row[4]),
        "image_path":    row[5],
        "created_at":    row[6],
        "status":        row[7],
    }


def add_message(sid: str, role: str, content: str):
    from datetime import datetime
    session = get_session(sid)
    if not session:
        raise ValueError(f"Session {sid} not found")
    conversation = session["conversation"]
    conversation.append({
        "role":      role,
        "content":   content,
        "timestamp": datetime.utcnow().strftime("%I:%M:%S %p"),
    })
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE sessions SET conversation = ? WHERE id = ?",
        (json.dumps(conversation), sid),
    )
    conn.commit()
    conn.close()


def complete_session(sid: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE sessions SET status = 'completed' WHERE id = ?", (sid,))
    conn.commit()
    conn.close()


def save_report(session_id: str, content: str) -> str:
    rid  = str(uuid.uuid4())[:8].upper()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO reports VALUES (?, ?, ?, ?)",
        (rid, session_id, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return rid


def list_sessions(user_id: str = "default") -> list[dict]:
    """Return sessions for a specific user only."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, crime_type, created_at, status FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "crime_type": r[1], "created_at": r[2], "status": r[3]}
        for r in rows
    ]


def delete_session(sid: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    conn.commit()
    conn.close()