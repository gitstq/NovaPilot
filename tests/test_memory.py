"""Tests for NovaPilot memory engine and store."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.memory.store import MemoryStore
from novapilot.memory.engine import MemoryEngine


class TestMemoryStore(unittest.TestCase):
    """Test cases for MemoryStore."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.temp_dir, "test_memory.json")
        self.store = MemoryStore(store_path=self.store_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test store initializes and creates file."""
        self.assertTrue(os.path.exists(self.store_path))

    def test_add_entry(self):
        """Test adding a memory entry."""
        entry_id = self.store.add("Test memory content")
        self.assertIsNotNone(entry_id)
        self.assertIsInstance(entry_id, str)

    def test_get_entry(self):
        """Test retrieving a memory entry."""
        entry_id = self.store.add("Test content")
        entry = self.store.get(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["content"], "Test content")

    def test_get_nonexistent_entry(self):
        """Test retrieving a nonexistent entry returns None."""
        entry = self.store.get("nonexistent")
        self.assertIsNone(entry)

    def test_update_entry(self):
        """Test updating a memory entry."""
        entry_id = self.store.add("Original content")
        result = self.store.update(entry_id, content="Updated content")
        self.assertTrue(result)

        entry = self.store.get(entry_id)
        self.assertEqual(entry["content"], "Updated content")

    def test_delete_entry(self):
        """Test deleting a memory entry."""
        entry_id = self.store.add("To be deleted")
        result = self.store.delete(entry_id)
        self.assertTrue(result)

        entry = self.store.get(entry_id)
        self.assertIsNone(entry)

    def test_search(self):
        """Test searching memory entries."""
        self.store.add("Python programming language")
        self.store.add("JavaScript web development")
        self.store.add("Python data science with pandas")

        results = self.store.search("Python")
        self.assertGreater(len(results), 0)

    def test_list_all(self):
        """Test listing all entries."""
        self.store.add("Entry 1", category="knowledge")
        self.store.add("Entry 2", category="task")
        self.store.add("Entry 3", category="knowledge")

        all_entries = self.store.list_all()
        self.assertEqual(len(all_entries), 3)

        knowledge = self.store.list_all(category="knowledge")
        self.assertEqual(len(knowledge), 2)

    def test_count(self):
        """Test counting entries."""
        self.store.add("Entry 1", category="a")
        self.store.add("Entry 2", category="a")
        self.store.add("Entry 3", category="b")

        self.assertEqual(self.store.count(), 3)
        self.assertEqual(self.store.count("a"), 2)

    def test_clear(self):
        """Test clearing entries."""
        self.store.add("Entry 1", category="a")
        self.store.add("Entry 2", category="b")

        count = self.store.clear(category="a")
        self.assertEqual(count, 1)
        self.assertEqual(self.store.count(), 1)

    def test_clear_all(self):
        """Test clearing all entries."""
        self.store.add("Entry 1")
        self.store.add("Entry 2")

        count = self.store.clear()
        self.assertEqual(count, 2)
        self.assertEqual(self.store.count(), 0)

    def test_export_import_json(self):
        """Test exporting and importing JSON data."""
        self.store.add("Memory 1", tags=["tag1"])
        self.store.add("Memory 2", tags=["tag2"])

        exported = self.store.export_data("json")
        self.assertIn("Memory 1", exported)

        # Create new store and import
        new_path = os.path.join(self.temp_dir, "new_memory.json")
        new_store = MemoryStore(store_path=new_path)
        count = new_store.import_data(exported, "json")
        self.assertEqual(count, 2)

    def test_export_jsonl(self):
        """Test exporting as JSONL format."""
        self.store.add("Memory 1")
        exported = self.store.export_data("jsonl")
        lines = exported.strip().split("\n")
        self.assertEqual(len(lines), 1)

    def test_get_stats(self):
        """Test getting store statistics."""
        self.store.add("Entry 1", category="knowledge")
        stats = self.store.get_stats()
        self.assertEqual(stats["total_entries"], 1)
        self.assertIn("knowledge", stats["categories"])


class TestMemoryEngine(unittest.TestCase):
    """Test cases for MemoryEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        store_path = os.path.join(self.temp_dir, "test_memory.json")
        self.store = MemoryStore(store_path=store_path)
        self.engine = MemoryEngine(store=self.store)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_remember(self):
        """Test storing a memory."""
        entry_id = self.engine.remember("Python is a programming language")
        self.assertIsNotNone(entry_id)

    def test_recall(self):
        """Test recalling memories with semantic search."""
        self.engine.remember("Python is a popular programming language")
        self.engine.remember("JavaScript is used for web development")
        self.engine.remember("Machine learning uses neural networks")

        results = self.engine.recall("programming language", top_k=2)
        self.assertGreater(len(results), 0)
        # First result should be about Python (programming language)
        self.assertIn("Python", results[0]["entry"]["content"])

    def test_recall_with_category(self):
        """Test recalling memories filtered by category."""
        self.engine.remember("Buy groceries", category="task")
        self.engine.remember("Python lists are mutable", category="knowledge")

        results = self.engine.recall("Python", category="knowledge")
        for r in results:
            self.assertEqual(r["entry"]["category"], "knowledge")

    def test_forget(self):
        """Test deleting a memory."""
        entry_id = self.engine.remember("To be forgotten")
        result = self.engine.forget(entry_id)
        self.assertTrue(result)

    def test_classify_content(self):
        """Test automatic content classification."""
        task_id = self.engine.remember("Remember to buy milk tomorrow")
        task_entry = self.store.get(task_id)
        self.assertEqual(task_entry["category"], "task")

        knowledge_id = self.engine.remember("The speed of light is 299792458 m/s")
        knowledge_entry = self.store.get(knowledge_id)
        self.assertEqual(knowledge_entry["category"], "knowledge")

    def test_extract_keywords(self):
        """Test keyword extraction."""
        keywords = self.engine._extract_keywords(
            "Python programming language with list comprehension",
            top_n=3,
        )
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        vec_a = {"python": 0.5, "language": 0.3}
        vec_b = {"python": 0.4, "code": 0.2}
        vec_c = {"java": 0.5, "spring": 0.3}

        sim_ab = self.engine._cosine_similarity(vec_a, vec_b)
        sim_ac = self.engine._cosine_similarity(vec_a, vec_c)

        # A and B share "python", A and C share nothing
        self.assertGreater(sim_ab, sim_ac)
        self.assertGreater(sim_ab, 0)

    def test_list_memories(self):
        """Test listing memories."""
        self.engine.remember("Memory 1")
        self.engine.remember("Memory 2")
        memories = self.engine.list_memories()
        self.assertEqual(len(memories), 2)

    def test_export_memories(self):
        """Test exporting memories."""
        self.engine.remember("Test memory")
        exported = self.engine.export_memories("json")
        self.assertIn("Test memory", exported)

    def test_get_stats(self):
        """Test getting engine statistics."""
        self.engine.remember("Test")
        stats = self.engine.get_stats()
        self.assertEqual(stats["total_entries"], 1)


if __name__ == "__main__":
    unittest.main()
