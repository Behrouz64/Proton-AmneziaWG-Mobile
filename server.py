"""Proton AmneziaWG Mobile Scanner — High-Performance Mobile Web Server."""

from __future__ import annotations
import argparse
import base64
import json
import os
import socket
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Any, Optional

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.models import ServerCluster, UserCredentials, ObfuscationPreset
from core.dns_resolver import DnsResolver
from core.checker import UdpChecker
from core.config_builder import ConfigBuilder
from core.vpn_detector import VpnDetector


class ScannerState:
    """Thread-safe application state shared across HTTP requests."""

    def __init__(self, data_file: str):
        self.data_file = data_file
        self.clusters: List[ServerCluster] = []
        self.credentials: UserCredentials = UserCredentials()
        self.preset: ObfuscationPreset = ObfuscationPreset()
        self.resolver = DnsResolver()
        self.checker = UdpChecker()
        self.is_scanning = False
        self.scan_progress = {"total": 0, "completed": 0, "working": 0, "status": "Ready"}
        self._lock = threading.Lock()
        self.load_data()

    def load_data(self) -> None:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ui = data.get("user_interface", {})
                    self.credentials = UserCredentials(
                        private_key=ui.get("private_key", "cF4B4RXTVug8PI2+mDxm8f1G/Ro0NHuWeO6jyOWRp18="),
                        address=ui.get("address", "10.2.0.2/32"),
                        dns=ui.get("dns", "10.2.0.1"),
                    )
                    self.clusters = [ServerCluster.from_dict(s) for s in data.get("servers", [])]
            except Exception as e:
                print(f"Error loading {self.data_file}: {e}")

    def save_credentials(self, privkey: str, address: str, dns: str) -> None:
        with self._lock:
            self.credentials.private_key = privkey.strip()
            self.credentials.address = address.strip() if address.strip() else "10.2.0.2/32"
            self.credentials.dns = dns.strip() if dns.strip() else "10.2.0.1"
            try:
                if os.path.exists(self.data_file):
                    with open(self.data_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["user_interface"] = self.credentials.to_dict()
                    with open(self.data_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error persisting credentials to {self.data_file}: {e}")

    def run_scan(self, continent: str = "All", tier: str = "all") -> List[ServerCluster]:
        with self._lock:
            self.is_scanning = True
            targets = [
                c for c in self.clusters
                if (continent == "All" or c.continent == continent)
                and (tier == "all" or (tier == "free" and c.is_free) or (tier == "premium" and not c.is_free))
            ]
            self.scan_progress = {"total": len(targets), "completed": 0, "working": 0, "status": "Resolving DoH..."}

        try:
            # Step 1: Encrypted DoH Resolution
            self.resolver.resolve_batch(targets)

            # Step 2: Concurrently probe UDP latency
            with self._lock:
                self.scan_progress["status"] = "Testing UDP reachability..."

            checked = self.checker.check_batch(targets)

            with self._lock:
                working = sum(1 for c in checked if c.best_ping is not None)
                self.scan_progress = {
                    "total": len(targets),
                    "completed": len(targets),
                    "working": working,
                    "status": f"Completed ({working} working)",
                }
                checked.sort(key=lambda c: (0 if c.best_ping is not None else 1, c.best_ping or 9999))
                self.is_scanning = False
            return checked
        except Exception as e:
            with self._lock:
                self.is_scanning = False
                self.scan_progress["status"] = f"Error: {e}"
            return targets


GLOBAL_STATE: Optional[ScannerState] = None


class MobileApiHandler(BaseHTTPRequestHandler):
    """Handles HTTP routes for mobile touch interface, REST API, subscriptions, and downloads."""

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, content: bytes, content_type: str, filename: Optional[str] = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Root / Index
        if path in ("/", "/index.html"):
            index_path = os.path.join(BASE_DIR, "index.html")
            if not os.path.exists(index_path):
                index_path = os.path.join(BASE_DIR, "templates", "index.html")
            with open(index_path, "rb") as f:
                content = f.read()
            self._send_file(content, "text/html; charset=utf-8")
            return

        # 2. Icons & Manifest in Root
        root_assets = {
            "/favicon.svg": ("image/svg+xml", "favicon.svg"),
            "/favicon.png": ("image/png", "favicon.png"),
            "/apple-touch-icon.png": ("image/png", "apple-touch-icon.png"),
            "/icon-192.png": ("image/png", "icon-192.png"),
            "/icon-512.png": ("image/png", "icon-512.png"),
            "/manifest.json": ("application/manifest+json", "manifest.json"),
        }
        if path in root_assets:
            ctype, fname = root_assets[path]
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    self._send_file(f.read(), ctype)
                return

        # 3. Static Assets
        if path.startswith("/static/"):
            rel_file = path[len("/static/"):]
            safe_file = os.path.basename(rel_file)
            fpath = os.path.join(BASE_DIR, "static", safe_file)
            if os.path.exists(fpath):
                ctype = "text/css" if safe_file.endswith(".css") else "application/javascript"
                with open(fpath, "rb") as f:
                    self._send_file(f.read(), ctype)
                return
            self.send_error(404, "File Not Found")
            return

        # 4. Status API
        if path == "/api/status":
            is_vpn = VpnDetector.is_vpn_active()
            clusters = GLOBAL_STATE.clusters
            free_cnt = sum(1 for c in clusters if c.is_free)
            data = {
                "vpn_active": is_vpn,
                "total_servers": len(clusters),
                "free_servers": free_cnt,
                "premium_servers": len(clusters) - free_cnt,
                "is_scanning": GLOBAL_STATE.is_scanning,
                "progress": GLOBAL_STATE.scan_progress,
                "credentials": {
                    "has_key": GLOBAL_STATE.credentials.is_configured,
                    "private_key": GLOBAL_STATE.credentials.private_key,
                    "address": GLOBAL_STATE.credentials.address,
                    "dns": GLOBAL_STATE.credentials.dns,
                    "preview": f"...{GLOBAL_STATE.credentials.private_key[-8:]}" if GLOBAL_STATE.credentials.is_configured else "Not Set",
                },
            }
            self._send_json(data)
            return

        # 5. Servers API
        if path == "/api/servers":
            continent = query.get("continent", ["All"])[0]
            tier = query.get("tier", ["all"])[0]

            def matches_cont(s_cont: str, q_cont: str) -> bool:
                if not q_cont or q_cont.lower() == "all":
                    return True
                q_norm = q_cont.lower().replace("-", "_").replace(" ", "_")
                s_norm = s_cont.lower().replace("-", "_").replace(" ", "_")
                if q_norm == s_norm:
                    return True
                if q_norm == "americas" and s_norm in ("north_america", "south_america"):
                    return True
                return False

            servers = [
                c for c in GLOBAL_STATE.clusters
                if matches_cont(c.continent, continent)
                and (tier == "all" or (tier == "free" and c.is_free) or (tier == "premium" and not c.is_free))
            ]
            resp = []
            for s in servers:
                s_dict = s.to_dict()
                s_dict["shadowrocket_url"] = ConfigBuilder.build_shadowrocket_url(s, GLOBAL_STATE.credentials, GLOBAL_STATE.preset)
                s_dict["shadowrocket_deeplink"] = ConfigBuilder.build_shadowrocket_deeplink(s, GLOBAL_STATE.credentials, GLOBAL_STATE.preset)
                resp.append(s_dict)
            self._send_json({"servers": resp, "count": len(resp)})
            return

        # 6. Pre-generated Subscription Files (sub.txt, sub_free.txt, sub_premium.txt, etc.)
        if path.startswith("/sub") and path.endswith(".txt"):
            fname = os.path.basename(path)
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    self._send_file(f.read(), "text/plain; charset=utf-8")
                return

        # 7. Live Dynamic Subscription Endpoint (/sub)
        if path == "/sub" or path.startswith("/sub"):
            continent = query.get("continent", ["All"])[0]
            tier = query.get("tier", ["all"])[0]
            no_obfs = query.get("obfs", ["1"])[0] == "0" or query.get("noobfs", ["0"])[0] == "1" or query.get("preset", [""])[0] == "none"
            preset_to_use = ObfuscationPreset(name="Pure WireGuard", jc=0, jmin=0, jmax=0, s1=0, s2=0, h1=1, h2=2, h3=3, h4=4) if no_obfs else GLOBAL_STATE.preset

            def matches_cont(s_cont: str, q_cont: str) -> bool:
                if not q_cont or q_cont.lower() == "all":
                    return True
                q_norm = q_cont.lower().replace("-", "_").replace(" ", "_")
                s_norm = s_cont.lower().replace("-", "_").replace(" ", "_")
                if q_norm == s_norm:
                    return True
                if q_norm == "americas" and s_norm in ("north_america", "south_america"):
                    return True
                return False

            working_clusters = [
                c for c in GLOBAL_STATE.clusters
                if c.effective_ip
                and matches_cont(c.continent, continent)
                and (tier == "all" or (tier == "free" and c.is_free) or (tier == "premium" and not c.is_free))
            ]
            b64_sub = ConfigBuilder.generate_subscription_base64(
                working_clusters, GLOBAL_STATE.credentials, preset_to_use, tier=tier
            )
            self._send_file(b64_sub.encode("utf-8"), "text/plain; charset=utf-8", f"proton_{tier}_{continent.lower().replace(' ', '_')}_subscription.txt")
            return

        # 8. Single Config Download
        if path == "/export/conf":
            hostname = query.get("hostname", [""])[0]
            cluster = next((c for c in GLOBAL_STATE.clusters if c.hostname == hostname), None)
            if cluster and cluster.effective_ip:
                conf = ConfigBuilder.build_amnezia_config(cluster, GLOBAL_STATE.credentials, GLOBAL_STATE.preset)
                tier_prefix = "FREE_" if cluster.is_free else ""
                fname = f"Proton_{tier_prefix}{cluster.country}_{cluster.city}_{cluster.effective_ip}.conf"
                self._send_file(conf.encode("utf-8"), "text/plain; charset=utf-8", fname)
                return
            self.send_error(404, "Server cluster not found or has no IP")
            return

        # 9. Batch ZIP Download
        if path == "/export/zip":
            tier = query.get("tier", ["all"])[0]
            working_clusters = [c for c in GLOBAL_STATE.clusters if c.effective_ip]
            zip_bytes = ConfigBuilder.generate_batch_zip_bytes(
                working_clusters, GLOBAL_STATE.credentials, GLOBAL_STATE.preset, tier=tier
            )
            self._send_file(zip_bytes, "application/zip", "Proton_AmneziaWG_Mobile_Configs.zip")
            return

        # 10. QR Code Image Endpoint
        if path == "/api/qr":
            text = query.get("text", [""])[0]
            if text:
                data_url = ConfigBuilder.generate_qr_code_data_url(text)
                if data_url.startswith("data:image/png;base64,"):
                    raw_png = base64.b64decode(data_url.split(",")[1])
                    self._send_file(raw_png, "image/png")
                    return
            self.send_error(400, "Missing text parameter for QR code")
            return

        self.send_error(404, "Endpoint Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        # 1. Trigger Batch DoH & Scan
        if path == "/api/scan":
            continent = payload.get("continent", "All")
            tier = payload.get("tier", "all")
            if GLOBAL_STATE.is_scanning:
                self._send_json({"error": "Scan already in progress"}, 409)
                return

            def _background_worker():
                GLOBAL_STATE.run_scan(continent=continent, tier=tier)

            t = threading.Thread(target=_background_worker, daemon=True)
            t.start()
            self._send_json({"message": "Scan started", "continent": continent, "tier": tier})
            return

        # 2. Update User Credentials
        if path == "/api/credentials":
            privkey = payload.get("private_key", "")
            address = payload.get("address", "10.2.0.2/32")
            dns = payload.get("dns", "10.2.0.1")
            GLOBAL_STATE.save_credentials(privkey, address, dns)
            self._send_json({"message": "Credentials updated", "configured": GLOBAL_STATE.credentials.is_configured})
            return

        # 3. Update Obfuscation Preset
        if path == "/api/obfuscation":
            preset_dict = payload.get("preset", {})
            with GLOBAL_STATE._lock:
                GLOBAL_STATE.preset = ObfuscationPreset(
                    name=preset_dict.get("name", "Custom"),
                    jc=int(preset_dict.get("jc", 4)),
                    jmin=int(preset_dict.get("jmin", 50)),
                    jmax=int(preset_dict.get("jmax", 1000)),
                    s1=int(preset_dict.get("s1", 0)),
                    s2=int(preset_dict.get("s2", 0)),
                    h1=int(preset_dict.get("h1", 1)),
                    h2=int(preset_dict.get("h2", 2)),
                    h3=int(preset_dict.get("h3", 3)),
                    h4=int(preset_dict.get("h4", 4)),
                )
            self._send_json({"message": "Preset updated", "preset": GLOBAL_STATE.preset.to_dict()})
            return

        self.send_error(404, "Endpoint Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress noisy request logs."""
        pass


def get_local_ip() -> str:
    """Find LAN IPv4 address for QR code / phone connection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def main() -> None:
    parser = argparse.ArgumentParser(description="Proton AmneziaWG Mobile Server")
    parser.add_argument("--port", type=int, default=8081, help="Port to listen on (default: 8081)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    args = parser.parse_args()

    data_file = os.path.join(BASE_DIR, "data", "proton_servers.json")
    global GLOBAL_STATE
    GLOBAL_STATE = ScannerState(data_file)

    server_address = (args.host, args.port)
    httpd = ThreadingHTTPServer(server_address, MobileApiHandler)

    local_ip = get_local_ip()
    port = args.port

    print("==================================================================")
    print("       ⚛️  Proton AmneziaWG Mobile Standalone Server  ⚛️           ")
    print("==================================================================")
    print(f" Loaded Clusters   : {len(GLOBAL_STATE.clusters)} deduplicated endpoints")
    free_cnt = sum(1 for c in GLOBAL_STATE.clusters if c.is_free)
    print(f"   ├─ Free Nodes   : {free_cnt}")
    print(f"   └─ Plus Nodes   : {len(GLOBAL_STATE.clusters) - free_cnt}")
    print(f" Local Access      : http://localhost:{port}")
    print(f" Mobile / LAN Access: http://{local_ip}:{port}")
    print("==================================================================")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()


if __name__ == "__main__":
    main()
