"""AgentPent — Scope Guard.

Tüm araç çağrılarını hedef kapsamına göre kontrol eder.
Kapsam dışı hedeflere erişimi engeller.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse
import fnmatch
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from config.settings import settings

logger = logging.getLogger("agentpent.scope_guard")


class OutOfScopeError(Exception):
    """Kapsam dışı hedefe erişim denemesi."""


class ScopeProfile:
    """Tek bir scope profilini temsil eder."""

    def __init__(
        self,
        name: str,
        allowed_cidrs: List[str],
        allowed_domains: List[str],
        allowed_ports: List[str],
        denied_cidrs: Optional[List[str]] = None,
        denied_domains: Optional[List[str]] = None,
        **kwargs,
    ):
        self.name = name
        self.allowed_networks = [
            ipaddress.ip_network(c, strict=False) for c in allowed_cidrs
        ]
        self.allowed_domains = allowed_domains
        self.denied_networks = [
            ipaddress.ip_network(c, strict=False) for c in (denied_cidrs or [])
        ]
        self.denied_domains = denied_domains or []

        # Port aralıklarını parse et
        self.allowed_port_ranges: List[Tuple[int, int]] = []
        for p in allowed_ports:
            if "-" in p:
                lo, hi = p.split("-", 1)
                self.allowed_port_ranges.append((int(lo), int(hi)))
            else:
                self.allowed_port_ranges.append((int(p), int(p)))

    def is_ip_allowed(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for net in self.denied_networks:
            if addr in net:
                return False
        if not self.allowed_networks:
            return False
        return any(addr in net for net in self.allowed_networks)

    def is_domain_allowed(self, domain: str) -> bool:
        domain = domain.lower().strip()
        for pattern in self.denied_domains:
            if fnmatch.fnmatch(domain, pattern.lower()):
                return False
        if not self.allowed_domains:
            return False
        return any(
            fnmatch.fnmatch(domain, pat.lower()) for pat in self.allowed_domains
        )

    def is_port_allowed(self, port: int) -> bool:
        if not self.allowed_port_ranges:
            return True
        return any(lo <= port <= hi for lo, hi in self.allowed_port_ranges)


class ScopeGuard:
    """Merkezi kapsam kontrol servisi."""

    def __init__(self, scopes_file: Optional[str] = None):
        self._path = Path(scopes_file or settings.scopes_file)
        self._profiles: Dict[str, ScopeProfile] = {}
        self._active_profile: str = "default"
        self._load()

    def _load(self):
        if not self._path.exists():
            logger.warning("Scope dosyası bulunamadı: %s", self._path)
            return
        with open(self._path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._active_profile = data.get("active_profile", "default")
        for key, profile_data in data.get("profiles", {}).items():
            self._profiles[key] = ScopeProfile(**profile_data)
        logger.info(
            "Scope yüklendi — profil: %s (%d profil)",
            self._active_profile,
            len(self._profiles),
        )

    @property
    def active(self) -> Optional[ScopeProfile]:
        return self._profiles.get(self._active_profile)

    def set_profile(self, name: str) -> None:
        if name not in self._profiles:
            raise ValueError("Scope profili bulunamadı: {}".format(name))
        self._active_profile = name
        logger.info("Scope profili değiştirildi: %s", name)

    @property
    def profile_names(self) -> List[str]:
        return list(self._profiles.keys())

    def validate_target(self, target: str, port: Optional[int] = None) -> bool:
        if not settings.require_scope:
            return True

        # Boş target → hedef-bağımsız araçlar (graph, rag vb.) için geçerli
        if not target or not target.strip():
            return True

        profile = self.active
        if profile is None:
            raise OutOfScopeError("Aktif scope profili yok — tüm hedefler engellendi")

        # URL formatındaki target'lardan host'u çıkar
        # Örn: "http://65.61.137.117" → "65.61.137.117"
        clean_target = target.strip()
        if "://" in clean_target:
            try:
                parsed = urlparse(clean_target)
                clean_target = parsed.hostname or clean_target
            except Exception:
                pass

        try:
            ipaddress.ip_address(clean_target)
            is_ip = True
        except ValueError:
            is_ip = False
        if is_ip:
            if not profile.is_ip_allowed(clean_target):
                raise OutOfScopeError(
                    "IP kapsam dışı: {} (profil: {})".format(clean_target, profile.name)
                )
        else:
            if not profile.is_domain_allowed(clean_target):
                raise OutOfScopeError(
                    "Domain kapsam dışı: {} (profil: {})".format(clean_target, profile.name)
                )
        if port is not None and not profile.is_port_allowed(port):
            raise OutOfScopeError(
                "Port kapsam dışı: {} (profil: {})".format(port, profile.name)
            )
        return True

    def check(self, target: str, port: Optional[int] = None) -> bool:
        try:
            return self.validate_target(target, port)
        except OutOfScopeError:
            return False


# Singleton
scope_guard = ScopeGuard()
