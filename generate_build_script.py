"""Generator script to produce build_standalone.py for Proton AmneziaWG Mobile."""

import os
import re

SURF_DIR = "/Users/elahekaveh/Desktop/VPN antigravity/Surfshark_AmneziaWG_Mobile"
PROTON_DIR = "/Users/elahekaveh/Desktop/VPN antigravity/Proton_AmneziaWG_Mobile"

with open(os.path.join(SURF_DIR, "build_standalone.py"), "r", encoding="utf-8") as f:
    code = f.read()

# 1. Basic Replacements
code = code.replace("surfshark_servers.json", "proton_servers.json")
code = code.replace('eIAi8RMy6+QScRWERt/+jEedxdqro4FFJO9A8L3ptGU=', 'cF4B4RXTVug8PI2+mDxm8f1G/Ro0NHuWeO6jyOWRp18=')
code = code.replace("10.14.0.2/16", "10.2.0.2/32")
code = code.replace("10.14.0.2", "10.2.0.2")
code = code.replace("162.252.172.57, 149.154.159.92", "10.2.0.1")
code = code.replace("Surfshark AmneziaWG Mobile", "Proton AmneziaWG Mobile")
code = code.replace("Surfshark AWG Mobile", "Proton AWG Mobile")
code = code.replace("Surfshark AmneziaWG", "Proton AmneziaWG")
code = code.replace("Surfshark", "Proton")
code = code.replace("surfshark_standalone.html", "proton_standalone.html")
code = code.replace("Surfshark-AmneziaWG-Mobile", "Proton-AmneziaWG-Mobile")
code = code.replace("surfshark-amneziawg-sub", "proton-amneziawg-sub")
code = code.replace("surfshark_awg_settings", "proton_awg_settings")
code = code.replace("surfshark_managed_devices", "proton_managed_devices")
code = code.replace("surfshark_cf_worker_url", "proton_cf_worker_url")
code = code.replace("surfshark_auth_session", "proton_auth_session")
code = code.replace("#0b0f17", "#0c0d14")
code = code.replace("🦈", "⚛️")

# 2. Stats bar: Update count placeholder
code = code.replace(
    '<span id="stat-total" class="stat-value">76</span>',
    '<span id="stat-total" class="stat-value">782</span>'
)

# 3. Add Tier Chips and split North/South America in continent-chips
tier_chips_html = """            <!-- Tier Filter Chips -->
            <div class="chips-scroll" id="tier-chips" style="margin-bottom: 8px;">
                <button class="chip active" data-tier="all">🌐 All Tiers (782)</button>
                <button class="chip" data-tier="free">🆓 Free Nodes (50)</button>
                <button class="chip" data-tier="premium">💎 Plus / Premium (732)</button>
            </div>
"""
old_continent_chips = """            <div class="chips-scroll" id="continent-chips">
                <button class="chip active" data-continent="All">All</button>
                <button class="chip" data-continent="Europe">Europe</button>
                <button class="chip" data-continent="Americas">Americas</button>
                <button class="chip" data-continent="Asia">Asia</button>
                <button class="chip" data-continent="Africa">Africa</button>
                <button class="chip" data-continent="Oceania">Oceania</button>
            </div>"""

new_continent_chips = """            <div class="chips-scroll" id="continent-chips">
                <button class="chip active" data-continent="All">All (782)</button>
                <button class="chip" data-continent="Europe">Europe (273)</button>
                <button class="chip" data-continent="North America">North America (289)</button>
                <button class="chip" data-continent="South America">South America (26)</button>
                <button class="chip" data-continent="Asia">Asia (102)</button>
                <button class="chip" data-continent="Africa">Africa (65)</button>
                <button class="chip" data-continent="Oceania">Oceania (27)</button>
            </div>"""

code = code.replace(old_continent_chips, tier_chips_html + new_continent_chips)

# 4. Add selectedTier to App state
code = code.replace(
    'selectedContinent: "All",',
    'selectedContinent: "All",\n        selectedTier: "all",'
)

# 5. Add tier filter logic and Americas handling to applyFilters
old_filter_block = """        if (App.selectedContinent !== "All") {{
            list = list.filter(s => s.continent === App.selectedContinent);
        }}"""

new_filter_block = """        if (App.selectedTier === "free") {{
            list = list.filter(s => s.tier === "free");
        }} else if (App.selectedTier === "premium") {{
            list = list.filter(s => s.tier === "premium" || !s.tier);
        }}

        if (App.selectedContinent !== "All") {{
            if (App.selectedContinent === "Americas") {{
                list = list.filter(s => s.continent === "Americas" || s.continent === "North America" || s.continent === "South America");
            }} else {{
                list = list.filter(s => s.continent === App.selectedContinent);
            }}
        }}"""

code = code.replace(old_filter_block, new_filter_block)

# 6. Add tier chips event listener next to continent chips listener
old_chips_listener = """        // Continent clicks
        document.getElementById("continent-chips").addEventListener("click", (e) => {{
            const chip = e.target.closest(".chip");
            if (!chip) return;
            document.querySelectorAll("#continent-chips .chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            App.selectedContinent = chip.dataset.continent;
            applyFilters();
        }});"""

new_chips_listener = """        // Tier clicks
        const tierChipsEl = document.getElementById("tier-chips");
        if (tierChipsEl) {{
            tierChipsEl.addEventListener("click", (e) => {{
                const chip = e.target.closest(".chip");
                if (!chip) return;
                document.querySelectorAll("#tier-chips .chip").forEach(c => c.classList.remove("active"));
                chip.classList.add("active");
                App.selectedTier = chip.dataset.tier;
                applyFilters();
            }});
        }}

        // Continent clicks
        document.getElementById("continent-chips").addEventListener("click", (e) => {{
            const chip = e.target.closest(".chip");
            if (!chip) return;
            document.querySelectorAll("#continent-chips .chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            App.selectedContinent = chip.dataset.continent;
            applyFilters();
        }});"""

code = code.replace(old_chips_listener, new_chips_listener)

# 7. Update buildRemark to support tier badge and server_name
old_remark = """    function buildRemark(srv, targetIp = null, index = 0, total = 1) {{
        const loc = srv.city || srv.country;
        const ip = targetIp || srv.effective_ip || srv.hostname;
        const suffix = total > 1 ? ` #${{index + 1}}` : "";
        const pingStr = srv.ping_ms ? ` — ${{srv.ping_ms}}ms` : "";
        return `⚛️ ${{srv.flag}} ${{srv.country}} — ${{loc}}${{suffix}} (${{ip}})${{pingStr}}`;
    }}"""

new_remark = """    function buildRemark(srv, targetIp = null, index = 0, total = 1) {{
        const loc = srv.server_name || srv.city || srv.country;
        const ip = targetIp || srv.effective_ip || srv.hostname;
        const suffix = total > 1 ? ` #${{index + 1}}` : "";
        const tierBadge = srv.tier === "free" ? "🆓 " : "";
        const scBadge = srv.secure_core ? "🛡️ " : "";
        const pingStr = srv.ping_ms ? ` — ${{srv.ping_ms}}ms` : "";
        return `⚛️ ${{tierBadge}}${{scBadge}}${{srv.flag}} ${{srv.country}} — ${{loc}}${{suffix}} (${{ip}})${{pingStr}}`;
    }}"""

code = code.replace(old_remark, new_remark)

# 8. Update renderCards to show Tier and Secure Core badges
old_card_badges = """            let badgeHtml = "";
            if (s.is_doh_resolved) {{
                badgeHtml = `<span class="badge badge-resolved">⚡ ${{s.ping_ms}}ms (${{ips.length}} IPs)</span>`;
            }} else {{
                badgeHtml = `<span class="badge badge-unresolved">Seed (${{ips.length}} IPs)</span>`;
            }}"""

new_card_badges = """            let badgeHtml = "";
            const isFree = s.tier === "free";
            const tierBadge = isFree
                ? `<span class="badge badge-tier-free" style="margin-right: 4px;">🆓 FREE</span>`
                : `<span class="badge badge-tier-premium" style="margin-right: 4px;">💎 PLUS</span>`;
            const scBadge = s.secure_core ? `<span class="badge badge-sc" style="margin-right: 4px;">🛡️ SC</span>` : "";

            if (s.is_doh_resolved) {{
                badgeHtml = `${{tierBadge}}${{scBadge}}<span class="badge badge-resolved">⚡ ${{s.ping_ms}}ms</span>`;
            }} else {{
                badgeHtml = `${{tierBadge}}${{scBadge}}<span class="badge badge-unresolved">Ready</span>`;
            }}"""

code = code.replace(old_card_badges, new_card_badges)

# Also update title in card:
code = code.replace(
    '<div class="server-info-title">${{s.country}} · ${{s.city}}</div>',
    '<div class="server-info-title">${{s.country}} · ${{s.server_name || s.city}}</div>'
)

# 9. Update modal-sub with Tier selector
old_modal_sub_scope = """                <div class="form-group" style="margin-bottom: 12px;">
                    <label for="sub-scope-select">Select Region / Continent</label>
                    <select id="sub-scope-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 10px; border-radius: var(--radius-md); font-size: 13px; outline: none;">
                        <option value="all">🌐 Global / All Continents (151 Nodes)</option>
                        <option value="europe">🇪🇺 Europe (83 Nodes)</option>
                        <option value="asia">🌏 Asia (32 Nodes)</option>
                        <option value="americas">🌎 Americas (22 Nodes)</option>
                        <option value="africa">🌍 Africa (8 Nodes)</option>
                        <option value="oceania">🇦🇺 Oceania (6 Nodes)</option>
                    </select>
                </div>"""

new_modal_sub_scope = """                <div class="modal-grid-2" style="margin-bottom: 12px;">
                    <div class="form-group">
                        <label for="sub-tier-select">Account Tier</label>
                        <select id="sub-tier-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 10px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                            <option value="all">🌐 All Tiers (782 Nodes)</option>
                            <option value="free">🆓 Free Nodes (50 Nodes)</option>
                            <option value="premium">💎 Plus / Premium (732 Nodes)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="sub-scope-select">Region / Continent</label>
                        <select id="sub-scope-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 10px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                            <option value="all">🌐 Global / All</option>
                            <option value="europe">🇪🇺 Europe (273 Nodes)</option>
                            <option value="north_america">🌎 North America (289 Nodes)</option>
                            <option value="south_america">🌎 South America (26 Nodes)</option>
                            <option value="asia">🌏 Asia (102 Nodes)</option>
                            <option value="africa">🌍 Africa (65 Nodes)</option>
                            <option value="oceania">🇦🇺 Oceania (27 Nodes)</option>
                        </select>
                    </div>
                </div>"""

code = code.replace(old_modal_sub_scope, new_modal_sub_scope)

# Update sub-scope-select event handler to also observe sub-tier-select
old_sub_scope_event = """        const subScopeSelect = document.getElementById("sub-scope-select");
        if (subScopeSelect) {{
            subScopeSelect.addEventListener("change", () => {{
                const val = subScopeSelect.value;
                const txtInput = document.getElementById("sub-url-input");
                const b64Input = document.getElementById("sub-b64-input");
                const base = "https://behrouz64.github.io/Proton-AmneziaWG-Mobile";
                if (val === "all") {{
                    txtInput.value = base + "/sub.txt";
                    b64Input.value = base + "/sub_base64.txt";
                }} else {{
                    txtInput.value = base + "/sub_" + val + ".txt";
                    b64Input.value = base + "/sub_" + val + "_b64.txt";
                }}
            }});
        }}"""

new_sub_scope_event = """        function updateSubModalUrls() {{
            const scopeSelect = document.getElementById("sub-scope-select");
            const tierSelect = document.getElementById("sub-tier-select");
            const txtInput = document.getElementById("sub-url-input");
            const b64Input = document.getElementById("sub-b64-input");
            const base = "https://behrouz64.github.io/Proton-AmneziaWG-Mobile";

            const tier = tierSelect ? tierSelect.value : "all";
            const scope = scopeSelect ? scopeSelect.value : "all";

            if (tier === "free") {{
                txtInput.value = base + "/sub_free.txt";
                b64Input.value = base + "/sub_free_b64.txt";
            }} else if (tier === "premium") {{
                txtInput.value = base + "/sub_premium.txt";
                b64Input.value = base + "/sub_premium_b64.txt";
            }} else if (scope !== "all") {{
                txtInput.value = base + "/sub_" + scope + ".txt";
                b64Input.value = base + "/sub_" + scope + "_b64.txt";
            }} else {{
                txtInput.value = base + "/sub.txt";
                b64Input.value = base + "/sub_base64.txt";
            }}
        }}

        const subScopeSelect = document.getElementById("sub-scope-select");
        if (subScopeSelect) subScopeSelect.addEventListener("change", updateSubModalUrls);
        const subTierSelect = document.getElementById("sub-tier-select");
        if (subTierSelect) subTierSelect.addEventListener("change", updateSubModalUrls);"""

code = code.replace(old_sub_scope_event, new_sub_scope_event)

# 10. Update Device Form to add Tier Selection
old_dev_sub_actions = """                        <div class="sub-actions-row">
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-duration-select">Duration / Expiry</label>
                                <select id="dev-duration-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="30">30 Days</option>
                                    <option value="7">7 Days (Trial)</option>
                                    <option value="60">60 Days (2 Months)</option>
                                    <option value="90">90 Days (3 Months)</option>
                                    <option value="180">180 Days (6 Months)</option>
                                    <option value="365">365 Days (1 Year)</option>
                                    <option value="0">Unlimited (No Expiry)</option>
                                </select>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-region-select">Region / Continent</label>
                                <select id="dev-region-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="all">🌐 All Continents</option>
                                    <option value="europe">🇪🇺 Europe</option>
                                    <option value="asia">🌏 Asia</option>
                                    <option value="americas">🌎 Americas</option>
                                    <option value="africa">🌍 Africa</option>
                                    <option value="oceania">🇦🇺 Oceania</option>
                                </select>
                            </div>
                        </div>"""

new_dev_sub_actions = """                        <div class="sub-actions-row">
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-tier-select">Account Tier</label>
                                <select id="dev-tier-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="all">🌐 All Tiers</option>
                                    <option value="free">🆓 Free Only</option>
                                    <option value="premium">💎 Plus / Premium</option>
                                </select>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-obfs-select">Obfuscation</label>
                                <select id="dev-obfs-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="awg">🛡️ AmneziaWG (DPI Bypass)</option>
                                    <option value="none">🌐 Pure WireGuard (No Obfs)</option>
                                </select>
                            </div>
                        </div>
                        <div class="sub-actions-row" style="margin-top: 8px;">
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-duration-select">Duration / Expiry</label>
                                <select id="dev-duration-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="30">30 Days</option>
                                    <option value="7">7 Days (Trial)</option>
                                    <option value="60">60 Days (2 Months)</option>
                                    <option value="90">90 Days (3 Months)</option>
                                    <option value="180">180 Days (6 Months)</option>
                                    <option value="365">365 Days (1 Year)</option>
                                    <option value="0">Unlimited (No Expiry)</option>
                                </select>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label for="dev-region-select">Region</label>
                                <select id="dev-region-select" style="width: 100%; background: var(--bg-main); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                    <option value="all">🌐 All</option>
                                    <option value="europe">🇪🇺 Europe</option>
                                    <option value="north_america">🌎 North America</option>
                                    <option value="south_america">🌎 South America</option>
                                    <option value="asia">🌏 Asia</option>
                                    <option value="africa">🌍 Africa</option>
                                    <option value="oceania">🇦🇺 Oceania</option>
                                </select>
                            </div>
                        </div>"""

code = code.replace(old_dev_sub_actions, new_dev_sub_actions)

# Update device creation handler to include tier & obfuscation
old_dev_creation_js = """                const name = document.getElementById("dev-name-input").value.trim();
                const key = document.getElementById("dev-key-input").value.trim();
                const durationDays = parseInt(document.getElementById("dev-duration-select").value, 10);
                const region = document.getElementById("dev-region-select").value;

                if (!name) {{
                    alert("Please enter a device name / label.");
                    return;
                }}
                if (!key) {{
                    alert("Please enter the WireGuard private key from your Proton account.");
                    return;
                }}

                const nowSec = Math.floor(Date.now() / 1000);
                const expSec = durationDays > 0 ? (nowSec + durationDays * 86400) : 0;
                const workerBase = getEffectiveWorkerUrl();

                const subUrl = workerBase + "/sub?key=" + encodeURIComponent(key) +
                               "&name=" + encodeURIComponent(name) +
                               "&exp=" + expSec +
                               "&continent=" + encodeURIComponent(region);

                const devObj = {{
                    id: "dev_" + Date.now(),
                    name: name,
                    key: key,
                    durationDays: durationDays,
                    expTimestamp: expSec,
                    region: region,
                    url: subUrl,
                    createdAt: nowSec
                }};"""

new_dev_creation_js = """                const name = document.getElementById("dev-name-input").value.trim();
                const key = document.getElementById("dev-key-input").value.trim();
                const tier = document.getElementById("dev-tier-select") ? document.getElementById("dev-tier-select").value : "all";
                const obfsChoice = document.getElementById("dev-obfs-select") ? document.getElementById("dev-obfs-select").value : "awg";
                const durationDays = parseInt(document.getElementById("dev-duration-select").value, 10);
                const region = document.getElementById("dev-region-select").value;

                if (!name) {{
                    alert("Please enter a device name / label.");
                    return;
                }}
                if (!key) {{
                    alert("Please enter the WireGuard private key from your Proton account.");
                    return;
                }}

                const nowSec = Math.floor(Date.now() / 1000);
                const expSec = durationDays > 0 ? (nowSec + durationDays * 86400) : 0;
                const workerBase = getEffectiveWorkerUrl();

                let subUrl = workerBase + "/sub?key=" + encodeURIComponent(key) +
                               "&name=" + encodeURIComponent(name) +
                               "&exp=" + expSec +
                               "&tier=" + encodeURIComponent(tier) +
                               "&continent=" + encodeURIComponent(region);
                if (obfsChoice === "none") {{
                    subUrl += "&obfs=0";
                }}

                const devObj = {{
                    id: "dev_" + Date.now(),
                    name: name,
                    key: key,
                    tier: tier,
                    obfs: obfsChoice,
                    durationDays: durationDays,
                    expTimestamp: expSec,
                    region: region,
                    url: subUrl,
                    createdAt: nowSec
                }};"""

code = code.replace(old_dev_creation_js, new_dev_creation_js)

# Update renderManagedDevices to show Tier pill and Obfs badge for each device
old_dev_name_line = """                            '<strong style="font-size: 12px; color: var(--text-primary);">' + escapeHtml(dev.name) + '</strong>' +
                            '<span style="font-size: 10px; color: var(--text-secondary); text-transform: capitalize;">(' + (dev.region || "all") + ')</span>' +"""

new_dev_name_line = """                            '<strong style="font-size: 12px; color: var(--text-primary);">' + escapeHtml(dev.name) + '</strong>' +
                            (dev.tier === "free" ? '<span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981;">🆓 Free</span>' : (dev.tier === "premium" ? '<span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; background: rgba(109, 74, 255, 0.2); color: #a78bfa;">💎 Plus</span>' : '<span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; background: rgba(56, 189, 248, 0.15); color: #38bdf8;">🌐 All</span>')) +
                            (dev.obfs === "none" ? '<span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; background: rgba(234, 179, 8, 0.2); color: #eab308;">🌐 WireGuard</span>' : '<span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; background: rgba(59, 130, 246, 0.2); color: #60a5fa;">🛡️ AWG</span>') +
                            '<span style="font-size: 10px; color: var(--text-secondary); text-transform: capitalize;">(' + (dev.region ? escapeHtml(dev.region.replace(/_/g, " ")) : "all") + ')</span>' +"""

code = code.replace(old_dev_name_line, new_dev_name_line)

# 11. Add Pure WireGuard option to Settings Modal preset select
old_preset_select = """                            <label for="cfg-obfs-preset">Obfuscation Preset</label>
                            <select id="cfg-obfs-preset" style="width: 100%; background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                <option value="default">⚡ Standard / Proton Official (Default)</option>
                                <option value="aggressive">🛡️ Aggressive DPI Bypass (Heavy Obfuscation)</option>
                                <option value="light">🚀 Low Overhead / Low Ping (Fast &amp; Light)</option>
                                <option value="extreme">🔥 Extreme Randomization (High Entropy)</option>
                                <option value="custom">⚙️ Custom (Manual Edit)</option>
                            </select>"""

new_preset_select = """                            <label for="cfg-obfs-preset">Obfuscation Preset</label>
                            <select id="cfg-obfs-preset" style="width: 100%; background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary); padding: 9px; border-radius: var(--radius-md); font-size: 12px; outline: none;">
                                <option value="default">⚡ Standard / Proton Official (AmneziaWG)</option>
                                <option value="none">🌐 بدون مبهم‌سازی / Pure WireGuard (No Obfs)</option>
                                <option value="aggressive">🛡️ Aggressive DPI Bypass (Heavy Obfuscation)</option>
                                <option value="light">🚀 Low Overhead / Low Ping (Fast &amp; Light)</option>
                                <option value="extreme">🔥 Extreme Randomization (High Entropy)</option>
                                <option value="custom">⚙️ Custom (Manual Edit)</option>
                            </select>"""

code = code.replace(old_preset_select, new_preset_select)

# 12. Add 'none' preset to OBFUSCATION_PRESETS
old_obfs_presets = """    const OBFUSCATION_PRESETS = {{
        default: {{
            name: "Standard",
            jc: 4, jmin: 50, jmax: 1000, s1: 0, s2: 0, h1: 1, h2: 2, h3: 3, h4: 4
        }},
        aggressive: {{"""

new_obfs_presets = """    const OBFUSCATION_PRESETS = {{
        default: {{
            name: "Standard",
            jc: 4, jmin: 50, jmax: 1000, s1: 0, s2: 0, h1: 1, h2: 2, h3: 3, h4: 4
        }},
        none: {{
            name: "Pure WireGuard",
            jc: 0, jmin: 0, jmax: 0, s1: 0, s2: 0, h1: 1, h2: 2, h3: 3, h4: 4
        }},
        aggressive: {{"""

code = code.replace(old_obfs_presets, new_obfs_presets)

# 13. Update detectPreset to detect 'none'
old_detect_preset = """    function detectPreset(s) {{
        for (const [key, p] of Object.entries(OBFUSCATION_PRESETS)) {{
            if (
                Number(s.jc) === p.jc && Number(s.jmin) === p.jmin && Number(s.jmax) === p.jmax &&
                Number(s.s1) === p.s1 && Number(s.s2) === p.s2 &&
                Number(s.h1) === p.h1 && Number(s.h2) === p.h2 && Number(s.h3) === p.h3 && Number(s.h4) === p.h4
            ) {{
                return key;
            }}
        }}
        return "custom";
    }}"""

new_detect_preset = """    function detectPreset(s) {{
        if (Number(s.jc) === 0 && Number(s.s1) === 0 && Number(s.s2) === 0 && Number(s.h1) === 1 && Number(s.h2) === 2 && Number(s.h3) === 3 && Number(s.h4) === 4) {{
            return "none";
        }}
        for (const [key, p] of Object.entries(OBFUSCATION_PRESETS)) {{
            if (
                Number(s.jc) === p.jc && Number(s.jmin) === p.jmin && Number(s.jmax) === p.jmax &&
                Number(s.s1) === p.s1 && Number(s.s2) === p.s2 &&
                Number(s.h1) === p.h1 && Number(s.h2) === p.h2 && Number(s.h3) === p.h3 && Number(s.h4) === p.h4
            ) {{
                return key;
            }}
        }}
        return "custom";
    }}"""

code = code.replace(old_detect_preset, new_detect_preset)

# 14. Update buildWireguardUrl to skip obfs params when obfuscation is disabled
old_build_wg_url = """    function buildWireguardUrl(srv, targetIp = null, index = 0, total = 1) {{
        const ip = targetIp || srv.effective_ip || (srv.resolved_ips && srv.resolved_ips[0]) || srv.hostname;
        const s = App.settings;
        const privkey = encodeURIComponent(s.privkey);
        const pubkey = encodeURIComponent(srv.public_key);
        const addr = (s.address || "10.2.0.2").split("/")[0].trim();
        const dnsEncoded = encodeURIComponent(s.dns || "10.2.0.1");
        const remark = encodeURIComponent(buildRemark(srv, ip, index, total));

        const obfsObj = {{
            s1: String(s.s1 !== undefined ? s.s1 : 0),
            h2: String(s.h2 !== undefined ? s.h2 : 2),
            jmax: String(s.jmax || 1000),
            s2: String(s.s2 !== undefined ? s.s2 : 0),
            h3: String(s.h3 !== undefined ? s.h3 : 3),
            jc: String(s.jc || 4),
            jmin: String(s.jmin || 50),
            h1: String(s.h1 || 1),
            h4: String(s.h4 !== undefined ? s.h4 : 4)
        }};
        const obfsParam = encodeURIComponent(JSON.stringify(obfsObj));

        const params = [
            `publicKey=${{pubkey}}`,
            `privateKey=${{privkey}}`,
            `ip=${{addr}}`,
            `dns=${{dnsEncoded}}`,
            `mtu=1280`,
            `udp=1`,
            `keepalive=25`,
            `obfs=amneziawg`,
            `obfsParam=${{obfsParam}}`
        ].join("&");

        return `wg://${{ip}}:${{srv.port || 51820}}?${{params}}#${{remark}}`;
    }}"""

new_build_wg_url = """    function buildWireguardUrl(srv, targetIp = null, index = 0, total = 1) {{
        const ip = targetIp || srv.effective_ip || (srv.resolved_ips && srv.resolved_ips[0]) || srv.hostname;
        const s = App.settings;
        const privkey = encodeURIComponent(s.privkey);
        const pubkey = encodeURIComponent(srv.public_key);
        const addr = (s.address || "10.2.0.2").split("/")[0].trim();
        const dnsEncoded = encodeURIComponent(s.dns || "10.2.0.1");
        const remark = encodeURIComponent(buildRemark(srv, ip, index, total));
        const isObfs = !(Number(s.jc) === 0 && Number(s.s1) === 0 && Number(s.s2) === 0 && Number(s.h1) === 1 && Number(s.h2) === 2 && Number(s.h3) === 3 && Number(s.h4) === 4);

        const params = [
            `publicKey=${{pubkey}}`,
            `privateKey=${{privkey}}`,
            `ip=${{addr}}`,
            `dns=${{dnsEncoded}}`,
            `mtu=1280`,
            `udp=1`,
            `keepalive=25`
        ];

        if (isObfs) {{
            const obfsObj = {{
                s1: String(s.s1 !== undefined ? s.s1 : 0),
                h2: String(s.h2 !== undefined ? s.h2 : 2),
                jmax: String(s.jmax || 1000),
                s2: String(s.s2 !== undefined ? s.s2 : 0),
                h3: String(s.h3 !== undefined ? s.h3 : 3),
                jc: String(s.jc || 4),
                jmin: String(s.jmin || 50),
                h1: String(s.h1 || 1),
                h4: String(s.h4 !== undefined ? s.h4 : 4)
            }};
            const obfsParam = encodeURIComponent(JSON.stringify(obfsObj));
            params.push("obfs=amneziawg");
            params.push(`obfsParam=${{obfsParam}}`);
        }}

        return `wg://${{ip}}:${{srv.port || 51820}}?${{params.join("&")}}#${{remark}}`;
    }}"""

code = code.replace(old_build_wg_url, new_build_wg_url)

# 15. Update buildAmneziaConf to skip obfs parameters when disabled
new_build_conf = """    function buildAmneziaConf(srv, targetIp = null, index = 0, total = 1) {{
        const ip = targetIp || srv.effective_ip || (srv.resolved_ips && srv.resolved_ips[0]) || srv.hostname;
        const s = App.settings;
        const suffix = total > 1 ? ` #${{index + 1}}` : "";
        const isObfs = !(Number(s.jc) === 0 && Number(s.s1) === 0 && Number(s.s2) === 0 && Number(s.h1) === 1 && Number(s.h2) === 2 && Number(s.h3) === 3 && Number(s.h4) === 4);
        const loc = srv.server_name || srv.city || srv.country;
        const confLines = [
            `# Proton ${{isObfs ? "AmneziaWG" : "WireGuard"}} — ${{srv.country}} - ${{loc}}${{suffix}}`,
            `# Endpoint: ${{ip}}:${{srv.port || 51820}}`,
            "",
            "[Interface]",
            `PrivateKey = ${{s.privkey}}`,
            `Address = ${{s.address}}`,
            `DNS = ${{s.dns}}`
        ];

        if (isObfs) {{
            confLines.push(
                `Jc = ${{s.jc}}`,
                `Jmin = ${{s.jmin}}`,
                `Jmax = ${{s.jmax}}`,
                `S1 = ${{s.s1}}`,
                `S2 = ${{s.s2}}`,
                `H1 = ${{s.h1}}`,
                `H2 = ${{s.h2}}`,
                `H3 = ${{s.h3}}`,
                `H4 = ${{s.h4}}`
            );
        }}

        confLines.push(
            "",
            "[Peer]",
            `PublicKey = ${{srv.public_key}}`,
            "AllowedIPs = 0.0.0.0/0, ::/0",
            `Endpoint = ${{ip}}:${{srv.port || 51820}}`,
            "PersistentKeepalive = 25",
            ""
        );

        return confLines.join("\\\\n");
    }}"""

code = re.sub(r"function buildAmneziaConf\(srv.*?\n    \}\}", lambda _: new_build_conf, code, flags=re.DOTALL)

target_file = os.path.join(PROTON_DIR, "build_standalone.py")
with open(target_file, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Successfully generated {target_file}")
