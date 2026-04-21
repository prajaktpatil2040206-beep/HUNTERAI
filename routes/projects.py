"""
HunterAI - Project & Hunt CRUD Routes
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from storage.local_store import projects_store, hunts_store

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/api/projects", methods=["GET"])
def list_projects():
    """List all projects."""
    projects = projects_store.list_all()
    # Enrich with hunt counts
    for p in projects:
        hunts = hunts_store.search(p["_id"], fields=["project_id"])
        p["hunt_count"] = len(hunts)
    return jsonify({"projects": projects})


@projects_bp.route("/api/projects", methods=["POST"])
def create_project():
    """Create a new project."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Project name is required"}), 400

    project_id = projects_store.generate_id()
    project = {
        "name": data["name"],
        "description": data.get("description", ""),
        "scope": data.get("scope", ""),
        "target_url": data.get("target_url", ""),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    projects_store.save(project_id, project)
    project["_id"] = project_id
    return jsonify({"success": True, "project": project}), 201


@projects_bp.route("/api/projects/<project_id>", methods=["GET"])
def get_project(project_id):
    """Get a single project."""
    project = projects_store.load(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    # Get hunts for this project
    all_hunts = hunts_store.list_all()
    project["hunts"] = [h for h in all_hunts if h.get("project_id") == project_id]
    return jsonify({"project": project})


@projects_bp.route("/api/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    """Update a project."""
    data = request.get_json()
    project = projects_store.load(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    if "name" in data:
        project["name"] = data["name"]
    if "description" in data:
        project["description"] = data["description"]
    if "scope" in data:
        project["scope"] = data["scope"]
    if "status" in data:
        project["status"] = data["status"]

    projects_store.save(project_id, project)
    return jsonify({"success": True, "project": project})


@projects_bp.route("/api/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    """Delete a project."""
    if projects_store.delete(project_id):
        return jsonify({"success": True})
    return jsonify({"error": "Project not found"}), 404


# ─── HUNTS ───────────────────────────────────────────────────────

@projects_bp.route("/api/hunts", methods=["POST"])
def create_hunt():
    """Create a new hunt within a project."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    project_id = data.get("project_id")
    name = data.get("name", "New Hunt")

    hunt_id = hunts_store.generate_id()
    hunt = {
        "project_id": project_id,
        "name": name,
        "target_url": data.get("target_url", ""),
        "target_type": data.get("target_type", "web"),
        "description": data.get("description", ""),
        "mode": data.get("mode", "intermediate"),
        "status": "idle",  # idle, running, paused, completed
        "scope": data.get("scope", []),
        "findings_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    hunts_store.save(hunt_id, hunt)
    hunt["_id"] = hunt_id
    return jsonify({"success": True, "hunt": hunt}), 201


@projects_bp.route("/api/hunts/<hunt_id>", methods=["GET"])
def get_hunt(hunt_id):
    """Get a single hunt."""
    hunt = hunts_store.load(hunt_id)
    if not hunt:
        return jsonify({"error": "Hunt not found"}), 404
    return jsonify({"hunt": hunt})


@projects_bp.route("/api/hunts", methods=["GET"])
def list_hunts():
    """List all hunts, optionally filtered by project."""
    project_id = request.args.get("project_id")
    hunts = hunts_store.list_all()
    if project_id:
        hunts = [h for h in hunts if h.get("project_id") == project_id]
    return jsonify({"hunts": hunts})


@projects_bp.route("/api/hunts/<hunt_id>", methods=["PUT"])
def update_hunt(hunt_id):
    """Update a hunt."""
    data = request.get_json()
    hunt = hunts_store.load(hunt_id)
    if not hunt:
        return jsonify({"error": "Hunt not found"}), 404

    for key in ["name", "status", "mode", "description", "target_url"]:
        if key in data:
            hunt[key] = data[key]

    hunts_store.save(hunt_id, hunt)
    return jsonify({"success": True, "hunt": hunt})


@projects_bp.route("/api/hunts/<hunt_id>", methods=["DELETE"])
def delete_hunt(hunt_id):
    """Delete a hunt."""
    if hunts_store.delete(hunt_id):
        return jsonify({"success": True})
    return jsonify({"error": "Hunt not found"}), 404


@projects_bp.route("/api/recent-hunts", methods=["GET"])
def recent_hunts():
    """Get recent hunts across all projects."""
    hunts = hunts_store.list_all(sort_by="_updated_at", reverse=True)
    # Limit to 20
    hunts = hunts[:20]
    # Enrich with project name
    for h in hunts:
        if h.get("project_id"):
            project = projects_store.load(h["project_id"])
            h["project_name"] = project.get("name", "Unknown") if project else "Unknown"
    return jsonify({"hunts": hunts})
