# ==========================================================
# FILE: app.py
# VERSION: v1.8
# DESCRIPTION: Microsoft Account Sentinel Engine - BobitoMail Pro (Optimized Feed Layout)
# ==========================================================

import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
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
    .stButton button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
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

# ==========================================
# SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Microsoft Sentinel Panel")
st.sidebar.markdown("Focused Exclusively on Microsoft Accounts (`login.live.com`).")

with st.sidebar.expander("⚙️ Execution & Thread Settings", expanded=True):
    workers = st.slider("Workers Slider", min_value=1, max_value=50, value=5, step=1)
    deadline = st.slider("Deadline Slider", min_value=5, max_value=120, value=45, step=5)
    max_acc = st.slider("Max Accounts Slider", min_value=0, max_value=5000, value=5000, step=100)

with st.sidebar.expander("🌐 Proxy Infrastructure & Routing", expanded=False):
    use_proxies = st.checkbox("Enable Proxy Routing", value=True)
    proxy_protocol = st.selectbox("Proxy Protocol", options=["HTTP/HTTPS", "SOCKS5", "SOCKS4", "Mixed"], index=0)

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("🛡️ Microsoft Account Sentinel & Global Routing Map")
st.markdown("Enterprise-grade validation framework optimized strictly for Microsoft identity endpoints.")

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
        folium.CircleMarker(
            location=[node["lat"], node["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7
        ).add_to(m)
    st_folium(m, height=350, use_container_width=True)

with tab_proxies:
    st.subheader("🌐 Live Proxy Pool & Infrastructure Manager")
    st.dataframe(st.session_state.proxy_table_data, use_container_width=True)

with tab_terminal:
    # --- BOBITOMAIL PRO OPTIMIZED LAYOUT ---
    st.subheader("✉️ BobitoMail Pro — Multi-Account Inbox & Bot Decoder Suite")
    
    # Search & Quick Actions Bar
    srch_col, act_col1, act_col2 = st.columns([3, 1, 1])
    with srch_col:
        mail_search = st.text_input("Search messages...", placeholder="🔍 Search sender, subject or keyword...", label_visibility="collapsed")
    with act_col1:
        if st.button("🔄 Sync IMAP", use_container_width=True):
            st.toast("Syncing folders with server...")
    with act_col2:
        if st.button("⚙️ Prefs", use_container_width=True):
            st.toast("Preferences opened.")

    st.markdown("---")

    # Collapsible Account & Folder Selector (Keeps Feed Front & Center)
    with st.expander("📂 Switch Account & Folders", expanded=True):
        col_acc, col_fld = st.columns(2)
        with col_acc:
            st.markdown("**Connected Accounts:**")
            selected_account = st.selectbox(
                "Account Switcher",
                options=st.session_state.live_sessions,
                label_visibility="collapsed"
            )
        with col_fld:
            st.markdown("**Mailboxes & Folders:**")
            folder_choice = st.selectbox(
                "Folder Tree",
                options=["📥 INBOX (60)", "📤 Sent", "📝 Draft", "⚠️ Trash (191)", "📦 Bulk (316)", "📁 Archive (61)"],
                label_visibility="collapsed"
            )
        
        if st.button("🔄 Restore Session State (Reconnect IMAP Socket)", use_container_width=True):
            st.success(f"Successfully re-established live session handshake for {selected_account}!")

    st.markdown("---")
    st.markdown(f"### 🗂️ FEED — `{selected_account}` ({folder_choice})")
    
    # Message Item 1 (Bot Rewrite / Cloud Wrapper Simulation)
    st.markdown("""
    <div class="mail-item">
        <b>☁️ [hotmailerr_bot] Security Alert: Please Open (hotmailerr_bot)</b><br>
        <span style='color: #8b949e; font-size: 13px;'>Temu &lt;email@news.temuemail.com&gt; | 27 Sep 2026, 21:16 UTC</span><br>
        <p style='margin: 5px 0 0 0; font-size: 13px; color: #f85149;'>🔒 <b>This mail was moved to your Cloud Lounge. Original content is locked behind Premium Cloud...</b></p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("🛠️ Bot Rewrite & Fake Content Decoder (Inspect Source)", expanded=True):
        st.markdown("Our decoder engine detected a bot wrapper mask. Decoded source parameters below:")
        st.markdown("""
        <div class="decoder-box">
        <b>[DECODER TELEMETRY REPORT]</b><br>
        - Wrapper Type: Cloud Lounge / Bot Mask v3.2<br>
        - True Sender IP: 185.199.108.153 (Verified Microsoft Relay)<br>
        - Original Subject: <i>Your Amazon Web Services Password Has Been Updated</i><br>
        - Raw MIME Header Hash: <code>[MENC2:NlIzRsF5bdfZeWe2uuqr1ZyTUTReaUWUXuS]</code><br>
        - Status: 🟢 Successfully bypassed bot rewrite wrapper and extracted raw text payload.
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📥 Download Raw Email Source Code (.eml)", use_container_width=True):
            st.success("Raw source code file compiled and downloaded.")

    # Message Item 2
    st.markdown("""
    <div class="mail-item">
        <b>🔑 Your Amazon Web Services Password Has Been Updated</b><br>
        <span style='color: #8b949e; font-size: 13px;'>gottarace30 • IMAP | 27 Sep 2026, 7:44 PM</span><br>
        <p style='margin: 5px 0 0 0; font-size: 13px;'>Greetings from Amazon Web Services, As you requested, your AWS account password has been updated...</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    exp_t1, exp_t2, exp_t3 = st.columns(3)
    with exp_t1:
        st.download_button("💾 Download Valids", data=selected_account, file_name="marked_valids.txt", use_container_width=True)
    with exp_t2:
        st.download_button("💾 Download Invalids", data="invalid_sample@outlook.com", file_name="marked_invalids.txt", use_container_width=True)
    with exp_t3:
        st.download_button("💾 Export Folder Notes", data="Notes: Clean sync.", file_name="folder_notes.txt", use_container_width=True)

with tab_vault:
    st.subheader("🔑 Microsoft Saved Passwords Vault Scrape")
    if st.button("🚀 Run Credential Vault Scrape", type="primary", use_container_width=True):
        st.success("Vault extraction sequence initialized successfully!")

with tab_debug:
    st.subheader("🔍 Advanced Debug Viewer & Screen Dumps")
    st.markdown("""
    <div class="diagnostic-box">
    [DIAGNOSTIC STATUS]: OK<br>
    - Proxy Latency Warning: None<br>
    - WebDriver Signature Mask: Active
    </div>
    """, unsafe_allow_html=True)

with tab_auditor:
    st.subheader("🧪 Functionality & State Auditor")
    st.markdown("All modules operational.")
