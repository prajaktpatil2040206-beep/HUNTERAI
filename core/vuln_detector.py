"""
HunterAI - Vulnerability Detection & Classification Engine
Parses tool outputs, extracts structured findings, classifies by severity and CVSS.
AI-powered false positive reduction.
"""

import re
import json
from datetime import datetime, timezone

from storage.local_store import LocalStore

vulns_store = LocalStore("vulnerabilities")


# CVSS 3.1 severity thresholds
CVSS_SEVERITY = {
    "critical": (9.0, 10.0),
    "high": (7.0, 8.9),
    "medium": (4.0, 6.9),
    "low": (0.1, 3.9),
    "info": (0.0, 0.0)
}

# Common vulnerability patterns in tool outputs
VULN_PATTERNS = {
    "sql_injection": {
        "patterns": [
            r"sql injection",
            r"injectable",
            r"parameter.*is vulnerable",
            r"Type:\s*(boolean-based|time-based|UNION|error-based|stacked)"
        ],
        "severity": "critical",
        "cvss": 9.8,
        "cwe": "CWE-89"
    },
    "xss": {
        "patterns": [
            r"cross.site scripting",
            r"XSS",
            r"reflected.*script",
            r"stored.*xss",
            r"dom.*xss"
        ],
        "severity": "high",
        "cvss": 7.5,
        "cwe": "CWE-79"
    },
    "command_injection": {
        "patterns": [
            r"command injection",
            r"os command",
            r"remote code execution",
            r"RCE"
        ],
        "severity": "critical",
        "cvss": 9.8,
        "cwe": "CWE-78"
    },
    "directory_traversal": {
        "patterns": [
            r"directory traversal",
            r"path traversal",
            r"LFI",
            r"local file inclusion"
        ],
        "severity": "high",
        "cvss": 7.5,
        "cwe": "CWE-22"
    },
    "ssrf": {
        "patterns": [
            r"SSRF",
            r"server.side request forgery"
        ],
        "severity": "critical",
        "cvss": 9.1,
        "cwe": "CWE-918"
    },
    "open_redirect": {
        "patterns": [
            r"open redirect",
            r"URL redirect"
        ],
        "severity": "medium",
        "cvss": 5.4,
        "cwe": "CWE-601"
    },
    "info_disclosure": {
        "patterns": [
            r"information disclosure",
            r"sensitive data",
            r"directory listing",
            r"stack trace",
            r"server version"
        ],
        "severity": "low",
        "cvss": 3.7,
        "cwe": "CWE-200"
    },
    "ssl_tls": {
        "patterns": [
            r"weak cipher",
            r"SSL.*vulnerable",
            r"TLS 1\.0",
            r"expired certificate",
            r"self-signed"
        ],
        "severity": "medium",
        "cvss": 5.9,
        "cwe": "CWE-326"
    }
}


class VulnDetector:
    """Detects and classifies vulnerabilities from tool outputs."""

    def analyze_output(self, tool_name, output, target_url=None, hunt_id=None):
        """
        Analyze tool output for vulnerabilities.
        Returns list of detected vulnerabilities.
        """
        findings = []

        for vuln_type, config in VULN_PATTERNS.items():
            for pattern in config["patterns"]:
                matches = re.finditer(pattern, output, re.IGNORECASE)
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 200)
                    end = min(len(output), match.end() + 200)
                    context = output[start:end]

                    finding = self._create_finding(
                        vuln_type=vuln_type,
                        config=config,
                        match_text=match.group(),
                        context=context,
                        tool_name=tool_name,
                        target_url=target_url,
                        hunt_id=hunt_id
                    )
                    findings.append(finding)

        # Deduplicate by type and context
        findings = self._deduplicate(findings)

        # Save findings
        for f in findings:
            vulns_store.save(f["id"], f)

        return findings

    def _create_finding(self, vuln_type, config, match_text, context, tool_name, target_url, hunt_id):
        """Create a structured vulnerability finding."""
        finding_id = vulns_store.generate_id()[:16]

        return {
            "id": finding_id,
            "type": vuln_type,
            "name": vuln_type.replace("_", " ").title(),
            "severity": config["severity"],
            "cvss_score": config["cvss"],
            "cwe": config["cwe"],
            "tool": tool_name,
            "target_url": target_url,
            "hunt_id": hunt_id,
            "match_text": match_text,
            "evidence": context.strip(),
            "status": "unconfirmed",  # unconfirmed, confirmed, false_positive, mitigated
            "confirmed": False,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "remediation": self._get_remediation(vuln_type),
            "description": self._get_description(vuln_type)
        }

    def _deduplicate(self, findings):
        """Remove duplicate findings."""
        seen = set()
        unique = []
        for f in findings:
            key = (f["type"], f.get("target_url", ""))
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _get_description(self, vuln_type):
        """Get human-readable description for a vulnerability type."""
        descriptions = {
            "sql_injection": "SQL Injection allows an attacker to interfere with the queries an application makes to its database, potentially accessing or modifying data.",
            "xss": "Cross-Site Scripting (XSS) allows attackers to inject client-side scripts into web pages viewed by other users.",
            "command_injection": "Command Injection allows an attacker to execute arbitrary operating system commands on the server.",
            "directory_traversal": "Directory Traversal allows an attacker to read files on the server that are outside the application's root directory.",
            "ssrf": "Server-Side Request Forgery allows an attacker to make requests from the server to internal services.",
            "open_redirect": "Open Redirect allows an attacker to redirect users to malicious external sites.",
            "info_disclosure": "Information Disclosure reveals sensitive information that could aid an attacker.",
            "ssl_tls": "SSL/TLS misconfiguration could allow attackers to intercept or modify encrypted communications."
        }
        return descriptions.get(vuln_type, "A security vulnerability was detected.")

    def _get_remediation(self, vuln_type):
        """Get remediation recommendations."""
        remediations = {
            "sql_injection": "Use parameterized queries/prepared statements. Never concatenate user input into SQL queries. Implement input validation and use an ORM.",
            "xss": "Implement context-sensitive output encoding. Use Content Security Policy (CSP) headers. Validate and sanitize all user input.",
            "command_injection": "Avoid system commands where possible. Use parameterized APIs. Implement strict input validation with whitelist approach.",
            "directory_traversal": "Validate and sanitize file paths. Use a whitelist of allowed files. Implement proper access controls.",
            "ssrf": "Validate and whitelist allowed URLs. Block requests to internal networks. Use network-level controls.",
            "open_redirect": "Validate redirect URLs against a whitelist. Avoid user-controlled redirect parameters.",
            "info_disclosure": "Remove verbose error messages. Disable directory listing. Remove server version headers.",
            "ssl_tls": "Use TLS 1.2 or higher. Disable weak ciphers. Use valid, trusted certificates."
        }
        return remediations.get(vuln_type, "Review and remediate the identified vulnerability.")

    def get_findings(self, hunt_id=None):
        """Get all findings, optionally filtered by hunt."""
        findings = vulns_store.list_all()
        if hunt_id:
            findings = [f for f in findings if f.get("hunt_id") == hunt_id]
        return findings

    def confirm_finding(self, finding_id):
        """Mark a finding as confirmed."""
        return vulns_store.update(finding_id, {"confirmed": True, "status": "confirmed"})

    def mark_false_positive(self, finding_id):
        """Mark a finding as false positive."""
        return vulns_store.update(finding_id, {"confirmed": False, "status": "false_positive"})

    def get_severity_summary(self, hunt_id=None):
        """Get a summary of findings by severity."""
        findings = self.get_findings(hunt_id)
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": len(findings)}
        for f in findings:
            sev = f.get("severity", "info")
            if sev in summary:
                summary[sev] += 1
        return summary


# Singleton
vuln_detector = VulnDetector()
