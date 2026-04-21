"""
HunterAI - CLI Launcher
Python entry point called by the hunterai bash script.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from app import main as start_app
    start_app()


if __name__ == "__main__":
    main()
