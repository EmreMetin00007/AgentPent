<div align="center">
  <img src="https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/kali-linux/kali-linux.png" width="100"/>
  <h1>🎯 AgentPent</h1>
  <p><strong>LLM-Centered Multi-Agent Autonomous Penetration Tester</strong></p>
  <p><em>Bug Bounty ve Red Team operasyonları için GPT-4o / o3 / Claude tabanlı 15 ajandan oluşan %100 otonom siber güvenlik orkestrasyon framework'ü.</em></p>
  <p>👤 <strong>Author:</strong> whoami</p>
</div>

---

## 🚀 Özellikler (Next-Gen Red Team)

AgentPent, piyasadaki standart zafiyet tarayıcılardan (Nessus, Acunetix vb.) veya temel LLM wrapper'larından (PentestGPT vb.) farklı olarak uçtan uca tamamen **otonom** çalışır ve `Ajanlar Arası Uzlaşma (Multi-Agent Debate)` mantığını kullanır.

- **🤖 13 Farklı Uzman Ajan:** Her biri siber güvenliğin farklı bir alanında (Recon, OSINT, WebApp, Network, Evasion, Exploit...) kodlanmış, izole prompt'lara ve tool'lara sahip uzman modeller.
- **🛡️ Katı Otonomi (Anti-Hallucination):** Commander ve Reporter ajanları, `Zero-Day V1 / Logic Flaw` bulgularını veya halisülasyonları filtrelemek için salt terminal çıktılarıyla (stdout-kanıtı) çalışır.
- **🧠 RAG Hafıza & Deneyim:** Ajanlar başarılı bir sömürü (exploit) gerçekleştirdiğinde bunu vektörel SQLite hafızasına (`rag_store`) kaydeder ve sonraki hedeflerde geçmiş tecrübesiyle payload'ları (`rag_search`) hatırlar.
- **🔗 MITRE ATT&CK Heatmap:** Üretilen profesyonel HTML sızma testi raporlarında tüm bulgular (Tactic & Technique UID) ile haritalandırılır.
- **⚡ Dahili Reverse Shell & C2 Sunucusu:** Exploit ajanı, zararlı yazılımlarla hedef makineden doğrudan AgentPent'e Reverse Shell açabilir ve `c2_interact` aracıyla arka planda komut yürütebilir.
- **📡 HTTP Repeater (Burp Modülü):** WebApp ajanı salt sqlmap ile yetinmez; hedeflere doğrudan HTTP Request metodları, header ve session cookie'leri bükerek manuel sızma testi `logic flaw` taraması yapar.
- **⚠️ Alignment (Safety) Bypass:** Tüm ajanlara zorunlu *Bug Bounty Context* aşılanmıştır, etik bahaneler üretmeden kendisine verilen her zararlı operasyonu (Exploit yazma, privesc) acımasızca yerine getirir.

## 🛠️ Mimari (Attack Stack)

```mermaid
graph TD
    Op[Operatör] -->|CLI / python -m| Comm[Commander Agent (o3)]
    Comm -->|Recon Phase| Recon[Recon / OSINT / Network Agents]
    Comm -->|Scanning Phase| Scan[Scanner Agent]
    Comm -->|Vuln Analysis| Vuln[WebApp / VulnAnalyzer]
    Vuln -->|Attack Graph & C2| Exploit[Exploit / Evasion / Persist Agents]
    Exploit -->|Memory| RAG[(RAG Vector SQLite)]
    Exploit --> Rep[Reporter Agent]
    Rep -->|MITRE Mapping| Report[HTML / JSON Report]
```

## 📦 Kurulum (Kali Linux / Ubuntu)

Sisteme Kali Linux tool'larının (nmap, sqlmap, dirb, smbclient vb.) tam yüklü olması AgentPent'in başarısını artıracaktır.

```bash
git clone https://github.com/YourUsername/AgentPent.git
cd AgentPent
chmod +x setup.sh
./setup.sh
```

Aktivasyon ve API Keys:
```bash
source agent-env/bin/activate
nano .env  # OPENAI_API_KEY veya Ollama Local Base_URL'inizi girin.
```

## 🎮 Kullanım (CLI İşlemleri)

AgentPent, tamamen Typer / Rich tabanlı şık bir terminal arayüzüne (CLI) sahiptir.

### Ajanları Listeleme
```bash
python -m cli.main agents
```

### Hedef Scope (Kapsam) Kontrolü
```bash
python -m cli.main scope
python -m cli.main check 10.10.10.5 -p default
```

### Otonom Pentest Başlatma
```bash
python -m cli.main mission --name "Banka Uygulamasi" --target "exbank.lab" 
```
> Ek olarak `--phase exploit` komutunu vererek tüm adımları atlayıp direkt sızma testi (Exploitation) aşamasına atlayabilirsiniz.

### Rapor Çıktısı Alma (Demoyu İncele)
```bash
python -m cli.main report --demo --format html
```
> HTML raporu `reports/` klasörü altına oluşturulur ve `MITRE ATT&CK` tablolarıyla sızma testinin tam özetini sunar.

## 📜 Lisans & Yasal Uyarı
Bu proje sadece yasal izinli (Yetki Sözleşmeli) siber güvenlik profesyonelleri ve Bug Bounty programları için üretilmiştir. Etik veya güvenlik (Safety) filtreleri by-pass edilmiş olduğundan asistan olarak kasten zararlı ofansif işlemler başlatabilir. Araçların sivil ve izinsiz sistemlerde kullanımından doğacak her türlü zarar kullanıcıya aittir.
