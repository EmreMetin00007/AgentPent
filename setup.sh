#!/bin/bash
# ------------------------------------------------------------------------------
# AgentPent - Kali Linux Deployment Script
# ------------------------------------------------------------------------------
set -e

echo "[*] AgentPent Kurulumu Başlıyor..."

# 1. Sistem ve Ağ Paketlerini Güncelle
echo "[*] Kali / Ubuntu Repoları Güncelleniyor..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Pentest Tool'larını Yükle (AgentPent'in kullandığı core toollar)
echo "[*] Zorunlu Pentest Araçları (Nmap, Nikto, Sqlmap vb.) Yükleniyor..."
sudo apt-get install -y nmap nikto sqlmap dirb smbclient python3-pip python3-venv git

# 3. Python Virtual Environment Oluştur
echo "[*] Python Virtual Environment (agent-env) oluşturuluyor..."
python3 -m venv agent-env
source agent-env/bin/activate

# 4. PyPI Gereksinimlerini Yükle
echo "[*] Python kütüphaneleri yükleniyor..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Env Şablonunu Kopyala
if [ ! -f .env ]; then
    echo "[*] .env.example dosyası .env olarak kopyalanıyor..."
    cp .env.example .env
    echo "[!] Lütfen .env dosyasını açıp OPENAI_API_KEY bilginizi giriniz!"
fi

echo ""
echo "[+] Kurulum Tamamlandı! 🔥"
echo "[+] Çalıştırmak için şu komutları kullanın:"
echo "    source agent-env/bin/activate"
echo "    python -m cli.main report --demo --format html"
echo "    python -m cli.main mission --name 'Kali Test' --target '10.10.10.5'"
