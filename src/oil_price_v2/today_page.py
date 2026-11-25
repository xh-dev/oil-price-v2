"""Read the retail (pump) prices from the today-discount page (no AI)."""
import logging
import re

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# --- selectors: change here when the site changes ---
CARD = "div.blr"
TITLE = ".blr__title strong"
FIRST_PANEL_TEXT = ".panel-group--discount > .panel .panel__heading-text"


def product_key(name: str) -> str:
    """Make names from both pages comparable.

    'Sinopec - SINO Power (Standard Petrol)' and 'Sinopec-SINO Power' -> 'sinopec-sino power'
    """
    name = re.sub(r"\(.*?\)", "", name).replace("\u00ae", "")
    name = re.sub(r"\s*-\s*", "-", name)
    return " ".join(name.split()).lower()


def parse_pump_prices(html: str) -> dict[str, float]:
    """{product_key: price in HKD per litre}"""
    soup = BeautifulSoup(html, "html.parser")
    prices: dict[str, float] = {}
    for card in soup.select(CARD):
        title = card.select_one(TITLE)
        first = card.select_one(FIRST_PANEL_TEXT)  # the list price panel comes first
        m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", first.get_text(" ") if first else "")
        if title and m:
            prices[product_key(title.get_text(" "))] = float(m.group(1).replace(",", ""))
    if not prices:
        log.warning("No pump prices found on the today page (selector '%s').", CARD)
    return prices

