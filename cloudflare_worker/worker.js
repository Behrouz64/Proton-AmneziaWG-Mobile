/**
 * Cloudflare Worker for Proton VPN AmneziaWG
 * - Multi-User Management with Cloudflare KV
 * - Role-Based Access (Admin & Standard Users)
 * - Cloud Device Synchronization across Mobile & Desktop
 * - Password Reset with Master Recovery Key
 * - Tier Separation (Free vs. Premium vs. All)
 * - Dynamic Private Key & Expiry Subscriptions for Shadowrocket
 */

const GITHUB_PAGES_BASE = "https://behrouz64.github.io/Proton-AmneziaWG-Mobile";
const JWT_SECRET = "proton_awg_secret_salt_2026";

async function hashPassword(password) {
  const enc = new TextEncoder().encode(password + JWT_SECRET);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

function textResponse(text, status = 200, headers = {}) {
  return new Response(text, {
    status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      ...headers,
    },
  });
}

async function verifyAuth(request, env) {
  const authHeader = request.headers.get("Authorization") || "";
  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!token) return null;

  try {
    const raw = atob(token);
    const [username, expStr, sig] = raw.split(":");
    if (!username || !expStr || !sig) return null;

    if (Date.now() > parseInt(expStr, 10)) return null;

    const expectedSig = (await hashPassword(username + expStr)).substring(0, 16);
    if (sig !== expectedSig) return null;

    const usersJson = await env.PROTON_KV.get("users_registry");
    const users = usersJson ? JSON.parse(usersJson) : {};
    const user = users[username];
    if (!user) return null;

    return { username, role: user.role };
  } catch (e) {
    return null;
  }
}

async function createToken(username) {
  const exp = Date.now() + 30 * 86400 * 1000; // 30 days session
  const sig = (await hashPassword(username + exp)).substring(0, 16);
  return btoa(`${username}:${exp}:${sig}`);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const params = url.searchParams;

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      });
    }

    // ==========================================
    // 0. WEB APP & STATIC PROXY (Cloudflare Edge)
    // ==========================================
    if (url.pathname === "/" || url.pathname === "/index.html" || url.pathname === "/app") {
      const isHtml = (request.headers.get("Accept") || "").includes("text/html");
      const hasSubParam = params.has("key") || params.has("exp") || params.has("format") || params.has("b64");
      if (isHtml && !hasSubParam) {
        try {
          const upstream = await fetch(`${GITHUB_PAGES_BASE}/index.html`, {
            cf: { cacheTtl: 180, cacheEverything: true },
          });
          if (upstream.ok) {
            const html = await upstream.text();
            return new Response(html, {
              status: 200,
              headers: {
                "Content-Type": "text/html; charset=utf-8",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=180",
              },
            });
          }
        } catch (e) {
          // fall through
        }
      }
    }

    // Static Assets & Subscriptions Proxy
    if (
      url.pathname.endsWith(".txt") ||
      url.pathname.endsWith(".svg") ||
      url.pathname.endsWith(".png") ||
      url.pathname.endsWith(".json")
    ) {
      try {
        const assetResp = await fetch(`${GITHUB_PAGES_BASE}${url.pathname}`, {
          cf: { cacheTtl: 300, cacheEverything: true },
        });
        if (assetResp.ok) {
          const contentType = assetResp.headers.get("Content-Type") || "text/plain; charset=utf-8";
          return new Response(assetResp.body, {
            status: 200,
            headers: {
              "Content-Type": contentType,
              "Access-Control-Allow-Origin": "*",
              "Cache-Control": "public, max-age=300",
            },
          });
        }
      } catch (e) {
        // fall through
      }
    }

    // ==========================================
    // 1. API: AUTH STATUS & SETUP (First-time Admin)
    // ==========================================
    if (url.pathname === "/api/auth/status") {
      const usersJson = await env.PROTON_KV.get("users_registry");
      const users = usersJson ? JSON.parse(usersJson) : {};
      const hasUsers = Object.keys(users).length > 0;
      return jsonResponse({ hasAdmin: hasUsers, count: Object.keys(users).length });
    }

    if (url.pathname === "/api/auth/setup" && request.method === "POST") {
      const usersJson = await env.PROTON_KV.get("users_registry");
      let users = usersJson ? JSON.parse(usersJson) : {};
      
      // If admin already exists, don't allow re-setup
      if (Object.keys(users).length > 0) {
        return jsonResponse({ error: "System already initialized. Please login." }, 400);
      }

      const body = await request.json();
      const username = (body.username || "").trim().toLowerCase();
      const password = body.password || "";
      const recoveryKey = (body.recoveryKey || "").trim();

      if (!username || username.length < 3) {
        return jsonResponse({ error: "Username must be at least 3 characters." }, 400);
      }
      if (!password || password.length < 4) {
        return jsonResponse({ error: "Password must be at least 4 characters." }, 400);
      }
      if (!recoveryKey || recoveryKey.length < 8) {
        return jsonResponse({ error: "Recovery key must be provided (at least 8 chars)." }, 400);
      }

      const passHash = await hashPassword(password);
      const recHash = await hashPassword(recoveryKey);

      users[username] = {
        role: "admin",
        passHash,
        recHash,
        created: new Date().toISOString(),
      };

      await env.PROTON_KV.put("users_registry", JSON.stringify(users));
      const token = await createToken(username);

      return jsonResponse({
        success: true,
        token,
        username,
        role: "admin",
        message: "Admin account initialized successfully.",
      });
    }

    // ==========================================
    // 2. API: AUTH LOGIN
    // ==========================================
    if (url.pathname === "/api/auth/login" && request.method === "POST") {
      const body = await request.json();
      const username = (body.username || "").trim().toLowerCase();
      const password = body.password || "";

      const usersJson = await env.PROTON_KV.get("users_registry");
      const users = usersJson ? JSON.parse(usersJson) : {};
      const user = users[username];

      if (!user) {
        return jsonResponse({ error: "Invalid username or password" }, 401);
      }

      const inputHash = await hashPassword(password);
      if (inputHash !== user.passHash) {
        return jsonResponse({ error: "Invalid username or password" }, 401);
      }

      const token = await createToken(username);
      return jsonResponse({
        success: true,
        token,
        username,
        role: user.role,
      });
    }

    // ==========================================
    // 3. API: CURRENT USER (/api/auth/me)
    // ==========================================
    if (url.pathname === "/api/auth/me") {
      const auth = await verifyAuth(request, env);
      if (!auth) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }
      return jsonResponse({ username: auth.username, role: auth.role });
    }

    // ==========================================
    // 4. API: PASSWORD RESET (Using Recovery Key)
    // ==========================================
    if (url.pathname === "/api/auth/reset-password" && request.method === "POST") {
      const body = await request.json();
      const username = (body.username || "").trim().toLowerCase();
      const recoveryKey = (body.recoveryKey || "").trim();
      const newPassword = body.newPassword || "";

      if (!username || !recoveryKey || !newPassword || newPassword.length < 4) {
        return jsonResponse({ error: "Missing or invalid parameters" }, 400);
      }

      const usersJson = await env.PROTON_KV.get("users_registry");
      let users = usersJson ? JSON.parse(usersJson) : {};
      const user = users[username];

      if (!user) {
        return jsonResponse({ error: "User not found" }, 404);
      }

      const inputRecHash = await hashPassword(recoveryKey);
      if (inputRecHash !== user.recHash) {
        return jsonResponse({ error: "Invalid Master Recovery Key" }, 403);
      }

      user.passHash = await hashPassword(newPassword);
      users[username] = user;
      await env.PROTON_KV.put("users_registry", JSON.stringify(users));

      const token = await createToken(username);
      return jsonResponse({
        success: true,
        token,
        username,
        role: user.role,
        message: "Password reset successful.",
      });
    }

    // ==========================================
    // 5. API: ADMIN USER MANAGEMENT (/api/admin/users)
    // ==========================================
    if (url.pathname.startsWith("/api/admin/users")) {
      const auth = await verifyAuth(request, env);
      if (!auth || auth.role !== "admin") {
        return jsonResponse({ error: "Forbidden: Admin privileges required" }, 403);
      }

      const usersJson = await env.PROTON_KV.get("users_registry");
      let users = usersJson ? JSON.parse(usersJson) : {};

      // GET: List all users
      if (request.method === "GET") {
        const list = Object.keys(users).map(u => ({
          username: u,
          role: users[u].role,
          created: users[u].created || "",
        }));
        return jsonResponse({ users: list });
      }

      // POST: Create or update standard user
      if (request.method === "POST") {
        const body = await request.json();
        const username = (body.username || "").trim().toLowerCase();
        const password = body.password || "";
        const role = body.role === "admin" ? "admin" : "user";

        if (!username || username.length < 3 || !password || password.length < 4) {
          return jsonResponse({ error: "Username (min 3 chars) and password (min 4 chars) required" }, 400);
        }

        const passHash = await hashPassword(password);
        users[username] = {
          role,
          passHash,
          recHash: users[username]?.recHash || "",
          created: users[username]?.created || new Date().toISOString(),
        };

        await env.PROTON_KV.put("users_registry", JSON.stringify(users));
        return jsonResponse({ success: true, message: `User ${username} saved.` });
      }

      // DELETE: Delete user
      if (request.method === "DELETE") {
        const targetUser = params.get("username")?.trim().toLowerCase();
        if (!targetUser) return jsonResponse({ error: "Target username missing" }, 400);
        if (targetUser === auth.username) {
          return jsonResponse({ error: "Cannot delete your own admin account." }, 400);
        }

        delete users[targetUser];
        await env.PROTON_KV.put("users_registry", JSON.stringify(users));
        // Clean up user devices
        await env.PROTON_KV.delete(`devices_${targetUser}`);

        return jsonResponse({ success: true, message: `User ${targetUser} deleted.` });
      }
    }

    // ==========================================
    // 6. API: DEVICE MANAGEMENT (/api/devices)
    // ==========================================
    if (url.pathname.startsWith("/api/devices")) {
      const auth = await verifyAuth(request, env);
      if (!auth) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }

      const kvKey = `devices_${auth.username}`;

      // GET: Return saved devices
      if (request.method === "GET") {
        const devJson = await env.PROTON_KV.get(kvKey);
        const devices = devJson ? JSON.parse(devJson) : [];
        return jsonResponse({ devices });
      }

      // POST: Save or append device to Cloudflare KV
      if (request.method === "POST") {
        const newDev = await request.json();
        if (!newDev || !newDev.name || !newDev.key) {
          return jsonResponse({ error: "Invalid device data" }, 400);
        }

        const devJson = await env.PROTON_KV.get(kvKey);
        let devices = devJson ? JSON.parse(devJson) : [];

        // Check if device with same ID exists, update or add to front
        const existingIdx = devices.findIndex(d => d.id === newDev.id);
        if (existingIdx !== -1) {
          devices[existingIdx] = newDev;
        } else {
          devices.unshift(newDev);
        }

        await env.PROTON_KV.put(kvKey, JSON.stringify(devices));
        return jsonResponse({ success: true, devices });
      }

      // DELETE: Remove device from Cloudflare KV
      if (request.method === "DELETE") {
        const devId = params.get("id");
        if (!devId) return jsonResponse({ error: "Device ID missing" }, 400);

        const devJson = await env.PROTON_KV.get(kvKey);
        let devices = devJson ? JSON.parse(devJson) : [];
        devices = devices.filter(d => d.id !== devId);

        await env.PROTON_KV.put(kvKey, JSON.stringify(devices));
        return jsonResponse({ success: true, devices });
      }
    }

    // ==========================================
    // 7. SUBSCRIPTION ENDPOINT (/sub)
    // ==========================================
    const deviceKey = params.get("key") || "";
    const expParam = params.get("exp") || "0";
    const tier = (params.get("tier") || "all").toLowerCase(); // "all", "free", "premium"
    const continent = (params.get("continent") || params.get("region") || "all").toLowerCase();
    const returnB64 = params.get("b64") === "1" || params.get("format") === "base64";

    const nowSeconds = Math.floor(Date.now() / 1000);
    const expTimestamp = parseInt(expParam, 10) || 0;

    // Check expiration
    const isExpired = expTimestamp > 0 && nowSeconds > expTimestamp;
    if (isExpired) {
      const expDateStr = new Date(expTimestamp * 1000).toISOString().split("T")[0];
      const expiredRemark = encodeURIComponent(`⚠️ Subscription Expired on ${expDateStr} — Contact Admin`);
      const alertNode = `wg://127.0.0.1:51820?publicKey=RY8jot0tZvug%2FzGd4SDBa5yFlMvhzYEto55QfMPSTG0%3D&privateKey=cF4B4RXTVug8PI2%2BmDxm8f1G%2FRo0NHuWeO6jyOWRp18%3D&ip=10.2.0.2#${expiredRemark}`;
      
      const payload = returnB64 ? btoa(alertNode) : alertNode;
      return textResponse(payload, 200, { "X-Subscription-Status": "Expired" });
    }

    // Determine target subscription file from GitHub Pages
    let cleanContinent = continent.replace(/[\s\-]+/g, "_");
    if (cleanContinent === "na" || cleanContinent === "northamerica") cleanContinent = "north_america";
    if (cleanContinent === "sa" || cleanContinent === "southamerica") cleanContinent = "south_america";

    let sourceFileName = "sub.txt";
    if (["europe", "north_america", "south_america", "asia", "americas", "africa", "oceania"].includes(cleanContinent)) {
      sourceFileName = `sub_${cleanContinent}.txt`;
    } else if (tier === "free") {
      sourceFileName = "sub_free.txt";
    } else if (tier === "premium") {
      sourceFileName = "sub_premium.txt";
    }

    const targetUrl = `${GITHUB_PAGES_BASE}/${sourceFileName}`;

    try {
      const upstreamResp = await fetch(targetUrl, {
        cf: { cacheTtl: 300, cacheEverything: true },
      });

      if (!upstreamResp.ok) {
        return textResponse(`Error fetching upstream: ${upstreamResp.status}`, 502);
      }

      const rawContent = await upstreamResp.text();
      let lines = rawContent.split("\n").map(l => l.trim()).filter(l => l.startsWith("wg://"));

      // Filter by tier (even if continent was selected)
      if (tier === "free") {
        lines = lines.filter(l => l.includes("%F0%9F%86%93") || l.includes("🆓"));
      } else if (tier === "premium") {
        lines = lines.filter(l => !l.includes("%F0%9F%86%93") && !l.includes("🆓"));
      }

      if (lines.length === 0) {
        return textResponse("No active nodes found matching your tier/continent criteria.", 404);
      }

      // Add status info banner if expiring
      let infoNode = null;
      if (expTimestamp > 0) {
        const daysLeft = Math.ceil((expTimestamp - nowSeconds) / 86400);
        const expDateStr = new Date(expTimestamp * 1000).toISOString().split("T")[0];
        const infoRemark = encodeURIComponent(`⏳ Subscription Active until ${expDateStr} (${daysLeft} days left)`);
        infoNode = `wg://10.255.255.1:51820?publicKey=RY8jot0tZvug%2FzGd4SDBa5yFlMvhzYEto55QfMPSTG0%3D&privateKey=cF4B4RXTVug8PI2%2BmDxm8f1G%2FRo0NHuWeO6jyOWRp18%3D&ip=10.2.0.2#${infoRemark}`;
      }

      const noObfs = params.get("obfs") === "0" || params.get("noobfs") === "1" || params.get("preset") === "none";
      const encodedDeviceKey = encodeURIComponent(deviceKey);
      const processedNodes = lines.map(line => {
        let node = line;
        if (deviceKey) {
          node = node.replace(/privateKey=[^&]+/, `privateKey=${encodedDeviceKey}`);
        }
        if (noObfs) {
          node = node.replace(/&obfs=[^&]+/, "").replace(/&obfsParam=[^&#]+/, "");
        }
        return node;
      });

      const allNodes = infoNode ? [infoNode, ...processedNodes] : processedNodes;
      const finalBody = allNodes.join("\n") + "\n";
      const outputPayload = returnB64 ? btoa(unescape(encodeURIComponent(finalBody))) : finalBody;

      return textResponse(outputPayload, 200, {
        "Cache-Control": "public, max-age=180",
        "X-Nodes-Count": String(processedNodes.length),
        "X-Subscription-Tier": tier,
      });

    } catch (err) {
      return textResponse(`Worker internal error: ${err.message}`, 500);
    }
  },
};
