"""
HunterAI - Attack Planning Engine
AI-powered attack plan generation with 5 phases:
1. Target Analysis, 2. Attack Surface Mapping, 3. Plan Generation,
4. Feedback & Refinement, 5. Dynamic Re-planning
"""

import json
from datetime import datetime, timezone

from storage.local_store import LocalStore

plans_store = LocalStore("plans")


# OWASP Top 10 - 2021 test templates
OWASP_TOP_10 = [
    {
        "id": "A01",
        "name": "Broken Access Control",
        "tests": [
            {"name": "IDOR Testing", "tools": ["burpsuite", "ffuf"], "risk": "high"},
            {"name": "Directory Traversal", "tools": ["dotdotpwn", "ffuf"], "risk": "high"},
            {"name": "Privilege Escalation", "tools": ["burpsuite"], "risk": "critical"},
            {"name": "CORS Misconfiguration", "tools": ["curl"], "risk": "medium"}
        ]
    },
    {
        "id": "A02",
        "name": "Cryptographic Failures",
        "tests": [
            {"name": "SSL/TLS Analysis", "tools": ["sslscan", "testssl.sh"], "risk": "high"},
            {"name": "Weak Cipher Detection", "tools": ["nmap"], "risk": "medium"},
            {"name": "Certificate Validation", "tools": ["openssl"], "risk": "medium"}
        ]
    },
    {
        "id": "A03",
        "name": "Injection",
        "tests": [
            {"name": "SQL Injection", "tools": ["sqlmap"], "risk": "critical"},
            {"name": "XSS (Reflected)", "tools": ["dalfox", "xsser"], "risk": "high"},
            {"name": "XSS (Stored)", "tools": ["dalfox"], "risk": "critical"},
            {"name": "Command Injection", "tools": ["commix"], "risk": "critical"},
            {"name": "LDAP Injection", "tools": ["burpsuite"], "risk": "high"},
            {"name": "Template Injection (SSTI)", "tools": ["tplmap"], "risk": "critical"}
        ]
    },
    {
        "id": "A04",
        "name": "Insecure Design",
        "tests": [
            {"name": "Business Logic Flaws", "tools": ["burpsuite"], "risk": "high"},
            {"name": "Rate Limiting Check", "tools": ["ffuf", "wfuzz"], "risk": "medium"}
        ]
    },
    {
        "id": "A05",
        "name": "Security Misconfiguration",
        "tests": [
            {"name": "Default Credentials", "tools": ["hydra", "nmap"], "risk": "critical"},
            {"name": "Open Ports & Services", "tools": ["nmap", "masscan"], "risk": "medium"},
            {"name": "Directory Listing", "tools": ["gobuster", "dirb"], "risk": "low"},
            {"name": "Error Message Disclosure", "tools": ["nikto"], "risk": "low"},
            {"name": "HTTP Security Headers", "tools": ["curl", "nikto"], "risk": "medium"}
        ]
    },
    {
        "id": "A06",
        "name": "Vulnerable Components",
        "tests": [
            {"name": "CVE Scanning", "tools": ["nuclei", "nmap"], "risk": "high"},
            {"name": "CMS Version Detection", "tools": ["wpscan", "whatweb"], "risk": "medium"},
            {"name": "JavaScript Library Audit", "tools": ["retire.js"], "risk": "medium"}
        ]
    },
    {
        "id": "A07",
        "name": "Auth Failures",
        "tests": [
            {"name": "Brute Force Login", "tools": ["hydra", "burpsuite"], "risk": "high"},
            {"name": "Session Management", "tools": ["burpsuite"], "risk": "high"},
            {"name": "Password Policy Check", "tools": ["burpsuite"], "risk": "medium"},
            {"name": "JWT Analysis", "tools": ["jwt_tool"], "risk": "high"}
        ]
    },
    {
        "id": "A08",
        "name": "Software & Data Integrity",
        "tests": [
            {"name": "Deserialization Attacks", "tools": ["ysoserial"], "risk": "critical"},
            {"name": "CI/CD Pipeline Check", "tools": ["nuclei"], "risk": "high"}
        ]
    },
    {
        "id": "A09",
        "name": "Logging & Monitoring",
        "tests": [
            {"name": "Log Injection", "tools": ["burpsuite"], "risk": "medium"},
            {"name": "Audit Trail Check", "tools": ["manual"], "risk": "low"}
        ]
    },
    {
        "id": "A10",
        "name": "SSRF",
        "tests": [
            {"name": "SSRF Detection", "tools": ["burpsuite", "ffuf"], "risk": "critical"},
            {"name": "Internal Service Access", "tools": ["curl"], "risk": "high"}
        ]
    }
]


class AttackPlanner:
    """Generates and manages attack plans for security testing."""

    def generate_plan(self, target_info, available_tools, scope=None, hunt_mode="intermediate"):
        """
        Generate a comprehensive attack plan based on target info and available tools.

        target_info: dict with url, type, technology_stack, etc.
        available_tools: list of tool names available on the system
        scope: dict defining in-scope targets
        """
        plan_id = plans_store.generate_id()

        target_type = target_info.get("type", "web")
        plan_items = []
        item_order = 0

        # Phase 1: Reconnaissance items
        recon_items = self._generate_recon_items(target_info, available_tools)
        for item in recon_items:
            item_order += 1
            item["order"] = item_order
            item["phase"] = "reconnaissance"
            plan_items.append(item)

        # Phase 2: Scanning items based on OWASP
        if target_type == "web":
            scan_items = self._generate_web_scan_items(target_info, available_tools)
            for item in scan_items:
                item_order += 1
                item["order"] = item_order
                item["phase"] = "scanning"
                plan_items.append(item)

        # Phase 3: Exploitation items
        exploit_items = self._generate_exploit_items(target_info, available_tools)
        for item in exploit_items:
            item_order += 1
            item["order"] = item_order
            item["phase"] = "exploitation"
            plan_items.append(item)

        plan = {
            "plan_id": plan_id,
            "target": target_info,
            "scope": scope,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": plan_items,
            "total_items": len(plan_items),
            "approved_items": 0,
            "completed_items": 0,
            "findings": []
        }

        plans_store.save(plan_id, plan)
        return plan

    def _generate_recon_items(self, target_info, available_tools):
        """Generate reconnaissance plan items."""
        items = []
        url = target_info.get("url", "")
        domain = target_info.get("domain", url)

        recon_tasks = [
            {"name": "DNS Enumeration", "tool": "dnsrecon", "command": f"dnsrecon -d {domain}", "time": "2m", "risk": "info"},
            {"name": "Subdomain Discovery", "tool": "subfinder", "command": f"subfinder -d {domain} -silent", "time": "3m", "risk": "info"},
            {"name": "Port Scanning", "tool": "nmap", "command": f"nmap -sV -sC -p- --min-rate=1000 {domain}", "time": "10m", "risk": "info"},
            {"name": "Technology Detection", "tool": "whatweb", "command": f"whatweb {url}", "time": "1m", "risk": "info"},
            {"name": "WAF Detection", "tool": "wafw00f", "command": f"wafw00f {url}", "time": "1m", "risk": "info"},
            {"name": "Directory Discovery", "tool": "gobuster", "command": f"gobuster dir -u {url} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -t 50", "time": "15m", "risk": "info"},
            {"name": "Web Crawling", "tool": "katana", "command": f"katana -u {url} -d 3 -silent", "time": "5m", "risk": "info"},
        ]

        for task in recon_tasks:
            tool_name = task["tool"]
            # Only include if tool is available or provide install command
            tool_available = tool_name in available_tools or tool_name in ["curl", "dig", "host"]
            items.append({
                "id": plans_store.generate_id()[:12],
                "name": task["name"],
                "tool": tool_name,
                "command": task["command"],
                "time_estimate": task["time"],
                "risk_level": task["risk"],
                "status": "pending",
                "approved": False,
                "tool_available": tool_available,
                "rationale": f"Essential reconnaissance to discover {task['name'].lower()} for the target."
            })

        return items

    def _generate_web_scan_items(self, target_info, available_tools):
        """Generate web vulnerability scanning items from OWASP Top 10."""
        items = []
        url = target_info.get("url", "")

        for category in OWASP_TOP_10:
            for test in category["tests"]:
                primary_tool = test["tools"][0] if test["tools"] else "manual"
                tool_available = primary_tool in available_tools

                # Generate appropriate command
                command = self._generate_command(primary_tool, url, test["name"])

                items.append({
                    "id": plans_store.generate_id()[:12],
                    "name": f"[{category['id']}] {test['name']}",
                    "tool": primary_tool,
                    "command": command,
                    "time_estimate": "5m",
                    "risk_level": test["risk"],
                    "status": "pending",
                    "approved": False,
                    "tool_available": tool_available,
                    "owasp_category": category["name"],
                    "rationale": f"OWASP {category['id']}: Testing for {test['name']} vulnerabilities."
                })

        return items

    def _generate_exploit_items(self, target_info, available_tools):
        """Generate exploitation items."""
        items = []
        url = target_info.get("url", "")

        exploit_tasks = [
            {"name": "Automated Vulnerability Scan", "tool": "nuclei", "command": f"nuclei -u {url} -severity critical,high", "time": "10m", "risk": "high"},
            {"name": "Nikto Web Scanner", "tool": "nikto", "command": f"nikto -h {url}", "time": "15m", "risk": "medium"},
        ]

        for task in exploit_tasks:
            tool_available = task["tool"] in available_tools
            items.append({
                "id": plans_store.generate_id()[:12],
                "name": task["name"],
                "tool": task["tool"],
                "command": task["command"],
                "time_estimate": task["time"],
                "risk_level": task["risk"],
                "status": "pending",
                "approved": False,
                "tool_available": tool_available,
                "rationale": f"Exploitation phase: {task['name']}."
            })

        return items

    def _generate_command(self, tool, url, test_name):
        """Generate the appropriate CLI command for a tool and test."""
        commands = {
            "sqlmap": f"sqlmap -u {url} --batch --level=3 --risk=2",
            "nikto": f"nikto -h {url}",
            "nuclei": f"nuclei -u {url} -severity critical,high,medium",
            "wpscan": f"wpscan --url {url} --enumerate vp,vt,u",
            "dalfox": f"dalfox url {url} --silence",
            "xsser": f"xsser -u {url}",
            "commix": f"commix -u {url} --batch",
            "gobuster": f"gobuster dir -u {url} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
            "ffuf": f"ffuf -u {url}/FUZZ -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
            "sslscan": f"sslscan {url}",
            "hydra": f"hydra -l admin -P /usr/share/wordlists/rockyou.txt {url} http-post-form '/login:user=^USER^&pass=^PASS^:F=incorrect'",
            "nmap": f"nmap -sV -sC {url}",
            "curl": f"curl -I {url}",
        }
        return commands.get(tool, f"{tool} {url}")

    def update_item_status(self, plan_id, item_id, status, output=None):
        """Update the status of a plan item."""
        plan = plans_store.load(plan_id)
        if not plan:
            return None

        for item in plan["items"]:
            if item["id"] == item_id:
                item["status"] = status
                if output:
                    item["output"] = output
                if status == "completed":
                    plan["completed_items"] = sum(1 for i in plan["items"] if i["status"] == "completed")
                break

        plans_store.save(plan_id, plan)
        return plan

    def approve_items(self, plan_id, item_ids=None, approve_all=False):
        """Approve specific items or all items in a plan."""
        plan = plans_store.load(plan_id)
        if not plan:
            return None

        for item in plan["items"]:
            if approve_all or (item_ids and item["id"] in item_ids):
                item["approved"] = True

        plan["approved_items"] = sum(1 for i in plan["items"] if i["approved"])
        plan["status"] = "approved"
        plans_store.save(plan_id, plan)
        return plan

    def get_plan(self, plan_id):
        """Get a plan by ID."""
        return plans_store.load(plan_id)

    def list_plans(self, hunt_id=None):
        """List all plans, optionally filtered by hunt."""
        plans = plans_store.list_all()
        if hunt_id:
            plans = [p for p in plans if p.get("hunt_id") == hunt_id]
        return plans


# Singleton
attack_planner = AttackPlanner()
