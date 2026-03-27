"""AgentPent — CVE / NVD API Entegrasyonu.

NVD API v2 üzerinden CVE bilgisi sorgulama.
Servis versiyon bilgisinden zafiyet eşleştirmesi yapar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("agentpent.knowledge.cve_db")

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_CPE_API = "https://services.nvd.nist.gov/rest/json/cpes/2.0"


@dataclass
class CVEEntry:
    """Tek bir CVE kaydı."""

    cve_id: str
    description: str = ""
    cvss_v3_score: Optional[float] = None
    cvss_v3_severity: str = ""
    cvss_v2_score: Optional[float] = None
    attack_vector: str = ""
    attack_complexity: str = ""
    exploitability_score: Optional[float] = None
    impact_score: Optional[float] = None
    references: List[str] = field(default_factory=list)
    cpe_matches: List[str] = field(default_factory=list)
    published: str = ""
    last_modified: str = ""
    weaknesses: List[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        """CVSS v3 skorundan severity döndür."""
        if self.cvss_v3_score is None:
            return "UNKNOWN"
        if self.cvss_v3_score >= 9.0:
            return "CRITICAL"
        elif self.cvss_v3_score >= 7.0:
            return "HIGH"
        elif self.cvss_v3_score >= 4.0:
            return "MEDIUM"
        elif self.cvss_v3_score > 0:
            return "LOW"
        return "INFO"


class CVEDB:
    """NVD API v2 istemcisi."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self._api_key:
                headers["apiKey"] = self._api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── CVE Sorgulama ────────────────────────────────────

    async def get_cve(self, cve_id: str) -> Optional[CVEEntry]:
        """CVE ID'den detaylı bilgi çek."""
        session = await self._get_session()
        url = "{}?cveId={}".format(NVD_API_BASE, cve_id)

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning("NVD API %d: %s", resp.status, cve_id)
                    return None
                data = await resp.json()
                vulns = data.get("vulnerabilities", [])
                if not vulns:
                    return None
                return self._parse_cve(vulns[0].get("cve", {}))
        except Exception as exc:
            logger.error("NVD API hatası (%s): %s", cve_id, exc)
            return None

    async def search_by_keyword(
        self, keyword: str, results_per_page: int = 20
    ) -> List[CVEEntry]:
        """Anahtar kelime ile CVE ara."""
        session = await self._get_session()
        url = "{}?keywordSearch={}&resultsPerPage={}".format(
            NVD_API_BASE, keyword, results_per_page
        )

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [
                    self._parse_cve(v.get("cve", {}))
                    for v in data.get("vulnerabilities", [])
                ]
        except Exception as exc:
            logger.error("NVD arama hatası: %s", exc)
            return []

    async def search_by_cpe(
        self,
        product: str,
        version: Optional[str] = None,
        vendor: Optional[str] = None,
        results_per_page: int = 20,
    ) -> List[CVEEntry]:
        """CPE bazlı zafiyet arama (ürün + versiyon)."""
        # CPE 2.3 formatı oluştur
        vendor_part = vendor.lower().replace(" ", "_") if vendor else "*"
        product_part = product.lower().replace(" ", "_")
        version_part = version if version else "*"

        cpe_string = "cpe:2.3:a:{}:{}:{}:*:*:*:*:*:*:*".format(
            vendor_part, product_part, version_part
        )

        session = await self._get_session()
        url = "{}?cpeName={}&resultsPerPage={}".format(
            NVD_API_BASE, cpe_string, results_per_page
        )

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    # CPE tam eşleşme yoksa keyword ile dene
                    keyword = "{} {}".format(product, version) if version else product
                    return await self.search_by_keyword(keyword, results_per_page)
                data = await resp.json()
                results = [
                    self._parse_cve(v.get("cve", {}))
                    for v in data.get("vulnerabilities", [])
                ]
                return results
        except Exception as exc:
            logger.error("NVD CPE arama hatası: %s", exc)
            return []

    # ── Parse ────────────────────────────────────────────

    def _parse_cve(self, cve_data: Dict[str, Any]) -> CVEEntry:
        """NVD API CVE yanıtını CVEEntry'ye dönüştür."""
        cve_id = cve_data.get("id", "")

        # Description (İngilizce)
        desc = ""
        for d in cve_data.get("descriptions", []):
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break

        # CVSS v3
        cvss3_score = None
        cvss3_severity = ""
        attack_vector = ""
        attack_complexity = ""
        exploitability = None
        impact = None

        metrics = cve_data.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30"):
            v3_list = metrics.get(key, [])
            if v3_list:
                v3 = v3_list[0]
                cvss_data = v3.get("cvssData", {})
                cvss3_score = cvss_data.get("baseScore")
                cvss3_severity = cvss_data.get("baseSeverity", "")
                attack_vector = cvss_data.get("attackVector", "")
                attack_complexity = cvss_data.get("attackComplexity", "")
                exploitability = v3.get("exploitabilityScore")
                impact = v3.get("impactScore")
                break

        # CVSS v2 (fallback)
        cvss2_score = None
        v2_list = metrics.get("cvssMetricV2", [])
        if v2_list:
            cvss2_score = v2_list[0].get("cvssData", {}).get("baseScore")

        # References
        refs = [
            r.get("url", "")
            for r in cve_data.get("references", [])
            if r.get("url")
        ]

        # Weaknesses (CWE)
        weaknesses = []
        for w in cve_data.get("weaknesses", []):
            for wd in w.get("description", []):
                val = wd.get("value", "")
                if val and val != "NVD-CWE-Other":
                    weaknesses.append(val)

        # Published / Modified dates
        published = cve_data.get("published", "")
        last_modified = cve_data.get("lastModified", "")

        return CVEEntry(
            cve_id=cve_id,
            description=desc,
            cvss_v3_score=cvss3_score,
            cvss_v3_severity=cvss3_severity,
            cvss_v2_score=cvss2_score,
            attack_vector=attack_vector,
            attack_complexity=attack_complexity,
            exploitability_score=exploitability,
            impact_score=impact,
            references=refs[:10],
            published=published,
            last_modified=last_modified,
            weaknesses=weaknesses,
        )


# Singleton
cve_db = CVEDB()
