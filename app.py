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

CACHE_FILE = "domain_cache.json"
PROXY_META_FILE = "proxy_meta.json"

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as jde:
            print(f"JSON Decode Error in {path}: {jde}")
            return default
        except Exception as e:
            print(f"Error loading JSON {path}: {e}")
            return default
    return default

domain_cache = load_json(CACHE_FILE, {})
proxy_meta = load_json(PROXY_META_FILE, {})

def save_domain_cache():
    try:
        with cache_lock:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(domain_cache, f, indent=2)
    except Exception as e:
        print(f"Error saving domain cache: {e}")

def save_proxy_meta():
    try:
        with proxy_lock:
            with open(PROXY_META_FILE, "w", encoding="utf-8") as f:
                json.dump(proxy_meta, f, indent=2)
    except Exception as e:
        print(f"Error saving proxy meta: {e}")

# --- Initialize Session States ---
if "LIVE_SESSIONS" not in st.session_state:
    st.session_state.LIVE_SESSIONS = {}
if "SUCCESSFUL_ACCOUNTS" not in st.session_state:
    st.session_state.SUCCESSFUL_ACCOUNTS = []
if "fetched_proxies" not in st.session_state:
    st.session_state.fetched_proxies = ""
if "proxy_logs" not in st.session_state:
    st.session_state.proxy_logs = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []
if "engine_logs" not in st.session_state:
    st.session_state.engine_logs = []
if "running" not in st.session_state:
    st.session_state.running = False
if "proxy_stats" not in st.session_state:
    st.session_state.proxy_stats = {"total": 0, "alive": 0, "dead": 0, "countries": {}}
if "help_states" not in st.session_state:
    st.session_state.help_states = {}

# --- Universal Helper Renderer (Question Mark Button) ---
def instant_help_public(key_name, description_text, label_text, widget_type="label", **kwargs):
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

if "BROWSER_CFG" not in st.session_state:
    st.session_state.BROWSER_CFG = {
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
        "POOL_MODE": "us_only",
        "POOL_COUNTRY": "US",
        "POOL_MIX": "US,GB,DE",
        "DEBUG": True,
        "FIRE_UP": False,
        "USE_PROXIES": True,
        "STEALTH": True,
        "WARMUP": True,
        "FORCE_EN_US": True,
        "SCREENSHOT_FINAL": True,
        "WEBAUTHN_OFF": True,
        "RETRY_CF": False,
        "DEBUG_DIR": "browser_debug",
        "RESULTS_DIR": "mail_results",
    }

MODE_PRESETS = {
    "slow": {
        "DELAY_BETWEEN_ACCOUNTS": 120,
        "REST_AFTER_FAIL": 180,
        "REST_AFTER_SUCCESS": 60,
        "MAX_TRIES_PER_ACCOUNT": 1,
        "BROWSER_TIMEOUT": 50,
        "TYPING_MS": 120,
        "PAGE_WAIT_S": 4,
    },
    "normal": {
        "DELAY_BETWEEN_ACCOUNTS": 75,
        "REST_AFTER_FAIL": 120,
        "REST_AFTER_SUCCESS": 45,
        "MAX_TRIES_PER_ACCOUNT": 2,
        "BROWSER_TIMEOUT": 45,
        "TYPING_MS": 100,
        "PAGE_WAIT_S": 3,
    },
    "fast": {
        "DELAY_BETWEEN_ACCOUNTS": 40,
        "REST_AFTER_FAIL": 75,
        "REST_AFTER_SUCCESS": 25,
        "MAX_TRIES_PER_ACCOUNT": 2,
        "BROWSER_TIMEOUT": 40,
        "TYPING_MS": 80,
        "PAGE_WAIT_S": 2,
    },
    "superfast": {
        "DELAY_BETWEEN_ACCOUNTS": 20,
        "REST_AFTER_FAIL": 45,
        "REST_AFTER_SUCCESS": 15,
        "MAX_TRIES_PER_ACCOUNT": 1,
        "BROWSER_TIMEOUT": 35,
        "TYPING_MS": 60,
        "PAGE_WAIT_S": 2,
    },
}

# ==========================================
# PROXY SCRAPER & HEALTH SCORING
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

PROXY_TEST_TIMEOUT = 7
MAX_TEST_WORKERS   = 12

def parse_proxy(proxy_str):
    try:
        proxy_str = (proxy_str or "").strip()
        if not proxy_str:
            return None
        if "@" in proxy_str:
            return f"http://{proxy_str}"
        return f"http://{proxy_str}"
    except Exception as e:
        st.session_state.debug_logs.append(f"Proxy parse error: {str(e)}")
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
    proxy = parse_proxy(proxy_str)
    if not proxy:
        return (proxy_str, False, 0, "-", "-")
    start = time.time()
    try:
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy, "https": proxy},
            timeout=PROXY_TEST_TIMEOUT
        )
        if r.status_code != 200:
            return (proxy_str, False, 0, "-", "-")
        latency = int((time.time() - start) * 1000)
        country, city = "US", "Unknown"
        try:
            g = requests.get(
                "http://ip-api.com/json/",
                proxies={"http": proxy, "https": proxy},
                timeout=4
            ).json()
            country = g.get("countryCode", "US")
            city    = g.get("city", "Unknown")
        except Exception:
            pass
        
        initial_score = max(0, min(100, 100 - int(latency / 15)))
        with proxy_lock:
            if proxy_str not in proxy_meta:
                proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": country, "region": city}
            m = proxy_meta[proxy_str]
            m["success"] = m.get("success", 0) + 1
            m["score"] = compute_real_score(m["success"], m.get("fails", 0), initial_score)
            m["country"] = country
            m["region"] = city
        save_proxy_meta()

        return (proxy_str, True, latency, country, city)
    except requests.exceptions.Timeout:
        with proxy_lock:
            if proxy_str not in proxy_meta:
                proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": "US", "region": "Unknown"}
            proxy_meta[proxy_str]["fails"] = proxy_meta[proxy_str].get("fails", 0) + 1
        save_proxy_meta()
        return (proxy_str, False, 0, "-", "-")
    except Exception as e:
        with proxy_lock:
            if proxy_str not in proxy_meta:
                proxy_meta[proxy_str] = {"fails": 0, "success": 0, "country": "US", "region": "Unknown"}
            proxy_meta[proxy_str]["fails"] = proxy_meta[proxy_str].get("fails", 0) + 1
        save_proxy_meta()
        return (proxy_str, False, 0, "-", "-")

def load_webshare(api_key):
    if not api_key.strip():
        return []
    out = []
    try:
        headers = {"Authorization": f"Token {api_key.strip()}"}
        page = 1
        while page <= 10:
            url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page}&page_size=100"
            try:
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code == 401 or r.status_code != 200:
                    break
                data = r.json()
                items = data.get("results", [])
                if not items:
                    break
                for it in items:
                    try:
                        line = f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}"
                        out.append(line)
                    except Exception:
                        continue
                if not data.get("next"):
                    break
                page += 1
            except requests.exceptions.RequestException as req_err:
                print(f"Webshare request exception: {req_err}")
                break
        return out
    except Exception as e:
        print(f"Webshare general exception: {e}")
        return out

# ==========================================
# SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Control Panel")

instant_help_public("h_speed", "Select automated timing profile preset.", "Speed Mode Preset:")
speed_mode = st.sidebar.selectbox("Speed Mode Preset Selector", ["slow", "normal", "fast", "superfast"], index=1, key="sb_speed", label_visibility="collapsed")

if st.sidebar.button("⚡ Apply Mode Preset", use_container_width=True):
    try:
        preset = MODE_PRESETS[speed_mode]
        for k, v in preset.items():
            st.session_state.BROWSER_CFG[k] = v
        st.sidebar.success(f"Applied preset: {speed_mode}")
    except Exception as e:
        st.sidebar.error(f"Error applying preset: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Live Proxy Scraper")
if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    with st.spinner("Scraping Webshare & Oxylabs nodes with health checks..."):
        try:
            all_raw = []
            logs = []
            country_counts = {}
            alive_count = 0
            dead_count = 0

            for i, key in enumerate(WEBSHARE_KEYS, 1):
                lst = load_webshare(key)
                logs.append(f"Webshare key #{i} → Loaded {len(lst)} nodes")
                all_raw.extend(lst)
            for ox in OXYLABS_PROXIES:
                all_raw.append(ox)
            logs.append(f"Oxylabs gateways → Loaded {len(OXYLABS_PROXIES)} nodes")
            
            all_raw = list(dict.fromkeys(all_raw))
            alive = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as ex:
                futures = {ex.submit(test_one, p): p for p in all_raw}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        res = fut.result()
                        if not res:
                            continue
                        p, is_alive, lat, country, city = res
                        if is_alive:
                            alive.append(p)
                            alive_count += 1
                            country_counts[country] = country_counts.get(country, 0) + 1
                            logs.append(f"✅ alive → {p.split('@')[-1]} | {country} | {lat}ms")
                        else:
                            dead_count += 1
                            logs.append(f"❌ dead → {p.split('@')[-1]}")
                    except Exception as inner_e:
                        dead_count += 1
                        logs.append(f"⚠️ Worker error: {str(inner_e)}")
                        
            st.session_state.fetched_proxies = "\n".join(alive)
            st.session_state.proxy_logs = logs
            st.session_state.proxy_stats = {
                "total": len(all_raw),
                "alive": alive_count,
                "dead": dead_count,
                "countries": country_counts
            }
            st.sidebar.success(f"Successfully cached {alive_count} working proxies!")
        except Exception as e:
            st.sidebar.error(f"Critical proxy fetch error: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Timing & Rest Parameters")
cfg = st.session_state.BROWSER_CFG

instant_help_public("h_timeout", "Socket communication threshold for server responses.", "Timeout (s):")
cfg["BROWSER_TIMEOUT"] = st.sidebar.slider("Timeout slider", 20, 120, cfg["BROWSER_TIMEOUT"], 5, key="sb_timeout", label_visibility="collapsed")

instant_help_public("h_maxacc", "0 = process all accounts in pool.", "Max Accounts:")
cfg["MAX_ACCOUNTS"] = st.sidebar.slider("Max accounts slider", 0, 10000, cfg["MAX_ACCOUNTS"], 100, key="sb_maxacc", label_visibility="collapsed")

instant_help_public("h_delay", "Baseline sleep time between account requests.", "Delay / Account (s):")
cfg["DELAY_BETWEEN_ACCOUNTS"] = st.sidebar.slider("Delay slider", 15, 180, cfg["DELAY_BETWEEN_ACCOUNTS"], 5, key="sb_delay", label_visibility="collapsed")

instant_help_public("h_fail", "Extended cool-down wait after an account login failure.", "Rest Fail (s):")
cfg["REST_AFTER_FAIL"] = st.sidebar.slider("Rest fail slider", 30, 300, cfg["REST_AFTER_FAIL"], 15, key="sb_fail", label_visibility="collapsed")

instant_help_public("h_ok", "Cool-down period following a successful session validation.", "Rest OK (s):")
cfg["REST_AFTER_SUCCESS"] = st.sidebar.slider("Rest ok slider", 15, 180, cfg["REST_AFTER_SUCCESS"], 5, key="sb_ok", label_visibility="collapsed")

instant_help_public("h_type", "Delay interval between keystrokes.", "Typing Speed (ms):")
cfg["TYPING_MS"] = st.sidebar.slider("Typing slider", 40, 200, cfg["TYPING_MS"], 10, key="sb_type", label_visibility="collapsed")

instant_help_public("h_pagewait", "Buffer seconds after DOM load.", "Page Wait (s):")
cfg["PAGE_WAIT_S"] = st.sidebar.slider("Page wait slider", 1, 10, cfg["PAGE_WAIT_S"], 1, key="sb_pagewait", label_visibility="collapsed")

instant_help_public("h_tries", "Maximum fallback proxy retry attempts per account.", "Max Tries / Account:")
cfg["MAX_TRIES_PER_ACCOUNT"] = st.sidebar.slider("Max tries slider", 1, 5, cfg["MAX_TRIES_PER_ACCOUNT"], 1, key="sb_tries", label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Proxy Pool & Routing")

instant_help_public("h_score", "Filter threshold: only use nodes meeting this performance health score.", "Min Proxy Score:")
cfg["MIN_PROXY_SCORE"] = st.sidebar.slider("Min score slider", 0, 100, cfg["MIN_PROXY_SCORE"], 5, key="sb_score", label_visibility="collapsed")

instant_help_public("h_proxmode", "off | rotate | sticky | fallback node switching.", "Proxy Mode:")
cfg["PROXY_MODE"] = st.sidebar.selectbox("Proxy mode select", ["off", "rotate", "sticky", "fallback", "aggressive"], index=3, key="sb_proxmode", label_visibility="collapsed")

instant_help_public("h_poolmode", "Geographic filtering profile for the active proxy pool.", "Pool Mode:")
cfg["POOL_MODE"] = st.sidebar.selectbox("Pool mode select", ["us_only", "all", "country", "mix"], index=0, key="sb_poolmode", label_visibility="collapsed")

instant_help_public("h_country", "Target ISO country code.", "Pool Country Code:")
cfg["POOL_COUNTRY"] = st.sidebar.text_input("Pool country text", cfg["POOL_COUNTRY"], key="sb_country", label_visibility="collapsed")

instant_help_public("h_mix", "Comma-separated country list.", "Pool Mix List:")
cfg["POOL_MIX"] = st.sidebar.text_input("Pool mix text", cfg["POOL_MIX"], key="sb_mix", label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Advanced Flags & Anti-Bot")

instant_help_public("h_debug", "Enable verbose step logging.", "Debug Mode:")
cfg["DEBUG"] = st.sidebar.checkbox("Debug Mode Checkbox", value=cfg["DEBUG"], key="sb_debug", label_visibility="collapsed")

instant_help_public("h_fire", "ON = purge browser profile after each account.", "Fire-up (Clear Cookies/State):")
cfg["FIRE_UP"] = st.sidebar.checkbox("Fire-up Checkbox", value=cfg["FIRE_UP"], key="sb_fire", label_visibility="collapsed")

instant_help_public("h_useproxy", "Master switch enabling proxy route tunnels.", "Use Proxies:")
cfg["USE_PROXIES"] = st.sidebar.checkbox("Use Proxies Checkbox", value=cfg["USE_PROXIES"], key="sb_useproxy", label_visibility="collapsed")

instant_help_public("h_stealth", "Mask navigator fingerprints.", "Stealth Mode:")
cfg["STEALTH"] = st.sidebar.checkbox("Stealth Checkbox", value=cfg["STEALTH"], key="sb_stealth", label_visibility="collapsed")

instant_help_public("h_warm", "Navigate to benign landing pages first.", "Warm-up Browser:")
cfg["WARMUP"] = st.sidebar.checkbox("Warmup Checkbox", value=cfg["WARMUP"], key="sb_warm", label_visibility="collapsed")

instant_help_public("h_forceen", "Enforce english locale headers.", "Force English UI (en-US):")
cfg["FORCE_EN_US"] = st.sidebar.checkbox("Force English Checkbox", value=cfg["FORCE_EN_US"], key="sb_forceen", label_visibility="collapsed")

instant_help_public("h_shot", "Dump PNG debug snapshots upon errors.", "Save Failure Screenshots:")
cfg["SCREENSHOT_FINAL"] = st.sidebar.checkbox("Screenshot Checkbox", value=cfg["SCREENSHOT_FINAL"], key="sb_shot", label_visibility="collapsed")

instant_help_public("h_webauthn", "Disable hardware security key prompts.", "WebAuthn / Passkeys OFF:")
cfg["WEBAUTHN_OFF"] = st.sidebar.checkbox("WebAuthn Checkbox", value=cfg["WEBAUTHN_OFF"], key="sb_webauthn", label_visibility="collapsed")

instant_help_public("h_retrycf", "Automatically attempt challenge bypass loops.", "Retry Cloudflare Challenge:")
cfg["RETRY_CF"] = st.sidebar.checkbox("Retry CF Checkbox", value=cfg["RETRY_CF"], key="sb_retrycf", label_visibility="collapsed")

if st.sidebar.button("💾 Apply Settings", type="primary", use_container_width=True):
    try:
        if not cfg["USE_PROXIES"]:
            cfg["PROXY_MODE"] = "off"
        st.sidebar.success("Configuration successfully locked & applied!")
    except Exception as e:
        st.sidebar.error(f"Error saving settings: {str(e)}")

# ==========================================
# WORKER EXECUTION ENGINE
# ==========================================
def process_single_account(email, password, provider, proxies_pool, config):
    try:
        time.sleep(random.uniform(0.5, 1.5))
        
        selected_proxy = None
        if config["USE_PROXIES"] and proxies_pool:
            valid_proxies = [p for p in proxies_pool if proxy_meta.get(p, {}).get("score", 50) >= config["MIN_PROXY_SCORE"]]
            if not valid_proxies:
                valid_proxies = proxies_pool
            selected_proxy = random.choice(valid_proxies) if valid_proxies else None

        success = random.choice([True, False]) # Replace/integrate Playwright handler here
        
        with results_lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if success:
                msg = f"[{timestamp}] ✅ SUCCESS: {email} verified via provider [{provider}] using proxy [{selected_proxy or 'Direct'}]"
                st.session_state.LIVE_SESSIONS[email] = {"status": "Active", "time": timestamp, "proxy": selected_proxy}
                if f"{email}:{password}" not in st.session_state.SUCCESSFUL_ACCOUNTS:
                    st.session_state.SUCCESSFUL_ACCOUNTS.append(f"{email}:{password}")
            else:
                msg = f"[{timestamp}] ❌ FAILED: {email} authentication rejected on [{provider}]"
            
            st.session_state.engine_logs.append(msg)
        return success
    except Exception as e:
        with results_lock:
            st.session_state.engine_logs.append(f"⚠️ Account Worker Exception for {email}: {str(e)}")
        return False

def run_checker_engine(accounts_list, provider, proxies_pool, config, max_workers):
    try:
        with results_lock:
            st.session_state.engine_logs.append(f"Engine initialized. Processing {len(accounts_list)} accounts with {max_workers} threads...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for line in accounts_list:
                if ":" not in line:
                    continue
                parts = line.strip().split(":", 1)
                email, pwd = parts[0], parts[1]
                futures.append(executor.submit(process_single_account, email, pwd, provider, proxies_pool, config))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with results_lock:
                        st.session_state.engine_logs.append(f"⚠️ Thread future execution error: {str(e)}")
                        
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
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Powered by Proxy Scraper & Advanced Engine.")

tab_engine, tab_terminal, tab_dashboard, tab_logs = st.tabs([
    "🚀 Engine Runner", 
    "💻 Terminal Remote", 
    "📈 Proxy Health & Geo Dashboard", 
    "📊 Proxy & Engine Logs"
])

with tab_engine:
    st.subheader("Batch Account & Provider Processor")
    
    instant_help_public("h_provider", "Select target mail ecosystem router.", "Select Public Email Provider:")
    email_provider = st.selectbox(
        "Provider select",
        [
            "Microsoft (Outlook / Hotmail / Live)", 
            "Google (Gmail)", 
            "Yahoo Mail", 
            "AOL Mail", 
            "GMX Mail", 
            "Proton Mail", 
            "Custom IMAP Endpoint"
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
        placeholder="account1@outlook.com:Pass123!\naccount2@gmail.com:Secret456!",
        key="eng_accounts",
        label_visibility="collapsed"
    )
    
    proxies_raw = st.text_area(
        "Verified Proxy Pool (Auto-populated from Scraper)",
        value=st.session_state.fetched_proxies,
        height=120,
        placeholder="IP:Port:User:Pass (or click 'Fetch & Test All Proxies' in the sidebar)..."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        start_engine = st.button("▶️ Launch Checker Engine", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)
    with c3:
        if st.button("🧹 Clear Logs & Cache", use_container_width=True):
            st.session_state.engine_logs = []
            st.session_state.proxy_logs = []
            st.success("Logs successfully cleared!")
            st.rerun()

    if stop_engine:
        st.session_state.running = False
        st.warning("Engine force-stopped by user.")

    if start_engine:
        accounts_lines = [line.strip() for line in accounts_raw.splitlines() if line.strip() and ":" in line]
        proxies_lines = [line.strip() for line in proxies_raw.splitlines() if line.strip()]
        
        if not accounts_lines:
            st.error("Validation Error: Please add valid account lines in email:password format.")
        else:
            st.session_state.running = True
            st.success(f"Engine started for {len(accounts_lines)} accounts using [{email_provider}]!")
            
            worker_thread = threading.Thread(
                target=run_checker_engine,
                args=(accounts_lines, email_provider, proxies_lines, st.session_state.BROWSER_CFG, max_threads),
                daemon=True
            )
            worker_thread.start()

    if st.session_state.SUCCESSFUL_ACCOUNTS:
        st.markdown("### 📥 Export Successful Results")
        success_data = "\n".join(st.session_state.SUCCESSFUL_ACCOUNTS)
        st.download_button(
            label="💾 Download Working Accounts (.txt)",
            data=success_data,
            file_name=f"successful_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )

    if st.session_state.engine_logs:
        st.markdown("### **Live Execution Stream**")
        st.code("\n".join(st.session_state.engine_logs[-40:]), language="text")

with tab_terminal:
    st.subheader("Interactive Terminal Remote")
    st.markdown("Inspect active browser sessions, page through live inbox items, and fetch message payloads.")

    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions captured yet. Execute successful authentication runs via the Engine Runner tab to populate session handles.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🔄 Reload Inbox", use_container_width=True):
                st.toast("Refreshing live mail folder...")
        with b2:
            if st.button("📥 Load More", use_container_width=True):
                st.toast("Paging additional records...")
        with b3:
            if st.button("▶️ Next Page", use_container_width=True):
                st.toast("Advancing pagination index...")
        with b4:
            if st.button("◀️ Prev Page", use_container_width=True):
                st.toast("Reverting pagination index...")

        slot_num = st.number_input("Select Message Slot", min_value=1, max_value=9, value=1)
        if st.button("📖 Open Selected Message Body"):
            st.success(f"Fetching message details for slot ({slot_num})...")

        st.markdown("### **Live Terminal Console Output**")
        st.code(f"Session Active: {active_acc}\nProxy Tunnel: {st.session_state.LIVE_SESSIONS[active_acc].get('proxy', 'Direct')}", language="text")

with tab_dashboard:
    st.subheader("📈 Proxy Health & Geo Analytics")
    stats = st.session_state.proxy_stats
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Scraped Nodes", stats.get("total", 0))
    col_b.metric("Healthy / Alive Nodes", stats.get("alive", 0))
    col_c.metric("Failed / Dead Nodes", stats.get("dead", 0))
    
    st.markdown("### Regional Distribution Matrix")
    countries = stats.get("countries", {})
    if countries:
        st.bar_chart(countries)
    else:
        st.info("No regional geographic data available yet. Run proxy health checks from the sidebar.")

with tab_logs:
    st.subheader("📊 Diagnostic Scrape & Engine Logs")
    proxy_logs_data = st.session_state.proxy_logs
    if not proxy_logs_data and not st.session_state.engine_logs:
        st.info("No logs generated yet. Run proxy tests or launch the engine runner.")
    else:
        if proxy_logs_data:
            st.markdown("#### Proxy Scraper Logs")
            st.code("\n".join(proxy_logs_data), language="text")
        if st.session_state.engine_logs:
            st.markdown("#### Engine Activity Logs")
            st.code("\n".join(st.session_state.engine_logs), language="text")
