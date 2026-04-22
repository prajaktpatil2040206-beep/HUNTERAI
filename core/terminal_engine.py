"""
HunterAI - Terminal Execution Engine (v3)
Real-time subprocess execution with WebSocket streaming.
Features:
- Captures stdout/stderr separately for error detection
- Stores output per-process for AI error analysis
- Signals completion with exit codes
- Process management (kill, list)
- Error callback system for auto-fix triggering
- wait_for_completion() for synchronous fix loops
"""

import os
import subprocess
import threading
import time
import uuid
import json
from datetime import datetime, timezone
from collections import OrderedDict

from config import DATA_DIR

TERMINAL_LOGS_DIR = os.path.join(DATA_DIR, "terminal_logs")


class TerminalEngine:
    """Manages subprocess execution with real-time WebSocket streaming."""

    def __init__(self):
        self._processes = OrderedDict()
        self._socketio = None
        self._max_history = 200  # Keep last 200 processes
        self._error_callback = None  # Called when a process errors
        self._completion_events = {}  # process_id → threading.Event
        self._completion_lock = threading.Lock()
        os.makedirs(TERMINAL_LOGS_DIR, exist_ok=True)

    def set_socketio(self, socketio):
        """Connect the SocketIO instance for real-time streaming."""
        self._socketio = socketio

    def set_error_callback(self, callback):
        """
        Set a callback function that fires when a command exits with error.
        Signature: callback(process_id, hunt_id, error_context)
        """
        self._error_callback = callback

    def execute(self, command, cwd=None, hunt_id=None):
        """
        Execute a command asynchronously.
        Returns process_id immediately, streams output via WebSocket.
        """
        process_id = str(uuid.uuid4())[:12]

        process_info = {
            "id": process_id,
            "command": command,
            "hunt_id": hunt_id,
            "cwd": cwd or os.getcwd(),
            "status": "running",
            "exit_code": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "stdout": [],
            "stderr": [],
            "output_combined": [],
        }

        self._processes[process_id] = process_info

        # Create completion event for wait_for_completion()
        with self._completion_lock:
            self._completion_events[process_id] = threading.Event()

        # Trim old processes
        while len(self._processes) > self._max_history:
            old_id, _ = self._processes.popitem(last=False)
            with self._completion_lock:
                self._completion_events.pop(old_id, None)

        # Emit command started event
        self._emit("terminal_command", {
            "process_id": process_id,
            "command": command,
            "hunt_id": hunt_id
        })

        # Start execution in background thread
        thread = threading.Thread(
            target=self._run_process,
            args=(process_id, command, cwd, hunt_id),
            daemon=True
        )
        thread.start()

        return process_id

    def _run_process(self, process_id, command, cwd, hunt_id):
        """Execute the command and stream output."""
        exit_code = -1
        try:
            # Build unrestricted environment for full system access
            proc_env = os.environ.copy()
            proc_env["TERM"] = "xterm-256color"
            proc_env["HOME"] = os.environ.get("HOME", "/root")
            proc_env["LANG"] = "en_US.UTF-8"
            proc_env["DEBIAN_FRONTEND"] = "noninteractive"
            # Ensure all common tool paths are in PATH
            extra_paths = [
                "/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin",
                "/sbin", "/bin", "/snap/bin", "/usr/local/go/bin",
                "/root/.local/bin", "/root/go/bin", "/opt",
            ]
            existing_path = proc_env.get("PATH", "")
            for p in extra_paths:
                if p not in existing_path:
                    existing_path = f"{p}:{existing_path}"
            proc_env["PATH"] = existing_path

            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=proc_env,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid if os.name != 'nt' else None,
            )

            self._processes[process_id]["_proc"] = proc

            # Read stdout and stderr in separate threads
            stdout_thread = threading.Thread(
                target=self._stream_output,
                args=(process_id, proc.stdout, "stdout"),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._stream_output,
                args=(process_id, proc.stderr, "stderr"),
                daemon=True
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            proc.wait()

            # Wait for output threads to finish
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            exit_code = proc.returncode
            self._processes[process_id]["exit_code"] = exit_code
            self._processes[process_id]["status"] = "completed" if exit_code == 0 else "error"
            self._processes[process_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

            # Emit completion event
            self._emit("terminal_complete", {
                "process_id": process_id,
                "exit_code": exit_code,
                "status": self._processes[process_id]["status"],
                "hunt_id": hunt_id,
                "command": command,
                "has_errors": exit_code != 0
            })

            # Save log to file
            self._save_log(process_id)

            # Fire error callback if command failed
            if exit_code != 0 and self._error_callback:
                try:
                    error_ctx = self.get_error_context(process_id)
                    self._error_callback(process_id, hunt_id, error_ctx)
                except Exception:
                    pass  # Don't let callback errors break the engine

        except FileNotFoundError:
            self._processes[process_id]["status"] = "error"
            self._processes[process_id]["exit_code"] = 127
            error_msg = f"Command not found: {command.split()[0] if command else command}"
            self._processes[process_id]["stderr"].append(error_msg)
            self._emit("terminal_output", {
                "process_id": process_id,
                "data": error_msg,
                "type": "stderr"
            })
            self._emit("terminal_complete", {
                "process_id": process_id,
                "exit_code": 127,
                "status": "error",
                "hunt_id": hunt_id,
                "command": command,
                "has_errors": True
            })
            self._save_log(process_id)

            # Fire error callback
            if self._error_callback:
                try:
                    error_ctx = self.get_error_context(process_id)
                    self._error_callback(process_id, hunt_id, error_ctx)
                except Exception:
                    pass

        except Exception as e:
            self._processes[process_id]["status"] = "error"
            self._processes[process_id]["exit_code"] = -1
            error_msg = f"Execution error: {str(e)}"
            self._processes[process_id]["stderr"].append(error_msg)
            self._emit("terminal_output", {
                "process_id": process_id,
                "data": error_msg,
                "type": "stderr"
            })
            self._emit("terminal_complete", {
                "process_id": process_id,
                "exit_code": -1,
                "status": "error",
                "hunt_id": hunt_id,
                "command": command,
                "has_errors": True
            })
            self._save_log(process_id)

            # Fire error callback
            if self._error_callback:
                try:
                    error_ctx = self.get_error_context(process_id)
                    self._error_callback(process_id, hunt_id, error_ctx)
                except Exception:
                    pass

        finally:
            # Signal completion event so wait_for_completion() unblocks
            with self._completion_lock:
                event = self._completion_events.get(process_id)
                if event:
                    event.set()

    def _stream_output(self, process_id, pipe, output_type):
        """Stream output from a pipe line by line."""
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                line = line.rstrip('\n\r')
                if process_id in self._processes:
                    if output_type == "stdout":
                        self._processes[process_id]["stdout"].append(line)
                    else:
                        self._processes[process_id]["stderr"].append(line)
                    self._processes[process_id]["output_combined"].append(line)

                    self._emit("terminal_output", {
                        "process_id": process_id,
                        "data": line,
                        "type": output_type
                    })
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _emit(self, event, data):
        """Emit event via SocketIO if available."""
        if self._socketio:
            try:
                self._socketio.emit(event, data, namespace="/terminal")
            except Exception:
                pass

    def _save_log(self, process_id):
        """Save process log to disk for later analysis."""
        try:
            info = self._processes.get(process_id)
            if not info:
                return
            log_data = {
                "id": info["id"],
                "command": info["command"],
                "hunt_id": info["hunt_id"],
                "status": info["status"],
                "exit_code": info["exit_code"],
                "started_at": info["started_at"],
                "completed_at": info["completed_at"],
                "stdout": info["stdout"][-500:],  # Keep last 500 lines
                "stderr": info["stderr"][-200:],
            }
            log_file = os.path.join(TERMINAL_LOGS_DIR, f"{process_id}.json")
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ─── Public API ──────────────────────────────────────────

    def wait_for_completion(self, process_id, timeout=300):
        """
        Block until a process completes or timeout is reached.
        Returns True if process completed, False if timed out.
        Used by the autofix loop to wait for fix commands.
        """
        with self._completion_lock:
            event = self._completion_events.get(process_id)

        if not event:
            # Process might already be done or not exist
            info = self._processes.get(process_id)
            if info and info["status"] in ("completed", "error", "killed"):
                return True
            return False

        # Wait for the event to be set (process completion)
        return event.wait(timeout=timeout)

    def kill_process(self, process_id):
        """Kill a running process."""
        info = self._processes.get(process_id)
        if info and info.get("_proc"):
            try:
                info["_proc"].kill()
                info["status"] = "killed"
                info["exit_code"] = -9
                # Signal completion event
                with self._completion_lock:
                    event = self._completion_events.get(process_id)
                    if event:
                        event.set()
                return True
            except Exception:
                return False
        return False

    def get_process(self, process_id):
        """Get process info (without internal objects)."""
        info = self._processes.get(process_id)
        if info:
            return {k: v for k, v in info.items() if not k.startswith("_")}
        return None

    def get_output(self, process_id):
        """Get combined output of a process."""
        info = self._processes.get(process_id)
        if info:
            return "\n".join(info.get("output_combined", []))
        return None

    def get_error_context(self, process_id):
        """
        Get error context for a failed process — used to feed back to AI
        for auto-fix. Returns None if process succeeded.
        """
        info = self._processes.get(process_id)
        if not info:
            return None
        if info.get("exit_code", 0) == 0:
            return None

        return {
            "command": info.get("command", ""),
            "exit_code": info.get("exit_code"),
            "stdout": "\n".join(info.get("stdout", [])[-50:]),
            "stderr": "\n".join(info.get("stderr", [])[-50:]),
            "status": info.get("status", "error"),
        }

    def list_processes(self):
        """List all processes."""
        result = []
        for pid, info in self._processes.items():
            result.append({
                "id": info["id"],
                "command": info["command"],
                "hunt_id": info.get("hunt_id"),
                "status": info["status"],
                "exit_code": info.get("exit_code"),
                "started_at": info["started_at"],
            })
        return result

    def list_running(self):
        """List only running processes."""
        return [p for p in self.list_processes() if p["status"] == "running"]


# Singleton
terminal_engine = TerminalEngine()
