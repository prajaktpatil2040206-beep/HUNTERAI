"""
HunterAI - Main Flask Application
Entry point for the web server with SocketIO support.
"""

import os
import sys
import webbrowser
import threading

from flask import Flask, render_template, jsonify, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS

from config import load_config, ensure_directories, DATA_DIR
from core.terminal_engine import terminal_engine
from core.ai_manager import ai_manager
from core.autofix_engine import autofix_engine
from routes.chat import chat_bp
from routes.projects import projects_bp
from routes.models import models_bp
from routes.tools import tools_bp
from routes.terminal import terminal_bp, TerminalNamespace
from routes.assets import assets_bp
from routes.reports import reports_bp

# Initialize Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = "hunterai-secret-key-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max upload

# Enable CORS
CORS(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Register WebSocket namespace
socketio.on_namespace(TerminalNamespace("/terminal"))

# Connect terminal engine to socketio
terminal_engine.set_socketio(socketio)

# Initialize the auto-fix engine with all dependencies
autofix_engine.initialize(terminal_engine, ai_manager, socketio)

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(models_bp)
app.register_blueprint(tools_bp)
app.register_blueprint(terminal_bp)
app.register_blueprint(assets_bp)
app.register_blueprint(reports_bp)


# ─── MAIN ROUTES ────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main SPA."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """API health check."""
    config = load_config()
    return jsonify({
        "status": "running",
        "version": "1.0.0",
        "name": "HunterAI",
        "first_run": config.get("first_run", True),
        "data_dir": DATA_DIR
    })


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration."""
    config = load_config()
    return jsonify({"config": config})


@app.route("/api/config", methods=["PUT"])
def update_config():
    """Update configuration."""
    from flask import request
    from config import save_config
    data = request.get_json()
    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({"success": True, "config": config})


@app.route("/api/first-run-complete", methods=["POST"])
def complete_first_run():
    """Mark first run as complete."""
    from config import save_config
    config = load_config()
    config["first_run"] = False
    save_config(config)
    return jsonify({"success": True})


# ─── ERROR HANDLERS ─────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors — serve SPA for unmatched routes."""
    if request_wants_json():
        return jsonify({"error": "Not found"}), 404
    return render_template("index.html")


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error", "details": str(e)}), 500


def request_wants_json():
    """Check if request expects JSON response."""
    from flask import request
    return request.path.startswith("/api/")


# ─── STARTUP ────────────────────────────────────────────────────

BANNER = r"""
 ╔══════════════════════════════════════════════════════════════╗
 ║                                                              ║
 ║     🛡  H U N T E R A I                                      ║
 ║     Autonomous AI-Powered Bug Bounty Platform                ║
 ║                                                              ║
 ║     "Think Like a Hacker. Hunt Like a Machine."              ║
 ║                                                              ║
 ║     🌐 Interface: http://localhost:5000                      ║
 ║     📡 Status:    Running                                    ║
 ║     🔧 Docs:      http://localhost:5000/api/status           ║
 ║                                                              ║
 ╚══════════════════════════════════════════════════════════════╝
"""


def open_browser(port):
    """Open the browser after a short delay."""
    import time
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


def main():
    """Main entry point."""
    ensure_directories()
    config = load_config()

    host = config.get("server", {}).get("host", "0.0.0.0")
    port = config.get("server", {}).get("port", 5000)
    debug = config.get("server", {}).get("debug", False)

    print(BANNER)

    # Auto-open browser
    if not debug:
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Start the server
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
