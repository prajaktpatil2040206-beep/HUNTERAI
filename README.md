# HUNTERAI

**HunterAI** is an elite, autonomous AI-powered penetration testing and bug bounty platform designed to run directly on Kali Linux. It integrates multiple AI models (Gemini, Groq, Ollama, OpenAI, etc.) with core security tools to automate reconnaissance, vulnerability scanning, and exploitation with real-time WebSocket terminal execution.

![HunterAI dark lab](https://via.placeholder.com/800x400.png?text=HunterAI+GUI)

## 🌟 Key Features

* **Real-time Terminal Execution:** Seamless WebSocket streaming of terminal output right into the browser. Runs native Kali commands without `sudo` prompts (runs as root).
* **Multi-AI Brain:** Support for dozens of LLMs. Seamlessly switch between local (Ollama) and cloud (Gemini, Groq, OpenAI) models.
* **Auto-Fix & Self-Healing:** The AI detects command failures, automatically figures out what went wrong, installs missing tools, and fixes its own mistakes.
* **Action Approval Workflow:** Choose between `Feedback Mode` (you approve every command) or `Autonomous Mode` (the AI executes the entire attack plan automatically).
* **Vulnerability & Report Generation:** Automatically parses findings into a structured report based on CVSS 3.1 severity metrics.

## 🚀 Installation & Setup

HunterAI requires Python 3 and a Linux environment (Kali Linux recommended).

### 1. Clone the Repository

```bash
git clone https://github.com/prajaktpatil2040206-beep/HUNTERAI.git
cd HUNTERAI
```

### 2. Install Dependencies

You can install the required Python packages using pip:

```bash
# Recommended: Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Quick System Setup (Optional but recommended on Kali)

If you have the `install.sh` script, you can run it to automatically set up the system executable:

```bash
chmod +x install.sh
sudo ./install.sh
```

## 🎮 Running the Platform

To launch the HunterAI web interface:

```bash
# If you used the global installer:
sudo HUNTERAI

# Or run the script directly:
sudo python3 app.py
```

*Note: running as `sudo` is highly recommended so the AI engine can execute native Kali networking and reconnaissance tools without permission prompts.*

Once running, navigate to **http://localhost:5000** in your browser.

## 🛠️ Configuration & API Keys

Before starting a hunt, click the **Settings ⚙️** icon in the sidebar to configure your AI models.
You can use:
* Free APIs like Google Gemini or Groq.
* Paid services like OpenAI GPT-4.
* Completely local and private models via Ollama.

## ⚖️ Disclaimer

**HunterAI is designed for authorized penetration testing, bug bounty hunting, and educational purposes only.** Do not use this tool against targets you do not have explicit permission to test. The developers hold no liability for misuse.
