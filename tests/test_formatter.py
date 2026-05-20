"""Tests for NovaPilot formatter utility."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.utils.formatter import Formatter
from novapilot.utils.logger import Colors


class TestFormatter(unittest.TestCase):
    """Test cases for Formatter."""

    def setUp(self):
        """Set up test fixtures."""
        self.fmt = Formatter(color_enabled=False)

    def test_render_markdown_header(self):
        """Test Markdown header rendering."""
        result = self.fmt.render_markdown("# Title")
        self.assertIn("Title", result)

    def test_render_markdown_bold(self):
        """Test Markdown bold rendering."""
        result = self.fmt.render_markdown("This is **bold** text.")
        self.assertIn("bold", result)

    def test_render_markdown_italic(self):
        """Test Markdown italic rendering."""
        result = self.fmt.render_markdown("This is *italic* text.")
        self.assertIn("italic", result)

    def test_render_markdown_code_block(self):
        """Test Markdown code block rendering."""
        result = self.fmt.render_markdown("```python\nprint('hello')\n```")
        self.assertIn("print", result)
        self.assertIn("python", result)

    def test_render_markdown_inline_code(self):
        """Test Markdown inline code rendering."""
        result = self.fmt.render_markdown("Use `print()` function.")
        self.assertIn("print()", result)

    def test_render_markdown_list(self):
        """Test Markdown list rendering."""
        result = self.fmt.render_markdown("- Item 1\n- Item 2\n- Item 3")
        self.assertIn("Item 1", result)
        self.assertIn("Item 2", result)
        self.assertIn("Item 3", result)

    def test_render_markdown_blockquote(self):
        """Test Markdown blockquote rendering."""
        result = self.fmt.render_markdown("> A wise quote.")
        self.assertIn("A wise quote.", result)

    def test_render_markdown_horizontal_rule(self):
        """Test Markdown horizontal rule rendering."""
        result = self.fmt.render_markdown("---")
        self.assertGreater(len(result), 0)

    def test_render_markdown_empty(self):
        """Test rendering empty Markdown."""
        result = self.fmt.render_markdown("")
        self.assertEqual(result, "")

    def test_render_table(self):
        """Test table rendering."""
        headers = ["Name", "Age", "City"]
        rows = [
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]
        result = self.fmt.render_table(headers, rows)
        self.assertIn("Name", result)
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)

    def test_render_table_empty(self):
        """Test rendering empty table."""
        result = self.fmt.render_table([], [])
        self.assertEqual(result, "")

    def test_render_progress(self):
        """Test progress bar rendering."""
        result = self.fmt.render_progress(50, 100)
        self.assertIn("50.0%", result)

    def test_render_progress_full(self):
        """Test progress bar at 100%."""
        result = self.fmt.render_progress(100, 100)
        self.assertIn("100.0%", result)

    def test_render_progress_zero_total(self):
        """Test progress bar with zero total."""
        result = self.fmt.render_progress(0, 0)
        self.assertIn("100.0%", result)

    def test_render_tree(self):
        """Test tree structure rendering."""
        items = {
            "src": {
                "main.py": None,
                "utils": {
                    "helper.py": None,
                },
            },
            "README.md": None,
        }
        result = self.fmt.render_tree(items)
        self.assertIn("src", result)
        self.assertIn("main.py", result)
        self.assertIn("utils", result)
        self.assertIn("helper.py", result)
        self.assertIn("README.md", result)

    def test_success_message(self):
        """Test success message formatting."""
        result = self.fmt.success("Operation completed")
        self.assertIn("OK", result)
        self.assertIn("Operation completed", result)

    def test_error_message(self):
        """Test error message formatting."""
        result = self.fmt.error("Something went wrong")
        self.assertIn("ERR", result)
        self.assertIn("Something went wrong", result)

    def test_warning_message(self):
        """Test warning message formatting."""
        result = self.fmt.warning("Be careful")
        self.assertIn("WARN", result)

    def test_info_message(self):
        """Test info message formatting."""
        result = self.fmt.info("Information")
        self.assertIn("INFO", result)

    def test_bold(self):
        """Test bold text formatting."""
        result = self.fmt.bold("Bold text")
        self.assertIn("Bold text", result)

    def test_dim(self):
        """Test dim text formatting."""
        result = self.fmt.dim("Dim text")
        self.assertIn("Dim text", result)

    def test_wrap_text(self):
        """Test text wrapping."""
        long_text = "A" * 100
        result = self.fmt.wrap_text(long_text, width=20)
        lines = result.split("\n")
        for line in lines:
            self.assertLessEqual(len(line), 20)

    def test_render_key_value(self):
        """Test key-value pair rendering."""
        data = {"name": "NovaPilot", "version": "0.1.0"}
        result = self.fmt.render_key_value(data)
        self.assertIn("NovaPilot", result)
        self.assertIn("0.1.0", result)

    def test_highlight_code_python(self):
        """Test Python code highlighting."""
        code = 'def hello():\n    print("world")\n    return True'
        result = self.fmt.highlight_code(code, "python")
        self.assertIn("def", result)
        self.assertIn("print", result)

    def test_highlight_code_json(self):
        """Test JSON code highlighting."""
        code = '{"name": "test", "value": 42}'
        result = self.fmt.highlight_code(code, "json")
        self.assertIn("name", result)
        self.assertIn("test", result)

    def test_highlight_code_generic(self):
        """Test generic code highlighting."""
        code = 'some code with "strings" and # comments'
        result = self.fmt.highlight_code(code)
        self.assertIn("strings", result)

    def test_render_markdown_complex(self):
        """Test rendering complex Markdown document."""
        md = """# Document Title

## Section 1

This is a paragraph with **bold** and *italic* text.

- Item 1
- Item 2
- Item 3

```python
def greet(name):
    return f"Hello, {name}"
```

> A blockquote here.

---

## Section 2

Some `inline code` here.
"""
        result = self.fmt.render_markdown(md)
        self.assertIn("Document Title", result)
        self.assertIn("Section 1", result)
        self.assertIn("bold", result)
        self.assertIn("italic", result)
        self.assertIn("Item 1", result)
        self.assertIn("python", result)
        self.assertIn("greet", result)
        self.assertIn("blockquote", result)
        self.assertIn("inline code", result)


if __name__ == "__main__":
    unittest.main()
