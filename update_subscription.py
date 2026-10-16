"""Script to resolve Proton VPN subdomains via DoH and generate subscription files."""

from __future__ import annotations
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "proton_servers.json")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

servers = data["servers"]
ui = data.get("user_interface", {})
client_privkey = ui.get("private_key", "cF4B4RXTVug8PI2+mDxm8f1G/Ro0NHuWeO6jyOWRp18=")
client_ip = ui.get("address", "10.2.0.2/32").split("/")[0].strip()
dns_servers = ui.get("dns", "10.2.0.1").strip()

obfs_dict = {
    "s1": "0",
    "h2": "2",
    "jmax": "1000",
    "s2": "0",
    "h3": "3",
    "jc": "4",
    "jmin": "50",
    "h1": "1",
    "h4": "4",
}
obfs_param = urllib.parse.quote(json.dumps(obfs_dict, separators=(",", ":")))


def get_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🌐"
    try:
        return "".join(chr(127397 + ord(c.upper())) for c in code)
    except Exception:
        return "🌐"


def generate_node_url(server: dict, ip: str, sub_index: int = 0, total_ips: int = 1) -> str:
    country = server.get("country", "")
    city = server.get("city", "")
    server_name = server.get("server_name", "")
    tier = server.get("tier", "premium")
    secure_core = server.get("secure_core", False)
    flag = get_flag(server.get("country_code", ""))
    pubkey = urllib.parse.quote(server.get("public_key", ""), safe="")
    privkey = urllib.parse.quote(client_privkey, safe="")
    port = server.get("port", 51820)

    suffix = f" #{sub_index + 1}" if total_ips > 1 else ""
    loc = server_name if server_name else (city if city else country)
    tier_badge = "🆓 " if tier == "free" else ""
    sc_badge = "🛡️ " if secure_core else ""
    remark_str = f"⚛️ {tier_badge}{sc_badge}{flag} {country} — {loc}{suffix} ({ip})"
    remark = urllib.parse.quote(remark_str)

    params = [
        f"publicKey={pubkey}",
        f"privateKey={privkey}",
        f"ip={client_ip}",
        f"dns={urllib.parse.quote(dns_servers, safe='')}",
        "mtu=1280",
        "udp=1",
        "keepalive=25",
        "obfs=amneziawg",
        f"obfsParam={obfs_param}",
    ]
    return f"wg://{ip}:{port}?{'&'.join(params)}#{remark}"


def main():
    print(f"Loaded {len(servers)} deduplicated Proton server clusters.")

    # Generate all wg:// nodes
    all_nodes = []
    free_nodes = []
    premium_nodes = []

    for s in servers:
        ips = s.get("resolved_ips", [])
        if not ips:
            continue
        tier = s.get("tier", "premium")
        for idx, ip in enumerate(ips):
            node_url = generate_node_url(s, ip, sub_index=idx, total_ips=len(ips))
            all_nodes.append(node_url)
            if tier == "free":
                free_nodes.append(node_url)
            else:
                premium_nodes.append(node_url)

    print(f"Total nodes: {len(all_nodes)} (Free: {len(free_nodes)}, Premium: {len(premium_nodes)})")

    # 1. sub.txt & sub_base64.txt (All)
    with open(os.path.join(BASE_DIR, "sub.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_nodes) + "\n")
    b64_all = base64.b64encode("\n".join(all_nodes).encode("utf-8")).decode("utf-8")
    with open(os.path.join(BASE_DIR, "sub_base64.txt"), "w", encoding="utf-8") as f:
        f.write(b64_all + "\n")

    # 2. sub_free.txt & sub_free_b64.txt
    with open(os.path.join(BASE_DIR, "sub_free.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(free_nodes) + "\n")
    b64_free = base64.b64encode("\n".join(free_nodes).encode("utf-8")).decode("utf-8")
    with open(os.path.join(BASE_DIR, "sub_free_b64.txt"), "w", encoding="utf-8") as f:
        f.write(b64_free + "\n")

    # 3. sub_premium.txt & sub_premium_b64.txt
    with open(os.path.join(BASE_DIR, "sub_premium.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(premium_nodes) + "\n")
    b64_prem = base64.b64encode("\n".join(premium_nodes).encode("utf-8")).decode("utf-8")
    with open(os.path.join(BASE_DIR, "sub_premium_b64.txt"), "w", encoding="utf-8") as f:
        f.write(b64_prem + "\n")

    # 4. Continents
    continents = ["Europe", "Americas", "Asia", "Africa", "Oceania"]
    for cont in continents:
        cont_nodes = []
        for s in servers:
            s_cont = s.get("continent", "")
            if s_cont == cont or (cont == "Americas" and s_cont in ("North America", "South America")):
                ips = s.get("resolved_ips", [])
                for idx, ip in enumerate(ips):
                    cont_nodes.append(generate_node_url(s, ip, sub_index=idx, total_ips=len(ips)))

        c_name = cont.lower()
        with open(os.path.join(BASE_DIR, f"sub_{c_name}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(cont_nodes) + "\n")
        b64_cont = base64.b64encode("\n".join(cont_nodes).encode("utf-8")).decode("utf-8")
        with open(os.path.join(BASE_DIR, f"sub_{c_name}_b64.txt"), "w", encoding="utf-8") as f:
            f.write(b64_cont + "\n")

    print("All subscription files successfully generated.")


if __name__ == "__main__":
    main()
