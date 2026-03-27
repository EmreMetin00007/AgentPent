# -----------------------------------------------------------------------------
# AgentPent - Kali Linux production image
# -----------------------------------------------------------------------------
FROM kalilinux/kali-last-release:latest

LABEL maintainer="AgentPent Team"
LABEL description="LLM-Centered Multi-Agent Pentester"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/agentpent/.venv \
    PATH="/opt/agentpent/.venv/bin:$PATH"

# System packages + pentest toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    nmap \
    nikto \
    sqlmap \
    ffuf \
    httpx-toolkit \
    nuclei \
    subfinder \
    theharvester \
    whois \
    metasploit-framework \
    chisel \
    responder \
    curl \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Application workspace
WORKDIR /opt/agentpent

# Python dependencies in an isolated virtualenv
COPY requirements.txt .
RUN python3 -m venv "$VIRTUAL_ENV" \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Application source
COPY . .

# Runtime directories
RUN mkdir -p data logs reports/output

# Default ports
EXPOSE 4444 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -m core.startup_check || exit 1

# Entrypoint
ENTRYPOINT ["python", "-m", "cli.main"]
CMD ["--help"]
