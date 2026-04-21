"""
HunterAI - Asset Manager
Organizes all outputs: screenshots, logs, reports, extracted files.
Hierarchical organization by Project → Hunt → Asset Type.
"""

import os
import json
import shutil
import mimetypes
import zipfile
from datetime import datetime, timezone

from storage.local_store import LocalStore
from config import ASSETS_DIR

assets_store = LocalStore("assets")


class AssetManager:
    """Manages all generated assets from hunts."""

    def __init__(self):
        os.makedirs(ASSETS_DIR, exist_ok=True)

    def _get_hunt_dir(self, hunt_id):
        """Get the asset directory for a hunt."""
        path = os.path.join(ASSETS_DIR, hunt_id)
        os.makedirs(path, exist_ok=True)
        return path

    def save_asset(self, hunt_id, filename, content, asset_type="general", source_command=None):
        """
        Save an asset file and track it.
        content can be bytes or str.
        """
        asset_id = assets_store.generate_id()
        hunt_dir = self._get_hunt_dir(hunt_id)

        # Create type subdirectory
        type_dir = os.path.join(hunt_dir, asset_type)
        os.makedirs(type_dir, exist_ok=True)

        file_path = os.path.join(type_dir, filename)

        # Write file
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)

        # Track asset metadata
        mime_type, _ = mimetypes.guess_type(filename)
        asset_meta = {
            "asset_id": asset_id,
            "hunt_id": hunt_id,
            "filename": filename,
            "file_path": file_path,
            "asset_type": asset_type,
            "mime_type": mime_type or "application/octet-stream",
            "file_size": os.path.getsize(file_path),
            "source_command": source_command,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        assets_store.save(asset_id, asset_meta)
        return asset_meta

    def save_file_upload(self, hunt_id, file_obj, filename):
        """Save an uploaded file as an asset."""
        asset_id = assets_store.generate_id()
        hunt_dir = self._get_hunt_dir(hunt_id)
        uploads_dir = os.path.join(hunt_dir, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        file_path = os.path.join(uploads_dir, filename)
        file_obj.save(file_path)

        mime_type, _ = mimetypes.guess_type(filename)
        asset_meta = {
            "asset_id": asset_id,
            "hunt_id": hunt_id,
            "filename": filename,
            "file_path": file_path,
            "asset_type": "upload",
            "mime_type": mime_type or "application/octet-stream",
            "file_size": os.path.getsize(file_path),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        assets_store.save(asset_id, asset_meta)
        return asset_meta

    def save_screenshot(self, hunt_id, screenshot_path, description=""):
        """Track a screenshot as an asset."""
        if not os.path.exists(screenshot_path):
            return None

        asset_id = assets_store.generate_id()
        filename = os.path.basename(screenshot_path)

        # Copy to hunt assets
        hunt_dir = self._get_hunt_dir(hunt_id)
        screenshots_dir = os.path.join(hunt_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        dest_path = os.path.join(screenshots_dir, filename)
        shutil.copy2(screenshot_path, dest_path)

        asset_meta = {
            "asset_id": asset_id,
            "hunt_id": hunt_id,
            "filename": filename,
            "file_path": dest_path,
            "asset_type": "screenshot",
            "mime_type": "image/png",
            "file_size": os.path.getsize(dest_path),
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        assets_store.save(asset_id, asset_meta)
        return asset_meta

    def save_command_log(self, hunt_id, command, output, exit_code):
        """Save a command execution log as an asset."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cmd_{timestamp}.log"
        content = f"$ {command}\n\n{output}\n\n[Exit Code: {exit_code}]"
        return self.save_asset(hunt_id, filename, content, asset_type="logs", source_command=command)

    def list_assets(self, hunt_id=None, asset_type=None):
        """List assets, optionally filtered."""
        assets = assets_store.list_all()
        if hunt_id:
            assets = [a for a in assets if a.get("hunt_id") == hunt_id]
        if asset_type:
            assets = [a for a in assets if a.get("asset_type") == asset_type]
        return assets

    def get_asset(self, asset_id):
        """Get asset metadata."""
        return assets_store.load(asset_id)

    def get_asset_path(self, asset_id):
        """Get the file path for an asset."""
        meta = assets_store.load(asset_id)
        if meta and os.path.exists(meta.get("file_path", "")):
            return meta["file_path"]
        return None

    def create_zip(self, hunt_id):
        """Create a ZIP archive of all assets for a hunt."""
        hunt_dir = self._get_hunt_dir(hunt_id)
        zip_filename = f"hunt_{hunt_id}_assets.zip"
        zip_path = os.path.join(ASSETS_DIR, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(hunt_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, hunt_dir)
                    zf.write(file_path, arcname)

        return zip_path

    def delete_asset(self, asset_id):
        """Delete an asset file and metadata."""
        meta = assets_store.load(asset_id)
        if meta:
            file_path = meta.get("file_path", "")
            if os.path.exists(file_path):
                os.remove(file_path)
            assets_store.delete(asset_id)
            return True
        return False


# Singleton
asset_manager = AssetManager()
