"""Data models for Proton AmneziaWG Mobile Scanner."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


def country_code_to_flag(code: str) -> str:
    """Convert 2-letter ISO country code to Unicode flag emoji."""
    if not code or len(code) != 2:
        return "🌐"
    try:
        return "".join(chr(127397 + ord(c.upper())) for c in code)
    except Exception:
        return "🌐"


@dataclass
class ObfuscationPreset:
    name: str = "Proton Standard (DPI Bypass)"
    jc: int = 4
    jmin: int = 50
    jmax: int = 1000
    s1: int = 0
    s2: int = 0
    h1: int = 1
    h2: int = 2
    h3: int = 3
    h4: int = 4

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserCredentials:
    private_key: str = ""
    address: str = "10.2.0.2/32"
    dns: str = "10.2.0.1"

    @property
    def is_configured(self) -> bool:
        return bool(self.private_key and len(self.private_key.strip()) >= 32 and "YOUR_" not in self.private_key)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    ip: str
    port: int = 51820
    ping_ms: Optional[float] = None
    status: str = "Unchecked"  # "OK", "Slow", "Timeout", "Failed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServerCluster:
    country: str
    country_code: str
    city: str
    continent: str
    hostname: str
    public_key: str
    port: int = 51820
    resolved_ips: List[str] = field(default_factory=list)
    tier: str = "premium"  # "premium" or "free"
    secure_core: bool = False
    port_forward: bool = False
    server_name: str = ""
    best_ip: Optional[str] = None
    best_ping: Optional[float] = None
    scan_results: List[ScanResult] = field(default_factory=list)

    @property
    def is_free(self) -> bool:
        return self.tier == "free"

    @property
    def flag(self) -> str:
        return country_code_to_flag(self.country_code)

    @property
    def display_name(self) -> str:
        prefix = "⚛️"
        tier_str = " 🆓" if self.is_free else ""
        sc_str = " 🛡️" if self.secure_core else ""
        loc = self.server_name if self.server_name else (self.city if self.city else self.country)
        return f"{prefix}{tier_str}{sc_str} {self.flag} {self.country} — {loc}"

    @property
    def effective_ip(self) -> str:
        if self.best_ip:
            return self.best_ip
        if self.resolved_ips:
            return self.resolved_ips[0]
        return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "country_code": self.country_code,
            "city": self.city,
            "continent": self.continent,
            "hostname": self.hostname,
            "public_key": self.public_key,
            "port": self.port,
            "resolved_ips": self.resolved_ips,
            "tier": self.tier,
            "secure_core": self.secure_core,
            "port_forward": self.port_forward,
            "server_name": self.server_name,
            "best_ip": self.best_ip,
            "best_ping": self.best_ping,
            "effective_ip": self.effective_ip,
            "flag": self.flag,
            "display_name": self.display_name,
            "scan_results": [r.to_dict() for r in self.scan_results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerCluster":
        return cls(
            country=data.get("country", ""),
            country_code=data.get("country_code", "XX"),
            city=data.get("city", ""),
            continent=data.get("continent", "Global"),
            hostname=data.get("hostname", ""),
            public_key=data.get("public_key", ""),
            port=data.get("port", 51820),
            resolved_ips=data.get("resolved_ips", []),
            tier=data.get("tier", "premium"),
            secure_core=data.get("secure_core", False),
            port_forward=data.get("port_forward", False),
            server_name=data.get("server_name", ""),
            best_ip=data.get("best_ip"),
            best_ping=data.get("best_ping"),
        )
