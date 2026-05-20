"""Tests for NovaPilot tools."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from novapilot.tools.code_analyzer import CodeAnalyzer
from novapilot.tools.file_manager import FileManager
from novapilot.tools.calculator import Calculator


class TestCodeAnalyzer(unittest.TestCase):
    """Test cases for CodeAnalyzer."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = CodeAnalyzer()

    def test_detect_language_python(self):
        """Test Python language detection."""
        code = "def hello():\n    print('Hello')"
        self.assertEqual(self.analyzer.detect_language(code), "python")

    def test_detect_language_javascript(self):
        """Test JavaScript language detection."""
        code = "function hello() {\n  console.log('Hello');\n}"
        self.assertEqual(self.analyzer.detect_language(code), "javascript")

    def test_detect_language_typescript(self):
        """Test TypeScript language detection."""
        code = "const x: number = 42;\nfunction greet(name: string): void {}"
        self.assertEqual(self.analyzer.detect_language(code), "typescript")

    def test_detect_language_by_extension(self):
        """Test language detection by filename extension."""
        self.assertEqual(
            self.analyzer.detect_language("", "script.py"), "python"
        )
        self.assertEqual(
            self.analyzer.detect_language("", "app.ts"), "typescript"
        )
        self.assertEqual(
            self.analyzer.detect_language("", "index.js"), "javascript"
        )

    def test_analyze_python(self):
        """Test analyzing Python code."""
        code = '''"""Module docstring."""
import os

def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    def multiply(self, a, b):
        return a * b
'''
        result = self.analyzer.analyze(code, language="python")
        self.assertEqual(result["language"], "python")
        self.assertGreater(result["statistics"]["total_lines"], 0)
        self.assertEqual(result["structure"]["function_count"], 2)
        self.assertEqual(result["structure"]["class_count"], 1)
        self.assertGreater(result["complexity"]["overall"], 0)

    def test_analyze_javascript(self):
        """Test analyzing JavaScript code."""
        code = '''// A simple module
function greet(name) {
    if (name) {
        return "Hello, " + name;
    } else {
        return "Hello, World";
    }
}
'''
        result = self.analyzer.analyze(code, language="javascript")
        self.assertEqual(result["language"], "javascript")
        self.assertEqual(result["structure"]["function_count"], 1)

    def test_complexity_risk_levels(self):
        """Test cyclomatic complexity risk levels."""
        self.assertEqual(self.analyzer._risk_level(3), "low")
        self.assertEqual(self.analyzer._risk_level(7), "moderate")
        self.assertEqual(self.analyzer._risk_level(15), "high")
        self.assertEqual(self.analyzer._risk_level(25), "very_high")

    def test_format_analysis(self):
        """Test formatting analysis results."""
        code = "def hello():\n    print('Hello')"
        result = self.analyzer.analyze(code, language="python")
        formatted = self.analyzer.format_analysis(result)
        self.assertIn("Code Analysis", formatted)
        self.assertIn("Statistics", formatted)

    def test_execute(self):
        """Test tool execute interface."""
        result = self.analyzer.execute("def foo(): pass")
        self.assertIn("Code Analysis", result)

    def test_execute_with_dict(self):
        """Test tool execute with dict args."""
        result = self.analyzer.execute({
            "code": "def bar(): return 42",
            "language": "python",
        })
        self.assertIn("Code Analysis", result)


class TestFileManager(unittest.TestCase):
    """Test cases for FileManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.fm = FileManager(allowed_root=self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_file(self):
        """Test writing and reading a file."""
        path = os.path.join(self.temp_dir, "test.txt")
        self.fm.write_file(path, "Hello, World!")
        content = self.fm.read_file(path)
        self.assertEqual(content, "Hello, World!")

    def test_read_file_with_limit(self):
        """Test reading a file with line limit."""
        path = os.path.join(self.temp_dir, "test.txt")
        self.fm.write_file(path, "Line 1\nLine 2\nLine 3\n")
        content = self.fm.read_file(path, max_lines=2)
        self.assertEqual(content, "Line 1\nLine 2\n")

    def test_path_traversal_prevention(self):
        """Test that path traversal is prevented."""
        with self.assertRaises(ValueError):
            self.fm.read_file(os.path.join(self.temp_dir, "..", "etc", "passwd"))

    def test_list_directory(self):
        """Test listing directory contents."""
        os.makedirs(os.path.join(self.temp_dir, "subdir"))
        self.fm.write_file(os.path.join(self.temp_dir, "file.txt"), "test")

        entries = self.fm.list_directory(self.temp_dir)
        names = [e["name"] for e in entries]
        self.assertIn("file.txt", names)
        self.assertIn("subdir", names)

    def test_tree(self):
        """Test tree view generation."""
        os.makedirs(os.path.join(self.temp_dir, "subdir"))
        self.fm.write_file(os.path.join(self.temp_dir, "file.txt"), "test")

        tree = self.fm.tree(self.temp_dir)
        self.assertIn("file.txt", tree)
        self.assertIn("subdir", tree)

    def test_search_files_by_name(self):
        """Test searching files by name."""
        self.fm.write_file(os.path.join(self.temp_dir, "test.py"), "print('hi')")
        self.fm.write_file(os.path.join(self.temp_dir, "readme.md"), "# Title")

        results = self.fm.search_files(self.temp_dir, pattern="test")
        self.assertGreater(len(results), 0)

    def test_search_files_by_content(self):
        """Test searching files by content."""
        self.fm.write_file(
            os.path.join(self.temp_dir, "code.py"), "def hello(): pass"
        )
        self.fm.write_file(
            os.path.join(self.temp_dir, "other.py"), "x = 42"
        )

        results = self.fm.search_files(
            self.temp_dir, pattern="def hello", by_content=True
        )
        self.assertGreater(len(results), 0)

    def test_detect_file_type(self):
        """Test file type detection."""
        self.assertEqual(self.fm.detect_file_type("script.py"), "code")
        self.assertEqual(self.fm.detect_file_type("data.json"), "data")
        self.assertEqual(self.fm.detect_file_type("doc.md"), "document")
        self.assertEqual(self.fm.detect_file_type("image.png"), "image")

    def test_get_file_info(self):
        """Test getting file information."""
        path = os.path.join(self.temp_dir, "info_test.py")
        self.fm.write_file(path, "print('test')")

        info = self.fm.get_file_info(path)
        self.assertEqual(info["name"], "info_test.py")
        self.assertEqual(info["type"], "file")
        self.assertEqual(info["file_type"], "code")

    def test_execute(self):
        """Test tool execute interface."""
        result = self.fm.execute({"action": "info", "path": self.temp_dir})
        self.assertIn(self.temp_dir, result)


class TestCalculator(unittest.TestCase):
    """Test cases for Calculator."""

    def setUp(self):
        """Set up test fixtures."""
        self.calc = Calculator()

    def test_basic_arithmetic(self):
        """Test basic arithmetic operations."""
        self.assertEqual(self.calc.evaluate("2 + 3"), 5)
        self.assertEqual(self.calc.evaluate("10 - 4"), 6)
        self.assertEqual(self.calc.evaluate("3 * 7"), 21)
        self.assertEqual(self.calc.evaluate("15 / 4"), 3.75)

    def test_exponentiation(self):
        """Test exponentiation."""
        self.assertEqual(self.calc.evaluate("2 ** 10"), 1024)
        self.assertEqual(self.calc.evaluate("2 ^ 3"), 8)

    def test_math_functions(self):
        """Test mathematical functions."""
        self.assertAlmostEqual(self.calc.evaluate("sqrt(16)"), 4.0)
        self.assertAlmostEqual(self.calc.evaluate("abs(-5)"), 5)
        self.assertEqual(self.calc.evaluate("round(3.14159, 2)"), 3.14)

    def test_constants(self):
        """Test math constants."""
        import math
        self.assertAlmostEqual(self.calc.evaluate("pi"), math.pi, places=5)
        self.assertAlmostEqual(self.calc.evaluate("e"), math.e, places=5)

    def test_percentage(self):
        """Test percentage calculation."""
        result = self.calc.evaluate("50%")
        self.assertEqual(result, 0.5)

    def test_empty_expression_raises(self):
        """Test that empty expression raises ValueError."""
        with self.assertRaises(ValueError):
            self.calc.evaluate("")

    def test_unsafe_expression_raises(self):
        """Test that unsafe expressions are blocked."""
        with self.assertRaises(ValueError):
            self.calc.evaluate("__import__('os')")

    def test_unit_conversion_length(self):
        """Test length unit conversion."""
        result = self.calc.convert_unit(1, "km", "m")
        self.assertEqual(result, 1000)

        result = self.calc.convert_unit(1, "mi", "km")
        self.assertAlmostEqual(result, 1.609344, places=4)

    def test_unit_conversion_temperature(self):
        """Test temperature conversion."""
        self.assertEqual(self.calc.convert_unit(0, "c", "f"), 32)
        self.assertEqual(self.calc.convert_unit(32, "f", "c"), 0)
        self.assertAlmostEqual(self.calc.convert_unit(100, "c", "k"), 373.15)

    def test_unit_conversion_weight(self):
        """Test weight unit conversion."""
        result = self.calc.convert_unit(1, "kg", "lb")
        self.assertAlmostEqual(result, 2.204622, places=4)

    def test_parse_and_evaluate(self):
        """Test natural language parsing."""
        result = self.calc.parse_and_evaluate("2 + 3")
        self.assertIn("5", result)

    def test_parse_unit_conversion(self):
        """Test parsing unit conversion from natural language."""
        result = self.calc.parse_and_evaluate("1 km to m")
        self.assertIn("1000", result)

    def test_history(self):
        """Test calculation history."""
        self.calc.evaluate("2 + 3")
        self.calc.evaluate("10 * 5")
        history = self.calc.get_history()
        self.assertEqual(len(history), 2)

    def test_clear_history(self):
        """Test clearing history."""
        self.calc.evaluate("2 + 3")
        self.calc.clear_history()
        self.assertEqual(len(self.calc.get_history()), 0)

    def test_execute(self):
        """Test tool execute interface."""
        result = self.calc.execute("2 + 3")
        self.assertIn("5", result)


if __name__ == "__main__":
    unittest.main()
