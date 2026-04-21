"""
HunterAI - Local JSON Storage Engine
Replaces all database functionality with structured JSON files.
Thread-safe file operations with automatic directory creation.
"""

import os
import json
import uuid
import threading
import time
import glob
from datetime import datetime, timezone

from config import DATA_DIR


class LocalStore:
    """JSON-based local storage engine — no database required."""

    _locks = {}
    _global_lock = threading.Lock()

    def __init__(self, collection):
        """
        Initialize store for a specific collection.
        Collection maps to a subdirectory under data/.
        """
        self.collection = collection
        self.base_path = os.path.join(DATA_DIR, collection)
        os.makedirs(self.base_path, exist_ok=True)

    def _get_lock(self, file_path):
        """Get or create a lock for a specific file."""
        with self._global_lock:
            if file_path not in self._locks:
                self._locks[file_path] = threading.Lock()
            return self._locks[file_path]

    def _file_path(self, item_id):
        """Get the full file path for an item."""
        return os.path.join(self.base_path, f"{item_id}.json")

    def generate_id(self):
        """Generate a unique ID."""
        return str(uuid.uuid4()).replace("-", "")

    def save(self, item_id, data):
        """Save data to a JSON file."""
        file_path = self._file_path(item_id)
        lock = self._get_lock(file_path)

        # Add metadata
        if "_created_at" not in data:
            data["_created_at"] = datetime.now(timezone.utc).isoformat()
        data["_updated_at"] = datetime.now(timezone.utc).isoformat()
        data["_id"] = item_id

        with lock:
            # Write to temp file first, then rename (atomic on most filesystems)
            temp_path = file_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            # Replace original
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_path, file_path)

        return data

    def load(self, item_id):
        """Load data from a JSON file. Returns None if not found."""
        file_path = self._file_path(item_id)
        if not os.path.exists(file_path):
            return None

        lock = self._get_lock(file_path)
        with lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

    def delete(self, item_id):
        """Delete a JSON file."""
        file_path = self._file_path(item_id)
        if os.path.exists(file_path):
            lock = self._get_lock(file_path)
            with lock:
                os.remove(file_path)
            return True
        return False

    def list_all(self, sort_by="_updated_at", reverse=True):
        """List all items in the collection, sorted by a field."""
        items = []
        pattern = os.path.join(self.base_path, "*.json")
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items.append(data)
            except (json.JSONDecodeError, IOError):
                continue

        # Sort
        if sort_by:
            items.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

        return items

    def search(self, query, fields=None):
        """Search through items. Simple text search across specified fields."""
        if not query:
            return self.list_all()

        query_lower = query.lower()
        results = []
        items = self.list_all(sort_by=None)

        for item in items:
            search_fields = fields or item.keys()
            for field in search_fields:
                value = item.get(field, "")
                if isinstance(value, str) and query_lower in value.lower():
                    results.append(item)
                    break

        return results

    def count(self):
        """Count items in the collection."""
        pattern = os.path.join(self.base_path, "*.json")
        return len(glob.glob(pattern))

    def exists(self, item_id):
        """Check if an item exists."""
        return os.path.exists(self._file_path(item_id))

    def update(self, item_id, updates):
        """Partially update an existing item."""
        data = self.load(item_id)
        if data is None:
            return None
        data.update(updates)
        return self.save(item_id, data)

    def append_to_list(self, item_id, field, value):
        """Append a value to a list field in an item."""
        data = self.load(item_id)
        if data is None:
            return None
        if field not in data:
            data[field] = []
        data[field].append(value)
        return self.save(item_id, data)


# Pre-configured stores for each collection
projects_store = LocalStore("projects")
hunts_store = LocalStore("hunts")
chats_store = LocalStore("chats")
models_store = LocalStore("models")
tools_store = LocalStore("tools")
assets_store = LocalStore("assets")
reports_store = LocalStore("reports")
