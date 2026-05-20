"""Tests for NovaPilot LLM router."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.config import ConfigManager
from novapilot.llm.base import LLMBackend, LLMError
from novapilot.llm.router import LLMRouter


class TestLLMBackend(unittest.TestCase):
    """Test cases for LLMBackend base class."""

    def _make_concrete_backend(self, **config):
        """Create a concrete LLMBackend subclass for testing."""
        class ConcreteBackend(LLMBackend):
            def complete(self, prompt, system_prompt=None, temperature=None,
                         max_tokens=None, **kwargs):
                return {"content": "test", "usage": {}, "model": "test"}

            def stream(self, prompt, system_prompt=None, temperature=None,
                       max_tokens=None, **kwargs):
                yield "test"

        return ConcreteBackend(name="test", config=config)

    def test_estimate_tokens_english(self):
        """Test token estimation for English text."""
        text = "Hello, world! This is a test."
        tokens = LLMBackend.estimate_tokens(text)
        self.assertGreater(tokens, 0)
        # Should be roughly text_length / 4
        self.assertLess(tokens, len(text))

    def test_estimate_tokens_cjk(self):
        """Test token estimation for CJK text."""
        text = "你好世界"
        tokens = LLMBackend.estimate_tokens(text)
        self.assertGreater(tokens, 0)

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty text."""
        self.assertEqual(LLMBackend.estimate_tokens(""), 0)

    def test_get_temperature(self):
        """Test temperature value handling."""
        backend = self._make_concrete_backend(temperature=0.5)
        self.assertEqual(backend._get_temperature(None), 0.5)
        self.assertEqual(backend._get_temperature(0.9), 0.9)
        # Should clamp
        self.assertEqual(backend._get_temperature(-1.0), 0.0)
        self.assertEqual(backend._get_temperature(5.0), 2.0)

    def test_get_max_tokens(self):
        """Test max_tokens value handling."""
        backend = self._make_concrete_backend(max_tokens=2048)
        self.assertEqual(backend._get_max_tokens(None), 2048)
        self.assertEqual(backend._get_max_tokens(100), 100)
        # Should enforce minimum
        self.assertEqual(backend._get_max_tokens(0), 1)


class TestLLMRouter(unittest.TestCase):
    """Test cases for LLMRouter."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(self.temp_dir, "test_config.json")
        self.config = ConfigManager(config_path=config_path)
        # Enable ollama for testing (no API key needed)
        self.config.set_backend_config("ollama", enabled=True)
        self.router = LLMRouter(self.config)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test router initializes with configured backends."""
        backends = self.router.list_backends()
        self.assertGreater(len(backends), 0)

    def test_classify_task_simple_qa(self):
        """Test task classification for simple questions."""
        self.assertEqual(self.router.classify_task("What is Python?"), "simple_qa")
        self.assertEqual(self.router.classify_task("How does it work?"), "simple_qa")
        self.assertEqual(self.router.classify_task("Hello there"), "simple_qa")

    def test_classify_task_code_generation(self):
        """Test task classification for code generation."""
        self.assertEqual(
            self.router.classify_task("Write a Python function to sort a list"),
            "code_generation"
        )
        self.assertEqual(
            self.router.classify_task("Create a React component"),
            "code_generation"
        )

    def test_classify_task_long_document(self):
        """Test task classification for document analysis."""
        self.assertEqual(
            self.router.classify_task("Summarize this long document"),
            "long_document"
        )

    def test_classify_task_creative_writing(self):
        """Test task classification for creative writing."""
        self.assertEqual(
            self.router.classify_task("Write a short story about space"),
            "creative_writing"
        )

    def test_select_backend_returns_backend(self):
        """Test that select_backend returns a valid backend."""
        backend = self.router.select_backend(prompt="Hello")
        self.assertIsNotNone(backend)

    def test_select_backend_with_preferred(self):
        """Test selecting a specific backend by name."""
        backend = self.router.select_backend(preferred="ollama")
        self.assertIsNotNone(backend)
        self.assertEqual(backend.name, "ollama")

    def test_list_backends(self):
        """Test listing backends with status."""
        backends = self.router.list_backends()
        for b in backends:
            self.assertIn("name", b)
            self.assertIn("type", b)
            self.assertIn("model", b)
            self.assertIn("healthy", b)

    def test_get_backend(self):
        """Test getting a specific backend."""
        backend = self.router.get_backend("ollama")
        self.assertIsNotNone(backend)
        self.assertEqual(backend.name, "ollama")

    def test_get_nonexistent_backend(self):
        """Test getting a nonexistent backend returns None."""
        backend = self.router.get_backend("nonexistent")
        self.assertIsNone(backend)


if __name__ == "__main__":
    unittest.main()
