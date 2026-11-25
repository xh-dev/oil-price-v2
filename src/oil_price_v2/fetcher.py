"""Step 1: download the page."""
import logging
import time

import httpx

from oil_price_v2.errors import OilPriceError

log = logging.getLogger(__name__)

# Browser-like headers; the site rejects obvious bot clients.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
}
RETRIES = 3
TIMEOUT_SECONDS = 30


def fetch_html(url: str) -> str:
    last_error = "unknown error"
    for attempt in range(1, RETRIES + 1):
        try:
            response = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
        else:
            if response.status_code == 200:
                return response.text
            last_error = f"HTTP {response.status_code}"
            if response.status_code in (403, 429):
                raise OilPriceError(
                    f"Fetch blocked by the server ({last_error}). "
                    "GitHub-hosted runners are known to be blocked; run `fetch` from another machine."
                )
        log.warning("Fetch attempt %d/%d failed: %s", attempt, RETRIES, last_error)
        if attempt < RETRIES:
            time.sleep(2 ** attempt)
    raise OilPriceError(f"Could not fetch {url}: {last_error}")

