# ──────────────────────────────────────────────
# AgentPent — Kali Linux Tabanlı Production Image
# ──────────────────────────────────────────────
FROM kalilinux/kali-rolling:latest

LABEL maintainer="AgentPent Team"
LABEL description="LLM-Centered Multi-Agent Pentester"

# Sistem güncelleme + temel pentest araçları
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

# Çalışma dizini
WORKDIR /opt/agentpent

# Python bağımlılıkları
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Uygulama dosyaları
COPY . .

# Veri ve log dizinleri
RUN mkdir -p data logs reports/output

# Varsayılan port (C2 listener)
EXPOSE 4444 8080

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "from config.settings import settings; print('OK')" || exit 1

# Giriş noktası
ENTRYPOINT ["python3", "-m", "cli.main"]
CMD ["--help"]
