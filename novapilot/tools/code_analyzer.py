"""Code analysis tool for NovaPilot.

Provides syntax analysis, complexity measurement, and code statistics
for Python, JavaScript, and TypeScript source code.
"""

import re
import math
from collections import defaultdict


class CodeAnalyzer:
    """Static code analysis tool.

    Analyzes source code for complexity metrics, structure statistics,
    and formatting. Supports Python, JavaScript, and TypeScript.
    """

    # Trigger patterns for automatic tool activation
    trigger_patterns = [
        "analyze code", "code analysis", "code stats",
        "complexity", "cyclomatic",
    ]

    # Language definitions
    LANGUAGES = {
        "python": {
            "extensions": [".py", ".pyw"],
            "single_comment": "#",
            "multi_comment_start": '"""',
            "multi_comment_end": '"""',
            "function_pattern": r'^\s*def\s+(\w+)\s*\(',
            "class_pattern": r'^\s*class\s+(\w+)',
            "branch_keywords": [
                r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
                r'\bexcept\b', r'\band\b', r'\bor\b',
            ],
        },
        "javascript": {
            "extensions": [".js", ".jsx", ".mjs"],
            "single_comment": "//",
            "multi_comment_start": "/*",
            "multi_comment_end": "*/",
            "function_pattern": r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
            "class_pattern": r'class\s+(\w+)',
            "branch_keywords": [
                r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                r'\bcase\b', r'\bcatch\b', r'\?\?', r'\&\&', r'\|\|',
            ],
        },
        "typescript": {
            "extensions": [".ts", ".tsx"],
            "single_comment": "//",
            "multi_comment_start": "/*",
            "multi_comment_end": "*/",
            "function_pattern": r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*(?::\s*\w+)?\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
            "class_pattern": r'(?:interface|type|class)\s+(\w+)',
            "branch_keywords": [
                r'\bif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
                r'\bcase\b', r'\bcatch\b',
            ],
        },
    }

    def __init__(self):
        """Initialize CodeAnalyzer."""
        self._results_cache = {}

    def detect_language(self, code, filename=""):
        """Detect the programming language of the given code.

        Args:
            code: Source code string.
            filename: Optional filename for extension-based detection.

        Returns:
            Language identifier string ('python', 'javascript', 'typescript', 'unknown').
        """
        # Try filename extension first
        if filename:
            ext = self._get_extension(filename)
            for lang, config in self.LANGUAGES.items():
                if ext in config["extensions"]:
                    return lang

        # Heuristic detection
        if re.search(r'^\s*def\s+\w+\s*\(', code, re.MULTILINE):
            return "python"
        elif re.search(r':\s*(?:string|number|boolean|any)\b', code):
            return "typescript"
        elif re.search(r'(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s+)?(?:function|\())', code):
            return "javascript"

        return "unknown"

    def _get_extension(self, filename):
        """Get the file extension from a filename.

        Args:
            filename: File path or name string.

        Returns:
            Lowercase extension string (with dot), or empty string.
        """
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""

    def analyze(self, code, language=None, filename=""):
        """Perform a comprehensive code analysis.

        Args:
            code: Source code string.
            language: Language identifier. Auto-detected if None.
            filename: Optional filename for language detection.

        Returns:
            Dict with analysis results including statistics, complexity, and structure.
        """
        if language is None:
            language = self.detect_language(code, filename)

        if language not in self.LANGUAGES:
            return self._analyze_generic(code)

        lang_config = self.LANGUAGES[language]
        lines = code.split("\n")

        # Basic statistics
        stats = self._compute_stats(lines, lang_config, code)

        # Structure analysis
        structure = self._analyze_structure(code, lang_config)

        # Complexity analysis
        complexity = self._compute_complexity(code, lang_config)

        # Code quality metrics
        quality = self._compute_quality(lines, stats)

        return {
            "language": language,
            "filename": filename or "<anonymous>",
            "statistics": stats,
            "structure": structure,
            "complexity": complexity,
            "quality": quality,
        }

    def _compute_stats(self, lines, lang_config, code):
        """Compute basic code statistics.

        Args:
            lines: List of code lines.
            lang_config: Language configuration dict.
            code: Full source code string.

        Returns:
            Dict with line counts, blank lines, comment lines, etc.
        """
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0
        code_lines = 0
        in_multi_comment = False
        multi_start = lang_config["multi_comment_start"]
        multi_end = lang_config["multi_comment_end"]
        single_comment = lang_config["single_comment"]

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank_lines += 1
                continue

            # Check for multi-line comments
            if in_multi_comment:
                comment_lines += 1
                if multi_end in stripped:
                    in_multi_comment = False
                continue

            if stripped.startswith(multi_start):
                comment_lines += 1
                if multi_end in stripped[len(multi_start):]:
                    in_multi_comment = False
                else:
                    in_multi_comment = True
                continue

            if stripped.startswith(single_comment):
                comment_lines += 1
                continue

            code_lines += 1

        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
            "comment_ratio": round(comment_lines / max(total_lines, 1) * 100, 1),
            "avg_line_length": round(
                sum(len(line) for line in lines) / max(total_lines, 1), 1
            ),
            "max_line_length": max((len(line) for line in lines), default=0),
            "character_count": len(code),
        }

    def _analyze_structure(self, code, lang_config):
        """Analyze code structure (functions, classes, etc.).

        Args:
            code: Full source code string.
            lang_config: Language configuration dict.

        Returns:
            Dict with functions, classes, and nesting info.
        """
        functions = []
        classes = []

        # Find functions
        func_matches = re.finditer(
            lang_config["function_pattern"], code, re.MULTILINE
        )
        for match in func_matches:
            name = match.group(1) or match.group(2) or ""
            if name:
                line_num = code[:match.start()].count("\n") + 1
                functions.append({
                    "name": name,
                    "line": line_num,
                })

        # Find classes
        class_matches = re.finditer(
            lang_config["class_pattern"], code, re.MULTILINE
        )
        for match in class_matches:
            name = match.group(1)
            line_num = code[:match.start()].count("\n") + 1
            classes.append({
                "name": name,
                "line": line_num,
            })

        return {
            "functions": functions,
            "classes": classes,
            "function_count": len(functions),
            "class_count": len(classes),
        }

    def _compute_complexity(self, code, lang_config):
        """Compute cyclomatic complexity for each function.

        Cyclomatic complexity = 1 + number of decision points.
        Decision points include: if, elif, for, while, except, and, or, case.

        Args:
            code: Full source code string.
            lang_config: Language configuration dict.

        Returns:
            Dict with per-function complexity and overall metrics.
        """
        branch_patterns = lang_config["branch_keywords"]
        func_pattern = lang_config["function_pattern"]

        # Split code into functions
        functions_complexity = []
        overall_complexity = 1

        # Count branches in entire file
        for pattern in branch_patterns:
            overall_complexity += len(re.findall(pattern, code))

        # Per-function complexity
        func_matches = list(re.finditer(func_pattern, code, re.MULTILINE))
        for i, match in enumerate(func_matches):
            func_name = match.group(1) or match.group(2) or "anonymous"
            start = match.end()

            # Find the end of this function (next function or end of file)
            if i + 1 < len(func_matches):
                end = func_matches[i + 1].start()
            else:
                end = len(code)

            func_body = code[start:end]

            # Count decision points
            complexity = 1
            for pattern in branch_patterns:
                complexity += len(re.findall(pattern, func_body))

            functions_complexity.append({
                "name": func_name,
                "complexity": complexity,
                "risk_level": self._risk_level(complexity),
            })

        # Calculate average
        avg_complexity = 0
        if functions_complexity:
            avg_complexity = round(
                sum(f["complexity"] for f in functions_complexity)
                / len(functions_complexity),
                1,
            )

        return {
            "overall": overall_complexity,
            "average": avg_complexity,
            "risk_level": self._risk_level(overall_complexity),
            "functions": functions_complexity,
            "max_function_complexity": max(
                (f["complexity"] for f in functions_complexity), default=0
            ),
        }

    def _risk_level(self, complexity):
        """Determine risk level based on cyclomatic complexity.

        Args:
            complexity: Cyclomatic complexity value.

        Returns:
            Risk level string ('low', 'moderate', 'high', 'very_high').
        """
        if complexity <= 5:
            return "low"
        elif complexity <= 10:
            return "moderate"
        elif complexity <= 20:
            return "high"
        else:
            return "very_high"

    def _compute_quality(self, lines, stats):
        """Compute code quality metrics.

        Args:
            lines: List of code lines.
            stats: Code statistics dict.

        Returns:
            Dict with quality indicators.
        """
        code_lines = stats["code_lines"]
        max_line = stats["max_line_length"]

        # Lines exceeding 80 and 120 characters
        long_lines_80 = sum(1 for l in lines if len(l) > 80)
        long_lines_120 = sum(1 for l in lines if len(l) > 120)

        # Comment coverage assessment
        comment_ratio = stats["comment_ratio"]
        if comment_ratio >= 20:
            comment_grade = "good"
        elif comment_ratio >= 10:
            comment_grade = "moderate"
        else:
            comment_grade = "low"

        return {
            "long_lines_80": long_lines_80,
            "long_lines_120": long_lines_120,
            "line_length_grade": "good" if max_line <= 120 else "needs_improvement",
            "comment_coverage": comment_grade,
            "comment_ratio": comment_ratio,
        }

    def _analyze_generic(self, code):
        """Perform basic analysis for unknown languages.

        Args:
            code: Source code string.

        Returns:
            Basic analysis result dict.
        """
        lines = code.split("\n")
        total = len(lines)
        blank = sum(1 for l in lines if not l.strip())
        code_lines = total - blank

        return {
            "language": "unknown",
            "filename": "<anonymous>",
            "statistics": {
                "total_lines": total,
                "code_lines": code_lines,
                "blank_lines": blank,
                "comment_lines": 0,
                "comment_ratio": 0,
                "avg_line_length": round(
                    sum(len(l) for l in lines) / max(total, 1), 1
                ),
                "max_line_length": max((len(l) for l in lines), default=0),
                "character_count": len(code),
            },
            "structure": {
                "functions": [],
                "classes": [],
                "function_count": 0,
                "class_count": 0,
            },
            "complexity": {
                "overall": 1,
                "average": 0,
                "risk_level": "unknown",
                "functions": [],
                "max_function_complexity": 0,
            },
            "quality": {
                "long_lines_80": sum(1 for l in lines if len(l) > 80),
                "long_lines_120": sum(1 for l in lines if len(l) > 120),
                "line_length_grade": "unknown",
                "comment_coverage": "unknown",
                "comment_ratio": 0,
            },
        }

    def format_analysis(self, result):
        """Format analysis results as a readable string.

        Args:
            result: Analysis result dict from analyze().

        Returns:
            Formatted multi-line string with analysis results.
        """
        lines = [
            f"Code Analysis: {result['filename']} ({result['language']})",
            "=" * 50,
            "",
            "Statistics:",
            f"  Total lines:      {result['statistics']['total_lines']}",
            f"  Code lines:       {result['statistics']['code_lines']}",
            f"  Blank lines:      {result['statistics']['blank_lines']}",
            f"  Comment lines:    {result['statistics']['comment_lines']}",
            f"  Comment ratio:    {result['statistics']['comment_ratio']}%",
            f"  Avg line length:  {result['statistics']['avg_line_length']}",
            f"  Max line length:  {result['statistics']['max_line_length']}",
            "",
            "Structure:",
            f"  Functions:        {result['structure']['function_count']}",
            f"  Classes:          {result['structure']['class_count']}",
        ]

        # List functions
        for func in result["structure"]["functions"]:
            lines.append(f"    - {func['name']} (line {func['line']})")

        lines.extend([
            "",
            "Complexity:",
            f"  Overall:          {result['complexity']['overall']} "
            f"({result['complexity']['risk_level']})",
            f"  Average:          {result['complexity']['average']}",
            f"  Max function:     {result['complexity']['max_function_complexity']}",
        ])

        # List function complexities
        for func in result["complexity"]["functions"]:
            lines.append(
                f"    - {func['name']}: {func['complexity']} ({func['risk_level']})"
            )

        lines.extend([
            "",
            "Quality:",
            f"  Lines > 80 chars: {result['quality']['long_lines_80']}",
            f"  Lines > 120 chars:{result['quality']['long_lines_120']}",
            f"  Comment coverage: {result['quality']['comment_coverage']}",
        ])

        return "\n".join(lines)

    def execute(self, args):
        """Execute code analysis (tool interface).

        Args:
            args: Can be a code string, filename, or dict with 'code'/'filename' keys.

        Returns:
            Formatted analysis string.
        """
        if isinstance(args, dict):
            code = args.get("code", "")
            filename = args.get("filename", "")
            language = args.get("language", None)
        else:
            code = str(args)
            filename = ""
            language = None

        # If it looks like a filename, try to read it
        if not code and filename and not "\n" in str(args):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    code = f.read()
            except (IOError, OSError):
                return f"Error: Could not read file '{filename}'"

        if not code:
            return "Error: No code provided for analysis."

        result = self.analyze(code, language, filename)
        return self.format_analysis(result)
