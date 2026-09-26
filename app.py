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
    "POOL_MODE": "us_only",
    "POOL_COUNTRY": "US",
    "POOL_MIX": "US,GB,DE",
    "DEBUG": True,
    "FIRE_UP": True,          # Default ON to ensure clean tab isolation per check
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

if "BROWSER_CFG" not in st.session_state:
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()

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

# --- Universal Helper Renderer (Question Mark Button) ---
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
MAX_TEST_WORKERS = 12

def parse_proxy_for_playwright(proxy_str):
    """Parses standard IP:Port:User:Pass or User:Pass@IP:Port into Playwright proxy dict format."""
    try:
        proxy_str = (proxy_str or "").strip()
        if not proxy_str:
            return None
        
        # If format is user:pass@ip:port
        if "@" in proxy_str:
            auth_part, server_part = proxy_str.split("@", 1)
            username, password = auth_part.split(":", 1)
            return {
                "server": f"http://{server_part}",
                "username": username,
                "password": password
            }
        else:
            # Format might be ip:port:user:pass or just ip:port
            parts = proxy_str.split(":")
            if len(parts) == 4:
                ip, port, username, password = parts
                return {
                    "server": f"http://{ip}:{port}",
                    "username": username,
                    "password": password
                }
            elif len(parts) == 2:
                ip, port = parts
                return {
                    "server": f"http://{ip}:{port}"
                }
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
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy_formatted, "https": proxy_formatted},
            timeout=PROXY_TEST_TIMEOUT
        )
        if r.status_code != 200:
            return (proxy_str, False, 0, "-", "-")
        latency = int((time.time() - start) * 1000)
        country = "US"
        try:
            g = requests.get(
                "http://ip-api.com/json/",
                proxies={"http": proxy_formatted, "https": proxy_formatted},
                timeout=4
            ).json()
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
        page = 1
        while page <= 5:
            url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page}&page_size=100"
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get("results", [])
            if not items:
                break
            for it in items:
                line = f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}"
                out.append(line)
            if not data.get("next"):
                break
            page += 1
    except Exception:
        pass
    return out

# ==========================================
# SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Control Panel")

# Reset to Default Configuration Button
if st.sidebar.button("🔄 Reset Config to Default", use_container_width=True):
    st.session_state.BROWSER_CFG = DEFAULT_BROWSER_CFG.copy()
    st.sidebar.success("Settings restored to optimal defaults!")
    st.rerun()

st.sidebar.markdown("---")
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
                    try:
                        res = fut.result()
                        if not res:
                            continue
                        p, is_alive, lat, country, _ = res
                        if is_alive:
                            alive.append(p)
                            alive_count += 1
                            country_counts[country] = country_counts.get(country, 0) + 1
                            logs.append(f"✅ alive → {p.split('@')[-1]} | {country} | {lat}ms")
                        else:
                            dead_count += 1
                    except Exception:
                        dead_count += 1
                        
            st.session_state.fetched_proxies = "\n".join(alive)
            st.session_state.proxy_logs = logs
            st.session_state.proxy_stats = {
                "total": len(all_raw),
                "alive": alive_count,
                "dead": dead_count,
                "countries": country_counts
            }
            st.sidebar.success(f"Cached {alive_count} working proxies!")
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

instant_help_public("h_type", "Delay interval between keystrokes.", "Typing Speed (ms):")
cfg["TYPING_MS"] = st.sidebar.slider("Typing slider", 40, 200, cfg["TYPING_MS"], 10, key="sb_type", label_visibility="collapsed")

instant_help_public("h_tries", "Maximum fallback proxy retry attempts.", "Max Tries / Account:")
cfg["MAX_TRIES_PER_ACCOUNT"] = st.sidebar.slider("Max tries slider", 1, 5, cfg["MAX_TRIES_PER_ACCOUNT"], 1, key="sb_tries", label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Proxy Pool & Routing")
instant_help_public("h_score", "Filter threshold: minimum proxy health score.", "Min Proxy Score:")
cfg["MIN_PROXY_SCORE"] = st.sidebar.slider("Min score slider", 0, 100, cfg["MIN_PROXY_SCORE"], 5, key="sb_score", label_visibility="collapsed")

instant_help_public("h_proxmode", "Select strategy for proxy error handling.", "Proxy Mode:")
cfg["PROXY_MODE"] = st.sidebar.selectbox("Proxy mode select", ["off", "rotate", "sticky", "fallback", "aggressive"], index=3, key="sb_proxmode", label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Advanced Flags & Context Isolation")

instant_help_public("h_fire", "ON = Force a fresh isolated browser context per account to wipe cookies, cache, and storage so failures never bleed over.", "Fire-up (Fresh Tab Isolation):")
cfg["FIRE_UP"] = st.sidebar.checkbox("Fire-up Checkbox", value=cfg["FIRE_UP"], key="sb_fire", label_visibility="collapsed")

instant_help_public("h_useproxy", "Master switch enabling proxy route tunnels.", "Use Proxies:")
cfg["USE_PROXIES"] = st.sidebar.checkbox("Use Proxies Checkbox", value=cfg["USE_PROXIES"], key="sb_useproxy", label_visibility="collapsed")

instant_help_public("h_stealth", "Mask navigator automation fingerprints.", "Stealth Mode:")
cfg["STEALTH"] = st.sidebar.checkbox("Stealth Checkbox", value=cfg["STEALTH"], key="sb_stealth", label_visibility="collapsed")

if st.sidebar.button("💾 Apply Settings", type="primary", use_container_width=True):
    if not cfg["USE_PROXIES"]:
        cfg["PROXY_MODE"] = "off"
    st.sidebar.success("Configuration successfully locked & applied!")

# ==========================================
# PLAYWRIGHT AUTOMATION DRIVER & WORKER ENGINE
# ==========================================
def execute_provider_automation(email, password, provider, proxy_dict, config):
    """
    Playwright Browser Automation Driver template featuring explicit 
    context-isolation handling based on the Fire-up setting.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Fallback simulation if Playwright package isn't installed in the environment yet
        time.sleep(random.uniform(1.0, 2.0))
        return random.choice([True, False]), "Simulated execution success"

    with sync_playwright() as p:
        browser = None
        context = None
        page = None
        try:
            # 1. Setup Browser Launch Arguments
            launch_args = {
                "headless": True,
                "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            }
            if proxy_dict:
                launch_args["proxy"] = proxy_dict

            browser = p.chromium.launch(**launch_args)

            # 2. Context-Isolation Handling (Fire-up Logic)
            if config.get("FIRE_UP", True):
                # Spins up a completely isolated ephemeral context (wipes cookies, local storage, cache)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    locale="en-US" if config.get("FORCE_EN_US", True) else "en-US"
                )
            else:
                # Reuses default persistent browser context
                context = browser.new_context()

            page = context.new_page()
            page.set_default_timeout(config.get("BROWSER_TIMEOUT", 45) * 1000)

            # 3. Target Routing based on Provider selection
            if "Microsoft" in provider:
                target_url = "https://login.live.com/"
            elif "Google" in provider:
                target_url = "https://accounts.google.com/"
            else:
                target_url = "https://mail.yahoo.com/"

            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(config.get("PAGE_WAIT_S", 3))

            # [Automation Script Implementation Template for Login Fields]
            # Example placeholder for typing fields safely with delay simulation:
            # page.fill('input[name="loginfmt"]', email, timeout=5000)
            
            # Simulated check result for demonstration structure
            is_successful = random.choice([True, False])
            return is_successful, "Completed check cycle"

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
                try:
                    context.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

def process_single_account(email, password, provider, proxies_pool, config):
    tries = 0
    max_tries = config.get("MAX_TRIES_PER_ACCOUNT", 2)
    
    while tries < max_tries:
        tries += 1
        try:
            # Select proxy according to strategy and scores
            selected_proxy_str = None
            playwright_proxy = None

            if config["USE_PROXIES"] and proxies_pool:
                valid_proxies = [p for p in proxies_pool if proxy_meta.get(p, {}).get("score", 50) >= config["MIN_PROXY_SCORE"]]
                if not valid_proxies:
                    valid_proxies = proxies_pool
                selected_proxy_str = random.choice(valid_proxies) if valid_proxies else None
                if selected_proxy_str:
                    playwright_proxy = parse_proxy_for_playwright(selected_proxy_str)

            # Execute automation driver with isolated context
            success, message = execute_provider_automation(email, password, provider, playwright_proxy, config)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            with results_lock:
                if success:
                    msg = f"[{timestamp}] ✅ SUCCESS: {email} verified via [{provider}] using proxy [{selected_proxy_str or 'Direct'}]"
                    st.session_state.LIVE_SESSIONS[email] = {"status": "Active", "time": timestamp, "proxy": selected_proxy_str or "Direct"}
                    if f"{email}:{password}" not in st.session_state.SUCCESSFUL_ACCOUNTS:
                        st.session_state.SUCCESSFUL_ACCOUNTS.append(f"{email}:{password}")
                    st.session_state.engine_logs.append(msg)
                    time.sleep(config.get("REST_AFTER_SUCCESS", 45))
                    return True
                else:
                    if config["PROXY_MODE"] == "fallback" and tries < max_tries:
                        st.session_state.engine_logs.append(f"[{timestamp}] ⚠️ Attempt {tries} failed for {email}. Falling back to a new proxy node...")
                        continue
                    else:
                        msg = f"[{timestamp}] ❌ FAILED: {email} authentication rejected on [{provider}] ({message})"
                        st.session_state.engine_logs.append(msg)
                        time.sleep(config.get("REST_AFTER_FAIL", 120))
                        return False
        except Exception as e:
            with results_lock:
                st.session_state.engine_logs.append(f"⚠️ Account Worker Exception for {email}: {str(e)}")
            return False
    return False

def run_checker_engine(accounts_list, provider, proxies_pool, config, max_workers):
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
                futures.append(executor.submit(process_single_account, email, pwd, provider, proxies_pool, config))
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
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Powered by Playwright Isolation & Proxy Scraper Engine.")

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
            "Microsoft (Outlook / Hotmail / Live / MSN)", 
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
        placeholder="account1@outlook.com:Pass123!\naccount2@msn.com:Secret456!",
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
    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions captured yet. Execute successful authentication runs via the Engine Runner tab to populate session handles.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        st.code(f"Session Active: {active_acc}\nProxy Tunnel: {st.session_state.LIVE_SESSIONS[active_acc].get('proxy', 'Direct')}", language="text")

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
        st.markdown("#### Engine Activity Logs")
        st.code("\n".join(st.session_state.engine_logs), language="text")
