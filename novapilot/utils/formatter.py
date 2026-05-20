"""Output formatting utilities for NovaPilot.

Provides terminal-friendly formatting for Markdown text, tables,
code blocks with syntax highlighting, progress bars, and tree structures.
All rendering is done using ANSI escape codes - no external dependencies.
"""

import os
import re
import textwrap
import math
from novapilot.utils.logger import Colors


class Formatter:
    """Terminal output formatter with Markdown rendering, tables, and more.

    All methods produce ANSI-decorated strings suitable for terminal output.
    Color output can be disabled globally via the color_enabled parameter.
    """

    def __init__(self, color_enabled=True):
        """Initialize Formatter.

        Args:
            color_enabled: Whether to use ANSI color codes in output.
        """
        self.color_enabled = color_enabled
        if not color_enabled:
            Colors.disable()

    # ── Markdown Rendering ─────────────────────────────────────────────

    def render_markdown(self, text):
        """Render Markdown text to terminal-formatted output.

        Supports: headers (#, ##, ###), bold (**text**), italic (*text*),
        inline code (`code`), code blocks (```lang ... ```), lists (- item),
        blockquotes (> text), horizontal rules (---), and links.

        Args:
            text: Markdown-formatted text string.

        Returns:
            Terminal-formatted string with ANSI styling.
        """
        if not text:
            return ""

        lines = text.split("\n")
        output = []
        in_code_block = False
        code_lang = ""

        for line in lines:
            # Toggle code block
            if line.strip().startswith("```"):
                if in_code_block:
                    output.append(Colors.RESET)
                    in_code_block = False
                    code_lang = ""
                else:
                    in_code_block = True
                    code_lang = line.strip()[3:].strip()
                    if code_lang:
                        output.append(
                            f"{Colors.DIM}  {code_lang}{Colors.RESET}\n"
                            f"{Colors.DIM}{'─' * 40}{Colors.RESET}"
                        )
                    else:
                        output.append(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
                continue

            # Inside code block - render with line numbers
            if in_code_block:
                highlighted = self.highlight_code(line, code_lang)
                output.append(highlighted)
                continue

            # Horizontal rule
            if re.match(r'^---+\s*$', line.strip()):
                output.append(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")
                continue

            # Headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2)
                output.append(self._render_header(title, level))
                continue

            # Blockquote
            if line.strip().startswith(">"):
                content = line.strip()[1:].strip()
                output.append(
                    f"{Colors.DIM}│{Colors.RESET} "
                    f"{Colors.YELLOW}{content}{Colors.RESET}"
                )
                continue

            # Unordered list
            list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
            if list_match:
                indent = len(list_match.group(1))
                content = list_match.group(2)
                prefix = "  " * (indent // 2)
                output.append(
                    f"{prefix}{Colors.CYAN}●{Colors.RESET} {content}"
                )
                continue

            # Ordered list
            olist_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
            if olist_match:
                indent = len(olist_match.group(1))
                content = olist_match.group(2)
                prefix = "  " * (indent // 2)
                output.append(
                    f"{prefix}{Colors.CYAN}◉{Colors.RESET} {content}"
                )
                continue

            # Empty line
            if not line.strip():
                output.append("")
                continue

            # Regular paragraph with inline formatting
            output.append(self._render_inline(line))

        return "\n".join(output)

    def _render_header(self, title, level):
        """Render a Markdown header.

        Args:
            title: Header text.
            level: Header level (1-6).

        Returns:
            Formatted header string.
        """
        styles = {
            1: (Colors.BOLD + Colors.WHITE, "\n" + "=" * 60),
            2: (Colors.BOLD + Colors.CYAN, "\n" + "-" * 50),
            3: (Colors.BOLD + Colors.YELLOW, ""),
            4: (Colors.BOLD + Colors.GREEN, ""),
            5: (Colors.BOLD + Colors.MAGENTA, ""),
            6: (Colors.BOLD + Colors.DIM, ""),
        }
        color, underline = styles.get(level, (Colors.WHITE, ""))
        result = f"{color}{title}{Colors.RESET}"
        if underline:
            result += f"\n{Colors.DIM}{underline}{Colors.RESET}"
        return result

    def _render_inline(self, text):
        """Render inline Markdown formatting (bold, italic, code, links).

        Args:
            text: Text with inline Markdown.

        Returns:
            Formatted text string.
        """
        result = text

        # Inline code (process first to avoid conflicts)
        result = re.sub(
            r'`([^`]+)`',
            lambda m: f"{Colors.BG_BLUE}{Colors.WHITE} {m.group(1)} {Colors.RESET}",
            result,
        )

        # Bold
        result = re.sub(
            r'\*\*(.+?)\*\*',
            lambda m: f"{Colors.BOLD}{m.group(1)}{Colors.RESET}",
            result,
        )

        # Italic
        result = re.sub(
            r'\*(.+?)\*',
            lambda m: f"{Colors.MAGENTA}{m.group(1)}{Colors.RESET}",
            result,
        )

        # Links [text](url)
        result = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            lambda m: f"{Colors.UNDERLINE if hasattr(Colors, 'UNDERLINE') else ''}"
                       f"{Colors.CYAN}{m.group(1)}{Colors.RESET}"
                       f"{Colors.DIM} ({m.group(2)}){Colors.RESET}",
            result,
        )

        return result

    # ── Code Highlighting ──────────────────────────────────────────────

    def highlight_code(self, code, language=""):
        """Apply simple keyword-based syntax highlighting to code.

        Supports Python, JavaScript, TypeScript, JSON, and generic highlighting.

        Args:
            code: Source code string (single line or multi-line).
            language: Programming language identifier.

        Returns:
            Syntax-highlighted code string with ANSI colors.
        """
        if not code and code != "":
            return ""

        lines = code.split("\n") if "\n" in code else [code]
        highlighted = []

        for i, line in enumerate(lines):
            line_num = f"{Colors.DIM}{i + 1:>4}{Colors.RESET} │ "
            highlighted_line = self._highlight_line(line, language)
            highlighted.append(line_num + highlighted_line)

        return "\n".join(highlighted)

    def _highlight_line(self, line, language=""):
        """Apply syntax highlighting to a single line of code.

        Args:
            line: Single line of source code.
            language: Programming language identifier.

        Returns:
            Highlighted line string.
        """
        # Escape any existing ANSI codes to avoid corruption
        # We work with raw text and add colors

        if language in ("python", "py"):
            return self._highlight_python(line)
        elif language in ("javascript", "js"):
            return self._highlight_javascript(line)
        elif language in ("typescript", "ts"):
            return self._highlight_typescript(line)
        elif language == "json":
            return self._highlight_json(line)
        elif language in ("bash", "sh", "shell"):
            return self._highlight_shell(line)
        else:
            return self._highlight_generic(line)

    def _highlight_python(self, line):
        """Highlight a Python code line.

        Args:
            line: Python source code line.

        Returns:
            Highlighted line string.
        """
        # Python keywords
        keywords = (
            r'\b(and|as|assert|async|await|break|class|continue|def|del|'
            r'elif|else|except|finally|for|from|global|if|import|in|is|'
            r'lambda|nonlocal|not|or|pass|raise|return|try|while|with|'
            r'yield|True|False|None)\b'
        )

        # Built-in functions
        builtins = (
            r'\b(print|len|range|str|int|float|list|dict|set|tuple|'
            r'open|type|isinstance|hasattr|getattr|setattr|input|'
            r'super|property|staticmethod|classmethod|enumerate|zip|'
            r'map|filter|sorted|reversed|any|all|min|max|sum|abs|'
            r'round|hex|oct|bin|chr|ord|id|hash|dir|vars|help|'
            r'__init__|__name__|__main__)\b'
        )

        # Strings (single and double quoted, triple quotes)
        string_pattern = r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|f\"[^\"]*\"|f\'[^\']*\'|\"[^\"\\]*(?:\\.[^\"\\]*)*\"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'

        # Comments
        comment_pattern = r'(#.*)$'

        # Decorators
        decorator_pattern = r'(@\w+)'

        # Numbers
        number_pattern = r'\b(\d+\.?\d*)\b'

        result = line

        # Process in order to avoid double-highlighting
        # First, protect strings and comments
        protected = []
        for pattern in [string_pattern, comment_pattern]:
            matches = list(re.finditer(pattern, result))
            for match in reversed(matches):
                idx = len(protected)
                placeholder = f"\x00PROTECTED{idx}\x00"
                protected.append((match.start(), match.end(), match.group()))
                result = result[:match.start()] + placeholder + result[match.end():]

        # Apply keyword highlighting
        result = re.sub(
            keywords,
            lambda m: f"{Colors.MAGENTA}{m.group()}{Colors.RESET}",
            result,
        )

        # Apply builtin highlighting
        result = re.sub(
            builtins,
            lambda m: f"{Colors.CYAN}{m.group()}{Colors.RESET}",
            result,
        )

        # Apply decorator highlighting
        result = re.sub(
            decorator_pattern,
            lambda m: f"{Colors.YELLOW}{m.group()}{Colors.RESET}",
            result,
        )

        # Apply number highlighting
        result = re.sub(
            number_pattern,
            lambda m: f"{Colors.GREEN}{m.group()}{Colors.RESET}",
            result,
        )

        # Restore protected sections with their colors
        for idx, (start, end, original) in enumerate(protected):
            placeholder = f"\x00PROTECTED{idx}\x00"
            if original.startswith("#"):
                colored = f"{Colors.DIM}{Colors.GREEN}{original}{Colors.RESET}"
            else:
                colored = f"{Colors.YELLOW}{original}{Colors.RESET}"
            result = result.replace(placeholder, colored)

        return result

    def _highlight_javascript(self, line):
        """Highlight a JavaScript code line.

        Args:
            line: JavaScript source code line.

        Returns:
            Highlighted line string.
        """
        keywords = (
            r'\b(const|let|var|function|return|if|else|for|while|do|'
            r'switch|case|break|continue|new|this|class|extends|import|'
            r'export|default|from|async|await|try|catch|finally|throw|'
            r'typeof|instanceof|in|of|void|delete|yield|true|false|null|'
            r'undefined|NaN|Infinity)\b'
        )

        result = line

        # Protect strings
        protected = []
        string_pattern = r'(`[^`]*`|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
        for match in reversed(list(re.finditer(string_pattern, result))):
            idx = len(protected)
            placeholder = f"\x00PROTECTED{idx}\x00"
            protected.append(match.group())
            result = result[:match.start()] + placeholder + result[match.end():]

        # Protect comments
        comment_pattern = r'(//.*$|/\*[\s\S]*?\*/)'
        for match in reversed(list(re.finditer(comment_pattern, result))):
            idx = len(protected)
            placeholder = f"\x00PROTECTED{idx}\x00"
            protected.append(match.group())
            result = result[:match.start()] + placeholder + result[match.end():]

        # Keywords
        result = re.sub(
            keywords,
            lambda m: f"{Colors.MAGENTA}{m.group()}{Colors.RESET}",
            result,
        )

        # Numbers
        result = re.sub(
            r'\b(\d+\.?\d*)\b',
            lambda m: f"{Colors.GREEN}{m.group()}{Colors.RESET}",
            result,
        )

        # Restore
        for idx, original in enumerate(protected):
            placeholder = f"\x00PROTECTED{idx}\x00"
            if original.startswith("//") or original.startswith("/*"):
                colored = f"{Colors.DIM}{Colors.GREEN}{original}{Colors.RESET}"
            else:
                colored = f"{Colors.YELLOW}{original}{Colors.RESET}"
            result = result.replace(placeholder, colored)

        return result

    def _highlight_typescript(self, line):
        """Highlight a TypeScript code line.

        Extends JavaScript highlighting with TypeScript-specific keywords.

        Args:
            line: TypeScript source code line.

        Returns:
            Highlighted line string.
        """
        # TypeScript adds type keywords
        ts_keywords = (
            r'\b(interface|type|enum|namespace|declare|abstract|implements|'
            r'public|private|protected|readonly|as|is|keyof|infer|never|'
            r'unknown|any|void|string|number|boolean|object|symbol|bigint)\b'
        )

        result = self._highlight_javascript(line)

        # Add TypeScript keyword highlighting
        result = re.sub(
            ts_keywords,
            lambda m: f"{Colors.CYAN}{m.group()}{Colors.RESET}",
            result,
        )

        return result

    def _highlight_json(self, line):
        """Highlight a JSON code line.

        Args:
            line: JSON source code line.

        Returns:
            Highlighted line string.
        """
        # Keys
        result = re.sub(
            r'"([^"]+)"(\s*:)',
            lambda m: f'{Colors.CYAN}"{m.group(1)}"{Colors.RESET}{m.group(2)}',
            line,
        )

        # String values
        result = re.sub(
            r':\s*"([^"]*)"',
            lambda m: f': {Colors.YELLOW}"{m.group(1)}"{Colors.RESET}',
            result,
        )

        # Numbers
        result = re.sub(
            r':\s*(\d+\.?\d*)',
            lambda m: f': {Colors.GREEN}{m.group(1)}{Colors.RESET}',
            result,
        )

        # Booleans and null
        result = re.sub(
            r':\s*(true|false|null)',
            lambda m: f': {Colors.MAGENTA}{m.group(1)}{Colors.RESET}',
            result,
        )

        return result

    def _highlight_shell(self, line):
        """Highlight a shell/bash code line.

        Args:
            line: Shell source code line.

        Returns:
            Highlighted line string.
        """
        # Comments
        if line.strip().startswith("#"):
            return f"{Colors.DIM}{Colors.GREEN}{line}{Colors.RESET}"

        # Commands at start
        result = re.sub(
            r'^(\s*)(\w+)',
            lambda m: f"{m.group(1)}{Colors.GREEN}{m.group(2)}{Colors.RESET}",
            line,
        )

        # Flags
        result = re.sub(
            r'(\s)(--?\w+)',
            lambda m: f"{m.group(1)}{Colors.CYAN}{m.group(2)}{Colors.RESET}",
            result,
        )

        # Strings
        result = re.sub(
            r'"([^"]*)"',
            lambda m: f'{Colors.YELLOW}"{m.group(1)}"{Colors.RESET}',
            result,
        )

        return result

    def _highlight_generic(self, line):
        """Apply generic syntax highlighting.

        Highlights comments (#), strings, and numbers.

        Args:
            line: Source code line.

        Returns:
            Highlighted line string.
        """
        result = line

        # Comments
        if result.strip().startswith("#"):
            return f"{Colors.DIM}{Colors.GREEN}{result}{Colors.RESET}"

        # Strings
        result = re.sub(
            r'"([^"]*)"',
            lambda m: f'{Colors.YELLOW}"{m.group(1)}"{Colors.RESET}',
            result,
        )
        result = re.sub(
            r"'([^']*)'",
            lambda m: f"{Colors.YELLOW}'{m.group(1)}'{Colors.RESET}",
            result,
        )

        # Numbers
        result = re.sub(
            r'\b(\d+\.?\d*)\b',
            lambda m: f"{Colors.GREEN}{m.group()}{Colors.RESET}",
            result,
        )

        return result

    # ── Table Rendering ────────────────────────────────────────────────

    def render_table(self, headers, rows, max_col_width=40):
        """Render data as a formatted terminal table.

        Args:
            headers: List of column header strings.
            rows: List of row lists (each row is a list of cell values).
            max_col_width: Maximum width for any column.

        Returns:
            Formatted table string.
        """
        if not headers:
            return ""

        # Convert all values to strings
        str_headers = [str(h) for h in headers]
        str_rows = [[str(cell) for cell in row] for row in rows]

        # Calculate column widths
        num_cols = len(str_headers)
        col_widths = [len(h) for h in str_headers]

        for row in str_rows:
            for i, cell in enumerate(row):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell))

        # Cap column widths
        col_widths = [min(w, max_col_width) for w in col_widths]

        # Build separator line
        separator = "+"
        for w in col_widths:
            separator += "-" * (w + 2) + "+"

        # Build header
        header_line = "|"
        for i, h in enumerate(str_headers):
            padded = self._pad_cell(h, col_widths[i])
            header_line += f" {Colors.BOLD}{padded}{Colors.RESET} |"

        # Build rows
        row_lines = []
        for row in str_rows:
            row_line = "|"
            for i, cell in enumerate(row):
                if i < num_cols:
                    padded = self._pad_cell(cell, col_widths[i])
                    row_line += f" {padded} |"
                else:
                    break
            row_lines.append(row_line)

        # Combine
        parts = [separator, header_line, separator]
        for row_line in row_lines:
            parts.append(row_line)
        parts.append(separator)

        return "\n".join(parts)

    def _pad_cell(self, text, width):
        """Pad or truncate a table cell to the specified width.

        Args:
            text: Cell text content.
            width: Target width.

        Returns:
            Padded/truncated string.
        """
        # Strip ANSI codes for length calculation
        clean = re.sub(r'\033\[[0-9;]*m', '', text)
        if len(clean) > width:
            # Truncate with ellipsis
            return clean[:width - 3] + "..."
        return text + " " * (width - len(clean))

    # ── Progress Bar ───────────────────────────────────────────────────

    def render_progress(self, current, total, prefix="", width=40,
                        fill_char="█", empty_char="░"):
        """Render a progress bar.

        Args:
            current: Current progress value.
            total: Total/target value.
            prefix: Text to display before the bar.
            width: Width of the progress bar in characters.
            fill_char: Character for filled portion.
            empty_char: Character for empty portion.

        Returns:
            Formatted progress bar string.
        """
        if total <= 0:
            percent = 100.0
        else:
            percent = min(100.0, (current / total) * 100.0)

        filled = int(width * percent / 100)
        empty = width - filled

        bar = (
            f"{Colors.GREEN}{fill_char * filled}{Colors.RESET}"
            f"{Colors.DIM}{empty_char * empty}{Colors.RESET}"
        )

        return f"{prefix} {bar} {percent:5.1f}%"

    # ── Tree Structure ─────────────────────────────────────────────────

    def render_tree(self, items, prefix="", indent="  "):
        """Render a tree structure from a nested dict or list.

        Args:
            items: Dict or list representing the tree structure.
                  Dicts use keys as node names, lists use item string values.
            prefix: Prefix string for the current level.
            indent: Indentation string per level.

        Returns:
            Formatted tree string.
        """
        lines = []

        if isinstance(items, dict):
            entries = list(items.items())
        elif isinstance(items, (list, tuple)):
            entries = [(str(item), item) for item in items]
        else:
            return str(items)

        for i, (name, value) in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if isinstance(value, (dict, list, tuple)) and value:
                lines.append(f"{prefix}{connector}{Colors.CYAN}{name}{Colors.RESET}")
                lines.append(self.render_tree(value, child_prefix, indent))
            else:
                display_value = ""
                if isinstance(value, dict) and not value:
                    display_value = " {}"
                elif isinstance(value, list) and not value:
                    display_value = " []"
                elif not isinstance(value, (dict, list, tuple)):
                    display_value = f" {Colors.DIM}{value}{Colors.RESET}"
                lines.append(
                    f"{prefix}{connector}{Colors.CYAN}{name}{Colors.RESET}"
                    f"{display_value}"
                )

        return "\n".join(lines)

    # ── Status Indicators ──────────────────────────────────────────────

    def success(self, message):
        """Format a success message with a checkmark.

        Args:
            message: Success message text.

        Returns:
            Formatted success string.
        """
        return f"{Colors.GREEN}  [OK] {message}{Colors.RESET}"

    def error(self, message):
        """Format an error message with an X mark.

        Args:
            message: Error message text.

        Returns:
            Formatted error string.
        """
        return f"{Colors.RED} [ERR] {message}{Colors.RESET}"

    def warning(self, message):
        """Format a warning message with a warning symbol.

        Args:
            message: Warning message text.

        Returns:
            Formatted warning string.
        """
        return f"{Colors.YELLOW} [WARN] {message}{Colors.RESET}"

    def info(self, message):
        """Format an info message with an info symbol.

        Args:
            message: Info message text.

        Returns:
            Formatted info string.
        """
        return f"{Colors.BLUE} [INFO] {message}{Colors.RESET}"

    # ── Misc Formatting ────────────────────────────────────────────────

    def bold(self, text):
        """Wrap text in bold ANSI codes.

        Args:
            text: Text to bold.

        Returns:
            Bold-formatted text.
        """
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    def dim(self, text):
        """Wrap text in dim ANSI codes.

        Args:
            text: Text to dim.

        Returns:
            Dim-formatted text.
        """
        return f"{Colors.DIM}{text}{Colors.RESET}"

    def color(self, text, color_code):
        """Wrap text in a custom ANSI color.

        Args:
            text: Text to color.
            color_code: ANSI color code string.

        Returns:
            Colored text.
        """
        return f"{color_code}{text}{Colors.RESET}"

    def wrap_text(self, text, width=80, indent=""):
        """Wrap text to a specified width with optional indentation.

        Args:
            text: Text to wrap.
            width: Maximum line width.
            indent: Indentation string for wrapped lines.

        Returns:
            Wrapped text string.
        """
        wrapped = textwrap.wrap(text, width=width - len(indent))
        if not wrapped:
            return ""
        lines = [wrapped[0]]
        for line in wrapped[1:]:
            lines.append(indent + line)
        return "\n".join(lines)

    def render_key_value(self, data, indent=2):
        """Render a dictionary as aligned key-value pairs.

        Args:
            data: Dictionary of key-value pairs.
            indent: Number of spaces for indentation.

        Returns:
            Formatted key-value string.
        """
        if not data:
            return ""

        prefix = " " * indent
        max_key_len = max(len(str(k)) for k in data.keys())

        lines = []
        for key, value in data.items():
            key_str = f"{Colors.CYAN}{str(key):<{max_key_len}}{Colors.RESET}"
            val_str = f"{Colors.WHITE}{value}{Colors.RESET}"
            lines.append(f"{prefix}{key_str} : {val_str}")

        return "\n".join(lines)
