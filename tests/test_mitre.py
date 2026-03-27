"""AgentPent — MITRE ATT&CK Unit Tests."""

from core.mission import Finding, Severity, AttackPhase
from core.report_generator import report_generator, Mission
import json

def test_mitre_finding_model():
    # Modelin yeni listeleri kabul ettiğinden emin ol
    f = Finding(
        title="Zero-Day Logic Flaw",
        description="Bypassed login via HTTP Repeater parameter tampering.",
        target="192.168.1.100",
        severity=Severity.HIGH,
        mitre_tactics=["TA0006", "TA0008"],
        mitre_techniques=["T1110"]
    )
    
    assert "TA0006" in f.mitre_tactics
    assert "T1110" in f.mitre_techniques

def test_mitre_report_html_rendering():
    # Rapor generatörünün html cıktısında rozet basıp basmadıgını kontrol et
    m = Mission(name="Mitre Test")
    f = Finding(
        title="Test Vuln",
        target="10.0.0.1",
        description="Desc",
        mitre_tactics=["TA0001"],
        mitre_techniques=["T1190"]
    )
    m.add_finding(f)
    
    html = report_generator.generate(m, format="html")
    
    # Yeni tablo başlığı var mı?
    assert "<th>MITRE ATT&CK</th>" in html
    # Rozetler doğru parse edilmiş mi?
    assert ">TA0001</span>" in html
    assert ">T1190</span>" in html

def test_mitre_report_json_rendering():
    m = Mission(name="Mitre JSON Test")
    f = Finding(
        title="Test JSON Vuln",
        target="10.0.0.2",
        description="Desc",
        mitre_tactics=["TA0008"],
        mitre_techniques=["T1059", "T1003"]
    )
    m.add_finding(f)
    
    json_out = report_generator.generate(m, format="json")
    data = json.loads(json_out)
    
    findings = data.get("findings", [])
    assert len(findings) == 1
    assert "TA0008" in findings[0]["mitre_tactics"]
    assert "T1059" in findings[0]["mitre_techniques"]
