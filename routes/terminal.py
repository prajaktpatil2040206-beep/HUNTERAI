"""
HunterAI - Terminal WebSocket Routes
Real-time terminal streaming via WebSocket + REST endpoints.
"""

from flask import Blueprint, request, jsonify
from flask_socketio import Namespace, emit

from core.terminal_engine import terminal_engine

terminal_bp = Blueprint("terminal", __name__)


class TerminalNamespace(Namespace):
    """WebSocket namespace for real-time terminal streaming."""

    def on_connect(self):
        """Handle client connection."""
        emit("terminal_status", {"status": "connected", "message": "Terminal connected"})

    def on_disconnect(self):
        """Handle client disconnection."""
        pass

    def on_execute(self, data):
        """Execute a command from WebSocket."""
        command = data.get("command", "").strip()
        hunt_id = data.get("hunt_id")
        cwd = data.get("cwd")

        if not command:
            emit("terminal_error", {"error": "No command provided"})
            return

        process_id = terminal_engine.execute(command, cwd=cwd, hunt_id=hunt_id)
        emit("terminal_started", {
            "process_id": process_id,
            "command": command
        })

    def on_kill(self, data):
        """Kill a running process."""
        process_id = data.get("process_id")
        if process_id:
            success = terminal_engine.kill_process(process_id)
            emit("terminal_killed", {
                "process_id": process_id,
                "success": success
            })

    def on_list_processes(self, data=None):
        """List all running processes."""
        processes = terminal_engine.list_running()
        emit("process_list", {"processes": processes})


# REST endpoints for terminal
@terminal_bp.route("/api/terminal/execute", methods=["POST"])
def execute_command():
    """Execute a terminal command via REST."""
    data = request.get_json()
    command = data.get("command", "").strip()
    hunt_id = data.get("hunt_id")
    cwd = data.get("cwd")

    if not command:
        return jsonify({"error": "No command provided"}), 400

    process_id = terminal_engine.execute(command, cwd=cwd, hunt_id=hunt_id)
    return jsonify({
        "success": True,
        "process_id": process_id,
        "command": command
    })


@terminal_bp.route("/api/terminal/kill/<process_id>", methods=["POST"])
def kill_process(process_id):
    """Kill a running process."""
    success = terminal_engine.kill_process(process_id)
    return jsonify({"success": success})


@terminal_bp.route("/api/terminal/processes", methods=["GET"])
def list_processes():
    """List all processes."""
    processes = terminal_engine.list_processes()
    return jsonify({"processes": processes})


@terminal_bp.route("/api/terminal/output/<process_id>", methods=["GET"])
def get_output(process_id):
    """Get output of a specific process."""
    output = terminal_engine.get_output(process_id)
    process = terminal_engine.get_process(process_id)
    if output is not None:
        return jsonify({"output": output, "process": process})
    return jsonify({"error": "Process not found"}), 404
