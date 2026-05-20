"""Tests for NovaPilot chat engine and history."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.chat.history import ChatHistory
from novapilot.chat.engine import ChatEngine, SYSTEM_PROMPTS


class TestChatHistory(unittest.TestCase):
    """Test cases for ChatHistory."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.history = ChatHistory(history_dir=self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_session(self):
        """Test creating a new session."""
        session_id = self.history.create_session("Test Session")
        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, str)
        self.assertEqual(self.history.get_current_session_id(), session_id)

    def test_add_message(self):
        """Test adding messages to a session."""
        self.history.create_session("Test")
        msg = self.history.add_message("user", "Hello")
        self.assertIn("role", msg)
        self.assertEqual(msg["role"], "user")
        self.assertEqual(msg["content"], "Hello")
        self.assertIn("timestamp", msg)

    def test_get_messages(self):
        """Test retrieving messages from a session."""
        self.history.create_session("Test")
        self.history.add_message("user", "Hello")
        self.history.add_message("assistant", "Hi there!")

        messages = self.history.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

    def test_get_messages_with_limit(self):
        """Test retrieving messages with a limit."""
        self.history.create_session("Test")
        for i in range(10):
            self.history.add_message("user", f"Message {i}")

        messages = self.history.get_messages(limit=3)
        self.assertEqual(len(messages), 3)

    def test_list_sessions(self):
        """Test listing sessions."""
        self.history.create_session("Session 1")
        self.history.create_session("Session 2")

        sessions = self.history.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_search_sessions(self):
        """Test searching sessions by content."""
        self.history.create_session("Python Help")
        self.history.add_message("user", "How to use list comprehension in Python")
        self.history.add_message("assistant", "Use [x for x in iterable]")

        results = self.history.search_sessions("Python")
        self.assertGreater(len(results), 0)

    def test_delete_session(self):
        """Test deleting a session."""
        session_id = self.history.create_session("To Delete")
        self.history.add_message("user", "Test")

        result = self.history.delete_session(session_id)
        self.assertTrue(result)

        sessions = self.history.list_sessions()
        self.assertEqual(len(sessions), 0)

    def test_clear_all(self):
        """Test clearing all sessions."""
        self.history.create_session("S1")
        self.history.create_session("S2")

        count = self.history.clear_all()
        self.assertEqual(count, 2)
        self.assertEqual(len(self.history.list_sessions()), 0)

    def test_export_session_markdown(self):
        """Test exporting a session as Markdown."""
        self.history.create_session("Export Test")
        self.history.add_message("user", "Hello")
        self.history.add_message("assistant", "Hi!")

        session_id = self.history.get_current_session_id()
        exported = self.history.export_session(session_id, "markdown")
        self.assertIn("Export Test", exported)
        self.assertIn("Hello", exported)
        self.assertIn("Hi!", exported)

    def test_export_session_json(self):
        """Test exporting a session as JSON."""
        self.history.create_session("Export Test")
        self.history.add_message("user", "Hello")

        session_id = self.history.get_current_session_id()
        exported = self.history.export_session(session_id, "json")
        import json
        data = json.loads(exported)
        self.assertIn("messages", data)

    def test_session_stats(self):
        """Test getting session statistics."""
        self.history.create_session("Stats Test")
        self.history.add_message("user", "Hello")

        stats = self.history.get_session_stats()
        self.assertEqual(stats["total_sessions"], 1)
        self.assertEqual(stats["total_messages"], 1)


class TestChatEngine(unittest.TestCase):
    """Test cases for ChatEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        from novapilot.config import ConfigManager
        config_path = os.path.join(self.temp_dir, "test_config.json")
        self.config = ConfigManager(config_path=config_path)
        self.config.set_backend_config("ollama", enabled=True)

        from novapilot.llm.router import LLMRouter
        self.router = LLMRouter(self.config)
        self.engine = ChatEngine(
            llm_router=self.router,
            config_manager=self.config,
        )

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test engine initializes properly."""
        self.assertIsNotNone(self.engine.system_prompt)
        self.assertGreater(self.engine.max_context_messages, 0)

    def test_set_system_prompt(self):
        """Test setting system prompt by template name."""
        self.engine.set_system_prompt("coder")
        self.assertIn("programmer", self.engine.system_prompt)

    def test_set_custom_system_prompt(self):
        """Test setting a custom system prompt."""
        custom = "You are a helpful cat."
        self.engine.set_system_prompt(custom)
        self.assertEqual(self.engine.system_prompt, custom)

    def test_new_session(self):
        """Test creating a new session."""
        session_id = self.engine.new_session("Test")
        self.assertIsNotNone(session_id)

    def test_register_tool(self):
        """Test registering a tool."""
        mock_tool = MagicMock()
        self.engine.register_tool("test_tool", mock_tool)
        tools = self.engine.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertTrue(tools[0]["enabled"])

    def test_enable_disable_tool(self):
        """Test enabling and disabling tools."""
        mock_tool = MagicMock()
        self.engine.register_tool("test_tool", mock_tool)

        self.engine.enable_tool("test_tool", False)
        tools = self.engine.list_tools()
        self.assertFalse(tools[0]["enabled"])

        self.engine.enable_tool("test_tool", True)
        tools = self.engine.list_tools()
        self.assertTrue(tools[0]["enabled"])

    def test_get_stats(self):
        """Test getting engine statistics."""
        stats = self.engine.get_stats()
        self.assertIn("session_id", stats)
        self.assertIn("message_count", stats)
        self.assertIn("tools_registered", stats)

    def test_context_building(self):
        """Test context window building."""
        self.engine.new_session()
        for i in range(5):
            self.engine._messages.append({
                "role": "user",
                "content": f"Message {i}",
            })

        context = self.engine._build_context(max_messages=3)
        self.assertEqual(len(context), 3)


if __name__ == "__main__":
    unittest.main()
