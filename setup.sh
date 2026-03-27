#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] AgentPent full setup is starting..."
echo "[*] Updating apt package indexes..."
sudo apt-get update

echo "[*] Installing required system packages..."
sudo apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3.11 \
    python3.11-venv \
    nmap \
    nikto \
    sqlmap \
    dirb \
    smbclient

echo "[*] Bootstrapping the local AgentPent launcher..."
"${SCRIPT_DIR}/agentpent" --help >/dev/null

echo
echo "[+] Setup completed."
echo "[+] Use the project directly from the repo root with:"
echo "    ./agentpent --help"
echo "    ./agentpent agents"
echo "    ./agentpent mission --name 'Kali Test' --target '127.0.0.1' --phase reconnaissance"
