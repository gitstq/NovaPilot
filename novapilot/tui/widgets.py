"""TUI widget components for NovaPilot.

Provides reusable terminal UI components including text boxes,
list boxes, progress bars, status bars, and a simple Markdown renderer.
All built using ANSI escape codes for maximum compatibility.
"""

import os
import sys
import time
import threading
from novapilot.utils.logger import Colors


class TextBox:
    """Multi-line text display widget.

    Renders text content within a defined width, handling
    word wrapping and scrolling.
    """

    def __init__(self, width=80, height=10):
        """Initialize TextBox.

        Args:
            width: Display width in characters.
            height: Display height in lines.
        """
        self.width = width
        self.height = height
        self._lines = []
        self._scroll_offset = 0

    def set_content(self, text):
        """Set the text content, wrapping to the widget width.

        Args:
            text: Text content string.
        """
        self._lines = self._wrap_text(text, self.width)
        self._scroll_offset = 0

    def _wrap_text(self, text, width):
        """Wrap text to fit within the specified width.

        Args:
            text: Text to wrap.
            width: Maximum line width.

        Returns:
            List of wrapped line strings.
        """
        if not text:
            return []

        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            # Handle words with newlines
            if "\n" in word:
                parts = word.split("\n")
                for i, part in enumerate(parts):
                    if i > 0:
                        lines.append(current_line)
                        current_line = ""
                    if part:
                        test = current_line + (" " if current_line else "") + part
                        if len(test) <= width:
                            current_line = test
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = part[:width]
                            if len(part) > width:
                                lines.append(current_line)
                                current_line = ""
            else:
                test = current_line + (" " if current_line else "") + word
                if len(test) <= width:
                    current_line = test
                else:
                    if current_line:
                        lines.append(current_line)
                    # Handle words longer than width
                    if len(word) > width:
                        lines.extend([
                            word[i:i + width]
                            for i in range(0, len(word), width)
                        ])
                        current_line = ""
                    else:
                        current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def scroll_up(self, lines=1):
        """Scroll content up.

        Args:
            lines: Number of lines to scroll.
        """
        self._scroll_offset = max(0, self._scroll_offset - lines)

    def scroll_down(self, lines=1):
        """Scroll content down.

        Args:
            lines: Number of lines to scroll.
        """
        max_offset = max(0, len(self._lines) - self.height)
        self._scroll_offset = min(max_offset, self._scroll_offset + lines)

    def scroll_to_bottom(self):
        """Scroll to the bottom of the content."""
        self._scroll_offset = max(0, len(self._lines) - self.height)

    def scroll_to_top(self):
        """Scroll to the top of the content."""
        self._scroll_offset = 0

    def render(self):
        """Render the text box content.

        Returns:
            List of rendered line strings.
        """
        visible = self._lines[self._scroll_offset:self._scroll_offset + self.height]

        # Pad with empty lines if needed
        while len(visible) < self.height:
            visible.append("")

        return visible

    @property
    def total_lines(self):
        """Get total number of content lines.

        Returns:
            Total line count.
        """
        return len(self._lines)

    @property
    def is_at_bottom(self):
        """Check if scrolled to the bottom.

        Returns:
            True if at the bottom of content.
        """
        return self._scroll_offset >= max(0, len(self._lines) - self.height)


class ListBox:
    """Selectable list widget.

    Displays a list of items with selection highlighting
    and keyboard navigation support.
    """

    def __init__(self, items=None, width=80, height=10):
        """Initialize ListBox.

        Args:
            items: Initial list of item strings.
            width: Display width in characters.
            height: Display height in lines.
        """
        self.items = items or []
        self.width = width
        self.height = height
        self._selected_index = 0
        self._scroll_offset = 0

    def set_items(self, items):
        """Set the list items.

        Args:
            items: List of item strings.
        """
        self.items = list(items)
        self._selected_index = 0
        self._scroll_offset = 0

    def add_item(self, item):
        """Add an item to the list.

        Args:
            item: Item string to add.
        """
        self.items.append(item)

    def clear(self):
        """Clear all items."""
        self.items.clear()
        self._selected_index = 0
        self._scroll_offset = 0

    def move_up(self):
        """Move selection up one item."""
        if self._selected_index > 0:
            self._selected_index -= 1
            if self._selected_index < self._scroll_offset:
                self._scroll_offset = self._selected_index

    def move_down(self):
        """Move selection down one item."""
        if self._selected_index < len(self.items) - 1:
            self._selected_index += 1
            if self._selected_index >= self._scroll_offset + self.height:
                self._scroll_offset = self._selected_index - self.height + 1

    def select_index(self, index):
        """Select an item by index.

        Args:
            index: Item index to select.
        """
        if 0 <= index < len(self.items):
            self._selected_index = index
            if index < self._scroll_offset:
                self._scroll_offset = index
            elif index >= self._scroll_offset + self.height:
                self._scroll_offset = index - self.height + 1

    @property
    def selected(self):
        """Get the currently selected item.

        Returns:
            Selected item string, or None if empty.
        """
        if self.items and 0 <= self._selected_index < len(self.items):
            return self.items[self._selected_index]
        return None

    @property
    def selected_index(self):
        """Get the current selection index.

        Returns:
            Selected index integer.
        """
        return self._selected_index

    def render(self):
        """Render the list box.

        Returns:
            List of rendered line strings with selection highlighting.
        """
        visible = self.items[self._scroll_offset:self._scroll_offset + self.height]
        lines = []

        for i, item in enumerate(visible):
            actual_index = self._scroll_offset + i
            if actual_index == self._selected_index:
                # Selected item with highlight
                indicator = f"{Colors.BOLD}{Colors.CYAN}> {Colors.RESET}"
                line = f"{Colors.BG_BLUE}{Colors.WHITE} {item:<{self.width - 2}} {Colors.RESET}"
            else:
                indicator = f"{Colors.DIM}  {Colors.RESET}"
                line = f" {item:<{self.width - 2}} "

            lines.append(indicator + line)

        # Pad with empty lines
        while len(lines) < self.height:
            lines.append(f"{Colors.DIM}  {'':<{self.width - 2}} {Colors.RESET}")

        return lines


class ProgressBar:
    """Progress bar widget.

    Displays a visual progress indicator with percentage,
            status text, and optional animation.
    """

    def __init__(self, width=40, fill_char="\u2588", empty_char="\u2591"):
        """Initialize ProgressBar.

        Args:
            width: Bar width in characters.
            fill_char: Character for filled portion.
            empty_char: Character for empty portion.
        """
        self.width = width
        self.fill_char = fill_char
        self.empty_char = empty_char
        self._current = 0
        self._total = 100
        self._label = ""
        self._status = ""

    def set_progress(self, current, total=None):
        """Set the progress values.

        Args:
            current: Current progress value.
            total: Total value. Keeps previous total if None.
        """
        self._current = current
        if total is not None:
            self._total = total

    def set_label(self, label):
        """Set the progress label.

        Args:
            label: Label text string.
        """
        self._label = label

    def set_status(self, status):
        """Set the status text.

        Args:
            status: Status text string.
        """
        self._status = status

    @property
    def percent(self):
        """Get current progress percentage.

        Returns:
            Float percentage (0-100).
        """
        if self._total <= 0:
            return 100.0
        return min(100.0, (self._current / self._total) * 100.0)

    def render(self):
        """Render the progress bar.

        Returns:
            Formatted progress bar string.
        """
        pct = self.percent
        filled = int(self.width * pct / 100)
        empty = self.width - filled

        # Color based on progress
        if pct >= 100:
            color = Colors.GREEN
        elif pct >= 50:
            color = Colors.YELLOW
        else:
            color = Colors.RED

        bar = (
            f"{color}{self.fill_char * filled}{Colors.RESET}"
            f"{Colors.DIM}{self.empty_char * empty}{Colors.RESET}"
        )

        parts = []
        if self._label:
            parts.append(f"{Colors.BOLD}{self._label}{Colors.RESET} ")
        parts.append(f" {bar} ")
        parts.append(f"{Colors.BOLD}{pct:5.1f}%{Colors.RESET}")
        if self._status:
            parts.append(f" {Colors.DIM}{self._status}{Colors.RESET}")

        return "".join(parts)

    def render_inline(self):
        """Render a compact inline progress bar.

        Returns:
            Compact progress bar string.
        """
        pct = self.percent
        filled = int(self.width * pct / 100)
        empty = self.width - filled

        bar = f"{Colors.GREEN}{self.fill_char * filled}{Colors.DIM}{self.empty_char * empty}{Colors.RESET}"
        return f"{bar} {pct:5.1f}%"


class StatusBar:
    """Status bar widget for displaying application state.

    Shows key-value pairs, mode indicators, and status messages
    in a single-line bar at the bottom of the terminal.
    """

    def __init__(self, width=80):
        """Initialize StatusBar.

        Args:
            width: Bar width in characters.
        """
        self.width = width
        self._sections = []
        self._left_text = ""
        self._right_text = ""
        self._mode = ""
        self._color = Colors.DIM

    def set_left(self, text):
        """Set the left-aligned text.

        Args:
            text: Left-aligned text string.
        """
        self._left_text = text

    def set_right(self, text):
        """Set the right-aligned text.

        Args:
            text: Right-aligned text string.
        """
        self._right_text = text

    def set_mode(self, mode):
        """Set the mode indicator.

        Args:
            mode: Mode text (e.g., 'NORMAL', 'INSERT').
        """
        self._mode = mode

    def add_section(self, text, color=None):
        """Add a section to the status bar.

        Args:
            text: Section text.
            color: Optional ANSI color code.
        """
        self._sections.append({"text": text, "color": color})

    def clear_sections(self):
        """Clear all sections."""
        self._sections.clear()

    def render(self):
        """Render the status bar.

        Returns:
            Formatted status bar string.
        """
        parts = []

        # Mode indicator
        if self._mode:
            parts.append(
                f" {Colors.BOLD}{Colors.BG_BLUE}{Colors.WHITE}"
                f" {self._mode} {Colors.RESET} "
            )

        # Left text
        if self._left_text:
            parts.append(f" {self._left_text} ")

        # Separator
        parts.append(f"{Colors.DIM} | {Colors.RESET}")

        # Sections
        for section in self._sections:
            color = section.get("color", Colors.WHITE)
            parts.append(
                f" {color}{section['text']}{Colors.RESET} "
            )

        # Fill remaining space
        result = "".join(parts)
        clean_len = len(re.sub(r'\033\[[0-9;]*m', '', result))
        remaining = max(0, self.width - clean_len - len(self._right_text))

        result += " " * remaining

        # Right text
        if self._right_text:
            result += f"{Colors.DIM}{self._right_text}{Colors.RESET} "

        return result


class MarkdownRenderer:
    """Simplified Markdown renderer for terminal display.

    Renders Markdown text with ANSI formatting for headers,
    bold, italic, code, lists, and code blocks.
    """

    def __init__(self, width=80, color_enabled=True):
        """Initialize MarkdownRenderer.

        Args:
            width: Maximum render width.
            color_enabled: Whether to use ANSI colors.
        """
        self.width = width
        self.color_enabled = color_enabled
        if not color_enabled:
            Colors.disable()

    def render(self, text):
        """Render Markdown text to terminal-formatted lines.

        Args:
            text: Markdown-formatted text.

        Returns:
            List of formatted line strings.
        """
        if not text:
            return []

        lines = text.split("\n")
        output = []
        in_code_block = False

        for line in lines:
            # Code block toggle
            if line.strip().startswith("```"):
                if in_code_block:
                    output.append(f"{Colors.RESET}")
                    in_code_block = False
                else:
                    lang = line.strip()[3:].strip()
                    output.append(
                        f"{Colors.DIM}  {lang or 'code'}"
                        f"{'─' * max(1, 40 - len(lang))}{Colors.RESET}"
                    )
                    in_code_block = True
                continue

            if in_code_block:
                output.append(f"{Colors.YELLOW}  {line}{Colors.RESET}")
                continue

            # Headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2)
                output.append(self._render_header(title, level))
                continue

            # Horizontal rule
            if re.match(r'^---+\s*$', line.strip()):
                output.append(f"{Colors.DIM}{'─' * self.width}{Colors.RESET}")
                continue

            # Blockquote
            if line.strip().startswith(">"):
                content = line.strip()[1:].strip()
                output.append(
                    f"{Colors.DIM}│{Colors.RESET} "
                    f"{Colors.YELLOW}{content}{Colors.RESET}"
                )
                continue

            # List items
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

            # Inline formatting
            output.append(self._render_inline(line))

        return output

    def _render_header(self, title, level):
        """Render a Markdown header.

        Args:
            title: Header text.
            level: Header level (1-6).

        Returns:
            Formatted header string.
        """
        styles = {
            1: (Colors.BOLD + Colors.WHITE, "=" * min(60, self.width)),
            2: (Colors.BOLD + Colors.CYAN, "-" * min(50, self.width)),
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
        """Render inline Markdown formatting.

        Args:
            text: Text with inline Markdown.

        Returns:
            Formatted text string.
        """
        import re
        result = text

        # Inline code
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

        return result


# Need re for MarkdownRenderer
import re
