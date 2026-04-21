"""
HunterAI - Chat API Routes (v3)
Enhanced with:
- Auto error detection → AI auto-fix loop
- Plan → Approve → Execute workflow
- Accept / Accept All / Reject action system
- Autonomous vs Feedback execution modes
- Error context feedback to AI for self-healing
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

chat_bp = Blueprint("chat", __name__)

# Pending actions store
actions_store = LocalStore("actions")


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
            # Auto-execute all
            for cmd in commands:
                pid = terminal_engine.execute(cmd, hunt_id=hunt_id)
                executed_actions.append({
                    "command": cmd,
                    "process_id": pid,
                    "status": "executing"
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
    Auto-fix a failed command by sending the error context back to AI.
    The AI analyzes the error and provides a corrected command.
    This is the self-healing loop.
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

    # Load chat history
    chat = chats_store.load(hunt_id) or {"hunt_id": hunt_id, "messages": []}

    # Add error notification to chat
    error_msg = {
        "id": _gen_id(),
        "role": "system",
        "content": f"❌ **Command failed** (exit code {error_ctx['exit_code']}):\n```\n{error_ctx['command']}\n```\n**Error output:**\n```\n{error_ctx['stderr'][:500]}\n```\n\n🔧 *Auto-fix engaged — analyzing error...*",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    chat["messages"].append(error_msg)

    # Build context for AI error fix
    ai_messages = []
    for m in chat["messages"][-30:]:
        if m["role"] in ("user", "assistant"):
            ai_messages.append({"role": m["role"], "content": m["content"]})

    # Add the error as a user message asking for fix
    ai_messages.append({
        "role": "user",
        "content": f"The command `{error_ctx['command']}` failed with exit code {error_ctx['exit_code']}.\n\nError output:\n```\n{error_ctx['stderr'][:1000]}\n```\n\nStdout:\n```\n{error_ctx['stdout'][:500]}\n```\n\nPlease analyze this error, explain what went wrong, and provide the corrected command. If a tool is missing, install it first."
    })

    # Get AI fix
    result = ai_manager.chat(ai_messages, hunt_mode=mode, exec_mode=exec_mode, error_context=error_ctx)

    if "error" in result:
        fix_response = f"⚠️ Auto-fix failed: {result['error']}"
        fix_commands = []
    else:
        fix_response = result.get("response", "Could not generate fix.")
        fix_commands = _extract_commands(fix_response)

    # Save AI fix response
    fix_msg_id = _gen_id()
    fix_msg = {
        "id": fix_msg_id,
        "role": "assistant",
        "content": fix_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_auto_fix": True
    }
    chat["messages"].append(fix_msg)
    chats_store.save(hunt_id, chat)

    # Handle fix commands
    pending_actions = []
    executed_actions = []

    if fix_commands:
        if exec_mode == "autonomous":
            for cmd in fix_commands:
                pid = terminal_engine.execute(cmd, hunt_id=hunt_id)
                executed_actions.append({"command": cmd, "process_id": pid, "status": "executing"})
        else:
            for i, cmd in enumerate(fix_commands):
                action_id = _gen_id()
                action = {
                    "action_id": action_id,
                    "hunt_id": hunt_id,
                    "message_id": fix_msg_id,
                    "type": "fix_command",
                    "command": cmd,
                    "status": "pending",
                    "order": i,
                    "original_error_process": process_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                actions_store.save(action_id, action)
                pending_actions.append(action)

    return jsonify({
        "success": True,
        "message": fix_msg,
        "error_message": error_msg,
        "fix_commands": fix_commands,
        "pending_actions": pending_actions,
        "executed_actions": executed_actions,
        "exec_mode": exec_mode
    })


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
    if not action_id:
        return jsonify({"error": "action_id required"}), 400

    action = actions_store.load(action_id)
    if not action:
        return jsonify({"error": "Action not found"}), 404
    if action["status"] != "pending":
        return jsonify({"error": "Action already processed"}), 400

    pid = terminal_engine.execute(action["command"], hunt_id=action.get("hunt_id"))
    action["status"] = "accepted"
    action["process_id"] = pid
    action["executed_at"] = datetime.now(timezone.utc).isoformat()
    actions_store.save(action_id, action)

    return jsonify({"success": True, "action": action, "process_id": pid})


@chat_bp.route("/api/chat/actions/accept-all", methods=["POST"])
def accept_all_actions():
    data = request.get_json()
    hunt_id = data.get("hunt_id")
    if not hunt_id:
        return jsonify({"error": "hunt_id required"}), 400

    all_actions = actions_store.list_all()
    pending = [a for a in all_actions if a.get("hunt_id") == hunt_id and a.get("status") == "pending"]
    pending.sort(key=lambda x: x.get("order", 0))

    executed = []
    for action in pending:
        pid = terminal_engine.execute(action["command"], hunt_id=hunt_id)
        action["status"] = "accepted"
        action["process_id"] = pid
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
    if not command:
        return jsonify({"error": "No command provided"}), 400
    pid = terminal_engine.execute(command, hunt_id=hunt_id)
    return jsonify({"success": True, "process_id": pid, "command": command})


@chat_bp.route("/api/chat/process-status/<process_id>", methods=["GET"])
def get_process_status(process_id):
    """Get the status and error context of a process — used for auto-fix checks."""
    proc = terminal_engine.get_process(process_id)
    if not proc:
        return jsonify({"error": "Process not found"}), 404
    error_ctx = terminal_engine.get_error_context(process_id)
    return jsonify({
        "process": proc,
        "has_error": error_ctx is not None,
        "error_context": error_ctx
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
