"""
HunterAI - Tool Inventory Routes
"""

from flask import Blueprint, request, jsonify
from core.tool_scanner import scan_all_tools, get_inventory, get_tool_info, is_tool_available, get_install_command

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/api/tools", methods=["GET"])
def list_tools():
    """Get the full tool inventory."""
    inventory = get_inventory()
    if not inventory:
        return jsonify({"inventory": None, "message": "No scan performed yet. Trigger a scan first."})
    return jsonify({"inventory": inventory})


@tools_bp.route("/api/tools/scan", methods=["POST"])
def trigger_scan():
    """Trigger a new tool scan."""
    try:
        inventory = scan_all_tools()
        return jsonify({
            "success": True,
            "total_installed": inventory["total_installed"],
            "total_known": inventory["total_known"],
            "categories": {k: {"installed": len(v["installed"]), "missing": len(v["missing"])} for k, v in inventory["categories"].items()}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/api/tools/<tool_name>", methods=["GET"])
def get_tool(tool_name):
    """Get info about a specific tool."""
    info = get_tool_info(tool_name)
    if info:
        return jsonify({"tool": info})
    return jsonify({"tool": None, "available": False, "install_command": get_install_command(tool_name)})


@tools_bp.route("/api/tools/check", methods=["POST"])
def check_tools():
    """Check if multiple tools are available."""
    data = request.get_json()
    tools = data.get("tools", [])
    results = {}
    for tool in tools:
        results[tool] = {
            "available": is_tool_available(tool),
            "install_command": get_install_command(tool) if not is_tool_available(tool) else None
        }
    return jsonify({"results": results})
