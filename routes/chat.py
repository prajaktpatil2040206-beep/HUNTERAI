"""
HunterAI - Chat API Routes (v4)
Enhanced with:
- Full auto-fix loop integration (error → classify → fix → retry)
- Plan → Approve → Execute workflow
- Accept / Accept All / Reject action system
- Autonomous mode auto-triggers fix loop on failures
- Error context feedback to AI for self-healing
- Autofix status & abort endpoints
"""

import os
import re
import json
import time
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from storage.local_store import chats_store, hunts_store, LocalStore
from core.ai_manager import ai_manager
from core.terminal_engine import terminal_engine
from core.asset_manager import asset_manager
from core.autofix_engine import autofix_engine

chat_bp = Blueprint("chat", __name__)

# Pending actions store
actions_store = LocalStore("actions")

# Track which processes are under autonomous auto-fix
# so the error callback knows when to trigger the loop
_autonomous_processes = {}  # process_id → {hunt_id, mode, exec_mode}
_autonomous_lock = __import__("threading").Lock()


def _register_autonomous_process(process_id, hunt_id, mode, exec_mode):
    """Register a process for autonomous auto-fix on failure."""
    with _autonomous_lock:
        _autonomous_processes[process_id] = {
            "hunt_id": hunt_id,
            "mode": mode,
            "exec_mode": exec_mode,
        }


def _on_process_error(process_id, hunt_id, error_context):
    """
    Error callback — fired by terminal engine when any command fails.
    If the process was in autonomous mode, auto-trigger the fix loop.
    """
    with _autonomous_lock:
        proc_info = _autonomous_processes.pop(process_id, None)

    if proc_info and proc_info["exec_mode"] == "autonomous":
        # Auto-start the fix loop for autonomous processes
        autofix_engine.start_fix_loop(
            process_id=process_id,
            hunt_id=proc_info["hunt_id"],
            mode=proc_info["mode"],
            exec_mode="autonomous",
        )


# Wire the error callback into the terminal engine
terminal_engine.set_error_callback(_on_process_error)


@chat_bp.route("/api/chat/send", methods=["POST"])
def send_message():
    """Send a message and get AI response with structured planning."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    hunt_id = data.get("hunt_id")
    message = data.get("message", "").strip()
    mode = data.get("mode", "intermediate")
    exec_mode = data.get("exec_mode", "feedback")
    model_id = data.get("model_id")

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if not hunt_id:
        return jsonify({"error": "hunt_id is required"}), 400

    # Load/create chat
    chat = chats_store.load(hunt_id) or {
        "hunt_id": hunt_id,
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Add user message
    user_msg = {
        "id": _gen_id(),
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    chat["messages"].append(user_msg)

    # Build AI messages (limit context window to last 40 messages)
    ai_messages = []
    for m in chat["messages"][-40:]:
        if m["role"] in ("user", "assistant"):
            ai_messages.append({"role": m["role"], "content": m["content"]})

    # Get AI response
    result = ai_manager.chat(ai_messages, hunt_mode=mode, exec_mode=exec_mode, model_id=model_id)

    if "error" in result:
        ai_response = f"⚠️ {result['error']}"
        commands = []
    else:
        ai_response = result.get("response", "No response generated.")
        commands = _extract_commands(ai_response)

    # Save AI message
    ai_msg_id = _gen_id()
    ai_msg = {
        "id": ai_msg_id,
        "role": "assistant",
        "content": ai_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
    }
    chat["messages"].append(ai_msg)
    chats_store.save(hunt_id, chat)

    # Handle commands
    pending_actions = []
    executed_actions = []

    if commands:
        if exec_mode == "autonomous":
            # Auto-execute all and register for auto-fix on failure
            for cmd in commands:
                pid = terminal_engine.execute(cmd, hunt_id=hunt_id)
                _register_autonomous_process(pid, hunt_id, mode, exec_mode)
                executed_actions.append({
                    "command": cmd,
                    "process_id": pid,
                    "status": "executing",
                    "autofix_enabled": True,
                })
        else:
            # Create pending actions for approval
            for i, cmd in enumerate(commands):
                action_id = _gen_id()
                action = {
                    "action_id": action_id,
                    "hunt_id": hunt_id,
                    "message_id": ai_msg_id,
                    "type": "command",
                    "command": cmd,
                    "status": "pending",
                    "order": i,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                actions_store.save(action_id, action)
                pending_actions.append(action)

    return jsonify({
        "success": True,
        "message": ai_msg,
        "commands": commands,
        "pending_actions": pending_actions,
        "executed_actions": executed_actions,
        "exec_mode": exec_mode,
        "usage": result.get("usage", {})
    })


@chat_bp.route("/api/chat/auto-fix", methods=["POST"])
def auto_fix_error():
    """
    Trigger the self-healing auto-fix loop for a failed command.
    The loop retries up to MAX_RETRIES times, classifying errors and
    applying fixes until the command succeeds or retries are exhausted.
    """
    data = request.get_json()
    hunt_id = data.get("hunt_id")
    process_id = data.get("process_id")
    mode = data.get("mode", "intermediate")
    exec_mode = data.get("exec_mode", "feedback")

    if not hunt_id or not process_id:
        return jsonify({"error": "hunt_id and process_id required"}), 400

    # Get error context from terminal engine
    error_ctx = terminal_engine.get_error_context(process_id)
    if not error_ctx:
        return jsonify({"error": "No error found for this process, or process succeeded."}), 400

    # Log the error notification in the chat
    chat = chats_store.load(hunt_id) or {"hunt_id": hunt_id, "messages": []}
    error_msg = {
        "id": _gen_id(),
        "role": "system",
        "content": (
            f"❌ **Command failed** (exit code {error_ctx['exit_code']}):\n"
            f"```\n{error_ctx['command']}\n```\n"
            f"**Error output:**\n```\n{error_ctx['stderr'][:500]}\n```\n\n"
            f"🔧 *Auto-fix loop engaged — will retry up to 5 times...*"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    chat["messages"].append(error_msg)
    chats_store.save(hunt_id, chat)

    # Start the auto-fix loop (runs in background thread)
    state_id = autofix_engine.start_fix_loop(
        process_id=process_id,
        hunt_id=hunt_id,
        mode=mode,
        exec_mode=exec_mode,
    )

    if not state_id:
        return jsonify({"error": "Could not start auto-fix loop."}), 500

    return jsonify({
        "success": True,
        "state_id": state_id,
        "message": error_msg,
        "status": "autofix_started",
        "max_retries": 5,
    })


@chat_bp.route("/api/chat/autofix-status/<state_id>", methods=["GET"])
def get_autofix_status(state_id):
    """Get the current state of an auto-fix loop."""
    state = autofix_engine.get_fix_state(state_id)
    if not state:
        return jsonify({"error": "Fix state not found"}), 404
    return jsonify({"fix_state": state})


@chat_bp.route("/api/chat/autofix-abort/<state_id>", methods=["POST"])
def abort_autofix(state_id):
    """Abort a running auto-fix loop."""
    success = autofix_engine.abort_fix(state_id)
    if success:
        return jsonify({"success": True, "message": "Auto-fix loop aborted."})
    return jsonify({"error": "Fix loop not found or already completed."}), 400


@chat_bp.route("/api/chat/autofix-active", methods=["GET"])
def list_active_fixes():
    """List all currently running auto-fix loops."""
    hunt_id = request.args.get("hunt_id")
    fixes = autofix_engine.list_active_fixes(hunt_id=hunt_id)
    return jsonify({"active_fixes": fixes})


# ─── Action Approval Endpoints ─────────────────────────────

@chat_bp.route("/api/chat/actions/pending", methods=["GET"])
def get_pending_actions():
    hunt_id = request.args.get("hunt_id")
    if not hunt_id:
        return jsonify({"error": "hunt_id required"}), 400
    all_actions = actions_store.list_all()
    pending = [a for a in all_actions if a.get("hunt_id") == hunt_id and a.get("status") == "pending"]
    pending.sort(key=lambda x: x.get("order", 0))
    return jsonify({"actions": pending})


@chat_bp.route("/api/chat/actions/accept", methods=["POST"])
def accept_action():
    data = request.get_json()
    action_id = data.get("action_id")
    auto_fix = data.get("auto_fix", False)  # Enable auto-fix for this action
    if not action_id:
        return jsonify({"error": "action_id required"}), 400

    action = actions_store.load(action_id)
    if not action:
        return jsonify({"error": "Action not found"}), 404
    if action["status"] != "pending":
        return jsonify({"error": "Action already processed"}), 400

    pid = terminal_engine.execute(action["command"], hunt_id=action.get("hunt_id"))

    # If auto-fix requested, register for auto-fix on failure
    if auto_fix:
        _register_autonomous_process(
            pid, action.get("hunt_id"),
            mode="intermediate", exec_mode="autonomous"
        )

    action["status"] = "accepted"
    action["process_id"] = pid
    action["auto_fix_enabled"] = auto_fix
    action["executed_at"] = datetime.now(timezone.utc).isoformat()
    actions_store.save(action_id, action)

    return jsonify({"success": True, "action": action, "process_id": pid})


@chat_bp.route("/api/chat/actions/accept-all", methods=["POST"])
def accept_all_actions():
    data = request.get_json()
    hunt_id = data.get("hunt_id")
    auto_fix = data.get("auto_fix", False)
    if not hunt_id:
        return jsonify({"error": "hunt_id required"}), 400

    all_actions = actions_store.list_all()
    pending = [a for a in all_actions if a.get("hunt_id") == hunt_id and a.get("status") == "pending"]
    pending.sort(key=lambda x: x.get("order", 0))

    executed = []
    for action in pending:
        pid = terminal_engine.execute(action["command"], hunt_id=hunt_id)

        if auto_fix:
            _register_autonomous_process(pid, hunt_id, "intermediate", "autonomous")

        action["status"] = "accepted"
        action["process_id"] = pid
        action["auto_fix_enabled"] = auto_fix
        action["executed_at"] = datetime.now(timezone.utc).isoformat()
        actions_store.save(action["_id"], action)
        executed.append({"action_id": action["_id"], "command": action["command"], "process_id": pid})

    return jsonify({"success": True, "executed_count": len(executed), "executed": executed})


@chat_bp.route("/api/chat/actions/reject", methods=["POST"])
def reject_action():
    data = request.get_json()
    action_id = data.get("action_id")
    if not action_id:
        return jsonify({"error": "action_id required"}), 400
    action = actions_store.load(action_id)
    if not action:
        return jsonify({"error": "Action not found"}), 404
    action["status"] = "rejected"
    action["rejected_at"] = datetime.now(timezone.utc).isoformat()
    actions_store.save(action_id, action)
    return jsonify({"success": True, "action": action})


@chat_bp.route("/api/chat/actions/reject-all", methods=["POST"])
def reject_all_actions():
    data = request.get_json()
    hunt_id = data.get("hunt_id")
    if not hunt_id:
        return jsonify({"error": "hunt_id required"}), 400
    all_actions = actions_store.list_all()
    pending = [a for a in all_actions if a.get("hunt_id") == hunt_id and a.get("status") == "pending"]
    for action in pending:
        action["status"] = "rejected"
        action["rejected_at"] = datetime.now(timezone.utc).isoformat()
        actions_store.save(action["_id"], action)
    return jsonify({"success": True, "rejected_count": len(pending)})


# ─── Chat History & Utilities ────────────────────────────────

@chat_bp.route("/api/chat/history/<hunt_id>", methods=["GET"])
def get_chat_history(hunt_id):
    chat = chats_store.load(hunt_id)
    if not chat:
        return jsonify({"messages": [], "pending_actions": []})
    all_actions = actions_store.list_all()
    pending = [a for a in all_actions if a.get("hunt_id") == hunt_id and a.get("status") == "pending"]
    return jsonify({"messages": chat.get("messages", []), "pending_actions": pending})


@chat_bp.route("/api/chat/upload", methods=["POST"])
def upload_file():
    hunt_id = request.form.get("hunt_id")
    if not hunt_id:
        return jsonify({"error": "hunt_id required"}), 400
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    asset = asset_manager.save_file_upload(hunt_id, file, file.filename)
    chat = chats_store.load(hunt_id) or {"hunt_id": hunt_id, "messages": []}
    chat["messages"].append({
        "id": _gen_id(),
        "role": "system",
        "content": f"📎 File uploaded: **{file.filename}** ({_fmt_size(asset['file_size'])})",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attachment": {"asset_id": asset["asset_id"], "filename": file.filename}
    })
    chats_store.save(hunt_id, chat)
    return jsonify({"success": True, "asset": asset})


@chat_bp.route("/api/chat/execute", methods=["POST"])
def execute_command_direct():
    data = request.get_json()
    command = data.get("command", "").strip()
    hunt_id = data.get("hunt_id")
    auto_fix = data.get("auto_fix", False)
    if not command:
        return jsonify({"error": "No command provided"}), 400

    pid = terminal_engine.execute(command, hunt_id=hunt_id)

    if auto_fix:
        _register_autonomous_process(pid, hunt_id, "intermediate", "autonomous")

    return jsonify({"success": True, "process_id": pid, "command": command, "auto_fix": auto_fix})


@chat_bp.route("/api/chat/process-status/<process_id>", methods=["GET"])
def get_process_status(process_id):
    """Get the status and error context of a process — used for auto-fix checks."""
    proc = terminal_engine.get_process(process_id)
    if not proc:
        return jsonify({"error": "Process not found"}), 404
    error_ctx = terminal_engine.get_error_context(process_id)

    # Also check if there's an active auto-fix loop for this process
    fix_state = autofix_engine.get_fix_state(process_id)

    return jsonify({
        "process": proc,
        "has_error": error_ctx is not None,
        "error_context": error_ctx,
        "autofix_state": fix_state,
    })


# ─── Helpers ─────────────────────────────────────────────────

def _gen_id():
    import uuid
    return str(uuid.uuid4())[:12]


def _extract_commands(response):
    """Extract executable commands from AI response bash code blocks."""
    commands = []
    pattern = r"```(?:bash|shell|sh|terminal|console)?\s*\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    for match in matches:
        for line in match.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip comments and output markers
            if line.startswith("#") or line.startswith("//") or line.startswith(">") or line.startswith("$"):
                continue
            # Strip sudo prefix (we already run as root)
            if line.startswith("sudo "):
                line = line[5:]
            commands.append(line)
    return commands


def _fmt_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
