"""
HunterAI - Scope Manager
Enforces scope boundaries, manages legal disclaimers,
and ensures authorized testing only.
"""

import re
import ipaddress
from urllib.parse import urlparse
from datetime import datetime, timezone

from storage.local_store import LocalStore

scope_store = LocalStore("scope")


class ScopeManager:
    """Manages testing scope and legal compliance."""

    def create_scope(self, hunt_id, targets, scope_type="strict"):
        """
        Create a scope definition for a hunt.

        targets: list of dicts with {type: 'domain'|'ip'|'cidr'|'wildcard', value: '...'}
        scope_type: 'strict' (blocks out-of-scope) or 'advisory' (warns only)
        """
        scope_id = hunt_id  # 1:1 with hunts

        scope_data = {
            "hunt_id": hunt_id,
            "targets": targets,
            "scope_type": scope_type,
            "legal_acknowledged": False,
            "acknowledged_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "log": []
        }

        scope_store.save(scope_id, scope_data)
        return scope_data

    def acknowledge_legal(self, hunt_id):
        """Record legal disclaimer acknowledgment."""
        scope = scope_store.load(hunt_id)
        if scope:
            scope["legal_acknowledged"] = True
            scope["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
            scope_store.save(hunt_id, scope)
            return True
        return False

    def check_scope(self, hunt_id, target):
        """
        Check if a target (URL, IP, domain) is in scope.
        Returns (is_in_scope, message).
        """
        scope = scope_store.load(hunt_id)
        if not scope:
            return True, "No scope defined — all targets allowed."

        if not scope.get("legal_acknowledged"):
            return False, "Legal disclaimer not acknowledged. Please review and accept before testing."

        # Parse the target
        target_domain = None
        target_ip = None

        try:
            parsed = urlparse(target)
            target_domain = parsed.hostname or target
        except Exception:
            target_domain = target

        try:
            target_ip = ipaddress.ip_address(target_domain)
        except ValueError:
            target_ip = None

        # Check against scope targets
        for scope_target in scope.get("targets", []):
            t_type = scope_target.get("type", "domain")
            t_value = scope_target.get("value", "")

            if t_type == "domain":
                if target_domain and (target_domain == t_value or target_domain.endswith("." + t_value)):
                    self._log_scope_check(hunt_id, target, True)
                    return True, f"In scope: matches domain {t_value}"

            elif t_type == "wildcard":
                pattern = t_value.replace("*.", "(.+\\.)?").replace("*", ".*")
                if target_domain and re.match(pattern, target_domain):
                    self._log_scope_check(hunt_id, target, True)
                    return True, f"In scope: matches wildcard {t_value}"

            elif t_type == "ip":
                if target_ip and str(target_ip) == t_value:
                    self._log_scope_check(hunt_id, target, True)
                    return True, f"In scope: matches IP {t_value}"

            elif t_type == "cidr":
                if target_ip:
                    try:
                        network = ipaddress.ip_network(t_value, strict=False)
                        if target_ip in network:
                            self._log_scope_check(hunt_id, target, True)
                            return True, f"In scope: within CIDR {t_value}"
                    except ValueError:
                        pass

        # Out of scope
        self._log_scope_check(hunt_id, target, False)
        scope_type = scope.get("scope_type", "strict")

        if scope_type == "strict":
            return False, f"OUT OF SCOPE: {target} is not in the defined scope. Execution blocked."
        else:
            return True, f"WARNING: {target} is outside the defined scope. Proceeding in advisory mode."

    def check_command(self, hunt_id, command):
        """
        Check if a command targets in-scope resources.
        Extracts URLs and IPs from the command and checks each.
        """
        # Extract URLs from command
        url_pattern = r'https?://[^\s\'"<>]+'
        ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'

        urls = re.findall(url_pattern, command)
        ips = re.findall(ip_pattern, command)

        targets = urls + ips

        if not targets:
            # No recognizable targets in command — allow
            return True, "No target URLs or IPs detected in command."

        for target in targets:
            in_scope, message = self.check_scope(hunt_id, target)
            if not in_scope:
                return False, message

        return True, "All targets in command are in scope."

    def _log_scope_check(self, hunt_id, target, in_scope):
        """Log a scope check for audit."""
        scope = scope_store.load(hunt_id)
        if scope:
            scope.setdefault("log", []).append({
                "target": target,
                "in_scope": in_scope,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            # Keep only last 1000 entries
            scope["log"] = scope["log"][-1000:]
            scope_store.save(hunt_id, scope)

    def get_scope(self, hunt_id):
        """Get scope definition."""
        return scope_store.load(hunt_id)

    def get_legal_text(self):
        """Get the legal disclaimer text."""
        return {
            "title": "HunterAI Legal Disclaimer & Authorization",
            "text": (
                "By using HunterAI, you confirm that:\n\n"
                "1. You have EXPLICIT WRITTEN AUTHORIZATION to test the target systems.\n"
                "2. You understand that unauthorized access to computer systems is ILLEGAL.\n"
                "3. You are conducting testing as part of an authorized bug bounty program, "
                "penetration test engagement, or on systems you own.\n"
                "4. You accept full responsibility for any actions performed using this tool.\n"
                "5. HunterAI developers are not liable for any misuse of this platform.\n\n"
                "Unauthorized access to computer systems is a criminal offense under the "
                "Computer Fraud and Abuse Act (CFAA) and similar laws worldwide."
            ),
            "acknowledgment_text": "I confirm I have authorization to test the defined targets."
        }


# Singleton
scope_manager = ScopeManager()
