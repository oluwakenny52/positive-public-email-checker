# ==========================================================
# FILE: app.py
# VERSION: v1.2
# DESCRIPTION: Microsoft Account Sentinel Engine - Full Front-End Proxy & UI Suite
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

# --- CUSTOM THEME STYLING ---
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

# ==========================================
# SIDEBAR CONTROL PANEL (FULL PROXY & THREAD SUITE)
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

with st.sidebar.expander("🌐 Proxy Infrastructure & Routing", expanded=False):
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

with st.sidebar.expander("🛡️ Behavioral Toggles", expanded=False):
    filter_disposable = st.checkbox("Filter Disposable Emails", value=True)
    use_proxies = st.checkbox("Enable Proxy Routing", value=True)
    stealth_mode = st.checkbox("Enable Browser Stealth", value=True)
    retry_cloudflare = st.checkbox("Auto-Retry Security Challenges", value=True)

if st.sidebar.button("💾 Apply Settings", type="primary", use_container_width=True):
    st.sidebar.success("Configuration settings stored successfully!")

st.sidebar.markdown("---")
col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    st.sidebar.markdown("**Loaded:** 0")
with col_p2:
    st.sidebar.markdown("**Alive:** 4")

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

tab_engine, tab_proxies, tab_terminal = st.tabs([
    "🚀 Engine Runner", 
    "🌐 Proxy Manager",
    "💻 Terminal Remote"
])

with tab_engine:
    # Metrics Overview Row
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

    # Interactive Global Proxy & Traffic Map
    st.subheader("🌍 Interactive Global Node & Traffic Map")
    st.markdown("Real-time geographic distribution of active proxy nodes routing your Microsoft verification requests.")

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

    # Batch Input Section
    st.subheader("📥 Microsoft Account Batch Input")
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        st.markdown("**Paste Combo List (`email:password`)**")
        st.text_area("Paste combo format", height=130, placeholder="user@outlook.com:SecurePassword123", label_visibility="collapsed")
    with col_input2:
        st.markdown("**Upload Combo Text File**")
        st.file_uploader("Upload .txt combo file", type=["txt"], label_visibility="collapsed")

    c1, c2, c3 = st.columns(3)
    with c1:
        start_engine = st.button("▶️ Launch Microsoft Engine", type="primary", use_container_width=True)
    with c2:
        stop_engine = st.button("⏹️ Stop / Force Unlock", use_container_width=True)
    with c3:
        clear_logs = st.button("🧹 Clear Logs & Cache", use_container_width=True)

    if start_engine:
        st.info("UI Shell Test: Launch button clicked successfully!")
    if stop_engine:
        st.warning("UI Shell Test: Stop button clicked successfully!")
    if clear_logs:
        st.success("UI Shell Test: Clear logs button clicked successfully!")

    # Export Button Placeholder
    st.markdown("### 📥 Flexible Export Format Options")
    st.download_button(
        label="💾 Download Working Accounts (TXT)",
        data="user@outlook.com:ExamplePassword123\n",
        file_name="microsoft_hits_sample.txt",
        mime="text/plain",
        use_container_width=True
    )

    st.markdown("### **📊 Live Execution Log Viewer**")
    st.code("[15:14:34] 🚀 UI Shell v1.2 initialized successfully. Proxy infrastructure suite loaded.", language="text")

with tab_proxies:
    st.subheader("🌐 Live Proxy Pool & Infrastructure Manager")
    st.markdown("Inspect, filter, and manage your active proxy rotation pool in real-time.")

    # Proxy Data Grid Table View
    st.dataframe(st.session_state.proxy_table_data, use_container_width=True)

    col_px1, col_px2, col_px3 = st.columns(3)
    with col_px1:
        if st.button("⚡ Run Pool Health Check", type="primary", use_container_width=True):
            st.success("Proxy health check sequence simulated!")
    with col_px2:
        if st.button("🧹 Clear Dead Proxies", use_container_width=True):
            st.warning("Dead proxies flushed from rotation pool.")
    with col_px3:
        st.download_button(
            label="📥 Export Active Proxies",
            data="192.168.1.10:8080\n172.16.25.4:3128\n",
            file_name="active_proxies.txt",
            mime="text/plain",
            use_container_width=True
        )

with tab_terminal:
    st.subheader("💻 Terminal Remote & Inbox Reader")
    st.info("No active Microsoft account sessions captured in shell mode yet.")
    st.code("""
Session Active    : N/A
Storage File Path : sessions/none.json
Proxy Tunnel      : N/A
Timestamp         : N/A
--------------------------------------------------
Latest Snippet / Inbox DOM:
Waiting for backend automation integration...
    """, language="text")
