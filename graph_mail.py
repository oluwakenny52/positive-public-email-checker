# ==========================================================
# FILE: graph_mail.py
# VERSION: v1.0 — Microsoft Graph API Inbox Sync for BobitoMail
# DESCRIPTION: Handles OAuth token refresh, message synchronization,
#              pagination, and individual message reader views.
# ==========================================================

import requests

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def refresh_graph_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Refreshes the Microsoft Graph OAuth2 access token."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": "https://graph.microsoft.com/Mail.Read offline_access"
    }
    try:
        response = requests.post(TOKEN_ENDPOINT, data=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token", refresh_token),
                "expires_in": data.get("expires_in")
            }
        return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sync_bobitomail_inbox(access_token: str, top: int = 50, skip: int = 0) -> dict:
    """Syncs mailbox messages (`/messages`) with pagination support."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{GRAPH_API_BASE}/me/messages?$top={top}&$skip={skip}&$select=id,subject,sender,receivedDateTime,bodyPreview,isRead"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            messages = []
            for msg in data.get("value", []):
                sender_email = msg.get("sender", {}).get("emailAddress", {}).get("address", "Unknown")
                sender_name = msg.get("sender", {}).get("emailAddress", {}).get("name", "Unknown")
                messages.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "No Subject"),
                    "sender": f"{sender_name} <{sender_email}>",
                    "received": msg.get("receivedDateTime"),
                    "preview": msg.get("bodyPreview"),
                    "is_read": msg.get("isRead", False)
                })
            return {
                "success": True,
                "messages": messages,
                "next_skip": skip + top if len(messages) == top else None
            }
        return {"success": False, "error": response.text, "messages": []}
    except Exception as e:
        return {"success": False, "error": str(e), "messages": []}


def fetch_message_detail(access_token: str, message_id: str) -> dict:
    """Fetches full reader view details for a specific message ID (`/messages/{id}`)."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            msg = response.json()
            body_content = msg.get("body", {}).get("content", "")
            body_type = msg.get("body", {}).get("contentType", "text")
            return {
                "success": True,
                "id": msg.get("id"),
                "subject": msg.get("subject"),
                "sender": msg.get("sender"),
                "received": msg.get("receivedDateTime"),
                "body_type": body_type,
                "body": body_content
            }
        return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}
