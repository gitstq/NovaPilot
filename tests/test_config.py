"""Tests for NovaPilot configuration management."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager."""

    def setUp(self):
        """Set up test fixtures with a temporary config file."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.config = ConfigManager(config_path=self.config_path)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization_creates_default_config(self):
        """Test that initialization creates a default config file."""
        self.assertTrue(os.path.exists(self.config_path))

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("backends", data)
        self.assertIn("openai", data["backends"])
        self.assertIn("anthropic", data["backends"])
        self.assertIn("ollama", data["backends"])

    def test_default_backend(self):
        """Test getting and setting the default backend."""
        self.assertEqual(self.config.default_backend, "openai")

        self.config.default_backend = "anthropic"
        self.assertEqual(self.config.default_backend, "anthropic")

    def test_set_invalid_default_backend(self):
        """Test that setting an invalid default backend raises ValueError."""
        with self.assertRaises(ValueError):
            self.config.default_backend = "nonexistent"

    def test_get_backend(self):
        """Test getting a specific backend configuration."""
        openai = self.config.get_backend("openai")
        self.assertIsNotNone(openai)
        self.assertEqual(openai["type"], "openai")
        self.assertEqual(openai["model"], "gpt-3.5-turbo")

    def test_get_nonexistent_backend(self):
        """Test getting a nonexistent backend returns None."""
        result = self.config.get_backend("nonexistent")
        self.assertIsNone(result)

    def test_list_backends(self):
        """Test listing all configured backends."""
        backends = self.config.list_backends()
        self.assertIsInstance(backends, list)
        self.assertGreaterEqual(len(backends), 3)

        names = [b["name"] for b in backends]
        self.assertIn("openai", names)
        self.assertIn("anthropic", names)
        self.assertIn("ollama", names)

    def test_add_backend(self):
        """Test adding a new backend."""
        self.config.add_backend(
            "custom",
            "openai",
            api_key="test-key",
            model="gpt-4",
        )

        backend = self.config.get_backend("custom")
        self.assertIsNotNone(backend)
        self.assertEqual(backend["type"], "openai")
        self.assertEqual(backend["api_key"], "test-key")
        self.assertEqual(backend["model"], "gpt-4")

    def test_add_backend_invalid_type(self):
        """Test that adding a backend with invalid type raises ValueError."""
        with self.assertRaises(ValueError):
            self.config.add_backend("bad", "invalid_type")

    def test_remove_backend(self):
        """Test removing a backend."""
        self.config.add_backend("temp", "ollama")
        self.assertIsNotNone(self.config.get_backend("temp"))

        self.config.remove_backend("temp")
        self.assertIsNone(self.config.get_backend("temp"))

    def test_remove_last_backend_raises(self):
        """Test that removing the last backend raises ValueError."""
        # Remove all but one
        for name in ["anthropic", "ollama"]:
            self.config.remove_backend(name)

        with self.assertRaises(ValueError):
            self.config.remove_backend("openai")

    def test_set_backend_config(self):
        """Test updating backend configuration fields."""
        self.config.set_backend_config("openai", model="gpt-4", temperature=0.5)

        backend = self.config.get_backend("openai")
        self.assertEqual(backend["model"], "gpt-4")
        self.assertEqual(backend["temperature"], 0.5)

    def test_tool_management(self):
        """Test tool enable/disable functionality."""
        self.config.set_tool_enabled("calculator", False)
        tool_config = self.config.get_tool_config("calculator")
        self.assertFalse(tool_config["enabled"])

        self.config.set_tool_enabled("calculator", True)
        tool_config = self.config.get_tool_config("calculator")
        self.assertTrue(tool_config["enabled"])

    def test_list_tools(self):
        """Test listing all tools."""
        tools = self.config.list_tools()
        self.assertIn("code_analyzer", tools)
        self.assertIn("file_manager", tools)
        self.assertIn("web_search", tools)
        self.assertIn("calculator", tools)

    def test_chat_config(self):
        """Test getting and setting chat configuration."""
        chat_config = self.config.get_chat_config()
        self.assertIn("system_prompt", chat_config)
        self.assertIn("max_context_messages", chat_config)

        self.config.set_chat_config(system_prompt="Custom prompt")
        updated = self.config.get_chat_config()
        self.assertEqual(updated["system_prompt"], "Custom prompt")

    def test_export_config(self):
        """Test exporting configuration as JSON string."""
        exported = self.config.export_config()
        data = json.loads(exported)
        self.assertIsInstance(data, dict)
        self.assertIn("backends", data)

    def test_reset_config(self):
        """Test resetting configuration to defaults."""
        self.config.set_backend_config("openai", model="gpt-4")
        self.config.reset()

        backend = self.config.get_backend("openai")
        self.assertEqual(backend["model"], "gpt-3.5-turbo")

    def test_merge_with_user_config(self):
        """Test that user config is properly merged with defaults."""
        # Write a partial user config
        user_config = {"version": "0.0.1", "default_backend": "ollama"}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(user_config, f)

        # Reload
        config = ConfigManager(config_path=self.config_path)
        self.assertEqual(config.default_backend, "ollama")
        # Should still have all default backends
        self.assertIsNotNone(config.get_backend("openai"))


if __name__ == "__main__":
    unittest.main()
