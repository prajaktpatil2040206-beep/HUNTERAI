"""
HunterAI - Auto-Fix Engine (Self-Healing Loop)
Orchestrates: Error → Classify → Fix → Retry (up to MAX_RETRIES)
"""

import re
import time
import threading
import logging
from datetime import datetime, timezone
from collections import OrderedDict

logger = logging.getLogger("hunterai.autofix")

MAX_RETRIES = 5
RETRY_COOLDOWN = 2.0
PROCESS_WAIT_TIMEOUT = 300

# ─── Error patterns and known fixes ─────────────────────────
ERROR_PATTERNS = {
    "missing_tool": {
        "patterns": [r"command not found", r"not found$", r"executable file not found"],
        "extract": r"(?:bash:\s*)?(\S+):\s*(?:command )?not found",
        "auto_fix_template": "apt-get install -y {tool_name}",
    },
    "missing_pip_package": {
        "patterns": [r"ModuleNotFoundError", r"No module named"],
        "extract": r"No module named ['\"]?(\w[\w.]*)",
        "auto_fix_template": "pip3 install {package_name}",
    },
    "missing_directory": {
        "patterns": [r"No such file or directory", r"ENOENT"],
        "extract": r"No such file or directory[:\s]*['\"]?([^\s'\"]+)",
        "auto_fix_template": "mkdir -p {dir_path}",
    },
    "permission_denied": {
        "patterns": [r"Permission denied", r"EACCES"],
        "extract": r"Permission denied[:\s]*['\"]?([^\s'\"]+)",
        "auto_fix_template": "chmod +x {file_path}",
    },
    "port_in_use": {
        "patterns": [r"Address already in use", r"EADDRINUSE"],
        "extract": r"(?:port|address).*?(\d{2,5})",
        "auto_fix_template": "fuser -k {port}/tcp 2>/dev/null; sleep 1",
    },
    "network_error": {
        "patterns": [r"Connection refused", r"Network unreachable", r"Could not resolve"],
        "extract": None,
        "auto_fix_template": None,
    },
    "pip_not_found": {
        "patterns": [r"pip3?: command not found", r"pip3?: not found"],
        "extract": None,
        "auto_fix_template": "apt-get install -y python3-pip",
    },
    "wordlist_missing": {
        "patterns": [r"wordlist.*not found", r"No such file.*/usr/share/wordlists"],
        "extract": None,
        "auto_fix_template": "apt-get install -y wordlists seclists && gunzip /usr/share/wordlists/rockyou.txt.gz 2>/dev/null; true",
    },
    "syntax_error": {
        "patterns": [r"syntax error", r"invalid option", r"unrecognized option"],
        "extract": None,
        "auto_fix_template": None,
    },
}

TOOL_PACKAGE_MAP = {
    "nmap": "nmap", "nikto": "nikto", "gobuster": "gobuster",
    "dirb": "dirb", "sqlmap": "sqlmap", "hydra": "hydra",
    "wpscan": "wpscan", "whatweb": "whatweb", "wafw00f": "wafw00f",
    "sslscan": "sslscan", "dnsrecon": "dnsrecon", "subfinder": "subfinder",
    "nuclei": "nuclei", "ffuf": "ffuf", "feroxbuster": "feroxbuster",
    "dalfox": "dalfox", "commix": "commix", "amass": "amass",
    "masscan": "masscan", "wfuzz": "wfuzz", "medusa": "medusa",
    "curl": "curl", "wget": "wget", "git": "git", "jq": "jq",
    "katana": "katana", "httpx": "httpx-toolkit",
}


class AutoFixEngine:
    """Orchestrates the self-healing error → fix → retry loop."""

    def __init__(self):
        self._terminal_engine = None
        self._ai_manager = None
        self._socketio = None
        self._fix_states = OrderedDict()
        self._max_states = 500
        self._lock = threading.Lock()

    def initialize(self, terminal_engine, ai_manager, socketio=None):
        """Wire up dependencies after all singletons are created."""
        self._terminal_engine = terminal_engine
        self._ai_manager = ai_manager
        self._socketio = socketio

    def start_fix_loop(self, process_id, hunt_id, mode="intermediate",
                       exec_mode="autonomous", original_command=None):
        """Start the auto-fix loop for a failed process in a background thread."""
        if not self._terminal_engine or not self._ai_manager:
            return None

        error_ctx = self._terminal_engine.get_error_context(process_id)
        if not error_ctx:
            return None

        state = {
            "state_id": process_id,
            "original_process_id": process_id,
            "original_command": original_command or error_ctx.get("command", ""),
            "hunt_id": hunt_id,
            "mode": mode,
            "exec_mode": exec_mode,
            "status": "running",
            "current_attempt": 0,
            "max_retries": MAX_RETRIES,
            "attempts": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "final_process_id": None,
        }

        with self._lock:
            self._fix_states[process_id] = state
            while len(self._fix_states) > self._max_states:
                self._fix_states.popitem(last=False)

        self._emit("autofix_start", {
            "state_id": process_id, "process_id": process_id,
            "command": state["original_command"], "hunt_id": hunt_id,
        })

        thread = threading.Thread(
            target=self._fix_loop, args=(process_id, error_ctx),
            daemon=True, name=f"autofix-{process_id[:8]}"
        )
        thread.start()
        return process_id

    def get_fix_state(self, state_id):
        with self._lock:
            return self._fix_states.get(state_id)

    def abort_fix(self, state_id):
        with self._lock:
            state = self._fix_states.get(state_id)
            if state and state["status"] == "running":
                state["status"] = "aborted"
                state["completed_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def list_active_fixes(self, hunt_id=None):
        with self._lock:
            return [
                s.copy() for s in self._fix_states.values()
                if s["status"] == "running" and
                (hunt_id is None or s.get("hunt_id") == hunt_id)
            ]

    # ─── Core Fix Loop ───────────────────────────────────────

    def _fix_loop(self, state_id, initial_error_ctx):
        """Main self-healing loop running in background thread."""
        state = self._fix_states.get(state_id)
        if not state:
            return

        current_error = initial_error_ctx
        last_failed_cmd = current_error.get("command", "")

        for attempt in range(1, MAX_RETRIES + 1):
            if state["status"] != "running":
                return

            state["current_attempt"] = attempt
            classification = self._classify_error(current_error)

            attempt_rec = {
                "attempt": attempt, "error_type": classification["type"],
                "failed_command": last_failed_cmd,
                "stderr_snippet": current_error.get("stderr", "")[:300],
                "fix_command": None, "fix_source": None,
                "fix_process_id": None, "result": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._emit("autofix_attempt", {
                "state_id": state_id, "attempt": attempt,
                "max_retries": MAX_RETRIES,
                "error_type": classification["type"],
                "failed_command": last_failed_cmd,
                "hunt_id": state.get("hunt_id"),
            })

            # ── Generate fix command ──
            fix_cmd, fix_source = None, None

            if classification.get("auto_fix"):
                fix_cmd = classification["auto_fix"]
                fix_source = "pattern"
            else:
                fix_cmd = self._ask_ai_for_fix(current_error, state)
                fix_source = "ai"

            if not fix_cmd:
                if classification["type"] == "network_error":
                    fix_cmd = last_failed_cmd
                    fix_source = "retry"
                else:
                    attempt_rec["result"] = "no_fix_found"
                    state["attempts"].append(attempt_rec)
                    time.sleep(RETRY_COOLDOWN)
                    continue

            attempt_rec["fix_command"] = fix_cmd
            attempt_rec["fix_source"] = fix_source

            # ── Execute fix command ──
            try:
                fix_pid = self._terminal_engine.execute(
                    fix_cmd, hunt_id=state.get("hunt_id")
                )
                attempt_rec["fix_process_id"] = fix_pid
            except Exception as e:
                logger.error(f"[AutoFix] Execute failed: {e}")
                attempt_rec["result"] = "execution_error"
                state["attempts"].append(attempt_rec)
                time.sleep(RETRY_COOLDOWN)
                continue

            # ── Wait for completion ──
            completed = self._terminal_engine.wait_for_completion(
                fix_pid, timeout=PROCESS_WAIT_TIMEOUT
            )
            if not completed:
                self._terminal_engine.kill_process(fix_pid)
                attempt_rec["result"] = "timeout"
                state["attempts"].append(attempt_rec)
                time.sleep(RETRY_COOLDOWN)
                continue

            # ── Check result ──
            fix_error = self._terminal_engine.get_error_context(fix_pid)

            if fix_error is None:
                # Fix command succeeded
                if fix_source == "retry" or fix_cmd == last_failed_cmd:
                    # Original command itself succeeded on retry
                    attempt_rec["result"] = "success"
                    state["attempts"].append(attempt_rec)
                    self._mark_success(state, fix_pid, attempt, fix_cmd)
                    return
                else:
                    # Fix applied (e.g., apt install), re-run original
                    attempt_rec["result"] = "fix_applied"
                    state["attempts"].append(attempt_rec)

                    retry_pid = self._terminal_engine.execute(
                        last_failed_cmd, hunt_id=state.get("hunt_id")
                    )
                    done = self._terminal_engine.wait_for_completion(
                        retry_pid, timeout=PROCESS_WAIT_TIMEOUT
                    )
                    if not done:
                        self._terminal_engine.kill_process(retry_pid)
                        current_error = {
                            "command": last_failed_cmd, "exit_code": -1,
                            "stderr": "Timed out after fix applied",
                            "stdout": "", "status": "timeout",
                        }
                        time.sleep(RETRY_COOLDOWN)
                        continue

                    retry_err = self._terminal_engine.get_error_context(retry_pid)
                    if retry_err is None:
                        self._mark_success(state, retry_pid, attempt, fix_cmd)
                        return
                    else:
                        current_error = retry_err
                        last_failed_cmd = retry_err.get("command", last_failed_cmd)
                        time.sleep(RETRY_COOLDOWN)
                        continue
            else:
                # Fix command failed — loop with new error
                attempt_rec["result"] = "fix_failed"
                state["attempts"].append(attempt_rec)
                self._emit("autofix_attempt_result", {
                    "state_id": state_id, "attempt": attempt,
                    "result": "fix_failed", "hunt_id": state.get("hunt_id"),
                })
                current_error = fix_error
                last_failed_cmd = fix_cmd
                time.sleep(RETRY_COOLDOWN)
                continue

        # ── Exhausted ──
        state["status"] = "exhausted"
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._emit("autofix_exhausted", {
            "state_id": state_id, "total_attempts": MAX_RETRIES,
            "original_command": state["original_command"],
            "hunt_id": state.get("hunt_id"),
        })

    def _mark_success(self, state, pid, attempt, fix_cmd):
        state["status"] = "success"
        state["final_process_id"] = pid
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._emit("autofix_success", {
            "state_id": state["state_id"], "attempt": attempt,
            "fix_command": fix_cmd, "fix_process_id": pid,
            "hunt_id": state.get("hunt_id"),
        })

    # ─── Error Classification ────────────────────────────────

    def _classify_error(self, error_ctx):
        stderr = error_ctx.get("stderr", "")
        stdout = error_ctx.get("stdout", "")
        command = error_ctx.get("command", "")
        combined = f"{stderr}\n{stdout}"

        for etype, cfg in ERROR_PATTERNS.items():
            for pat in cfg["patterns"]:
                if re.search(pat, combined, re.IGNORECASE):
                    result = {"type": etype, "description": cfg.get("description", etype),
                              "auto_fix": None, "extracted_value": None}
                    if cfg.get("extract"):
                        m = re.search(cfg["extract"], combined, re.IGNORECASE)
                        if m:
                            result["extracted_value"] = m.group(1)
                    if cfg.get("auto_fix_template"):
                        fix = self._build_fix(etype, cfg["auto_fix_template"],
                                              result["extracted_value"], command)
                        if fix:
                            result["auto_fix"] = fix
                    return result

        return {"type": "unknown", "description": "Unknown error", "auto_fix": None}

    def _build_fix(self, etype, template, extracted, command):
        if etype == "missing_tool":
            tool = extracted or (command.split()[0] if command.split() else None)
            if tool:
                return template.format(tool_name=TOOL_PACKAGE_MAP.get(tool, tool))
        elif etype == "missing_pip_package" and extracted:
            return template.format(package_name=extracted.split(".")[0])
        elif etype == "missing_directory" and extracted:
            return template.format(dir_path=extracted)
        elif etype == "permission_denied" and extracted:
            return template.format(file_path=extracted)
        elif etype == "port_in_use" and extracted:
            return template.format(port=extracted)
        elif "{" not in template:
            return template
        return None

    # ─── AI Fix Generation ───────────────────────────────────

    def _ask_ai_for_fix(self, error_ctx, state):
        if not self._ai_manager:
            return None
        messages = [{
            "role": "user",
            "content": (
                f"Fix this failed command.\n\n"
                f"**Command:** `{error_ctx.get('command', '')}`\n"
                f"**Exit code:** {error_ctx.get('exit_code', '?')}\n"
                f"**stderr:**\n```\n{error_ctx.get('stderr', '')[:800]}\n```\n"
                f"**stdout:**\n```\n{error_ctx.get('stdout', '')[:400]}\n```\n"
                f"Attempt {state['current_attempt']}/{MAX_RETRIES}.\n"
                f"Reply with ONLY the corrected command in a ```bash block."
            )
        }]
        result = self._ai_manager.chat_with_retry(
            messages, hunt_mode="pro", exec_mode="autonomous",
            error_context=error_ctx, max_retries=2,
        )
        if "error" in result:
            return None
        return self._parse_first_command(result.get("response", ""))

    def _parse_first_command(self, response):
        pattern = r"```(?:bash|shell|sh)?\s*\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        cmds = []
        for match in matches:
            for line in match.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    if line.startswith("sudo "):
                        line = line[5:]
                    cmds.append(line)
        if len(cmds) == 1:
            return cmds[0]
        elif cmds:
            return " && ".join(cmds)
        return None

    def _emit(self, event, data):
        if self._socketio:
            try:
                self._socketio.emit(event, data, namespace="/terminal")
            except Exception:
                pass


# Singleton
autofix_engine = AutoFixEngine()
