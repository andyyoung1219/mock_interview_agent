
import tempfile
import unittest
from pathlib import Path

from src.agent.graph import decide_action
from src.storage.sqlite_store import (
    SQLiteStore,
    SessionConflict,
)
from src.tools.document import parse_document


class TestAgentDecision(unittest.TestCase):

    def make_state(self, **changes):
        state = {
            "topic": "專題技術原理",
            "question": "為什麼選擇 RT-DETR？",
            "latest_answer": "因為 Transformer。",
            "answer_history": [],
            "followup_count": 0,
            "max_followups": 1,
            "topic_index": 0,
            "max_topics": 2,
            "suggestion": "FOLLOW_UP",
            "decision_reason": "缺少選型依據",
        }
        state.update(changes)
        return state

    def test_followup(self):
        result = decide_action(self.make_state())
        self.assertEqual(result["decision"], "FOLLOW_UP")
        self.assertEqual(len(result["answer_history"]), 1)

    def test_followup_limit(self):
        state = self.make_state(followup_count=1)
        result = decide_action(state)
        self.assertEqual(result["decision"], "NEXT_TOPIC")

    def test_finish(self):
        state = self.make_state(
            topic_index=1,
            followup_count=1,
        )
        result = decide_action(state)
        self.assertEqual(result["decision"], "FINISH")


class TestSQLite(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        db_path = Path(self.temp.name) / "test.db"
        self.store = SQLiteStore(db_path)
        self.db_path = db_path

        self.state = {
            "interview_type": "graduate",
            "difficulty": "medium",
            "status": "active",
            "answer_history": [],
            "question": "第一題",
        }

        self.store.create_session("test-session", self.state)

    def test_create_and_reload(self):
        new_store = SQLiteStore(self.db_path)
        result = new_store.load_session("test-session")

        self.assertIsNotNone(result)
        self.assertEqual(result["state"]["question"], "第一題")

    def test_update_and_submission(self):
        new_state = {
            **self.state,
            "question": "第二題",
            "answer_history": [{
                "topic": "專題技術原理",
                "question": "第一題",
                "answer": "測試回答",
                "decision": "NEXT_TOPIC",
                "reason": "回答完整",
            }],
        }

        response = {
            "status": "active",
            "question": "第二題",
            "decision": "NEXT_TOPIC",
        }

        self.store.update_session(
            "test-session",
            new_state,
            1,
            "submission-001",
            response,
        )

        loaded = self.store.load_session("test-session")

        self.assertEqual(loaded["version"], 2)
        self.assertEqual(
            len(self.store.get_turns("test-session")), 1
        )
        self.assertEqual(
            self.store.get_submission_response(
                "test-session", "submission-001"
            ),
            response,
        )

    def test_version_conflict(self):
        self.store.update_session(
            "test-session", self.state, 1
        )

        with self.assertRaises(SessionConflict):
            self.store.update_session(
                "test-session", self.state, 1
            )

    def test_summary_persistence(self):
        finished = {**self.state, "status": "finished"}

        self.store.update_session(
            "test-session", finished, 1
        )

        report = {
            "overview": "回答有基本概念",
            "strengths": [],
            "improvements": [],
            "suggestions": ["補充具體數據"],
        }

        self.store.save_summary("test-session", report)

        new_store = SQLiteStore(self.db_path)
        self.assertEqual(
            new_store.get_summary("test-session"),
            report,
        )


class TestDocument(unittest.TestCase):

    def test_unsupported_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.txt"
            path.write_text("hello", encoding="utf-8")

            result = parse_document(str(path))

            self.assertFalse(result["ok"])
            self.assertEqual(
                result["error_code"],
                "UNSUPPORTED_FORMAT",
            )


if __name__ == "__main__":
    unittest.main()
