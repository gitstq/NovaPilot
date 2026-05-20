"""Persistent memory storage for NovaPilot.

Handles JSON-based storage of memory entries with support for
incremental indexing, data compression, and import/export.
"""

import json
import os
import time
import gzip
import uuid
from datetime import datetime


class MemoryStore:
    """JSON-based persistent memory storage.

    Stores memory entries in a JSON file with support for
    metadata, categories, timestamps, and full CRUD operations.
    """

    def __init__(self, store_path=None):
        """Initialize MemoryStore.

        Args:
            store_path: Path to the JSON storage file.
                        Defaults to ~/.novapilot/memory.json.
        """
        from novapilot.config import MEMORY_PATH, NOVAPILOT_DIR
        self.store_path = store_path or MEMORY_PATH
        self._data = {
            "version": "0.1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "entries": [],
            "index": {},
        }
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        self._load()

    def _load(self):
        """Load memory data from disk.

        Creates a new empty store if the file doesn't exist.
        Handles corrupted files gracefully.
        """
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # Validate structure
                if isinstance(loaded, dict) and "entries" in loaded:
                    self._data = loaded
                else:
                    self._save()
            except (json.JSONDecodeError, IOError):
                # Corrupted file - start fresh
                self._save()
        else:
            self._save()

    def _save(self):
        """Save memory data to disk."""
        self._data["updated_at"] = datetime.now().isoformat()
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Failed to save memory store: {e}")

    def add(self, content, category="general", tags=None, metadata=None):
        """Add a new memory entry.

        Args:
            content: Memory content string.
            category: Category ('conversation', 'knowledge', 'task', 'general').
            tags: Optional list of tag strings.
            metadata: Optional dict of additional metadata.

        Returns:
            Entry ID string.
        """
        entry_id = str(uuid.uuid4())[:12]
        entry = {
            "id": entry_id,
            "content": content,
            "category": category,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "access_count": 0,
        }
        self._data["entries"].append(entry)
        self._update_index(entry)
        self._save()
        return entry_id

    def _update_index(self, entry):
        """Update the search index for a memory entry.

        Builds a simple inverted index mapping words to entry IDs.

        Args:
            entry: Memory entry dict.
        """
        words = self._tokenize(entry["content"])
        words.extend(entry.get("tags", []))

        for word in set(words):
            if word not in self._data["index"]:
                self._data["index"][word] = []
            if entry["id"] not in self._data["index"][word]:
                self._data["index"][word].append(entry["id"])

    def _tokenize(self, text):
        """Tokenize text into lowercase words.

        Simple whitespace and punctuation-based tokenization.

        Args:
            text: Input text string.

        Returns:
            List of lowercase word strings.
        """
        import re
        # Split on non-alphanumeric characters
        words = re.findall(r'\b[a-zA-Z0-9\u4e00-\u9fff]+\b', text.lower())
        return words

    def get(self, entry_id):
        """Get a memory entry by ID.

        Args:
            entry_id: Entry identifier string.

        Returns:
            Entry dict, or None if not found.
        """
        for entry in self._data["entries"]:
            if entry["id"] == entry_id:
                entry["access_count"] = entry.get("access_count", 0) + 1
                return entry
        return None

    def search(self, query, limit=10):
        """Search memory entries by query text.

        Uses the inverted index for fast word-based lookup.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of matching entry dicts.
        """
        query_words = self._tokenize(query)

        # Score entries by number of matching words
        scores = {}
        for word in query_words:
            entry_ids = self._data["index"].get(word, [])
            for eid in entry_ids:
                scores[eid] = scores.get(eid, 0) + 1

        # Sort by score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Return full entries
        results = []
        for eid in sorted_ids[:limit]:
            entry = self.get(eid)
            if entry:
                results.append({
                    "entry": entry,
                    "score": scores[eid],
                })

        return results

    def update(self, entry_id, content=None, category=None, tags=None,
               metadata=None):
        """Update an existing memory entry.

        Args:
            entry_id: Entry identifier.
            content: New content (None to keep existing).
            category: New category (None to keep existing).
            tags: New tags (None to keep existing).
            metadata: New metadata (None to keep existing, dict to merge).

        Returns:
            True if updated, False if entry not found.
        """
        for entry in self._data["entries"]:
            if entry["id"] == entry_id:
                if content is not None:
                    entry["content"] = content
                if category is not None:
                    entry["category"] = category
                if tags is not None:
                    entry["tags"] = tags
                if metadata is not None:
                    if isinstance(metadata, dict):
                        entry["metadata"].update(metadata)
                    else:
                        entry["metadata"] = metadata
                entry["updated_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def delete(self, entry_id):
        """Delete a memory entry.

        Args:
            entry_id: Entry identifier.

        Returns:
            True if deleted, False if not found.
        """
        initial_len = len(self._data["entries"])
        self._data["entries"] = [
            e for e in self._data["entries"] if e["id"] != entry_id
        ]

        if len(self._data["entries"]) < initial_len:
            # Rebuild index
            self._rebuild_index()
            self._save()
            return True
        return False

    def _rebuild_index(self):
        """Rebuild the entire search index from entries."""
        self._data["index"] = {}
        for entry in self._data["entries"]:
            self._update_index(entry)

    def list_all(self, category=None, limit=100):
        """List all memory entries, optionally filtered by category.

        Args:
            category: Optional category filter.
            limit: Maximum entries to return.

        Returns:
            List of entry dicts.
        """
        entries = self._data["entries"]
        if category:
            entries = [e for e in entries if e.get("category") == category]

        # Sort by creation time descending
        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        return entries[:limit]

    def count(self, category=None):
        """Count memory entries.

        Args:
            category: Optional category filter.

        Returns:
            Number of entries.
        """
        if category:
            return sum(
                1 for e in self._data["entries"]
                if e.get("category") == category
            )
        return len(self._data["entries"])

    def clear(self, category=None):
        """Clear memory entries.

        Args:
            category: If specified, only clear entries in this category.
                      If None, clear all entries.

        Returns:
            Number of entries deleted.
        """
        if category:
            initial = len(self._data["entries"])
            self._data["entries"] = [
                e for e in self._data["entries"]
                if e.get("category") != category
            ]
            deleted = initial - len(self._data["entries"])
        else:
            deleted = len(self._data["entries"])
            self._data["entries"] = []

        if deleted > 0:
            self._rebuild_index()
            self._save()
        return deleted

    def export_data(self, format_type="json"):
        """Export all memory data.

        Args:
            format_type: Export format ('json' or 'jsonl').

        Returns:
            String in the requested format.
        """
        if format_type == "jsonl":
            lines = []
            for entry in self._data["entries"]:
                lines.append(json.dumps(entry, ensure_ascii=False))
            return "\n".join(lines)
        else:
            return json.dumps(self._data, indent=2, ensure_ascii=False)

    def import_data(self, data_string, format_type="json"):
        """Import memory data.

        Args:
            data_string: Data string to import.
            format_type: Import format ('json' or 'jsonl').

        Returns:
            Number of entries imported.
        """
        count = 0

        if format_type == "jsonl":
            for line in data_string.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if "content" in entry:
                        entry.setdefault("id", str(uuid.uuid4())[:12])
                        entry.setdefault("category", "general")
                        entry.setdefault("tags", [])
                        entry.setdefault("metadata", {})
                        entry.setdefault("created_at", datetime.now().isoformat())
                        entry.setdefault("updated_at", datetime.now().isoformat())
                        entry.setdefault("access_count", 0)
                        self._data["entries"].append(entry)
                        self._update_index(entry)
                        count += 1
                except json.JSONDecodeError:
                    continue
        else:
            try:
                data = json.loads(data_string)
                entries = data.get("entries", [])
                if isinstance(data, list):
                    entries = data
                for entry in entries:
                    if isinstance(entry, dict) and "content" in entry:
                        entry.setdefault("id", str(uuid.uuid4())[:12])
                        entry.setdefault("category", "general")
                        entry.setdefault("tags", [])
                        entry.setdefault("metadata", {})
                        entry.setdefault("created_at", datetime.now().isoformat())
                        entry.setdefault("updated_at", datetime.now().isoformat())
                        entry.setdefault("access_count", 0)
                        self._data["entries"].append(entry)
                        self._update_index(entry)
                        count += 1
            except json.JSONDecodeError:
                return 0

        if count > 0:
            self._save()
        return count

    def export_compressed(self, output_path=None):
        """Export memory data as gzip-compressed JSON.

        Args:
            output_path: Output file path. If None, returns bytes.

        Returns:
            If output_path is None: compressed bytes.
            If output_path is set: file path string.
        """
        data = self.export_data("json")

        if output_path:
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                f.write(data)
            return output_path
        else:
            return gzip.compress(data.encode("utf-8"))

    def get_stats(self):
        """Get memory store statistics.

        Returns:
            Dict with entry counts, category breakdown, etc.
        """
        categories = {}
        for entry in self._data["entries"]:
            cat = entry.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        total_tags = sum(len(e.get("tags", [])) for e in self._data["entries"])
        total_access = sum(e.get("access_count", 0) for e in self._data["entries"])

        return {
            "total_entries": len(self._data["entries"]),
            "categories": categories,
            "total_tags": total_tags,
            "total_access_count": total_access,
            "index_size": len(self._data.get("index", {})),
            "created_at": self._data.get("created_at", ""),
            "updated_at": self._data.get("updated_at", ""),
        }
