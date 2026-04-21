"""
HunterAI - Kali Linux Tool Scanner & Inventory
Deep-scans the system for installed security tools, categorizes them,
and caches the inventory locally as JSON.
"""

import os
import subprocess
import json
import shutil
from datetime import datetime, timezone

from storage.local_store import tools_store


# Tool categories with known tools
TOOL_DATABASE = {
    "reconnaissance": [
        "nmap", "masscan", "rustscan", "unicornscan", "p0f",
        "whois", "dig", "host", "nslookup", "dnsrecon", "dnsmap", "dnsenum",
        "fierce", "sublist3r", "subfinder", "amass", "assetfinder",
        "theharvester", "maltego", "recon-ng", "spiderfoot",
        "shodan", "censys", "whatweb", "wafw00f", "httprobe"
    ],
    "scanning": [
        "nikto", "wpscan", "joomscan", "skipfish", "arachni",
        "nuclei", "wapiti", "zap-cli", "burpsuite",
        "gobuster", "dirb", "dirbuster", "feroxbuster", "ffuf", "wfuzz",
        "sslscan", "sslyze", "testssl.sh",
        "enum4linux", "smbclient", "smbmap", "rpcclient"
    ],
    "exploitation": [
        "sqlmap", "commix", "xsser", "dalfox",
        "msfconsole", "metasploit-framework", "searchsploit",
        "beef-xss", "bettercap", "responder",
        "crackmapexec", "impacket-scripts", "evil-winrm",
        "setoolkit", "koadic", "empire"
    ],
    "password_cracking": [
        "john", "hashcat", "hydra", "medusa", "ncrack", "patator",
        "ophcrack", "cewl", "crunch", "cupp",
        "hash-identifier", "hashid",
        "pdfcrack", "fcrackzip", "rarcrack"
    ],
    "wireless": [
        "aircrack-ng", "airodump-ng", "aireplay-ng",
        "wifite", "reaver", "pixiewps", "bully",
        "fern-wifi-cracker", "kismet"
    ],
    "forensics": [
        "autopsy", "binwalk", "foremost", "scalpel",
        "volatility", "bulk_extractor", "dc3dd",
        "exiftool", "strings", "file", "xxd", "hexdump"
    ],
    "reverse_engineering": [
        "ghidra", "radare2", "r2", "gdb", "objdump", "strace", "ltrace",
        "apktool", "jadx", "dex2jar", "jd-gui",
        "upx", "uncompyle6"
    ],
    "networking": [
        "wireshark", "tshark", "tcpdump", "netcat", "nc", "ncat", "socat",
        "proxychains", "tor", "iptables", "traceroute", "mtr",
        "hping3", "arping", "netdiscover", "arp-scan"
    ],
    "web_tools": [
        "curl", "wget", "httpie", "postman",
        "burpsuite", "zaproxy",
        "hakrawler", "gau", "waybackurls", "katana",
        "linkfinder", "secretfinder"
    ],
    "osint": [
        "sherlock", "socialscan", "holehe",
        "phoneinfoga", "twint",
        "exiftool", "metagoofil", "foca"
    ],
    "utilities": [
        "python3", "python", "pip3", "pip",
        "ruby", "gem", "perl",
        "git", "docker", "gcc", "make",
        "jq", "yq", "xmllint",
        "base64", "openssl", "gpg"
    ]
}


def scan_tool(tool_name):
    """Check if a tool is installed and get its details."""
    which_path = shutil.which(tool_name)
    if not which_path:
        return None

    info = {
        "name": tool_name,
        "path": which_path,
        "installed": True,
        "version": "unknown"
    }

    # Try to get version
    version_flags = ["--version", "-V", "-v", "version"]
    for flag in version_flags:
        try:
            result = subprocess.run(
                [which_path, flag],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.strip() or result.stderr.strip()
            if output and len(output) < 500:
                # Extract first line as version
                first_line = output.split("\n")[0].strip()
                if first_line:
                    info["version"] = first_line
                    break
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            continue

    return info


def scan_all_tools(progress_callback=None):
    """
    Scan the system for all known security tools.
    Returns a complete inventory.
    """
    inventory = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "categories": {},
        "total_installed": 0,
        "total_known": 0,
        "tools": {}
    }

    total_tools = sum(len(tools) for tools in TOOL_DATABASE.values())
    scanned = 0

    for category, tool_list in TOOL_DATABASE.items():
        category_data = {
            "installed": [],
            "missing": [],
            "total": len(tool_list)
        }

        for tool_name in tool_list:
            scanned += 1
            if progress_callback:
                progress_callback(scanned, total_tools, tool_name)

            info = scan_tool(tool_name)
            if info:
                info["category"] = category
                category_data["installed"].append(info)
                inventory["tools"][tool_name] = info
                inventory["total_installed"] += 1
            else:
                category_data["missing"].append(tool_name)

            inventory["total_known"] += 1

        inventory["categories"][category] = category_data

    # Save to local storage
    tools_store.save("inventory", inventory)

    return inventory


def get_inventory():
    """Get the cached tool inventory. Returns None if no scan has been done."""
    return tools_store.load("inventory")


def get_tool_info(tool_name):
    """Get info about a specific tool."""
    inventory = get_inventory()
    if inventory and tool_name in inventory.get("tools", {}):
        return inventory["tools"][tool_name]
    # Try live scan
    return scan_tool(tool_name)


def is_tool_available(tool_name):
    """Check if a tool is available on the system."""
    return shutil.which(tool_name) is not None


def get_install_command(tool_name):
    """Generate the install command for a missing tool."""
    # Try apt first
    commands = [
        f"sudo apt-get install -y {tool_name}",
        f"pip3 install {tool_name}",
        f"gem install {tool_name}",
        f"npm install -g {tool_name}",
        f"go install github.com/projectdiscovery/{tool_name}/v2/cmd/{tool_name}@latest"
    ]
    return commands[0]  # Default to apt

def get_tools_by_category(category):
    """Get all tools in a specific category."""
    inventory = get_inventory()
    if inventory:
        return inventory.get("categories", {}).get(category, {})
    return {"installed": [], "missing": [], "total": 0}


def get_available_tools_for_task(task_type):
    """Get tools that are available and suitable for a specific task type."""
    task_to_categories = {
        "web_scan": ["scanning", "web_tools", "exploitation"],
        "recon": ["reconnaissance", "osint"],
        "network_scan": ["reconnaissance", "networking"],
        "password_crack": ["password_cracking"],
        "exploit": ["exploitation"],
        "forensics": ["forensics", "reverse_engineering"],
        "wireless": ["wireless"]
    }

    categories = task_to_categories.get(task_type, ["utilities"])
    available = []
    inventory = get_inventory()

    if inventory:
        for cat in categories:
            cat_data = inventory.get("categories", {}).get(cat, {})
            available.extend(cat_data.get("installed", []))

    return available
