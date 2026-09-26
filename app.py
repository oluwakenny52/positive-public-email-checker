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

# Initialize Session States
if "LIVE_SESSIONS" not in st.session_state:
    st.session_state.LIVE_SESSIONS = {}
if "fetched_proxies" not in st.session_state:
    st.session_state.fetched_proxies = ""
if "proxy_logs" not in st.session_state:
    st.session_state.proxy_logs = []
if "running" not in st.session_state:
    st.session_state.running = False

# ==========================================
# EXACT CELL 2 CONFIG & BACKEND LOGIC
# ==========================================
WEBSHARE_KEYS = [
    "ty1wj93kaw0k1ab7vv05lqvga86zs6tu2ngqjkyo",   # old
    "z6rhxx6390l1kitf5zjptukkjbjielb56mwqr741",   # new
    "a0afl99r624zz7fs8fh5y1ck5f9a0me3kajz5xtn",
    "5gtgl0pheucjczwxjjwzh1u7edgs65dp4cyfbcl3",
    "dqibfb8n2kkp7w0sku8gielshqqv4lcq6vuzdltb",
    "mpb64af9rak5931lfvmoozs9hsepeovj59ggrufz",
    "0hnwlw0e590d0yo9odtr411p4rw85uqv3oenc0ej",
    "3enappszm6k7p4tm5czf9as9d3g95jgasbuuvcr8",
    "myyibaqdn66o8pavn4kti90x2ametb9117zdwyi3",
]

OXYLABS_PROXIES = [
    "user-Positive_S79mq-country-US:Kingfrosh5252+@dc.oxylabs.io:8000",          # old
    "user-Positivekenny_ls8CB-country-US:Adejoke52_52@dc.oxylabs.io:8000",       # new
]

PROXY_TEST_TIMEOUT = 7
MAX_TEST_WORKERS   = 12
PROXY_FILE         = "proxies.txt"
PROXY_META_FILE    = "proxy_meta.json"

def parse_proxy(proxy_str):
    proxy_str = (proxy_str or "").strip()
    if not proxy_str:
        return None
    if "@" in proxy_str:
        return f"http://{proxy_str}"
    return None

def test_one(proxy_str):
    proxy = parse_proxy(proxy_str)
    if not proxy:
        return None
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
        country, city = "-", "-"
        try:
            g = requests.get(
                "http://ip-api.com/json/",
                proxies={"http": proxy, "https": proxy},
                timeout=5
            ).json()
            country = g.get("country", "-")
            city    = g.get("city", "-")
        except Exception:
            pass
        return (proxy_str, True, latency, country, city)
    except Exception:
        return (proxy_str, False, 0, "-", "-")

def load_webshare(api_key):
    if not api_key.strip():
        return []
    out = []
    try:
        headers = {"Authorization": f"Token {api_key.strip()}"}
        page = 1
        while page <= 25:
            url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page}&page_size=100"
            r = requests.get(url, headers=headers, timeout=20)
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
    except Exception:
        return []

# ==========================================
# SIDEBAR: CONTROL PANEL & CELL 2 EXECUTOR
# ==========================================
st.sidebar.title("🎛️ Control Panel")
speed_mode = st.sidebar.selectbox("Speed Preset", ["normal", "slow", "fast", "superfast"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Cell 2: Live Proxy Scraper")
st.sidebar.markdown("Pull from your **9 Webshare keys** and **Oxylabs gateways**, run health scoring, and build `proxies.txt` automatically.")

if st.sidebar.button("🚀 Run Cell 2 Auto Proxy Fetcher", type="primary"):
    with st.spinner("Scraping and testing proxies across parallel workers..."):
        all_raw = []
        logs = []
        
        # Load Webshare keys
        for i, key in enumerate(WEBSHARE_KEYS, 1):
            lst = load_webshare(key)
            logs.append(f"Webshare key #{i} → {len(lst)} proxies")
            all_raw.extend(lst)

        # Load Oxylabs gateways
        for ox in OXYLABS_PROXIES:
            all_raw.append(ox)
        logs.append(f"Oxylabs gateways → {len(OXYLABS_PROXIES)}")

        # Dedup candidates
        all_raw = list(dict.fromkeys(all_raw))
        logs.append(f"Unique candidates: {len(all_raw)} | Workers: {MAX_TEST_WORKERS}")

        alive = []
        meta = {}

        # Parallel Testing Executor
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as ex:
            futures = {ex.submit(test_one, p): p for p in all_raw}
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                if not res:
                    continue
                p, is_alive, lat, country, city = res
                short = p.split("@")[-1]
                if is_alive:
                    alive.append(p)
                    score = max(10, 100 - (lat // 20))
                    meta[p] = {
                        "latency": lat,
                        "country": country,
                        "city": city,
                        "score": score,
                        "fails": 0,
                        "success": 1,
                        "last_ok": datetime.now().isoformat()
                    }
                    tag = " [OXYLABS]" if "oxylabs.io" in p else ""
                    logs.append(f"  alive → {short:<22} | {country} | {lat}ms | score={score}{tag}")
                else:
                    logs.append(f"  dead  → {short}")

        # Save to local persistence files
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(alive) + ("\n" if alive else ""))

        with open(PROXY_META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        st.session_state.fetched_proxies = "\n".join(alive)
        st.session_state.proxy_logs = logs
        st.sidebar.success(f"Cell 2 Complete! Saved {len(alive)} live working proxies.")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Stealth & Anti-Bot")
stealth_mode = st.sidebar.checkbox("Stealth Mode (Mask WebDriver)", value=True)
webauthn_block = st.sidebar.checkbox("Block WebAuthn / Passkeys", value=True)

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("⚡ Mega Ultimate Public Email Checker")
st.markdown("Domain: `positive-public-email-checker.streamlit.app` — Powered by Cell 2 Proxy Scraper & Health Engine.")

tab_engine, tab_terminal, tab_settings = st.tabs(["🚀 Engine Runner (Cell 5B)", "💻 Terminal Remote (Cell 5C)", "📊 Cell 2 Proxy Logs"])

with tab_engine:
    st.subheader("Batch Account & Proxy Manager")
    
    col1, col2 = st.columns(2)
    with col1:
        provider = st.selectbox("Email Provider", ["Microsoft (Outlook/Hotmail)", "Google (Gmail)", "Yahoo Mail"])
    with col2:
        max_threads = st.number_input("Concurrent Threads", min_value=1, max_value=10, value=3)

    accounts_raw = st.text_area(
        "Accounts Pool (email:password format, one per line)",
        height=130,
        placeholder="account1@outlook.com:Pass123!\naccount2@gmail.com:Secret456!"
    )
    
    # Automatically populated with the verified live working proxies from Cell 2 execution
    proxies_raw = st.text_area(
        "Verified Proxy Pool (Auto-loaded from Cell 2 Scraper)",
        value=st.session_state.fetched_proxies,
        height=120,
        placeholder="Click 'Run Cell 2 Auto Proxy Fetcher' in the sidebar to populate live nodes..."
    )

    c1, c2 = st.columns(2)
    with c1:
        start_engine = st.button("▶️ Launch Engine Runner", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)

    if start_engine:
        if not accounts_raw.strip():
            st.error("Please provide at least one account line.")
        else:
            st.session_state.running = True
            acc_list = [l for l in accounts_raw.splitlines() if ":" in l]
            proxy_list = [l for l in proxies_raw.splitlines() if l.strip()]
            st.success(f"Engine launched! Processing {len(acc_list)} accounts with {len(proxy_list)} verified healthy proxies.")

with tab_terminal:
    st.subheader("Terminal Remote & Session Inspector (Cell 5C)")
    st.markdown("Manage active browser sessions, page through items, and read message bodies.")

    if not st.session_state.LIVE_SESSIONS:
        st.info("No active sessions currently captured. Run logins via the Engine Runner to stream live accounts.")
    else:
        active_acc = st.selectbox("Active Account Session", list(st.session_state.LIVE_SESSIONS.keys()))
        
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🔄 Reload Inbox", use_container_width=True):
                st.toast("Reloading inbox stream...")
        with b2:
            if st.button("📥 Load More", use_container_width=True):
                st.toast("Loading additional entries...")
        with b3:
            if st.button("▶️ Next Page", use_container_width=True):
                st.toast("Moving forward through pool...")
        with b4:
            if st.button("◀️ Prev Page", use_container_width=True):
                st.toast("Moving backward through pool...")

        slot_num = st.number_input("Message Slot Number", min_value=1, max_value=9, value=1)
        if st.button("📖 Open Selected Message"):
            st.success(f"Fetching body for slot ({slot_num})...")

        st.markdown("### **Live Terminal Console Output**")
        st.code("System active. Cell 2 proxy pool connected.\nWaiting for user interaction...", language="text")

with tab_settings:
    st.subheader("📊 Cell 2 Execution Diagnostic Logs")
    if not st.session_state.proxy_logs:
        st.info("No proxy scraping logs available yet. Click 'Run Cell 2 Auto Proxy Fetcher' in the sidebar.")
    else:
        st.code("\n".join(st.session_state.proxy_logs), language="text")
