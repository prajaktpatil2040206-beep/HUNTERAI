"""
HunterAI - Asset Management Routes
"""

import os
from flask import Blueprint, request, jsonify, send_file

from core.asset_manager import asset_manager

assets_bp = Blueprint("assets", __name__)


@assets_bp.route("/api/assets", methods=["GET"])
def list_assets():
    """List assets, filtered by hunt_id and/or type."""
    hunt_id = request.args.get("hunt_id")
    asset_type = request.args.get("type")
    assets = asset_manager.list_assets(hunt_id=hunt_id, asset_type=asset_type)
    return jsonify({"assets": assets})


@assets_bp.route("/api/assets/<asset_id>", methods=["GET"])
def get_asset(asset_id):
    """Get asset metadata."""
    asset = asset_manager.get_asset(asset_id)
    if asset:
        return jsonify({"asset": asset})
    return jsonify({"error": "Asset not found"}), 404


@assets_bp.route("/api/assets/<asset_id>/download", methods=["GET"])
def download_asset(asset_id):
    """Download an asset file."""
    path = asset_manager.get_asset_path(asset_id)
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Asset file not found"}), 404


@assets_bp.route("/api/assets/zip/<hunt_id>", methods=["GET"])
def download_all_zip(hunt_id):
    """Download all assets for a hunt as ZIP."""
    try:
        zip_path = asset_manager.create_zip(hunt_id)
        return send_file(zip_path, as_attachment=True, download_name=f"hunt_{hunt_id}_assets.zip")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@assets_bp.route("/api/assets/<asset_id>", methods=["DELETE"])
def delete_asset(asset_id):
    """Delete an asset."""
    if asset_manager.delete_asset(asset_id):
        return jsonify({"success": True})
    return jsonify({"error": "Asset not found"}), 404
