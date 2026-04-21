#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# HunterAI — Setup Script for Kali Linux
# Run: sudo bash install.sh
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${RED}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║     🛡  H U N T E R A I  —  INSTALLER           ║"
echo "  ║     Autonomous Bug Bounty Platform               ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] Please run as root: sudo bash install.sh${NC}"
    exit 1
fi

echo -e "${CYAN}[*] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl wget > /dev/null 2>&1

echo -e "${CYAN}[*] Creating Python virtual environment...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv 2>/dev/null || true

echo -e "${CYAN}[*] Installing Python dependencies...${NC}"
source venv/bin/activate 2>/dev/null || true
pip3 install -r requirements.txt --quiet 2>/dev/null || pip3 install flask flask-socketio flask-cors requests cryptography python-dotenv psutil gevent gevent-websocket openai google-genai anthropic markdown Jinja2 --quiet

echo -e "${CYAN}[*] Creating data directories...${NC}"
mkdir -p "$INSTALL_DIR/data/projects"
mkdir -p "$INSTALL_DIR/data/hunts"
mkdir -p "$INSTALL_DIR/data/chats"
mkdir -p "$INSTALL_DIR/data/models"
mkdir -p "$INSTALL_DIR/data/tools"
mkdir -p "$INSTALL_DIR/data/assets"
mkdir -p "$INSTALL_DIR/data/reports"
mkdir -p "$INSTALL_DIR/data/scope"
mkdir -p "$INSTALL_DIR/data/plans"
mkdir -p "$INSTALL_DIR/data/vulnerabilities"
mkdir -p "$INSTALL_DIR/data/terminal_logs"
mkdir -p "$INSTALL_DIR/data/actions"

echo -e "${CYAN}[*] Making hunterai command executable...${NC}"
chmod +x "$INSTALL_DIR/hunterai"

# Create global symlink so 'hunterai' works from anywhere
ln -sf "$INSTALL_DIR/hunterai" /usr/local/bin/hunterai
# Also create uppercase alias
ln -sf "$INSTALL_DIR/hunterai" /usr/local/bin/HUNTERAI

echo -e "${CYAN}[*] Installing Playwright browsers (optional)...${NC}"
python3 -m playwright install chromium 2>/dev/null || echo -e "${YELLOW}[!] Playwright install skipped (run manually: python3 -m playwright install)${NC}"

echo -e "${CYAN}[*] Running initial tool scan...${NC}"
cd "$INSTALL_DIR"
python3 -c "from core.tool_scanner import scan_all_tools; r=scan_all_tools(); print(f'Found {r[\"total_installed\"]} tools')" 2>/dev/null || echo -e "${YELLOW}[!] Initial tool scan skipped${NC}"

echo ""
echo -e "${GREEN}  ╔══════════════════════════════════════════════════╗"
echo -e "  ║     ✓  INSTALLATION COMPLETE                     ║"
echo -e "  ║                                                    ║"
echo -e "  ║     Run HunterAI:                                  ║"
echo -e "  ║       sudo hunterai                                ║"
echo -e "  ║       sudo HUNTERAI                                ║"
echo -e "  ║                                                    ║"
echo -e "  ║     Open: http://localhost:5000                    ║"
echo -e "  ╚══════════════════════════════════════════════════╝${NC}"
echo ""
