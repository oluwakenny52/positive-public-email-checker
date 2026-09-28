# ==========================================================
# FILE: app.py
# VERSION: v2.0 (BobitoMail Interactive Reader & Pagination Suite)
# DESCRIPTION: Microsoft Account Sentinel Engine - BobitoMail Interface with Full Sidebar Suite & Reading View
# ==========================================================

import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import random
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Microsoft Account Sentinel Engine",
    page_icon="🛡️",
    layout="wide",
)

# --- CUSTOM THEME STYLING (BobitoMail Dark Theme) ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
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
        cursor: pointer;
    }
    .mail-item:hover {
        border-color: #58a6ff;
    }
    .decoder-box {
        background-color: #111418;
        border: 1px solid #f85149;
        padding: 15px;
        border-radius: 8px;
        font-family: monospace;
        font-size: 12px;
        color: #f0f6fc;
    }
    .reader-body {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 20px;
        border-radius: 8px;
        color: #f0f6fc;
        margin-bottom: 15px;
    }
    .stButton button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE SHELL INITIALIZATION ---
if "proxy_nodes" not in st.session_state:
    st.session_state.proxy_nodes = [
        {"lat": 37.7749, "lon": -122.4194, "city": "San Francisco, US", "status": "Active", "latency": "42ms"},
        {"lat": 51.5074, "lon": -0.1278, "city": "London, UK", "status": "Active", "latency": "85ms"},
        {"lat": 52.5200, "lon": 13.4050, "city": "Berlin, DE", "status": "Active", "latency": "64ms"},
        {"lat": 35.6762, "lon": 139.6503, "city": "Tokyo, JP", "status": "Active", "latency": "120ms"},
    ]

if "proxy_table_data" not in st.session_state:
    st.session_state.proxy_table_data = pd.DataFrame([
        {"IP:Port": "192.168.1.10:8080", "Protocol": "HTTP", "Country": "US", "Latency": "42ms", "Health Score": 95, "Status": "Active"},
        {"IP:Port": "172.16.25.4:3128", "Protocol": "HTTPS", "Country": "GB", "Latency": "85ms", "Health Score": 88, "Status": "Active"},
        {"IP:Port": "10.0.0.55:1080", "Protocol": "SOCKS5", "Country": "DE", "Latency": "64ms", "Health Score": 72, "Status": "Active"},
        {"IP:Port": "192.168.2.14:80", "Protocol": "HTTP", "Country": "JP", "Latency": "120ms", "Health Score": 45, "Status": "Degraded"},
    ])

if "live_sessions" not in st.session_state:
    st.session_state.live_sessions = [
        "ishad.satyen@outlook.com",
        "zohaib@hotmail.com",
        "wlicheng@allyun.com",
        "gottarace30@frontiernet.net",
        "derose7@outlook.com"
    ]

# Reader and Pagination State Management
if "selected_mail_id" not in st.session_state:
    st.session_state.selected_mail_id = None

if "current_page" not in st.session_state:
    st.session_state.current_page = 1

# ==========================================
# SIDEBAR CONTROL PANEL (COMPLETE SUITE)
# ==========================================
st.sidebar.title("🎛️ Microsoft Sentinel Panel")
st.sidebar.markdown("Focused Exclusively on Microsoft Accounts (`login.live.com`).")

with st.sidebar.expander("⚙️ Execution & Thread Settings", expanded=True):
    st.markdown("**Workers Start:**")
    workers = st.slider("Workers Slider", min_value=1, max_value=50, value=5, step=1, label_visibility="collapsed")

    st.markdown("**Deadline (s):**")
    deadline = st.slider("Deadline Slider", min_value=5, max_value=120, value=45, step=5, label_visibility="collapsed")

    st.markdown("**Max Accounts:**")
    max_acc = st.slider("Max Accounts Slider", min_value=0, max_value=5000, value=5000, step=100, label_visibility="collapsed")

    st.markdown("**Delay Between Accounts (s):**")
    delay_between_acc = st.slider("Delay Between Accounts", min_value=0, max_value=15, value=2, step=1, label_visibility="collapsed")

with st.sidebar.expander("🌐 Proxy Infrastructure & Routing", expanded=False):
    use_proxies = st.checkbox("Enable Proxy Routing", value=True)
    preflight_test = st.checkbox("Preflight Test Proxy against Live", value=True)

    st.markdown("**Proxy Protocol:**")
    proxy_protocol = st.selectbox("Proxy Protocol Select", options=["HTTP/HTTPS", "SOCKS5", "SOCKS4", "Mixed"], index=0, label_visibility="collapsed")

    st.markdown("**Rotation Strategy:**")
    rotation_strategy = st.selectbox("Rotation Strategy Select", options=["Sticky Session (Per Account)", "Round-Robin (Per Request)", "Static Pool"], index=0, label_visibility="collapsed")

    st.markdown("**Proxy Timeout (s):**")
    proxy_timeout = st.slider("Proxy Timeout Slider", min_value=2, max_value=30, value=10, step=1, label_visibility="collapsed")

    st.markdown("**Min Proxy Score:**")
    min_proxy_score = st.slider("Min proxy score Slider", min_value=0, max_value=100, value=40, step=5, label_visibility="collapsed")

    st.markdown("**Pool Mode:**")
    pool_mode = st.selectbox("Pool mode select", options=["us_only", "all", "country", "mix"], index=0, label_visibility="collapsed")

    st.markdown("**Country Code:**")
    country_code = st.text_input("Country code input", value="US", label_visibility="collapsed")

    st.markdown("**Mix List:**")
    mix_list = st.text_input("Mix list input", value="US,GB,DE", label_visibility="collapsed")

with st.sidebar.expander("🛡️ Stealth & Anti-Bot", expanded=False):
    stealth_mode = st.checkbox("Stealth Mode (Mask WebDriver)", value=True)
    fire_up_fail = st.checkbox("🔥 Fire-up on Fail (Clear Context / Fresh Tab)", value=True)
    force_en_us = st.checkbox("Force en-US UI Language", value=True)
    block_webauthn = st.checkbox("Block WebAuthn / Passkeys", value=True)
    warm_up = st.checkbox("Warm-up (Random Neutral Site)", value=True)
    keep_alive_js = st.checkbox("Keep-alive JSClicks (Prevent Idle)", value=True)
    device_pool = st.checkbox("Device Pool (Rotate UA / Viewport)", value=True)
    debug_verbose = st.checkbox("Verbose Protocol Path Logs", value=True)
    auto_kmsi = st.checkbox("Auto-Accept KMSI ('Stay signed in?')", value=True)

    st.markdown("**Speed Mode Preset:**")
    speed_preset = st.selectbox("Speed Preset", options=["slow", "normal", "fast", "superfast"], index=1, label_visibility="collapsed")

    st.markdown("**Typing Speed (ms/char):**")
    typing_speed = st.slider("Typing Speed", min_value=10, max_value=200, value=50, step=10, label_visibility="collapsed")

    st.markdown("**Mouse Move Delay (ms):**")
    mouse_delay = st.slider("Mouse Delay", min_value=0, max_value=500, value=100, step=25, label_visibility="collapsed")

with st.sidebar.expander("⏱️ Throttling, Rest & Backoff", expanded=False):
    st.markdown("**Rest After Fail (s):**")
    rest_fail = st.slider("Rest After Fail", min_value=0, max_value=30, value=3, step=1, label_visibility="collapsed")

    st.markdown("**Rest After Success (s):**")
    rest_success = st.slider("Rest After Success", min_value=0, max_value=30, value=5, step=1, label_visibility="collapsed")

    filter_disposable = st.checkbox("Filter Disposable Emails", value=True)
    retry_cloudflare = st.checkbox("Auto-Retry Security Challenges", value=True)
    captcha_alert_stop = st.checkbox("🚨 Captcha Pause & Notify (Stop on Hit)", value=True)
    sound_on_success = st.checkbox("🔔 Sound on Success / 2FA Alert", value=True)
    soft_rate_limit = st.checkbox("📉 Soft Rate-Limit Backoff Curve", value=True)
    extract_recovery = st.checkbox("🔮 [Predicted] Auto-Extract Recovery Info", value=True)

with st.sidebar.expander("🔗 Webhook & External API", expanded=False):
    st.markdown("**Webhook Endpoint URL:**")
    webhook_url = st.text_input("Webhook URL", value="", placeholder="https://discord.com/api/webhooks/...", label_visibility="collapsed")

    st.markdown("**Telegram Bot Token:**")
    tg_token = st.text_input("Telegram Token", value="", placeholder="123456:ABC-DEF...", type="password", label_visibility="collapsed")

    st.markdown("**Telegram Chat ID:**")
    tg_chat_id = st.text_input("Telegram Chat ID", value="", placeholder="-100xxxxxxxxxx", label_visibility="collapsed")

# Settings Action Buttons
col_sb1, col_sb2 = st.sidebar.columns(2)
with col_sb1:
    if st.button("🔄 Reset Defaults", use_container_width=True):
        st.sidebar.info("Settings reset to defaults.")
with col_sb2:
    if st.button("💾 Apply Settings", type="primary", use_container_width=True):
        st.sidebar.success("Configuration stored!")

st.sidebar.markdown("---")
col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    st.sidebar.markdown("**Loaded:** 0")
with col_p2:
    st.sidebar.markdown("**Alive:** 5")

with st.sidebar.expander("➕ Add Custom Proxies", expanded=False):
    st.text_area("Paste proxies (IP:Port:User:Pass)", placeholder="192.168.1.1:8080:user:pass", key="custom_proxies_box")
    if st.button("Append Custom Proxies", use_container_width=True):
        st.sidebar.success("Custom proxies appended.")

if st.sidebar.button("🚀 Fetch & Test All Proxies", type="primary", use_container_width=True):
    st.sidebar.success("Proxy pool test shell triggered.")

# ==========================================
# MAIN INTERFACE TABS & LAYOUT SHELL
# ==========================================
st.title("🛡️ Microsoft Account Sentinel & Global Routing Map")
st.markdown("Enterprise-grade validation framework optimized strictly for Microsoft identity endpoints (`login.live.com`).")

tab_engine, tab_proxies, tab_terminal, tab_vault, tab_debug, tab_auditor = st.tabs([
    "🚀 Engine Runner", 
    "🌐 Proxy Manager",
    "💻 BobitoMail Remote",
    "🔑 Vault Scrape",
    "🔍 Debug Viewer",
    "🧪 Functionality Auditor"
])

with tab_engine:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""<div class="metric-container"><h4>Total Loaded</h4><h2>0</h2></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="metric-container"><h4>Verified Hits</h4><h2 style='color: #2ea043;'>0</h2></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="metric-container"><h4>Active Proxies</h4><h2 style='color: #58a6ff;'>{}</h2></div>""".format(len(st.session_state.proxy_nodes)), unsafe_allow_html=True)
    with col4:
        st.markdown("""<div class="metric-container"><h4>Success Rate</h4><h2 style='color: #f0883e;'>0.0%</h2></div>""", unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("🌍 Interactive Global Node & Traffic Map")
    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="OpenStreetMap")
    for node in st.session_state.proxy_nodes:
        color = "green" if node["status"] == "Active" else "red"
        popup_text = f"<b>Location:</b> {node['city']}<br><b>Status:</b> {node['status']}<br><b>Latency:</b> {node['latency']}"
        folium.CircleMarker(
            location=[node["lat"], node["lon"]],
            radius=8,
            popup=folium.Popup(popup_text, max_width=250),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7
        ).add_to(m)

    st_folium(m, height=400, use_container_width=True)
    st.markdown("---")

    st.subheader("📥 Microsoft Account Batch Input & Domain Filter")
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        account_filter_mode = st.selectbox(
            "Account Domain Filter",
            options=["All Microsoft Accounts", "@outlook.com only", "@hotmail.com only", "@msn.com only", "MX-Pointed Microsoft Inboxes Only"],
            index=0
        )
    with col_filter2:
        st.markdown("**Filter Active Status:**")
        st.info(f"Targeting filter rule: `{account_filter_mode}`")

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.markdown("**Paste Combo List (`email:password`)**")
        st.text_area("Paste combo format", height=110, placeholder="user@outlook.com:SecurePassword123", label_visibility="collapsed")
    with col_input2:
        st.markdown("**Upload Combo Text File**")
        st.file_uploader("Upload .txt combo file", type=["txt"], label_visibility="collapsed")

    with st.expander("👤 Manual Single Account Login (Custom UI Engine)", expanded=False):
        st.markdown("Inject and execute a manual login run directly through our engine interface.")
        man_col1, man_col2, man_btn = st.columns([2, 2, 1])
        with man_col1:
            manual_email = st.text_input("Manual Email", placeholder="user@outlook.com", label_visibility="collapsed")
        with man_col2:
            manual_pass = st.text_input("Manual Password", placeholder="password123", type="password", label_visibility="collapsed")
        with man_btn:
            if st.button("🚀 Run Manual Login", type="primary", use_container_width=True):
                st.success("Manual login thread fired successfully!")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start_engine = st.button("▶️ Launch Engine", type="primary", use_container_width=True)
    with c2:
        pause_engine = st.button("⏸️ Pause Engine", use_container_width=True)
    with c3:
        stop_engine = st.button("⏹️ Force Unlock", use_container_width=True)
    with c4:
        clear_logs = st.button("🧹 Clear Logs", use_container_width=True)

    if start_engine:
        st.info("UI Shell Test: Launch button clicked successfully!")
    if pause_engine:
        st.warning("UI Shell Test: Engine paused.")
    if stop_engine:
        st.error("UI Shell Test: Force unlocked.")
    if clear_logs:
        st.success("UI Shell Test: Logs cleared.")

    st.markdown("### 📈 Engine Execution Progress")
    engine_progress = st.progress(0, text="Engine idle. Ready to launch checks.")

    st.markdown("### 📥 Flexible Export Format Options")
    col_exp1, col_exp2, col_exp3 = st.columns(3)
    with col_exp1:
        st.download_button("💾 Working Hits (TXT)", data="user@outlook.com:Pass123\n", file_name="microsoft_hits.txt", use_container_width=True)
    with col_exp2:
        st.download_button("💾 Checkpoints / Captcha", data="user@outlook.com:Pass123\n", file_name="microsoft_checkpoints.txt", use_container_width=True)
    with col_exp3:
        st.download_button("💾 Full Session JSON", data="{\"sessions\": []}\n", file_name="session_report.json", use_container_width=True)

    st.markdown("### **📊 Live Execution Log Viewer**")
    st.code("[15:14:34] 🚀 UI Shell v2.0 initialized successfully. All modules active.", language="text")

with tab_proxies:
    st.subheader("🌐 Live Proxy Pool & Infrastructure Manager")
    st.dataframe(st.session_state.proxy_table_data, use_container_width=True)

    col_px1, col_px2, col_px3 = st.columns(3)
    with col_px1:
        if st.button("⚡ Run Parallel Health Test", type="primary", use_container_width=True):
            st.success("Parallel proxy health check completed!")
    with col_px2:
        if st.button("🧹 Clear Dead Proxies", use_container_width=True):
            st.warning("Dead proxies flushed.")
    with col_px3:
        st.download_button("📥 Export Active Proxies", data="192.168.1.10:8080\n", file_name="active_proxies.txt", use_container_width=True)

with tab_terminal:
    # --- BOBITOMAIL PRO INTERACTIVE READER & PAGINATION SUITE ---
    st.subheader("✉️ BobitoMail Pro — Multi-Account Inbox & Bot Decoder Suite")
    
    # Top Search & Action Bar
    srch_col, act_col1, act_col2, act_col3 = st.columns([4, 1, 1, 1])
    with srch_col:
        mail_search = st.text_input("Search across messages...", placeholder="🔍 Search sender, subject or keyword...", label_visibility="collapsed")
    with act_col1:
        if st.button("🔄 Sync", use_container_width=True):
            st.toast("Syncing Microsoft Graph token sessions...")
    with act_col2:
        if st.button("📥 Export", use_container_width=True):
            st.toast("Exporting mail bundle...")
    with act_col3:
        if st.button("⚙️ Settings", use_container_width=True):
            st.toast("Mail client preferences opened.")

    st.markdown("---")

    # Collapsible Expander for Account Switcher & Folders
    with st.expander("📂 Switch Account & Folders (Click to Expand/Hide Tree)", expanded=False):
        sub_tab_acc, sub_tab_fld = st.tabs(["👤 Connected Accounts", "📁 Folder Tree"])
        with sub_tab_acc:
            selected_account = st.radio("Account Switcher", options=st.session_state.live_sessions, label_visibility="collapsed")
        with sub_tab_fld:
            folder_choice = st.radio("Folder Tree", options=["📥 INBOX (60)", "📤 Sent Items", "📝 Drafts", "⚠️ Junk Email (191)", "📦 Archive (61)", "🗑️ Deleted Items"], label_visibility="collapsed")
        st.markdown("---")
        if st.button("🔄 Refresh OAuth Access Token", use_container_width=True):
            st.success("Microsoft Graph token session refreshed!")
    
    if 'selected_account' not in locals():
        selected_account = st.session_state.live_sessions[3]
    if 'folder_choice' not in locals():
        folder_choice = "📥 INBOX (60)"

    st.markdown("---")

    # Feed Header
    col_fh1, col_fh2 = st.columns([3, 1])
    with col_fh1:
        st.markdown(f"### `{folder_choice.split()[0]}` — `{selected_account}`")
    with col_fh2:
        if st.button("🔄 Refresh Feed", use_container_width=True):
            st.toast("Feed refreshed successfully.")

    # --- LIVE DATASETS & PAGINATION GENERATOR ---
    page = st.session_state.current_page
    
    if page == 1:
        total_msgs_text = "Page 1 - 168 msgs"
        mail_database = [
            {"id": "msg_1", "sender": "Conservative Underground", "time": "7:52 PM", "subject": "Democrat Insider Just Revealed How Kamala Harris Used...", "body": "Dear Subscriber,\n\nRecent insider leaks from Washington DC indicate unprecedented internal polling shifts. Read the full exclusive breakdown inside our subscriber portal.\n\nBest regards,\nConservative Underground Team"},
            {"id": "msg_2", "sender": "no-reply@verify.signin.amazon.com", "time": "7:45 PM", "subject": "Verify your identity", "body": "Hello,\n\nWe detected a sign-in attempt from an unrecognized device in Frankfurt, Germany. Please confirm your identity using the verification link within 24 hours.\n\nAmazon Security Dept."},
            {"id": "msg_3", "sender": "account-update-no-reply@amazon.com", "time": "7:44 PM", "subject": "🔑 Your Amazon Web Services Password Has Been Updated", "body": "Hello developer,\n\nYour AWS root account password was successfully updated on Monday, September 28, 2026 at 19:44 UTC. If you did not perform this change, contact support immediately.\n\nAWS Identity Services"},
            {"id": "msg_4", "sender": "password-reset-no-reply@amazon.com", "time": "7:44 PM", "subject": "Amazon Web Services Password Assistance", "body": "We received a request to reset your Amazon Web Services password. Use confirmation code: 893-211 to proceed.\n\nAmazon Support"},
            {"id": "msg_5", "sender": "Tactical Shit", "time": "7:31 PM", "subject": "Glock 🔫 Forced Reset Trigger Just $49", "body": "Flash sale alert! Get our patent-pending forced reset trigger design kit at 50% off for the next 2 hours only.\n\nTactical Shit Store"},
            {"id": "msg_6", "sender": "Famous Footwear", "time": "7:29 PM", "subject": "FINAL HOURS 😲 to save $20", "body": "Your rewards cash is expiring tonight! Claim your $20 off bonus on any footwear order over $75.\n\nFamous Footwear Rewards"},
            {"id": "msg_7", "sender": "ClassicCars.com", "time": "7:11 PM", "subject": "Crunching the Numbers of the Pebble Beach Best of Show...", "body": "Take a deep dive into valuation trends for vintage Ferrari and Duesenberg models following this year's concours elegance.\n\nClassicCars Editorial"},
            {"id": "msg_8", "sender": "Patriot Pulse", "time": "7:04 PM", "subject": "An Iconic Local Steakhouse Chain Went From Ten Locations...", "body": "Discover how supply chain pressures and rising municipal taxes forced this century-old culinary staple to close its doors.\n\nPatriot Pulse Investigations"},
            {"id": "msg_9", "sender": "Netflix", "time": "6:35 PM", "subject": "What do you think of Beauty in Black?", "body": "Thanks for watching! We'd love to hear your thoughts on Tyler Perry's latest dramatic thriller series. Rate it now on your profile.\n\nNetflix Recommendations"}
        ]
    elif page == 2:
        total_msgs_text = "Page 2 - 168 msgs"
        mail_database = [
            {"id": "msg_10", "sender": "Steam Support", "time": "5:12 PM", "subject": "Your Steam Account: New login from browser", "body": "A login to your Steam account was detected from a web browser in Tokyo, Japan. Guard code: J89X2."},
            {"id": "msg_11", "sender": "GitHub Security", "time": "4:30 PM", "subject": "New personal access token generated", "body": "A personal access token (repo_scope) was generated for your GitHub account. If unauthorized, revoke it immediately."},
            {"id": "msg_12", "sender": "PayPal Notification", "time": "3:15 PM", "subject": "Receipt for your payment to DigitalOcean", "body": "You sent a payment of $24.00 USD to DigitalOcean, LLC for monthly cloud infrastructure hosting."},
            {"id": "msg_13", "sender": "Spotify", "time": "2:04 PM", "subject": "Your Weekly Discover Weekly is ready!", "body": "We've updated your custom playlist with 30 fresh indie and electronic tracks tailored to your listening history."},
            {"id": "msg_14", "sender": "Discord Team", "time": "1:22 PM", "subject": "Verify your email address for BobitoBot", "body": "Please click the link below to verify your email address and activate developer permissions for BobitoBot."},
            {"id": "msg_15", "sender": "Cloudflare Alerts", "time": "12:10 PM", "subject": "SSL Certificate Successfully Renewed", "body": "The Let's Encrypt SSL certificate was successfully renewed for another 90 days."}
        ]
    else:
        total_msgs_text = f"Page {page} - 168 msgs"
        mail_database = [
            {"id": "msg_100", "sender": "Archive System", "time": "10:00 AM", "subject": f"Archived Log Bundle #{page}", "body": f"This is an archived batch message loaded dynamically for page {page}. All systems nominal."}
        ]

    # --- FULL-SCREEN READING VIEW VS CLICKABLE LIST ---
    if st.session_state.selected_mail_id is None:
        # Render Clickable List Item Buttons for Mobile/Desktop Selection
        for item in mail_database:
            btn_label = f"📥 [Read] {item['sender']} — {item['subject']} ({item['time']})"
            if st.button(btn_label, key=f"btn_{item['id']}", use_container_width=True):
                st.session_state.selected_mail_id = item['id']
                st.rerun()
    else:
        # Full-Screen Replacement Reading Screen
        active_mail = next((m for m in mail_database if m['id'] == st.session_state.selected_mail_id), mail_database[0])
        
        if st.button("⬅️ Back to Inbox", type="primary"):
            st.session_state.selected_mail_id = None
            st.rerun()

        st.markdown(f"""
        <div class="reader-body">
            <h3>{active_mail['subject']}</h3>
            <p><b>From:</b> {active_mail['sender']} &lt;noreply@domain.com&gt;<br>
            <b>To:</b> {selected_account}<br>
            <b>Time:</b> {active_mail['time']}</p>
            <hr style="border-color: #30363d;">
            <p style="white-space: pre-wrap; font-family: sans-serif; font-size: 14px;">{active_mail['body']}</p>
        </div>
        """, unsafe_allow_html=True)

        # Bot Decoder Suite for Active Email
        with st.expander("🛠️ Bot Rewrite & Fake Content Decoder (Inspect Source)", expanded=False):
            st.markdown("""
            <div class="decoder-box">
            <b>[DECODER TELEMETRY REPORT]</b><br>
            - Wrapper Type: Cloud Lounge / Bot Mask v3.2<br>
            - True Sender IP: 185.199.108.153 (Verified Microsoft Relay)<br>
            - Raw MIME Header Hash: <code>[MENC2:NlIzRsF5bdfZeWe2uuqr1ZyTUTReaUWUXuS]</code><br>
            - Status: 🟢 Successfully bypassed bot wrapper and extracted raw text payload.
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Download Raw Email Source (.eml)", use_container_width=True):
                st.success("Raw source code file compiled and downloaded.")

    st.markdown("---")

    # --- FULLY FUNCTIONAL PAGINATION CONTROLS ---
    pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
    with pg_col1:
        if st.button("◀️ Newer", use_container_width=True):
            if st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                st.session_state.selected_mail_id = None
                st.toast(f"Switched to Page {st.session_state.current_page}")
                st.rerun()
            else:
                st.toast("You are already on the newest page (Page 1).")
    with pg_col2:
        st.markdown(f"<div style='text-align: center; padding: 6px; background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; font-size: 13px; font-weight: 600;'>{total_msgs_text}</div>", unsafe_allow_html=True)
    with pg_col3:
        if st.button("Older ▶️", use_container_width=True):
            st.session_state.current_page += 1
            st.session_state.selected_mail_id = None
            st.toast(f"Switched to Page {st.session_state.current_page}")
            st.rerun()

    st.markdown("---")
    exp_t1, exp_t2, exp_t3 = st.columns(3)
    with exp_t1:
        st.download_button("💾 Mark & Download Valids", data=selected_account, file_name="marked_valids.txt", use_container_width=True)
    with exp_t2:
        st.download_button("💾 Mark & Download Invalids", data="invalid_sample@outlook.com", file_name="marked_invalids.txt", use_container_width=True)
    with exp_t3:
        st.download_button("💾 Export Folder Notes", data="Notes: Clean token sync.", file_name="folder_notes.txt", use_container_width=True)

with tab_vault:
    st.subheader("🔑 Microsoft Saved Passwords Vault Scrape")
    vault_col1, vault_col2 = st.columns(2)
    with vault_col1:
        browser_target = st.selectbox("Select Target Browser Profile", options=["Google Chrome (Default)", "Microsoft Edge (Default)", "Custom User Data Directory"])
    with vault_col2:
        vault_action_mode = st.selectbox("Extraction Mode", options=["Extract Microsoft Only (*.live.com, *.outlook.com)", "Extract All Saved Credentials"])

    vault_path_input = st.text_input("Custom Profile Directory Path (Optional)", value="", placeholder="C:\\Users\\Admin\\AppData\\Local\\Google\\Chrome\\User Data")

    col_vbtn1, col_vbtn2 = st.columns(2)
    with col_vbtn1:
        if st.button("🚀 Run Credential Vault Scrape", type="primary", use_container_width=True):
            st.success("Vault extraction sequence initialized successfully!")
    with col_vbtn2:
        st.download_button("💾 Export Scraped Vault (JSON/CSV)", data="email,password\nuser@outlook.com,decrypted_pass", file_name="vault_credentials.csv", use_container_width=True)

    st.markdown("### 📊 Vault Scrape Results Preview")
    vault_df = pd.DataFrame([
        {"URL": "https://login.live.com", "Username": "user_vault_01@outlook.com", "Decryption Status": "Success", "Source": "Chrome Local State"},
        {"URL": "https://outlook.live.com", "Username": "enterprise_02@hotmail.com", "Decryption Status": "Success", "Source": "Edge Login Data"}
    ])
    st.dataframe(vault_df, use_container_width=True)

with tab_debug:
    st.subheader("🔍 Advanced Debug Viewer & Screen Dumps")
    st.markdown("### 🩺 Automated Error Diagnose Block")
    st.markdown("""
    <div class="diagnostic-box">
    [DIAGNOSTIC STATUS]: OK<br>
    - Proxy Latency Warning: None<br>
    - Cloudflare Challenge Bypass: Ready<br>
    - WebDriver Signature Mask: Active<br>
    - Last Error Captured: None recorded in current run buffer.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### 📜 Verbose Protocol Path Logs")
    st.code("[15:14:34] [VERBOSE] Initializing BobitoMail Microsoft Graph multi-account session streams...", language="text")

with tab_auditor:
    st.subheader("🧪 Functionality & State Auditor")
    st.markdown("""
    | Control Name | Type | Target Function | Last Trigger Status |
    | :--- | :--- | :--- | :--- |
    | **BobitoMail Feed & Pagination** | UI Component | Scrollable feed with Newer/Older controls | 🟢 Active |
    | **Bot Decoder** | Engine Parser | Strips bot wrappers & extracts source | 🟢 Online (`Ready`) |
    | **Vault Scraper** | Tab Module | Local browser credential extraction | 🟢 Standby (`Ready`) |
    """)
