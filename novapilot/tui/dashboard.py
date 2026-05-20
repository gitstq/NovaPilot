"""TUI Dashboard for NovaPilot.

Provides a curses-based terminal user interface with a chat area,
input field, status bar, and real-time streaming output display.
"""

import os
import sys
import time
import threading
import signal

try:
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False

from novapilot.utils.logger import Colors


class Dashboard:
    """Curses-based TUI dashboard for NovaPilot.

    Features:
    - Split-pane layout: chat area (top) and input field (bottom)
    - Status bar with mode indicator and connection status
    - Real-time streaming output display
    - Keyboard shortcuts for common actions
    - Scrollable chat history
    - Color theme support
    """

    # Keyboard shortcut definitions
    SHORTCUTS = {
        "ctrl_c": "Cancel/Exit",
        "ctrl_l": "Clear screen",
        "ctrl_u": "Clear input",
        "ctrl_n": "New session",
        "ctrl_s": "Save session",
        "ctrl_h": "Help",
        "up": "History navigation",
        "down": "History navigation",
        "pgup": "Scroll chat up",
        "pgdn": "Scroll chat down",
        "enter": "Send message",
        "tab": "Auto-complete",
    }

    # Color theme definitions
    THEMES = {
        "dark": {
            "background": curses.COLOR_BLACK,
            "foreground": curses.COLOR_WHITE,
            "accent": curses.COLOR_CYAN,
            "error": curses.COLOR_RED,
            "warning": curses.COLOR_YELLOW,
            "success": curses.COLOR_GREEN,
            "input_bg": curses.COLOR_BLUE,
            "status_bg": curses.COLOR_BLACK,
            "border": curses.COLOR_BLUE,
        },
        "light": {
            "background": curses.COLOR_WHITE,
            "foreground": curses.COLOR_BLACK,
            "accent": curses.COLOR_BLUE,
            "error": curses.COLOR_RED,
            "warning": curses.COLOR_MAGENTA,
            "success": curses.COLOR_GREEN,
            "input_bg": curses.COLOR_CYAN,
            "status_bg": curses.COLOR_WHITE,
            "border": curses.COLOR_BLACK,
        },
    }

    def __init__(self, chat_engine=None, config=None):
        """Initialize Dashboard.

        Args:
            chat_engine: ChatEngine instance for sending messages.
            config: Configuration dict with theme and display settings.
        """
        self.chat_engine = chat_engine
        self.config = config or {}
        self.theme_name = self.config.get("theme", "dark")
        self.color_enabled = self.config.get("color_enabled", True)

        # State
        self._running = False
        self._input_text = ""
        self._cursor_pos = 0
        self._chat_lines = []
        self._chat_scroll = 0
        self._input_history = []
        self._history_index = -1
        self._status_message = "Ready"
        self._status_color = "info"
        self._mode = "NORMAL"
        self._streaming = False
        self._stream_buffer = ""
        self._stream_lock = threading.Lock()

        # Curses state
        self._stdscr = None
        self._chat_win = None
        self._input_win = None
        self._status_win = None
        self._color_pairs = {}

    def _init_colors(self):
        """Initialize curses color pairs based on the selected theme."""
        if not curses.has_colors():
            return

        curses.start_color()
        curses.use_default_colors()

        theme = self.THEMES.get(self.theme_name, self.THEMES["dark"])

        # Define color pairs: (pair_id, foreground, background)
        pairs = {
            "normal": (1, theme["foreground"], theme["background"]),
            "accent": (2, theme["accent"], theme["background"]),
            "error": (3, theme["error"], theme["background"]),
            "warning": (4, theme["warning"], theme["background"]),
            "success": (5, theme["success"], theme["background"]),
            "input": (6, theme["foreground"], theme["input_bg"]),
            "status": (7, theme["foreground"], theme["status_bg"]),
            "border": (8, theme["border"], theme["background"]),
            "dim": (9, curses.COLOR_GRAY if curses.COLOR_GRAY else 8,
                     theme["background"]),
            "user_msg": (10, curses.COLOR_CYAN, theme["background"]),
            "bot_msg": (11, curses.COLOR_GREEN, theme["background"]),
        }

        for name, (pair_id, fg, bg) in pairs.items():
            try:
                curses.init_pair(pair_id, fg, bg)
                self._color_pairs[name] = pair_id
            except curses.error:
                pass

    def _get_color(self, name):
        """Get the curses color attribute for a named color.

        Args:
            name: Color pair name.

        Returns:
            Curses color attribute integer.
        """
        pair_id = self._color_pairs.get(name, 0)
        return curses.color_pair(pair_id)

    def _setup_windows(self):
        """Create and arrange the curses windows.

        Layout:
        - Chat area: top portion (height - 3 lines)
        - Input field: 1 line above status bar
        - Status bar: bottom line
        """
        max_y, max_x = self._stdscr.getmaxyx()

        # Chat window (top portion)
        chat_height = max(1, max_y - 3)
        self._chat_win = curses.newwin(chat_height, max_x, 0, 0)
        self._chat_win.scrollok(True)
        self._chat_win.idlok(True)

        # Input window (1 line)
        self._input_win = curses.newwin(1, max_x, chat_height, 0)

        # Status bar (bottom line)
        self._status_win = curses.newwin(1, max_x, max_y - 1, 0)

    def _draw_chat(self):
        """Render the chat area with all messages."""
        if not self._chat_win:
            return

        self._chat_win.erase()
        max_y, max_x = self._chat_win.getmaxyx()

        # Calculate visible range
        total_lines = len(self._chat_lines)
        visible_lines = max_y
        start = max(0, total_lines - visible_lines - self._chat_scroll)

        for i, line in enumerate(self._chat_lines[start:start + visible_lines]):
            try:
                if line.startswith("[USER]"):
                    self._chat_win.addstr(
                        i, 0, line[:max_x - 1],
                        self._get_color("user_msg")
                    )
                elif line.startswith("[BOT]"):
                    self._chat_win.addstr(
                        i, 0, line[:max_x - 1],
                        self._get_color("bot_msg")
                    )
                elif line.startswith("[ERR"):
                    self._chat_win.addstr(
                        i, 0, line[:max_x - 1],
                        self._get_color("error")
                    )
                elif line.startswith("[SYS"):
                    self._chat_win.addstr(
                        i, 0, line[:max_x - 1],
                        self._get_color("dim")
                    )
                else:
                    self._chat_win.addstr(
                        i, 0, line[:max_x - 1],
                        self._get_color("normal")
                    )
            except curses.error:
                pass

        self._chat_win.refresh()

    def _draw_input(self):
        """Render the input field with cursor."""
        if not self._input_win:
            return

        self._input_win.erase()
        max_y, max_x = self._input_win.getmaxyx()

        # Draw prompt
        prompt = "> " if not self._streaming else "... "
        try:
            self._input_win.addstr(0, 0, prompt, self._get_color("accent"))
        except curses.error:
            pass

        # Draw input text
        display_text = self._input_text
        available_width = max_x - len(prompt) - 1

        # Truncate if too long
        if len(display_text) > available_width:
            offset = len(display_text) - available_width
            display_text = display_text[offset:]

        try:
            self._input_win.addstr(
                0, len(prompt), display_text,
                self._get_color("input")
            )
        except curses.error:
            pass

        # Position cursor
        cursor_x = min(self._cursor_pos, len(self._input_text))
        if cursor_x > available_width:
            cursor_x = available_width
        try:
            self._input_win.move(0, len(prompt) + cursor_x)
        except curses.error:
            pass

        self._input_win.refresh()

    def _draw_status(self):
        """Render the status bar."""
        if not self._status_win:
            return

        self._status_win.erase()
        max_y, max_x = self._status_win.getmaxyx()

        # Mode indicator
        mode_text = f" {self._mode} "
        try:
            self._status_win.addstr(
                0, 0, mode_text,
                self._get_color("accent") | curses.A_BOLD
            )
        except curses.error:
            pass

        # Status message
        status_colors = {
            "info": "normal",
            "success": "success",
            "warning": "warning",
            "error": "error",
        }
        color_name = status_colors.get(self._status_color, "normal")
        status_text = f" {self._status_message} "

        try:
            self._status_win.addstr(
                0, len(mode_text), status_text,
                self._get_color(color_name)
            )
        except curses.error:
            pass

        # Right side info
        backend = "N/A"
        if self.chat_engine and hasattr(self.chat_engine, "router"):
            backends = self.chat_engine.router.list_backends()
            if backends:
                backend = backends[0].get("name", "N/A")

        right_text = f" Backend: {backend} | Ctrl+H: Help "
        right_x = max(0, max_x - len(right_text))

        try:
            self._status_win.addstr(
                0, right_x, right_text,
                self._get_color("dim")
            )
        except curses.error:
            pass

        self._status_win.refresh()

    def _refresh_all(self):
        """Refresh all windows."""
        self._draw_chat()
        self._draw_input()
        self._draw_status()

    def _add_chat_line(self, text):
        """Add a line to the chat display.

        Args:
            text: Line text to add.
        """
        # Wrap long lines
        max_x = 80
        if self._chat_win:
            max_x = self._chat_win.getmaxyx()[1]

        while len(text) > max_x:
            self._chat_lines.append(text[:max_x])
            text = text[max_x:]
        self._chat_lines.append(text)

        # Auto-scroll to bottom
        self._chat_scroll = 0
        self._draw_chat()

    def _set_status(self, message, color="info"):
        """Update the status bar message.

        Args:
            message: Status text.
            color: Status color ('info', 'success', 'warning', 'error').
        """
        self._status_message = message
        self._status_color = color
        self._draw_status()

    def _send_message(self):
        """Send the current input as a chat message."""
        text = self._input_text.strip()
        if not text or not self.chat_engine:
            return

        # Add to input history
        self._input_history.append(text)
        self._history_index = -1

        # Display user message
        self._add_chat_line(f"[USER] {text}")

        # Clear input
        self._input_text = ""
        self._cursor_pos = 0
        self._draw_input()

        # Check for commands
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Send to chat engine
        self._set_status("Thinking...", "warning")
        self._streaming = True
        self._draw_input()

        try:
            response_text = ""
            for chunk in self.chat_engine.send(text, stream=True):
                with self._stream_lock:
                    response_text += chunk
                    # Update display with streaming text
                    if chunk:
                        self._add_chat_line(f"[BOT] {chunk}")

            self._streaming = False
            self._set_status("Ready", "success")
        except Exception as e:
            self._streaming = False
            self._add_chat_line(f"[ERROR] {e}")
            self._set_status(f"Error: {e}", "error")

        self._draw_input()

    def _handle_command(self, text):
        """Handle slash commands.

        Args:
            text: Command string starting with '/'.
        """
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            self._show_help()
        elif command == "/clear":
            self._chat_lines.clear()
            self._chat_scroll = 0
            self._add_chat_line("[SYS] Chat cleared.")
        elif command == "/new":
            if self.chat_engine:
                self.chat_engine.new_session()
            self._chat_lines.clear()
            self._add_chat_line("[SYS] New session started.")
            self._set_status("New session", "success")
        elif command == "/history":
            sessions = self.chat_engine.history.list_sessions(limit=5) if self.chat_engine else []
            self._add_chat_line("[SYS] Recent sessions:")
            for s in sessions:
                self._add_chat_line(f"  {s['id']} - {s['title']} ({s['message_count']} msgs)")
        elif command == "/quit":
            self._running = False
        elif command == "/backend":
            if self.chat_engine and hasattr(self.chat_engine, "router"):
                backends = self.chat_engine.router.list_backends()
                self._add_chat_line("[SYS] Available backends:")
                for b in backends:
                    status = "OK" if b.get("healthy") else "DOWN"
                    self._add_chat_line(
                        f"  {b['name']} ({b['type']}) - {b['model']} [{status}]"
                    )
            else:
                self._add_chat_line("[SYS] No router configured.")
        elif command == "/theme":
            if args in self.THEMES:
                self.theme_name = args
                self._init_colors()
                self._add_chat_line(f"[SYS] Theme changed to '{args}'.")
            else:
                available = ", ".join(self.THEMES.keys())
                self._add_chat_line(f"[SYS] Available themes: {available}")
        else:
            self._add_chat_line(f"[SYS] Unknown command: {command}. Type /help for commands.")

    def _show_help(self):
        """Display help information in the chat area."""
        self._add_chat_line("[SYS] === NovaPilot Help ===")
        self._add_chat_line("[SYS] Commands:")
        self._add_chat_line("[SYS]   /help    - Show this help")
        self._add_chat_line("[SYS]   /clear   - Clear chat")
        self._add_chat_line("[SYS]   /new     - New session")
        self._add_chat_line("[SYS]   /history - List sessions")
        self._add_chat_line("[SYS]   /backend - Show backends")
        self._add_chat_line("[SYS]   /theme   - Change theme")
        self._add_chat_line("[SYS]   /quit    - Exit")
        self._add_chat_line("[SYS] Shortcuts:")
        for key, desc in self.SHORTCUTS.items():
            self._add_chat_line(f"[SYS]   {key:<12} - {desc}")

    def _handle_key(self, key):
        """Handle a key press event.

        Args:
            key: Key code from curses.getch().
        """
        if key == curses.KEY_ENTER or key == 10 or key == 13:
            self._send_message()

        elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            if self._cursor_pos > 0:
                self._input_text = (
                    self._input_text[:self._cursor_pos - 1]
                    + self._input_text[self._cursor_pos:]
                )
                self._cursor_pos -= 1

        elif key == curses.KEY_LEFT:
            if self._cursor_pos > 0:
                self._cursor_pos -= 1

        elif key == curses.KEY_RIGHT:
            if self._cursor_pos < len(self._input_text):
                self._cursor_pos += 1

        elif key == curses.KEY_UP:
            if self._input_history:
                if self._history_index < len(self._input_history) - 1:
                    self._history_index += 1
                    self._input_text = self._input_history[-(self._history_index + 1)]
                    self._cursor_pos = len(self._input_text)

        elif key == curses.KEY_DOWN:
            if self._history_index > 0:
                self._history_index -= 1
                self._input_text = self._input_history[-(self._history_index + 1)]
                self._cursor_pos = len(self._input_text)
            elif self._history_index == 0:
                self._history_index = -1
                self._input_text = ""
                self._cursor_pos = 0

        elif key == curses.KEY_PPAGE:  # Page Up
            self._chat_scroll += 5
            self._draw_chat()

        elif key == curses.KEY_NPAGE:  # Page Down
            self._chat_scroll = max(0, self._chat_scroll - 5)
            self._draw_chat()

        elif key == curses.KEY_HOME:
            self._cursor_pos = 0

        elif key == curses.KEY_END:
            self._cursor_pos = len(self._input_text)

        elif key == 3:  # Ctrl+C
            if self._streaming:
                self._streaming = False
                self._set_status("Cancelled", "warning")
            else:
                self._running = False

        elif key == 12:  # Ctrl+L
            self._chat_lines.clear()
            self._chat_scroll = 0
            self._add_chat_line("[SYS] Screen cleared.")

        elif key == 21:  # Ctrl+U
            self._input_text = ""
            self._cursor_pos = 0

        elif key == 14:  # Ctrl+N
            self._handle_command("/new")

        elif key == 19:  # Ctrl+S
            self._set_status("Session saved", "success")

        elif key == 8:  # Ctrl+H
            self._show_help()

        elif key == 9:  # Tab
            # Simple auto-complete for commands
            if self._input_text.startswith("/"):
                prefix = self._input_text.lower()
                commands = ["/help", "/clear", "/new", "/history",
                            "/backend", "/theme", "/quit"]
                matches = [c for c in commands if c.startswith(prefix)]
                if len(matches) == 1:
                    self._input_text = matches[0] + " "
                    self._cursor_pos = len(self._input_text)

        elif 32 <= key <= 126:  # Printable characters
            char = chr(key)
            self._input_text = (
                self._input_text[:self._cursor_pos]
                + char
                + self._input_text[self._cursor_pos:]
            )
            self._cursor_pos += 1

        self._draw_input()

    def run(self):
        """Start the TUI dashboard main loop.

        This is the primary entry point for the dashboard.
        Initializes curses, sets up windows, and runs the
        input handling loop.
        """
        if not CURSES_AVAILABLE:
            print("Error: curses module is not available on this platform.")
            print("Falling back to simple interactive mode.")
            self._run_simple_mode()
            return

        try:
            curses.wrapper(self._curses_main)
        except Exception as e:
            print(f"\nDashboard error: {e}")

    def _curses_main(self, stdscr):
        """Curses main function (called via curses.wrapper).

        Args:
            stdscr: Main curses window.
        """
        self._stdscr = stdscr
        curses.curs_set(1)
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)

        # Handle terminal resize
        signal.signal(signal.SIGWINCH, self._handle_resize)

        # Initialize
        self._init_colors()
        self._setup_windows()

        # Welcome message
        self._add_chat_line("[SYS] Welcome to NovaPilot!")
        self._add_chat_line("[SYS] Type /help for commands and shortcuts.")
        self._add_chat_line("")

        self._running = True
        self._refresh_all()

        # Main loop
        while self._running:
            try:
                key = self._stdscr.getch()
                if key != -1:
                    self._handle_key(key)
            except curses.error:
                continue

        # Cleanup
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    def _handle_resize(self, signum, frame):
        """Handle terminal resize signal.

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        if self._stdscr:
            curses.resizeterm(*self._stdscr.getmaxyx())
            self._setup_windows()
            self._refresh_all()

    def _run_simple_mode(self):
        """Fallback simple interactive mode when curses is not available.

        Provides basic chat functionality using standard I/O.
        """
        print(f"\n{Colors.BOLD}NovaPilot - Simple Mode{Colors.RESET}")
        print(f"Type /help for commands. Type /quit to exit.\n")

        self._running = True

        while self._running:
            try:
                prompt = f"{Colors.CYAN}> {Colors.RESET}"
                text = input(prompt).strip()

                if not text:
                    continue

                if text.startswith("/"):
                    self._handle_command(text)
                    # Also print to stdout in simple mode
                    if text == "/help":
                        self._show_help()
                    continue

                # Send message
                print(f"{Colors.CYAN}[You]{Colors.RESET} {text}")

                if self.chat_engine:
                    try:
                        self._set_status("Thinking...", "warning")
                        response = ""
                        for chunk in self.chat_engine.send(text, stream=True):
                            response += chunk
                            print(chunk, end="", flush=True)
                        print()
                        self._set_status("Ready", "success")
                    except Exception as e:
                        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}[Warning] No chat engine configured.{Colors.RESET}")

            except (KeyboardInterrupt, EOFError):
                print()
                self._running = False

        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
