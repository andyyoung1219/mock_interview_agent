"""面試 Session 與問答紀錄的 SQLite 儲存層。"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "interviews.db"


class SessionNotFound(Exception):
    """找不到指定 Session。"""


class SessionConflict(Exception):
    """Session 已經被其他請求更新。"""


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(
            db_path or os.getenv("INTERVIEW_DB_PATH", str(DEFAULT_DB_PATH))
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    interview_type TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interview_turns (
                    session_id TEXT NOT NULL,
                    turn_no INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_no),
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                ON sessions(updated_at)
            """)
            # 舊版資料庫自動升級，保留既有面試紀錄
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sessions)")
            }

            if "summary_json" not in columns:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN summary_json TEXT"
                )

    @staticmethod
    def _serialize(state: dict) -> str:
        return json.dumps(state, ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(self, session_id: str, state: dict) -> int:
        """第一次建立會話；返回初始版本號 1。"""
        now = self._now()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO sessions (
                    session_id, interview_type, difficulty, status,
                    state_json, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                session_id, state["interview_type"], state["difficulty"],
                state["status"], self._serialize(state), now, now
            ))
        return 1

    def load_session(self, session_id: str) -> dict | None:
        """載入完整 State 與版本號；不存在則回傳 None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["state"] = json.loads(result.pop("state_json"))
        return result

    def update_session(
        self, session_id: str, state: dict, expected_version: int
    ) -> int:
        """原子更新 State + 所有已回答回合；版本不符時拒絕覆寫。"""
        turns = state.get("answer_history", [])
        now = self._now()
        state_json = self._serialize(state)

        with self._connect() as conn:
            # 在讀取版本前取得寫入鎖，避免並行更新造成遺失回合。
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT version FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            if row is None:
                raise SessionNotFound(session_id)
            if row["version"] != expected_version:
                raise SessionConflict("會話已有較新的版本，請重新載入")

            conn.execute("""
                UPDATE sessions
                SET status = ?, state_json = ?, version = version + 1,
                    updated_at = ?
                WHERE session_id = ? AND version = ?
            """, (
                state["status"], state_json, now,
                session_id, expected_version
            ))

            # 問答紀錄從 State 重新同步，全部操作均在同一交易內。
            conn.execute(
                "DELETE FROM interview_turns WHERE session_id = ?",
                (session_id,)
            )
            conn.executemany("""
                INSERT INTO interview_turns (
                    session_id, turn_no, topic, question,
                    answer, decision, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    session_id, i, turn["topic"], turn["question"],
                    turn["answer"], turn["decision"], turn.get("reason", "")
                )
                for i, turn in enumerate(turns, start=1)
            ])
        return expected_version + 1

    def list_sessions(self) -> list[dict]:
        """歷史面試清單，不回傳履歷及文件內容。"""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT session_id, interview_type, difficulty, status,
                       version, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
            """).fetchall()
        return [dict(row) for row in rows]

    def get_turns(self, session_id: str) -> list[dict]:
        """依回合順序讀取面試問答。"""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT turn_no, topic, question, answer, decision, reason
                FROM interview_turns
                WHERE session_id = ?
                ORDER BY turn_no
            """, (session_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self, session_id: str) -> dict | None:
        """讀取已保存的面試摘要。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

        if row is None or row["summary_json"] is None:
            return None

        return json.loads(row["summary_json"])

    def save_summary(self, session_id: str, summary: dict) -> dict:
        """只儲存已完成面試的摘要，已存在則直接回傳。"""
        payload = self._serialize(summary)

        with self._connect() as conn:
            conn.execute("""
                UPDATE sessions
                SET summary_json = ?, updated_at = ?
                WHERE session_id = ?
                AND status = 'finished'
                AND summary_json IS NULL
            """, (payload, self._now(), session_id))

            row = conn.execute(
                "SELECT summary_json FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if row is None:
                raise SessionNotFound(session_id)

            if row["summary_json"] is None:
                raise ValueError("面試尚未完成，無法儲存摘要")

            return json.loads(row["summary_json"])

    