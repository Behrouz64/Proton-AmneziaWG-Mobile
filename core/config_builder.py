"""Config generator for Proton AmneziaWG, Shadowrocket deep links, subscriptions, and QR codes."""

from __future__ import annotations
import base64
import io
import json
import re
import urllib.parse
import zipfile
from typing import List, Optional, Tuple
from core.models import ServerCluster, UserCredentials, ObfuscationPreset

try:
    import qrcode
    _QR_AVAILABLE = True
except ImportError:
    _QR_AVAILABLE = False


class ConfigBuilder:
    """Generates WireGuard and AmneziaWG configs, Shadowrocket URLs, subscriptions, and ZIPs."""

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Strip non-alphanumeric chars for safe filenames across OSes."""
        cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned.strip("._")

    @classmethod
    def build_remark(cls, cluster: ServerCluster, ip: str, ping_ms: Optional[float] = None) -> str:
        """Generate human-readable remark string with emoji and ping."""
        loc = cluster.server_name if cluster.server_name else (cluster.city if cluster.city else cluster.country)
        tier_badge = "🆓 " if cluster.is_free else ""
        sc_badge = "🛡️ " if cluster.secure_core else ""
        ping_str = f" — {int(ping_ms)}ms" if ping_ms is not None else ""
        return f"⚛️ {tier_badge}{sc_badge}{cluster.flag} {cluster.country} — {loc} ({ip}){ping_str}"

    @classmethod
    def build_amnezia_config(
        cls,
        cluster: ServerCluster,
        credentials: UserCredentials,
        preset: Optional[ObfuscationPreset] = None,
        target_ip: Optional[str] = None,
    ) -> str:
        """Generate a complete AmneziaWG .conf configuration."""
        ip = target_ip or cluster.effective_ip
        if not ip:
            raise ValueError(f"Cluster {cluster.display_name} has no valid IP.")

        preset = preset or ObfuscationPreset()
        privkey = credentials.private_key if credentials.private_key else "INSERT_YOUR_PRIVATE_KEY_HERE"
        address = credentials.address if credentials.address else "10.2.0.2/32"
        dns = credentials.dns if credentials.dns else "10.2.0.1"

        lines = [
            f"# Proton {'AmneziaWG' if preset.is_obfuscated else 'WireGuard'} — {cluster.display_name}",
            f"# Endpoint: {ip}:{cluster.port} (Tier: {cluster.tier.upper()})",
            "",
            "[Interface]",
            f"PrivateKey = {privkey}",
            f"Address = {address}",
            f"DNS = {dns}",
        ]
        if preset.is_obfuscated:
            lines.extend([
                "",
                "# AmneziaWG Obfuscation (DPI Bypass)",
                f"Jc = {preset.jc}",
                f"Jmin = {preset.jmin}",
                f"Jmax = {preset.jmax}",
                f"S1 = {preset.s1}",
                f"S2 = {preset.s2}",
                f"H1 = {preset.h1}",
                f"H2 = {preset.h2}",
                f"H3 = {preset.h3}",
                f"H4 = {preset.h4}",
            ])
        lines.extend([
            "",
            "[Peer]",
            f"PublicKey = {cluster.public_key}",
            "AllowedIPs = 0.0.0.0/0, ::/0",
            f"Endpoint = {ip}:{cluster.port}",
            "PersistentKeepalive = 25",
        ])
        return "\n".join(lines) + "\n"

    @classmethod
    def build_shadowrocket_url(
        cls,
        cluster: ServerCluster,
        credentials: UserCredentials,
        preset: Optional[ObfuscationPreset] = None,
        target_ip: Optional[str] = None,
        ping_ms: Optional[float] = None,
    ) -> str:
        """Generate Shadowrocket-compatible wg:// URL."""
        ip = target_ip or cluster.effective_ip
        if not ip:
            raise ValueError(f"Cluster {cluster.display_name} has no valid IP.")

        preset = preset or ObfuscationPreset()
        privkey = credentials.private_key if credentials.private_key else "INSERT_YOUR_PRIVATE_KEY_HERE"
        address = credentials.address if credentials.address else "10.2.0.2/32"
        clean_ip = address.split("/")[0].strip()
        dns = credentials.dns if credentials.dns else "10.2.0.1"

        pubkey_encoded = urllib.parse.quote(cluster.public_key, safe="")
        privkey_encoded = urllib.parse.quote(privkey, safe="")
        dns_encoded = urllib.parse.quote(dns, safe="")

        params = [
            f"publicKey={pubkey_encoded}",
            f"privateKey={privkey_encoded}",
            f"ip={clean_ip}",
            f"dns={dns_encoded}",
            "mtu=1280",
            "udp=1",
            "keepalive=25",
        ]

        if preset.is_obfuscated:
            obfs_dict = {
                "s1": str(preset.s1),
                "h2": str(preset.h2),
                "jmax": str(preset.jmax),
                "s2": str(preset.s2),
                "h3": str(preset.h3),
                "jc": str(preset.jc),
                "jmin": str(preset.jmin),
                "h1": str(preset.h1),
                "h4": str(preset.h4),
            }
            obfs_json = json.dumps(obfs_dict, separators=(",", ":"))
            obfs_param = urllib.parse.quote(obfs_json)
            params.extend([
                "obfs=amneziawg",
                f"obfsParam={obfs_param}",
            ])

        param_str = "&".join(params)
        remark = cls.build_remark(cluster, ip, ping_ms)
        remark_encoded = urllib.parse.quote(remark)
        return f"wg://{ip}:{cluster.port}?{param_str}#{remark_encoded}"

    @classmethod
    def build_shadowrocket_deeplink(
        cls,
        cluster: ServerCluster,
        credentials: UserCredentials,
        preset: Optional[ObfuscationPreset] = None,
        target_ip: Optional[str] = None,
    ) -> str:
        """Generate shadowrocket://add/ deep link to import directly on iOS."""
        wg_url = cls.build_shadowrocket_url(cluster, credentials, preset, target_ip)
        return f"shadowrocket://add/{wg_url}" if wg_url else ""

    @classmethod
    def generate_subscription_base64(
        cls,
        clusters: List[ServerCluster],
        credentials: UserCredentials,
        preset: Optional[ObfuscationPreset] = None,
        tier: str = "all",  # "all", "premium", "free"
    ) -> str:
        """Build Base64 subscription payload for Shadowrocket."""
        urls: List[str] = []
        for cluster in clusters:
            if tier == "free" and not cluster.is_free:
                continue
            if tier == "premium" and cluster.is_free:
                continue

            target_ips = cluster.resolved_ips if cluster.resolved_ips else ([cluster.best_ip] if cluster.best_ip else ([cluster.hostname] if cluster.hostname else []))
            for ip in target_ips:
                try:
                    url = cls.build_shadowrocket_url(cluster, credentials, preset, target_ip=ip, ping_ms=cluster.best_ping)
                    urls.append(url)
                except ValueError:
                    continue

        content = "\n".join(urls)
        return base64.b64encode(content.encode("utf-8")).decode("utf-8")

    @classmethod
    def generate_batch_zip_bytes(
        cls,
        clusters: List[ServerCluster],
        credentials: UserCredentials,
        preset: Optional[ObfuscationPreset] = None,
        tier: str = "all",
    ) -> bytes:
        """Create an in-memory ZIP archive containing all .conf files grouped by continent/country."""
        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for cluster in clusters:
                if tier == "free" and not cluster.is_free:
                    continue
                if tier == "premium" and cluster.is_free:
                    continue

                target_ips = cluster.resolved_ips if cluster.resolved_ips else ([cluster.best_ip] if cluster.best_ip else ([cluster.hostname] if cluster.hostname else []))
                for idx, ip in enumerate(target_ips):
                    try:
                        conf_text = cls.build_amnezia_config(cluster, credentials, preset, target_ip=ip)
                        folder = cls.sanitize_filename(cluster.continent if cluster.continent else "Global")
                        tier_prefix = "FREE_" if cluster.is_free else ""
                        city_str = cls.sanitize_filename(cluster.city if cluster.city else "Server")
                        country_str = cls.sanitize_filename(cluster.country)
                        fname = f"{folder}/{tier_prefix}{country_str}_{city_str}_{ip}.conf"
                        zf.writestr(fname, conf_text.encode("utf-8"))
                        count += 1
                    except ValueError:
                        continue

            readme = (
                "Proton VPN AmneziaWG Mobile Edition\n"
                "===================================\n\n"
                f"Total Configurations: {count}\n"
                "Import these .conf files into AmneziaVPN, WireGuard, or Shadowrocket.\n"
                "Obfuscation Preset: Iran Standard DPI Bypass (Jc=4, Jmin=50, Jmax=1000)\n"
            )
            zf.writestr("README.txt", readme.encode("utf-8"))
        buf.seek(0)
        return buf.getvalue()

    @classmethod
    def generate_qr_code_data_url(cls, text: str) -> str:
        """Generate base64 PNG data URI for a QR code."""
        if not _QR_AVAILABLE:
            raise RuntimeError("qrcode package not available.")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
