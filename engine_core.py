# ==========================================================
# FILE: engine_core.py
# VERSION: v1.0 (Phase 2 - Asynchronous Protocol & Proxy Engine)
# DESCRIPTION: Core HTTP validation and routing engine for Microsoft accounts.
# ==========================================================

import asyncio
import httpx
import time

# Standard browser headers to mimic realistic Microsoft login requests
MICROSOFT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

async def test_single_proxy(proxy_url: str, timeout: int = 10) -> dict:
    """
    Asynchronously tests a proxy node against Microsoft's live endpoint 
    to verify latency, connection success, and score.
    """
    test_endpoint = "https://login.live.com/"
    start_time = time.time()
    
    # Format proxy structure for httpx
    proxies = {
        "http://": proxy_url,
        "https://": proxy_url
    }
    
    try:
        async with httpx.AsyncClient(proxies=proxies, timeout=timeout, follow_redirects=True) as client:
            response = await client.get(test_endpoint, headers=MICROSOFT_HEADERS)
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code in [200, 302, 401, 403]:
                return {
                    "proxy": proxy_url,
                    "status": "Active",
                    "latency": f"{latency}ms",
                    "status_code": response.status_code,
                    "success": True
                }
            else:
                return {
                    "proxy": proxy_url,
                    "status": "Dead",
                    "latency": f"{latency}ms",
                    "status_code": response.status_code,
                    "success": False
                }
    except Exception as e:
        return {
            "proxy": proxy_url,
            "status": "Error",
            "latency": "N/A",
            "error": str(e),
            "success": False
        }

async def batch_test_proxies(proxy_list: list, timeout: int = 10) -> list:
    """
    Fires asynchronous checks for a list of proxies simultaneously (concurrently).
    """
    tasks = [test_single_proxy(p, timeout) for p in proxy_list]
    results = await asyncio.gather(*tasks)
    return results
