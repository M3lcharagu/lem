"""Public unauthenticated Deriv ticks_history candles (no trading/auth calls)."""

from __future__ import annotations

import os
from urllib.parse import urlencode

WS_ENDPOINT = "wss://ws.derivws.com/websockets/v3"


def fetch_candles(symbol, granularity=60, count=120, app_id=None, timeout=15):
    """Fetch public OHLC candles; DERIV_APP_ID must be an operator-owned app ID."""
    app_id = (app_id or os.environ.get("DERIV_APP_ID", "")).strip()
    if not app_id:
        raise RuntimeError("DERIV_APP_ID is unset; configure a Deriv app ID for public WebSocket requests")
    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError("optional dependency websocket-client is required for Deriv candles") from exc
    url = WS_ENDPOINT + "?" + urlencode({"app_id": app_id})
    ws = websocket.create_connection(url, timeout=timeout)
    try:
        request = {
            "ticks_history": str(symbol), "adjust_start_time": 1,
            "count": int(count), "end": "latest", "granularity": int(granularity),
            "style": "candles", "req_id": 1,
        }
        ws.send(__import__("json").dumps(request))
        response = __import__("json").loads(ws.recv())
        if response.get("error"):
            raise RuntimeError("Deriv API error: " + str(response["error"].get("message", response["error"])))
        candles = response.get("candles")
        if not isinstance(candles, list) or not candles:
            raise RuntimeError("Deriv response contained no candle history")
        return [{key: float(item[key]) if key != "epoch" else int(item[key]) for key in ("epoch", "open", "high", "low", "close")} for item in candles]
    finally:
        ws.close()


def browser_probe(enabled=False):
    """Optional navigation diagnostic only; no unverified chart selectors are read."""
    if not enabled:
        return {"enabled": False, "status": "disabled"}
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        return {"enabled": True, "status": "unavailable", "reason": "optional Selenium is not installed"}
    options = Options()
    options.add_argument("--headless=new")
    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    try:
        service = Service(executable_path=driver_path) if driver_path else Service()
        driver = webdriver.Chrome(service=service, options=options)
        try:
            driver.get("https://charts.deriv.com")
            return {"enabled": True, "status": "navigated", "url": driver.current_url,
                    "live_chart_state": "not read: no verified selectors/integration are configured"}
        finally:
            driver.quit()
    except Exception as exc:
        return {"enabled": True, "status": "unavailable", "reason": str(exc),
                "compatibility": "Catalina-targeted ChromeDriver 115.x with matching Chrome is unverified"}
