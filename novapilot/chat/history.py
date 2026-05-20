"""Chat history management for NovaPilot.

Handles persistent storage of conversation history in JSON format.
Supports multiple sessions, search, and export functionality.
"""

import json
import os
import time
import uuid
from datetime import datetime


class ChatHistory:
    """Manages chat conversation history with local JSON storage.

    Conversations are organized by sessions and stored in
    ~/.novapilot/history/ as individual JSON files.
    """

    def __init__(self, history_dir=None):
        """Initialize ChatHistory.

        Args:
            history_dir: Directory for history storage.
                         Defaults to ~/.novapilot/history/.
        """
        from novapilot.config import HISTORY_DIR
        self.history_dir = history_dir or HISTORY_DIR
        os.makedirs(self.history_dir, exist_ok=True)
        self._current_session_id = None
        self._current_messages = []

    def create_session(self, title=None):
        """Create a new chat session.

        Args:
            title: Optional session title. Auto-generated if not provided.

        Returns:
            Session ID string (UUID).
        """
        session_id = str(uuid.uuid4())[:8]
        session = {
            "id": session_id,
            "title": title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [],
        }
        self._save_session(session)
        self._current_session_id = session_id
        self._current_messages = []
        return session_id

    def _session_path(self, session_id):
        """Get the file path for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Absolute file path string.
        """
        return os.path.join(self.history_dir, f"{session_id}.json")

    def _save_session(self, session):
        """Save a session to disk.

        Args:
            session: Session dict with messages.
        """
        path = self._session_path(session["id"])
        session["updated_at"] = datetime.now().isoformat()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(session, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Failed to save session {session['id']}: {e}")

    def _load_session(self, session_id):
        """Load a session from disk.

        Args:
            session_id: Session identifier.

        Returns:
            Session dict, or None if not found.
        """
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def add_message(self, role, content, session_id=None, metadata=None):
        """Add a message to a session.

        Args:
            role: Message role ('user', 'assistant', 'system', 'tool').
            content: Message content string.
            session_id: Session ID. Uses current session if not specified.
            metadata: Optional dict with additional message metadata.

        Returns:
            Message dict that was added.
        """
        sid = session_id or self._current_session_id
        if not sid:
            sid = self.create_session()

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        session = self._load_session(sid)
        if session is None:
            session = {
                "id": sid,
                "title": f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": [],
            }

        session["messages"].append(message)
        self._save_session(session)

        if sid == self._current_session_id:
            self._current_messages = session["messages"]

        return message

    def get_messages(self, session_id=None, limit=None):
        """Get messages from a session.

        Args:
            session_id: Session ID. Uses current session if not specified.
            limit: Maximum number of messages to return. None for all.

        Returns:
            List of message dicts.
        """
        sid = session_id or self._current_session_id
        if not sid:
            return []

        session = self._load_session(sid)
        if session is None:
            return []

        messages = session.get("messages", [])
        if limit:
            messages = messages[-limit:]
        return messages

    def get_current_session_id(self):
        """Get the current active session ID.

        Returns:
            Current session ID string, or None if no active session.
        """
        return self._current_session_id

    def set_current_session(self, session_id):
        """Set the current active session.

        Args:
            session_id: Session ID to make active.

        Returns:
            True if successful, False if session not found.
        """
        session = self._load_session(session_id)
        if session is None:
            return False
        self._current_session_id = session_id
        self._current_messages = session.get("messages", [])
        return True

    def list_sessions(self, limit=20):
        """List all saved sessions, sorted by update time.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dicts.
        """
        sessions = []
        for filename in os.listdir(self.history_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.history_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    session = json.load(f)
                sessions.append({
                    "id": session.get("id", ""),
                    "title": session.get("title", "Untitled"),
                    "created_at": session.get("created_at", ""),
                    "updated_at": session.get("updated_at", ""),
                    "message_count": len(session.get("messages", [])),
                })
            except (json.JSONDecodeError, IOError):
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions[:limit]

    def search_sessions(self, query, limit=10):
        """Search sessions by content.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of matching session summaries with matched messages.
        """
        query_lower = query.lower()
        results = []

        for filename in os.listdir(self.history_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.history_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    session = json.load(f)

                messages = session.get("messages", [])
                matched_indices = []
                for i, msg in enumerate(messages):
                    if query_lower in msg.get("content", "").lower():
                        matched_indices.append(i)

                if matched_indices:
                    results.append({
                        "id": session.get("id", ""),
                        "title": session.get("title", "Untitled"),
                        "updated_at": session.get("updated_at", ""),
                        "message_count": len(messages),
                        "matched_count": len(matched_indices),
                        "matched_indices": matched_indices[:5],
                    })
            except (json.JSONDecodeError, IOError):
                continue

        results.sort(key=lambda r: r["matched_count"], reverse=True)
        return results[:limit]

    def delete_session(self, session_id):
        """Delete a session.

        Args:
            session_id: Session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return False

        try:
            os.remove(path)
            if self._current_session_id == session_id:
                self._current_session_id = None
                self._current_messages = []
            return True
        except IOError:
            return False

    def clear_all(self):
        """Delete all session history files.

        Returns:
            Number of sessions deleted.
        """
        count = 0
        for filename in os.listdir(self.history_dir):
            if filename.endswith(".json"):
                try:
                    os.remove(os.path.join(self.history_dir, filename))
                    count += 1
                except IOError:
                    continue
        self._current_session_id = None
        self._current_messages = []
        return count

    def export_session(self, session_id, format_type="markdown"):
        """Export a session to a specific format.

        Args:
            session_id: Session ID to export.
            format_type: Export format ('markdown' or 'json').

        Returns:
            String in the requested format.

        Raises:
            ValueError: If session not found or format unsupported.
        """
        session = self._load_session(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found.")

        if format_type == "json":
            return json.dumps(session, indent=2, ensure_ascii=False)

        elif format_type == "markdown":
            lines = [
                f"# {session.get('title', 'Untitled')}",
                f"",
                f"**Created:** {session.get('created_at', 'N/A')}  ",
                f"**Updated:** {session.get('updated_at', 'N/A')}  ",
                f"**Messages:** {len(session.get('messages', []))}",
                f"",
                "---",
                "",
            ]

            for msg in session.get("messages", []):
                role = msg.get("role", "unknown").capitalize()
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")

                lines.append(f"### {role}")
                if timestamp:
                    lines.append(f"*{timestamp}*")
                lines.append("")
                lines.append(content)
                lines.append("")
                lines.append("---")
                lines.append("")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    def get_session_stats(self):
        """Get statistics about all sessions.

        Returns:
            Dict with total sessions, total messages, and date range.
        """
        sessions = self.list_sessions(limit=1000)
        total_messages = sum(s["message_count"] for s in sessions)

        if sessions:
            dates = [s["updated_at"] for s in sessions if s["updated_at"]]
            newest = max(dates) if dates else "N/A"
            oldest = min(dates) if dates else "N/A"
        else:
            newest = "N/A"
            oldest = "N/A"

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "newest_session": newest,
            "oldest_session": oldest,
        }
