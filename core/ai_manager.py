"""
HunterAI - Multi-AI Model Manager (v3)
Enhanced with:
- Structured planning workflow (Plan → Approve → Execute → Auto-fix)
- Auto error detection and self-healing loop
- Strong systematic methodology
- FREE + PAID model tiers
- Autonomous / Feedback execution modes
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from cryptography.fernet import Fernet

from storage.local_store import models_store
from config import DATA_DIR


# ─── Encryption ──────────────────────────────────────────────
_KEY_FILE = os.path.join(DATA_DIR, ".encryption_key")


def _get_cipher():
    os.makedirs(os.path.dirname(_KEY_FILE), exist_ok=True)
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(_KEY_FILE, "wb") as f:
            f.write(key)
    return Fernet(key)


def encrypt_api_key(api_key):
    if not api_key:
        return ""
    return _get_cipher().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key):
    if not encrypted_key:
        return ""
    return _get_cipher().decrypt(encrypted_key.encode()).decode()


# ─── Default API Key (Gemini free tier) ──────────────────────
DEFAULT_GEMINI_KEY = "AIzaSyAAwuwWOBrs2Ay2L5pb_MuvmwaWe8nDZbc"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# ─── Provider configs ────────────────────────────────────────
PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "gemini-2.5-flash", "gemini-2.5-pro",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
        ],
        "free_models": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "type": "gemini",
        "free_tier": True,
        "notes": "Free tier available! Get key: https://aistudio.google.com/app/apikey"
    },
    "groq": {
        "name": "Groq (Free & Fast)",
        "models": [
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "mixtral-8x7b-32768", "gemma2-9b-it",
        ],
        "free_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "base_url": "https://api.groq.com/openai/v1",
        "type": "openai",
        "free_tier": True,
        "notes": "FREE with rate limits! Get key: https://console.groq.com"
    },
    "openrouter": {
        "name": "OpenRouter (Many Free)",
        "models": [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "qwen/qwen-2.5-72b-instruct:free",
        ],
        "free_models": [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "qwen/qwen-2.5-72b-instruct:free",
        ],
        "base_url": "https://openrouter.ai/api/v1",
        "type": "openai",
        "free_tier": True,
        "notes": "FREE models! Get key: https://openrouter.ai/keys"
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "o3-mini"],
        "free_models": [],
        "base_url": "https://api.openai.com/v1",
        "type": "openai",
        "free_tier": False,
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "free_models": [],
        "base_url": "https://api.anthropic.com/v1",
        "type": "anthropic",
        "free_tier": False,
    },
    "mistral": {
        "name": "Mistral AI",
        "models": ["open-mistral-nemo", "mistral-small-latest", "mistral-large-latest", "codestral-latest"],
        "free_models": ["open-mistral-nemo"],
        "base_url": "https://api.mistral.ai/v1",
        "type": "openai",
        "free_tier": True,
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "free_models": [],
        "base_url": "https://api.moonshot.cn/v1",
        "type": "openai",
        "free_tier": False,
    },
    "ollama": {
        "name": "Ollama (Local/Free)",
        "models": ["llama3.2", "llama3.1", "mistral", "codellama", "deepseek-coder-v2", "phi3", "gemma2", "qwen2.5"],
        "free_models": ["llama3.2", "llama3.1", "mistral", "codellama", "deepseek-coder-v2", "phi3", "gemma2", "qwen2.5"],
        "base_url": "http://localhost:11434/v1",
        "type": "openai",
        "free_tier": True,
    },
    "custom": {
        "name": "Custom OpenAI-Compatible",
        "models": [],
        "free_models": [],
        "base_url": "",
        "type": "openai",
        "free_tier": False,
    }
}


# ─── Enhanced System Prompt — The Brain of HunterAI ─────────

SYSTEM_PROMPT = """You are HunterAI, an elite AI-powered penetration testing and bug bounty assistant running on Kali Linux with FULL ROOT privileges. You think like a senior penetration tester with 15+ years of experience.

═══ YOUR CAPABILITIES ═══
1. Execute ANY terminal command (root access, no sudo needed)
2. Run ALL Kali Linux tools (nmap, burpsuite, sqlmap, nikto, gobuster, etc.)
3. Automate browser-based testing
4. Generate attack plans with OWASP Top 10 coverage
5. Analyze outputs, detect vulnerabilities, classify by CVSS 3.1
6. Generate professional reports with evidence

═══ CRITICAL WORKFLOW — ALWAYS FOLLOW THIS ═══

**STEP 1 — UNDERSTAND THE TARGET**
Before anything, gather info about the target:
- What type? (web app, API, network, mobile)
- What's the URL/IP?
- What's in scope? What's excluded?
- Any known technologies?

**STEP 2 — CREATE AN ATTACK PLAN**
ALWAYS create a structured plan BEFORE executing commands. Format:

```
### 🎯 Attack Plan: [Target Name]

**Phase 1: Reconnaissance**
- [ ] 1.1 DNS enumeration [dig, whois] ~2min
- [ ] 1.2 Port scanning [nmap -sV -sC -O target] ~5min
- [ ] 1.3 Technology fingerprinting [whatweb, wappalyzer] ~2min

**Phase 2: Enumeration**
- [ ] 2.1 Directory brute-force [gobuster dir -u URL -w /usr/share/wordlists/dirb/common.txt] ~5min
- [ ] 2.2 Subdomain discovery [subfinder -d domain] ~3min

**Phase 3: Vulnerability Assessment**
- [ ] 3.1 Web vulnerability scan [nikto -h URL] ~10min
- [ ] 3.2 SQL injection testing [sqlmap -u URL --batch --crawl=2] ~15min
- [ ] 3.3 XSS detection [dalfox url URL] ~5min

**Phase 4: Exploitation**
(Only with explicit user approval)

**Phase 5: Reporting**
- [ ] 5.1 Compile findings
- [ ] 5.2 Generate report

**Estimated total time**: ~45min
```

After presenting the plan, ask: **"Shall I execute this plan? You can modify any steps, or say 'Execute All' to run everything."**

**STEP 3 — EXECUTE SYSTEMATICALLY**
- Execute one step at a time
- Show the exact command in a ```bash block
- Wait for output before proceeding
- Log all results

**STEP 4 — AUTO-DETECT AND FIX ERRORS**
If a command fails or produces an error:
1. Analyze the error message
2. Identify the root cause (missing tool, wrong syntax, permission, network issue)
3. Automatically fix it:
   - Missing tool? Install it: `apt-get install -y toolname`
   - Wrong syntax? Correct and re-run
   - Permission denied? Already root, check file paths
   - Network error? Check connectivity, try alternative approach
   - Tool not found? Use alternative tool for the same purpose
4. Re-execute the corrected command
5. NEVER give up on a step — always find an alternative

**STEP 5 — ANALYZE & REPORT FINDINGS**
For each finding:
- Title and description
- Severity: Critical/High/Medium/Low/Info
- CVSS 3.1 score
- Evidence (command output, screenshot reference)
- Impact assessment
- Remediation steps

═══ COMMAND EXECUTION RULES ═══
- Output commands in ```bash code blocks — they become executable buttons
- NEVER prefix with sudo (you already have root)
- Always use full paths for wordlists: /usr/share/wordlists/
- For long-running scans, use appropriate timeouts
- Chain commands with && for efficiency when safe
- Use --batch or -y flags to avoid interactive prompts
- Always specify output format when possible (-oN, -oX, --output)

═══ ERROR SELF-HEALING RULES ═══
When you see an error in command output:
- "command not found" → Install: `apt-get install -y <package>`
- "No such file or directory" → Check path, create directory, or use alternative
- "Connection refused" → Check if target is up, try different port
- "Permission denied" → Check file permissions, path issues
- Timeout → Increase timeout or split into smaller scans
- Dependency error → Install dependencies automatically
- ALWAYS propose and execute the fix, don't just report the error

═══ SMART TOOL SELECTION ═══
Use the BEST tool for each job:
- Port scanning: nmap (always with -sV -sC for version/script detection)
- Web scanning: nikto, nuclei
- Directory brute: gobuster, feroxbuster, ffuf
- Subdomain: subfinder, amass, sublist3r
- SQL injection: sqlmap (with --batch --forms)
- XSS: dalfox, xsser
- SSL: testssl.sh, sslscan
- CMS: wpscan (WordPress), droopescan (Drupal), joomscan (Joomla)
- API: postman, curl + custom scripts
- Fuzzing: ffuf, wfuzz
- Credential testing: hydra, medusa
- Network: masscan (fast), nmap (detailed)

═══ RESPONSE FORMAT ═══
- Use markdown formatting for clarity
- Use tables for structured data
- Use code blocks for commands and output
- Bold important findings
- Use ⚠️ for warnings, ✅ for success, ❌ for failures, 🔍 for analysis
- Always explain what a command does before suggesting it (in beginner/intermediate mode)"""

MODE_PROMPTS = {
    "beginner": "\n\n[MODE: BEGINNER] Explain everything in detail. Include theory, why each step matters, what the tool does, and what the output means. Be a patient teacher. Include learning resources where relevant.",
    "intermediate": "\n\n[MODE: INTERMEDIATE] Clear explanations but skip basics. Focus on methodology, findings, and next steps. Explain non-obvious techniques.",
    "pro": "\n\n[MODE: PRO HUNTER] Terse. Action-oriented. Commands and findings only. Skip explanations. Maximum efficiency."
}

EXECUTION_MODE_PROMPTS = {
    "autonomous": "\n\n[EXECUTION: AUTONOMOUS] Execute your plan step by step automatically. Output commands in ```bash blocks — they auto-execute. After each command, analyze results and continue. If errors occur, fix them automatically and retry. Don't wait for user input between steps.",
    "feedback": "\n\n[EXECUTION: FEEDBACK] Present your plan for approval. After plan approval, present EACH command for individual approval before execution. Wait for user to accept or reject each action. Group related commands together when possible."
}


class AIManager:
    """Manages multiple AI models with unified chat interface."""

    def __init__(self):
        self.active_model_id = None
        self._load_active_model()
        # Auto-setup default Gemini model if no models configured
        if not self.active_model_id:
            self._setup_default_model()

    def _setup_default_model(self):
        """Auto-configure default Gemini model on first launch."""
        if models_store.count() == 0:
            model_id, _ = self.add_model(
                provider="gemini",
                api_key=DEFAULT_GEMINI_KEY,
                model_name=DEFAULT_GEMINI_MODEL,
                display_name="Gemini 2.5 Flash (Default)"
            )
            self.set_active_model(model_id)
            print(f"  [*] Auto-configured default AI: {DEFAULT_GEMINI_MODEL}")

    def _load_active_model(self):
        models = models_store.list_all()
        for model in models:
            if model.get("is_active"):
                self.active_model_id = model["_id"]
                return

    def add_model(self, provider, api_key, model_name=None, custom_url=None, display_name=None):
        model_id = models_store.generate_id()
        provider_config = PROVIDERS.get(provider, PROVIDERS["custom"])
        is_free = model_name in provider_config.get("free_models", [])

        model_data = {
            "provider": provider,
            "provider_name": provider_config["name"],
            "model_name": model_name or (provider_config["models"][0] if provider_config["models"] else "default"),
            "display_name": display_name or f"{provider_config['name']} - {model_name}",
            "api_key_encrypted": encrypt_api_key(api_key) if api_key else "",
            "base_url": custom_url or provider_config["base_url"],
            "api_type": provider_config["type"],
            "is_active": False,
            "is_free": is_free,
            "token_usage": {"total_input": 0, "total_output": 0},
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        models_store.save(model_id, model_data)

        # Auto-activate first model
        if models_store.count() == 1:
            self.set_active_model(model_id)

        return model_id, model_data

    def test_model(self, provider, api_key, model_name=None, custom_url=None):
        provider_config = PROVIDERS.get(provider, PROVIDERS["custom"])
        api_type = provider_config["type"]
        base_url = custom_url or provider_config["base_url"]
        model = model_name or (provider_config["models"][0] if provider_config["models"] else "default")

        try:
            if api_type == "openai":
                return self._test_openai(base_url, api_key, model)
            elif api_type == "gemini":
                return self._test_gemini(base_url, api_key, model)
            elif api_type == "anthropic":
                return self._test_anthropic(base_url, api_key, model)
            else:
                return False, "Unknown API type"
        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to API endpoint"
        except Exception as e:
            return False, str(e)

    def _test_openai(self, base_url, api_key, model):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": [{"role": "user", "content": "Say 'connected' in one word."}], "max_tokens": 10}
        resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return True, "Connection successful ✓"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def _test_gemini(self, base_url, api_key, model):
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "Say 'connected' in one word."}]}]}
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, "Connection successful ✓"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def _test_anthropic(self, base_url, api_key, model):
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "Say 'connected' in one word."}]}
        resp = requests.post(f"{base_url}/messages", json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return True, "Connection successful ✓"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def set_active_model(self, model_id):
        for m in models_store.list_all():
            if m.get("is_active"):
                m["is_active"] = False
                models_store.save(m["_id"], m)
        model = models_store.load(model_id)
        if model:
            model["is_active"] = True
            models_store.save(model_id, model)
            self.active_model_id = model_id
            return True
        return False

    def get_active_model(self):
        if self.active_model_id:
            return models_store.load(self.active_model_id)
        return None

    def list_models(self):
        models = models_store.list_all(sort_by="_created_at")
        for m in models:
            if "api_key_encrypted" in m:
                m["has_api_key"] = bool(m["api_key_encrypted"])
                try:
                    decrypted = decrypt_api_key(m["api_key_encrypted"])
                    m["api_key_masked"] = "••••" + decrypted[-4:] if decrypted else ""
                except Exception:
                    m["api_key_masked"] = "••••"
                del m["api_key_encrypted"]
        return models

    def delete_model(self, model_id):
        if self.active_model_id == model_id:
            self.active_model_id = None
        return models_store.delete(model_id)

    def chat(self, messages, hunt_mode="intermediate", exec_mode="feedback", model_id=None, error_context=None):
        """
        Send messages to the active AI model.
        error_context: If provided, includes command error details for auto-fix.
        """
        target_model_id = model_id or self.active_model_id
        if not target_model_id:
            return {"error": "No AI model configured. Go to Settings → AI Models to add one."}

        model = models_store.load(target_model_id)
        if not model:
            return {"error": "Model not found. Please reconfigure in Settings."}

        api_key = decrypt_api_key(model.get("api_key_encrypted", ""))
        api_type = model.get("api_type", "openai")
        base_url = model.get("base_url", "")
        model_name = model.get("model_name", "")

        # Build system prompt
        system = SYSTEM_PROMPT
        system += MODE_PROMPTS.get(hunt_mode, MODE_PROMPTS["intermediate"])
        system += EXECUTION_MODE_PROMPTS.get(exec_mode, EXECUTION_MODE_PROMPTS["feedback"])

        # If there's error context, append it for auto-fix
        if error_context:
            system += f"\n\n[AUTO-FIX REQUIRED] The following command failed. Analyze the error, fix it, and provide the corrected command:\nCommand: {error_context.get('command', '')}\nExit Code: {error_context.get('exit_code', 'unknown')}\nError Output:\n```\n{error_context.get('stderr', '')}\n```\nFix this error automatically. Explain what went wrong briefly, then provide the corrected command in a ```bash block."

        try:
            if api_type == "openai":
                return self._chat_openai(base_url, api_key, model_name, system, messages)
            elif api_type == "gemini":
                return self._chat_gemini(base_url, api_key, model_name, system, messages)
            elif api_type == "anthropic":
                return self._chat_anthropic(base_url, api_key, model_name, system, messages)
            else:
                return {"error": f"Unknown API type: {api_type}"}
        except requests.exceptions.Timeout:
            return {"error": "AI request timed out. Try again or use a faster model."}
        except requests.exceptions.ConnectionError:
            return {"error": "Cannot reach AI provider. Check your internet connection."}
        except Exception as e:
            return {"error": f"AI error: {str(e)}"}

    def _chat_openai(self, base_url, api_key, model, system, messages):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        full_messages = [{"role": "system", "content": system}] + messages
        payload = {"model": model, "messages": full_messages, "max_tokens": 4096, "temperature": 0.7}
        resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"response": content, "usage": data.get("usage", {})}
        return {"error": f"API error ({resp.status_code}): {resp.text[:300]}"}

    def _chat_gemini(self, base_url, api_key, model, system, messages):
        """Chat with Gemini API. Auto-fallback to other models on 503/429."""
        # Models to try in order (current model first, then fallbacks)
        fallback_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        # Put the requested model first, then add fallbacks
        models_to_try = [model] + [m for m in fallback_models if m != model]

        contents = [
            {"role": "user", "parts": [{"text": system}]},
            {"role": "model", "parts": [{"text": "Understood. HunterAI ready. I will:\n1. Understand the target first\n2. Create a structured attack plan\n3. Ask for approval before executing\n4. Execute systematically\n5. Auto-detect and fix any errors\n6. Report findings with severity ratings\n\nReady to hunt."}]}
        ]
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7},
            "safetySettings": [
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            ]
        }

        last_error = ""
        for try_model in models_to_try:
            url = f"{base_url}/models/{try_model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=120)
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        content = data["candidates"][0]["content"]["parts"][0]["text"]
                        return {"response": content, "usage": data.get("usageMetadata", {}), "model_used": try_model}
                    except (KeyError, IndexError):
                        block_reason = data.get("candidates", [{}])[0].get("finishReason", "")
                        if block_reason == "SAFETY":
                            return {"error": "Gemini blocked the response due to safety filters. Try rephrasing or use a different model."}
                        last_error = "Gemini returned empty response."
                        continue
                elif resp.status_code in (429, 503):
                    # Rate limited or overloaded — try next model
                    last_error = f"{try_model} unavailable ({resp.status_code})"
                    time.sleep(1)  # Brief pause before fallback
                    continue
                else:
                    last_error = f"Gemini API error ({resp.status_code}): {resp.text[:300]}"
                    continue
            except requests.exceptions.Timeout:
                last_error = f"{try_model} timed out"
                continue
            except Exception as e:
                last_error = str(e)
                continue

        return {"error": f"All Gemini models unavailable. Last error: {last_error}. Please try again in a minute."}

    def _chat_anthropic(self, base_url, api_key, model, system, messages):
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": model, "system": system, "messages": messages, "max_tokens": 4096}
        resp = requests.post(f"{base_url}/messages", json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            content = data["content"][0]["text"]
            return {"response": content, "usage": data.get("usage", {})}
        return {"error": f"Claude API error ({resp.status_code}): {resp.text[:300]}"}


# Singleton
ai_manager = AIManager()
