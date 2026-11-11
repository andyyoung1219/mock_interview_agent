import tempfile
import unittest
from pathlib import Path
from src.storage.sqlite_store import SQLiteStore, SessionConflict


class SQLiteStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "interviews.db"
        self.store = SQLiteStore(self.db_path)
        self.state = {
            "interview_type": "graduate",
            "difficulty": "medium",
            "status": "active",
            "topic": "專題技術原理",
            "question": "為何選擇 RT-DETR？",
            "answer_history": [],
            "document_chunks": [{"doc_id": "resume.pdf", "source": "p1", "text": "測試文件"}],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_reload_update_delete(self):
        self.assertEqual(self.store.create_session("test-123", self.state), 1)
        self.assertEqual(self.store.load_session("test-123")["version"], 1)
        self.state["answer_history"].append({
            "topic": "專題技術原理", "question": "為何選擇 RT-DETR？",
            "answer": "因為需要比較不同架構", "decision": "NEXT_TOPIC",
            "reason": "已提供比較依據"
        })
        self.state["question"] = "如何評估模型？"
        self.assertEqual(self.store.update_session("test-123", self.state, 1), 2)
        # 重建 store，模擬重啟程式
        reloaded_store = SQLiteStore(self.db_path)
        loaded = reloaded_store.load_session("test-123")
        self.assertEqual(loaded["state"]["question"], "如何評估模型？")
        self.assertEqual(loaded["state"]["document_chunks"][0]["text"], "測試文件")
        self.assertEqual(len(reloaded_store.get_turns("test-123")), 1)
        self.assertEqual(len(reloaded_store.list_sessions()), 1)
        with self.assertRaises(SessionConflict):
            reloaded_store.update_session("test-123", self.state, 1)
        self.assertTrue(reloaded_store.delete_session("test-123"))
        self.assertIsNone(reloaded_store.load_session("test-123"))
        self.assertEqual(reloaded_store.get_turns("test-123"), [])


if __name__ == "__main__":
    unittest.main()
