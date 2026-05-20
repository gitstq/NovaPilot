"""Logging utility for NovaPilot.

Provides multi-level logging with both file and terminal output,
colored log messages, and automatic log rotation.
"""

import os
import sys
import time
import threading
from datetime import datetime


# ANSI color codes for terminal output
class Colors:
    """ANSI color escape codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @staticmethod
    def disable():
        """Disable all colors by resetting to empty strings."""
        Colors.RESET = ""
        Colors.BOLD = ""
        Colors.DIM = ""
        Colors.BLACK = ""
        Colors.RED = ""
        Colors.GREEN = ""
        Colors.YELLOW = ""
        Colors.BLUE = ""
        Colors.MAGENTA = ""
        Colors.CYAN = ""
        Colors.WHITE = ""
        Colors.GRAY = ""
        Colors.BG_RED = ""
        Colors.BG_GREEN = ""
        Colors.BG_YELLOW = ""
        Colors.BG_BLUE = ""


# Log level definitions
LOG_LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

# Color mapping for each log level
LEVEL_COLORS = {
    "DEBUG": Colors.CYAN,
    "INFO": Colors.GREEN,
    "WARNING": Colors.YELLOW,
    "ERROR": Colors.RED,
    "CRITICAL": Colors.BG_RED + Colors.WHITE + Colors.BOLD,
}


class Logger:
    """Multi-output logger with colored terminal support and file logging.

    Supports both terminal (stderr) and file output simultaneously.
    Includes automatic log file rotation based on size.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, name="NovaPilot", log_file=None, level="INFO",
                color_enabled=True):
        """Singleton pattern for Logger.

        Args:
            name: Logger name prefix.
            log_file: Path to log file. Defaults to ~/.novapilot/novapilot.log.
            level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            color_enabled: Whether to use colored output in terminal.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, name="NovaPilot", log_file=None, level="INFO",
                 color_enabled=True):
        """Initialize the Logger.

        Args:
            name: Logger name prefix.
            log_file: Path to log file. Defaults to ~/.novapilot/novapilot.log.
            level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            color_enabled: Whether to use colored output in terminal.
        """
        if self._initialized:
            return

        self._name = name
        self._level = LOG_LEVELS.get(level.upper(), LOG_LEVELS["INFO"])
        self._color_enabled = color_enabled
        self._file_handle = None
        self._max_file_size = 5 * 1024 * 1024  # 5MB rotation size
        self._lock = threading.Lock()

        if not color_enabled:
            Colors.disable()

        # Set up file logging
        if log_file is None:
            from novapilot.config import LOG_PATH
            log_file = LOG_PATH

        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        try:
            self._file_handle = open(log_file, "a", encoding="utf-8")
        except IOError:
            self._file_handle = None

        self._initialized = True

    def _rotate_log(self):
        """Rotate log file if it exceeds the maximum size."""
        if self._file_handle is None:
            return

        try:
            self._file_handle.flush()
            file_size = os.fstat(self._file_handle.fileno()).st_size
            if file_size > self._max_file_size:
                self._file_handle.close()
                log_path = self._file_handle.name if hasattr(self._file_handle, 'name') else None
                if log_path and os.path.exists(log_path):
                    backup_path = log_path + ".1"
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    os.rename(log_path, backup_path)
                self._file_handle = open(log_path, "a", encoding="utf-8")
        except (IOError, OSError):
            pass

    def _format_message(self, level, message, source=""):
        """Format a log message with timestamp, level, and source.

        Args:
            level: Log level string.
            message: Log message content.
            source: Optional source module name.

        Returns:
            Tuple of (terminal_formatted, file_formatted) strings.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_str = f"[{level:>8s}]"
        source_str = f"[{source}] " if source else ""

        # File format (plain text)
        file_msg = f"{timestamp} {level_str} {source_str}{message}\n"

        # Terminal format (colored)
        color = LEVEL_COLORS.get(level, Colors.WHITE)
        terminal_msg = (
            f"{Colors.DIM}{timestamp}{Colors.RESET} "
            f"{color}{level_str}{Colors.RESET} "
            f"{Colors.BLUE}{source_str}{Colors.RESET}"
            f"{message}{Colors.RESET}\n"
        )

        return terminal_msg, file_msg

    def _log(self, level, message, source=""):
        """Internal logging method.

        Args:
            level: Log level string.
            message: Log message content.
            source: Optional source module name.
        """
        if LOG_LEVELS.get(level, 0) < self._level:
            return

        terminal_msg, file_msg = self._format_message(level, message, source)

        with self._lock:
            # Write to terminal (stderr)
            sys.stderr.write(terminal_msg)
            sys.stderr.flush()

            # Write to file
            if self._file_handle:
                try:
                    self._file_handle.write(file_msg)
                    self._file_handle.flush()
                    self._rotate_log()
                except (IOError, OSError):
                    pass

    def debug(self, message, source=""):
        """Log a DEBUG level message.

        Args:
            message: Log message content.
            source: Optional source module name.
        """
        self._log("DEBUG", message, source)

    def info(self, message, source=""):
        """Log an INFO level message.

        Args:
            message: Log message content.
            source: Optional source module name.
        """
        self._log("INFO", message, source)

    def warning(self, message, source=""):
        """Log a WARNING level message.

        Args:
            message: Log message content.
            source: Optional source module name.
        """
        self._log("WARNING", message, source)

    def error(self, message, source=""):
        """Log an ERROR level message.

        Args:
            message: Log message content.
            source: Optional source module name.
        """
        self._log("ERROR", message, source)

    def critical(self, message, source=""):
        """Log a CRITICAL level message.

        Args:
            message: Log message content.
            source: Optional source module name.
        """
        self._log("CRITICAL", message, source)

    def set_level(self, level):
        """Set the minimum log level.

        Args:
            level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        """
        self._level = LOG_LEVELS.get(level.upper(), LOG_LEVELS["INFO"])

    def close(self):
        """Close the log file handle."""
        with self._lock:
            if self._file_handle:
                try:
                    self._file_handle.close()
                except IOError:
                    pass
                self._file_handle = None

    def __del__(self):
        """Destructor to ensure file handle is closed."""
        self.close()


def get_logger(name="NovaPilot", level="INFO", color_enabled=True):
    """Get or create a Logger instance.

    Args:
        name: Logger name prefix.
        level: Minimum log level.
        color_enabled: Whether to use colored output.

    Returns:
        Logger instance.
    """
    return Logger(name=name, level=level, color_enabled=color_enabled)
