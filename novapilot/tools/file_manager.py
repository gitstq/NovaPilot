"""File management tool for NovaPilot.

Provides file read/write operations, directory browsing with tree view,
file search capabilities, and file type detection.
Includes security measures to prevent path traversal attacks.
"""

import os
import re
import stat
import time
from datetime import datetime


# File type categories
FILE_CATEGORIES = {
    "code": {
        "extensions": {
            ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp",
            ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
            ".scala", ".r", ".lua", ".pl", ".sh", ".bash", ".zsh", ".ps1",
            ".html", ".css", ".scss", ".sass", ".less", ".sql", ".graphql",
        },
    },
    "data": {
        "extensions": {
            ".json", ".xml", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".ini",
            ".cfg", ".conf", ".env", ".properties",
        },
    },
    "document": {
        "extensions": {
            ".md", ".txt", ".rst", ".tex", ".pdf", ".doc", ".docx", ".odt",
            ".rtf",
        },
    },
    "image": {
        "extensions": {
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp",
            ".tiff", ".tif",
        },
    },
    "archive": {
        "extensions": {
            ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz",
        },
    },
    "executable": {
        "extensions": {
            ".exe", ".msi", ".dmg", ".app", ".deb", ".rpm", ".bin",
        },
    },
}


class FileManager:
    """File management tool with security features.

    Provides safe file operations with path traversal protection,
    file type detection, and directory browsing capabilities.
    """

    # Trigger patterns for automatic tool activation
    trigger_patterns = [
        "read file", "write file", "list files", "browse",
        "search file", "find file", "directory", "tree",
    ]

    def __init__(self, allowed_root=None):
        """Initialize FileManager.

        Args:
            allowed_root: Root directory path that constrains all file operations.
                          If None, the current working directory is used.
        """
        self.allowed_root = os.path.abspath(allowed_root or os.getcwd())

    def _check_path(self, path):
        """Validate that a path is within the allowed root directory.

        Prevents path traversal attacks using '..' and symlinks.

        Args:
            path: Path to validate.

        Returns:
            Absolute, validated path string.

        Raises:
            ValueError: If the path is outside the allowed root or is a symlink.
        """
        if not path:
            raise ValueError("Path cannot be empty.")

        # Resolve to absolute path
        abs_path = os.path.abspath(path)

        # Check for symlinks
        if os.path.islink(abs_path):
            real_path = os.path.realpath(abs_path)
            if not real_path.startswith(self.allowed_root):
                raise ValueError(
                    f"Access denied: symlink target '{real_path}' "
                    f"is outside allowed directory."
                )

        # Check that resolved path is within allowed root
        if not abs_path.startswith(self.allowed_root):
            raise ValueError(
                f"Access denied: '{path}' is outside the allowed directory."
            )

        return abs_path

    def read_file(self, path, encoding="utf-8", max_lines=None):
        """Read file contents safely.

        Args:
            path: File path to read.
            encoding: File encoding (default: utf-8).
            max_lines: Maximum number of lines to read. None for all.

        Returns:
            File contents string.

        Raises:
            ValueError: If path is invalid.
            IOError: If file cannot be read.
        """
        safe_path = self._check_path(path)

        if not os.path.isfile(safe_path):
            raise IOError(f"Not a file: {safe_path}")

        try:
            with open(safe_path, "r", encoding=encoding, errors="replace") as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    return "".join(lines)
                return f.read()
        except IOError as e:
            raise IOError(f"Failed to read file '{safe_path}': {e}")

    def write_file(self, path, content, encoding="utf-8"):
        """Write content to a file safely.

        Args:
            path: File path to write.
            content: Content string to write.
            encoding: File encoding (default: utf-8).

        Returns:
            Number of bytes written.

        Raises:
            ValueError: If path is invalid.
            IOError: If file cannot be written.
        """
        safe_path = self._check_path(path)

        # Ensure parent directory exists
        parent_dir = os.path.dirname(safe_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        try:
            with open(safe_path, "w", encoding=encoding) as f:
                f.write(content)
            return len(content.encode(encoding))
        except IOError as e:
            raise IOError(f"Failed to write file '{safe_path}': {e}")

    def list_directory(self, path=".", show_hidden=False):
        """List directory contents with file metadata.

        Args:
            path: Directory path to list.
            show_hidden: Whether to show hidden files.

        Returns:
            List of file info dicts with name, type, size, modified time.

        Raises:
            ValueError: If path is invalid.
            IOError: If directory cannot be read.
        """
        safe_path = self._check_path(path)

        if not os.path.isdir(safe_path):
            raise IOError(f"Not a directory: {safe_path}")

        entries = []
        try:
            for entry in sorted(os.listdir(safe_path)):
                if not show_hidden and entry.startswith("."):
                    continue

                full_path = os.path.join(safe_path, entry)
                try:
                    file_stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    entries.append({
                        "name": entry,
                        "type": "directory" if is_dir else "file",
                        "size": file_stat.st_size if not is_dir else 0,
                        "modified": datetime.fromtimestamp(
                            file_stat.st_mtime
                        ).isoformat(),
                        "permissions": stat.filemode(file_stat.st_mode),
                    })
                except (OSError, IOError):
                    entries.append({
                        "name": entry,
                        "type": "unknown",
                        "size": 0,
                        "modified": "unknown",
                        "permissions": "---------",
                    })
        except IOError as e:
            raise IOError(f"Failed to list directory '{safe_path}': {e}")

        return entries

    def tree(self, path=".", max_depth=5, show_hidden=False):
        """Generate a tree view of a directory structure.

        Args:
            path: Root directory path.
            max_depth: Maximum depth to traverse.
            show_hidden: Whether to show hidden files.

        Returns:
            Tree-formatted string.

        Raises:
            ValueError: If path is invalid.
        """
        safe_path = self._check_path(path)

        if not os.path.isdir(safe_path):
            return f"Not a directory: {safe_path}"

        lines = [os.path.basename(safe_path) or safe_path]
        self._build_tree(safe_path, lines, "", max_depth, 0, show_hidden)
        return "\n".join(lines)

    def _build_tree(self, path, lines, prefix, max_depth, current_depth,
                    show_hidden):
        """Recursively build tree structure.

        Args:
            path: Current directory path.
            lines: Accumulated output lines.
            prefix: Current line prefix for tree connectors.
            max_depth: Maximum traversal depth.
            current_depth: Current traversal depth.
            show_hidden: Whether to show hidden files.
        """
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(os.listdir(path))
        except (OSError, IOError):
            return

        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]

        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            full_path = os.path.join(path, entry)

            if os.path.isdir(full_path):
                lines.append(f"{prefix}{connector}{entry}/")
                self._build_tree(
                    full_path, lines, child_prefix,
                    max_depth, current_depth + 1, show_hidden
                )
            else:
                size = os.path.getsize(full_path)
                size_str = self._format_size(size)
                lines.append(f"{prefix}{connector}{entry} ({size_str})")

    def _format_size(self, size):
        """Format file size in human-readable format.

        Args:
            size: File size in bytes.

        Returns:
            Formatted size string (e.g., '1.5 KB', '2.3 MB').
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def search_files(self, path=".", pattern="", by_content=False,
                     extension=None, max_results=50):
        """Search for files by name, content, or extension.

        Args:
            path: Root directory to search in.
            pattern: Search pattern (regex supported).
            by_content: If True, search file contents instead of names.
            extension: Filter by file extension (e.g., '.py').
            max_results: Maximum number of results.

        Returns:
            List of dicts with file path and matching info.
        """
        safe_path = self._check_path(path)
        results = []
        regex = None

        if pattern:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                regex = re.compile(re.escape(pattern), re.IGNORECASE)

        for root, dirs, files in os.walk(safe_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                # Filter by extension
                if extension:
                    ext = self._get_extension(filename)
                    if ext != extension.lower():
                        continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, safe_path)

                match_info = None

                if by_content and regex:
                    # Search file contents
                    try:
                        with open(full_path, "r", encoding="utf-8",
                                  errors="replace") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    match_info = {
                                        "line": line_num,
                                        "preview": line.strip()[:100],
                                    }
                                    break
                    except (IOError, OSError):
                        continue
                elif regex:
                    # Search filename
                    if regex.search(filename):
                        match_info = {"matched_name": filename}
                else:
                    match_info = {"matched_name": filename}

                if match_info:
                    results.append({
                        "path": rel_path,
                        "full_path": full_path,
                        "size": os.path.getsize(full_path),
                        **match_info,
                    })

                    if len(results) >= max_results:
                        return results

        return results

    def _get_extension(self, filename):
        """Get lowercase file extension.

        Args:
            filename: File name string.

        Returns:
            Lowercase extension string with dot, or empty string.
        """
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""

    def detect_file_type(self, path):
        """Detect the category of a file based on its extension.

        Args:
            path: File path.

        Returns:
            Category string ('code', 'data', 'document', 'image',
            'archive', 'executable', 'unknown').
        """
        ext = self._get_extension(path)
        for category, info in FILE_CATEGORIES.items():
            if ext in info["extensions"]:
                return category
        return "unknown"

    def get_file_info(self, path):
        """Get detailed information about a file or directory.

        Args:
            path: File or directory path.

        Returns:
            Dict with file metadata.

        Raises:
            ValueError: If path is invalid.
            IOError: If path does not exist.
        """
        safe_path = self._check_path(path)

        if not os.path.exists(safe_path):
            raise IOError(f"Path does not exist: {safe_path}")

        file_stat = os.stat(safe_path)
        is_dir = os.path.isdir(safe_path)
        is_file = os.path.isfile(safe_path)

        info = {
            "path": safe_path,
            "name": os.path.basename(safe_path),
            "type": "directory" if is_dir else "file" if is_file else "other",
            "size": file_stat.st_size,
            "size_formatted": self._format_size(file_stat.st_size),
            "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(file_stat.st_atime).isoformat(),
            "permissions": stat.filemode(file_stat.st_mode),
            "file_type": self.detect_file_type(safe_path) if is_file else "directory",
        }

        if is_file:
            info["extension"] = self._get_extension(safe_path)

        return info

    def execute(self, args):
        """Execute file management operation (tool interface).

        Args:
            args: Dict with 'action' key and relevant parameters.
                  Actions: read, write, list, tree, search, info.

        Returns:
            Result string.
        """
        if isinstance(args, str):
            args = {"action": "info", "path": args}

        action = args.get("action", "info")

        try:
            if action == "read":
                content = self.read_file(
                    args["path"],
                    max_lines=args.get("max_lines"),
                )
                return content

            elif action == "write":
                bytes_written = self.write_file(
                    args["path"], args["content"]
                )
                return f"Written {bytes_written} bytes to {args['path']}"

            elif action == "list":
                entries = self.list_directory(
                    args.get("path", "."),
                    show_hidden=args.get("show_hidden", False),
                )
                lines = []
                for entry in entries:
                    type_char = "d" if entry["type"] == "directory" else "f"
                    size = self._format_size(entry["size"])
                    lines.append(
                        f"  {type_char} {entry['permissions']} "
                        f"{size:>10}  {entry['modified']}  {entry['name']}"
                    )
                return "\n".join(lines) if lines else "Empty directory."

            elif action == "tree":
                return self.tree(
                    args.get("path", "."),
                    max_depth=args.get("max_depth", 5),
                )

            elif action == "search":
                results = self.search_files(
                    path=args.get("path", "."),
                    pattern=args.get("pattern", ""),
                    by_content=args.get("by_content", False),
                    extension=args.get("extension"),
                    max_results=args.get("max_results", 50),
                )
                if not results:
                    return "No files found."
                lines = []
                for r in results:
                    if "matched_name" in r:
                        lines.append(f"  {r['path']}")
                    elif "line" in r:
                        lines.append(
                            f"  {r['path']}:{r['line']}: {r.get('preview', '')}"
                        )
                return "\n".join(lines)

            elif action == "info":
                info = self.get_file_info(args.get("path", "."))
                lines = [
                    f"  Path:         {info['path']}",
                    f"  Type:         {info['type']} ({info['file_type']})",
                    f"  Size:         {info['size_formatted']}",
                    f"  Permissions:  {info['permissions']}",
                    f"  Created:      {info['created']}",
                    f"  Modified:     {info['modified']}",
                ]
                if "extension" in info:
                    lines.append(f"  Extension:    {info['extension']}")
                return "\n".join(lines)

            else:
                return f"Unknown action: {action}. Use: read, write, list, tree, search, info."

        except (ValueError, IOError) as e:
            return f"Error: {e}"
