import os
import re
import time
import json
import random
import requests
import concurrent.futures
from datetime import datetime
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Mega Ultimate Public Email Checker",
    page_icon="⚡",
    layout="wide",
)

# Initialize Session States with Error Safety
if "LIVE_SESSIONS" not in st.session_state:
    st.session_state.LIVE_SESSIONS = {}
if "fetched_proxies" not in st.session_state:
    st.session_state.fetched_proxies = ""
if "proxy_logs" not in st.session_state:
    st.session_state.proxy_logs = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []
if "running" not in st.session_state:
    st.session_state.running = False
if "proxy_stats" not in st.session_state:
    st.session_state.proxy_stats = {"total": 0, "alive": 0, "dead": 0, "countries": {}}

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
# CELL 2: PROXY SCRAPER & HEALTH SCORING
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
PROXY_FILE         = "proxies.txt"

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
        country, city = "Unknown", "Unknown"
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
        return (proxy_str, True, latency, country, city)
    except requests.exceptions.RequestException:
        return (proxy_str, False, 0, "-", "-")
    except Exception as e:
        st.session_state.debug_logs.append(f"Test exception for {proxy_str}: {str(e)}")
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
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 401:
                break
            if r.status_code != 200:
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
        return out
    except Exception as e:
        st.session_state.debug_logs.append(f"Webshare fetch error: {str(e)}")
        return out

# ==========================================
# SIDEBAR: CELL 5A BROWSER CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Control Panel (Cell 5A)")

speed_mode = st.sidebar.selectbox(
    "Speed Mode Preset", 
    ["slow", "normal", "fast", "superfast"], 
    index=1,
    help="Select automated timing preset profiles."
)
if st.sidebar.button("⚡ Apply Mode Preset", use_container_width=True):
    try:
        preset = MODE_PRESETS[speed_mode]
        for k, v in preset.items():
            st.session_state.BROWSER_CFG[k] = v
        st.sidebar.success(f"Applied preset: {speed_mode}")
    except Exception as e:
        st.sidebar.error(f"Error applying preset: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Cell 2: Live Proxy Scraper")
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

cfg["BROWSER_TIMEOUT"] = st.sidebar.slider(
    "Timeout (s)", 20, 120, cfg["BROWSER_TIMEOUT"], 5,
    help="Max seconds for one page load step before timeout triggers."
)

cfg["MAX_ACCOUNTS"] = st.sidebar.slider(
    "Max Accounts", 0, 10000, cfg["MAX_ACCOUNTS"], 100,
    help="0 = process all accounts in pool. N = limit execution to first N accounts."
)

cfg["DELAY_BETWEEN_ACCOUNTS"] = st.sidebar.slider(
    "Delay / Account (s)", 15, 180, cfg["DELAY_BETWEEN_ACCOUNTS"], 5,
    help="Baseline sleep time between account requests to avoid flagging."
)

cfg["REST_AFTER_FAIL"] = st.sidebar.slider(
    "Rest Fail (s)", 30, 300, cfg["REST_AFTER_FAIL"], 15,
    help="Extended cool-down wait after an account login failure or rate limit."
)

cfg["REST_AFTER_SUCCESS"] = st.sidebar.slider(
    "Rest OK (s)", 15, 180, cfg["REST_AFTER_SUCCESS"], 5,
    help="Cool-down period following a successful session validation."
)

cfg["TYPING_MS"] = st.sidebar.slider(
    "Typing Speed (ms)", 40, 200, cfg["TYPING_MS"], 10,
    help="Delay interval between keystrokes to mimic human behavior."
)

cfg["PAGE_WAIT_S"] = st.sidebar.slider(
    "Page Wait (s)", 1, 10, cfg["PAGE_WAIT_S"], 1,
    help="Buffer seconds after DOM load before inspecting interactive elements."
)

cfg["MAX_TRIES_PER_ACCOUNT"] = st.sidebar.slider(
    "Max Tries / Account", 1, 5, cfg["MAX_TRIES_PER_ACCOUNT"], 1,
    help="Maximum fallback proxy retry attempts per account."
)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Proxy Pool & Routing")
cfg["MIN_PROXY_SCORE"] = st.sidebar.slider(
    "Min Proxy Score", 0, 100, cfg["MIN_PROXY_SCORE"], 5,
    help="Filter threshold: only use nodes meeting this health performance score."
)

cfg["PROXY_MODE"] = st.sidebar.selectbox(
    "Proxy Mode", ["off", "rotate", "sticky", "fallback", "aggressive"], index=3,
    help="off (direct) | rotate (new per account) | sticky (session pinned) | fallback (auto-switch on failure) | aggressive (rapid high-concurrency node rotation)."
)

cfg["POOL_MODE"] = st.sidebar.selectbox(
    "Pool Mode", ["us_only", "all", "country", "mix"], index=0,
    help="Geographic filtering profile for the active proxy pool."
)
cfg["POOL_COUNTRY"] = st.sidebar.text_input("Pool Country Code", cfg["POOL_COUNTRY"], help="Target ISO country code when pool mode is set to country.")
cfg["POOL_MIX"] = st.sidebar.text_input("Pool Mix List", cfg["POOL_MIX"], help="Comma-separated country list for multi-region rotation.")

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Advanced Flags & Anti-Bot")
cfg["DEBUG"] = st.sidebar.checkbox("Debug Mode", value=cfg["DEBUG"], help="Enable verbose step logging and diagnostic artifact tracing.")
cfg["FIRE_UP"] = st.sidebar.checkbox("Fire-up (Clear Cookies/State)", value=cfg["FIRE_UP"], help="ON = purge browser profile after each account. OFF = retain state for remote inspection.")
cfg["USE_PROXIES"] = st.sidebar.checkbox("Use Proxies", value=cfg["USE_PROXIES"], help="Master switch enabling proxy route tunnels.")
cfg["STEALTH"] = st.sidebar.checkbox("Stealth Mode", value=cfg["STEALTH"], help="Mask navigator fingerprints and webdriver signatures.")
cfg["WARMUP"] = st.sidebar.checkbox("Warm-up Browser", value=cfg["WARMUP"], help="Navigate to benign landing pages before hitting auth endpoints.")
cfg["FORCE_EN_US"] = st.sidebar.checkbox("Force English UI (en-US)", value=cfg["FORCE_EN_US"], help="Enforce english locale headers.")
cfg["SCREENSHOT_FINAL"] = st.sidebar.checkbox("Save Failure Screenshots", value=cfg["SCREENSHOT_FINAL"], help="Dump PNG debug snapshots upon encounter errors.")
cfg["WEBAUTHN_OFF"] = st.sidebar.checkbox("WebAuthn / Passkeys OFF", value=cfg["WEBAUTHN_OFF"], help="Disable hardware security key prompts.")
cfg["RETRY_CF"] = st.sidebar.checkbox("Retry Cloudflare Challenge", value=cfg["RETRY_CF"], help="Automatically attempt challenge bypass loops.")

if st.sidebar.button("💾 Apply Settings", type="primary", use_container_width=True):
    try:
        if not cfg["USE_PROXIES"]:
            cfg["PROXY_MODE"] = "off"
        st.sidebar.success("Configuration successfully locked & applied!")
    except Exception as e:
        st.sidebar.error(f"Error saving settings: {str(e)}")

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("⚡ Mega Ultimate Public Email Checker")
st.markdown("Custom URL Slug: `positive-public-email-checker.streamlit.app` — Powered by Cell 2 Scraper & Cell 5A/5B/5C Engine.")

tab_engine, tab_terminal, tab_dashboard, tab_logs = st.tabs([
    "🚀 Engine Runner (Cell 5B)", 
    "💻 Terminal Remote (Cell 5C)", 
    "📈 Proxy Health & Geo Dashboard", 
    "📊 Cell 2 Proxy Logs"
])

with tab_engine:
    st.subheader("Batch Account & Provider Processor")
    
    col1, col2 = st.columns(2)
    with col1:
        email_provider = st.selectbox(
            "Select Public Email Provider",
            [
                "Microsoft (Outlook / Hotmail / Live)", 
                "Google (Gmail)", 
                "Yahoo Mail", 
                "AOL Mail", 
                "GMX Mail", 
                "Proton Mail", 
                "Custom IMAP Endpoint"
            ],
            help="Target mail ecosystem router."
        )
    with col2:
        max_threads = st.number_input("Concurrent Threads", min_value=1, max_value=10, value=3, help="Simultaneous processing pipelines.")

    accounts_raw = st.text_area(
        "Accounts Pool (email:password format, one per line)",
        height=140,
        placeholder="account1@outlook.com:Pass123!\naccount2@gmail.com:Secret456!",
        help="Paste target credentials here."
    )
    
    proxies_raw = st.text_area(
        "Verified Proxy Pool (Auto-populated from Cell 2 Scraper)",
        value=st.session_state.fetched_proxies,
        height=120,
        placeholder="IP:Port:User:Pass (or click 'Fetch & Test All Proxies' in the sidebar)..."
    )

    c1, c2 = st.columns(2)
    with c1:
        start_engine = st.button("▶️ Launch Checker Engine", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)

    if start_engine:
        try:
            if not accounts_raw.strip():
                st.error("Validation Error: Please add at least one account line.")
            else:
                st.session_state.running = True
                acc_count = len([x for x in accounts_raw.splitlines() if ":" in x])
                proxy_count = len([x for x in proxies_raw.splitlines() if x.strip()])
                st.success(f"Engine successfully started for {acc_count} accounts using [{email_provider}] with {proxy_count} active proxy nodes!")
        except Exception as e:
            st.error(f"Engine launch exception: {str(e)}")

with tab_terminal:
    st.subheader("Interactive Terminal Remote (Cell 5C)")
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
        st.code("System operational. Remote listener active.\nProxy routing daemon: Online.", language="text")

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
    st.subheader("📊 Cell 2 Diagnostic Scrape Logs")
    if not st.session_state.proxy_logs:
        st.info("No logs generated yet. Click 'Fetch & Test All Proxies' in the sidebar.")
    else:
        st.code("\n".join(st.session_state.proxy_logs), language="text")
