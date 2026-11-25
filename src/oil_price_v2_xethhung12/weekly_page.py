"""Read the weekly-discount page into plain cells (no AI, no guessing).

The page is a table per product: rows are discount categories (Walk-in Discount,
Designated Station Discount, ...), columns are the next 7 days, and one cell can
span several days (colspan). This module turns that into a list of `Cell`s, each
knowing which days it covers. Interpreting the *text* of a cell is the job of an
interpreter (see `interpreters.py`).
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag

from oil_price_v2_xethhung12.errors import OilPriceError

# --- selectors: change here when the site changes ---
HEAD_DATES = "table.tb__headtable thead th .tb__head-sub"
PRODUCT_TABLE = "table.tb__table.tb__item"
ROW = "tbody.tb__tbody > tr"
ROW_HEADING = "td.tb__subhead"
CELL = "td.tb__cell"
CELL_TEXT = "span.tb__text"
CELL_REMARK = ".tooltipster__body"


@dataclass
class Cell:
    id: int
    category: str   # row heading, e.g. "Walk-in Discount"
    first_day: int  # index into WeeklyTable.dates
    last_day: int   # inclusive
    text: str
    remark: str     # tooltip text, often holds stations / conditions


@dataclass
class ProductTable:
    name: str  # e.g. "Sinopec - SINO Power (Standard Petrol)"
    cells: list[Cell] = field(default_factory=list)


@dataclass
class WeeklyTable:
    dates: list[date]
    products: list[ProductTable]


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ").replace("\xa0", " ").split()) if node else ""


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_day_month(text: str) -> tuple[int, int]:
    """'25 Nov' (en) or '11月25日' / '25 11月' (tc) -> (day, month)."""
    m = re.search(r"(\d{1,2})\s*([A-Za-z]{3})", text)
    if m and m.group(2).lower() in _MONTHS:
        return int(m.group(1)), _MONTHS[m.group(2).lower()]
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", text)  # 11月25日
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(\d{1,2})\s*日?\s*(\d{1,2})\s*月", text)  # 25日11月 / 25 11月
    if m:
        return int(m.group(1)), int(m.group(2))
    raise OilPriceError(f"Cannot read the date '{text}' in the weekly table header.")


def parse_dates(soup: BeautifulSoup, reference: date) -> list[date]:
    dates: list[date] = []
    year = reference.year
    for node in soup.select(HEAD_DATES):
        day, month = _parse_day_month(_text(node))
        d = date(year, month, day)
        if dates and d < dates[-1]:  # passed New Year
            year += 1
            d = date(year, month, day)
        dates.append(d)
    return dates


def parse_weekly(html: str, reference: datetime) -> WeeklyTable:
    soup = BeautifulSoup(html, "html.parser")
    dates = parse_dates(soup, reference.date())
    tables = soup.select(PRODUCT_TABLE)
    if not dates or not tables:
        raise OilPriceError(
            f"Weekly page: found {len(dates)} dates and {len(tables)} product tables "
            f"(selectors '{HEAD_DATES}', '{PRODUCT_TABLE}'); the page layout may have changed."
        )

    products: list[ProductTable] = []
    for table in tables:
        product = ProductTable(name=_text_attr(table.get("title")))
        category = ""
        for row in table.select(ROW):
            heading = row.select_one(ROW_HEADING)
            if heading:
                category = _text(heading)
            column = 0
            for td in row.select(CELL):
                span = int(td.get("colspan", 1))
                text = _text(td.select_one(CELL_TEXT))
                if text:  # empty cell = no benefit on those days
                    product.cells.append(
                        Cell(
                            id=len(product.cells),
                            category=category,
                            first_day=column,
                            last_day=min(column + span, len(dates)) - 1,
                            text=text,
                            remark=_text(td.select_one(CELL_REMARK)),
                        )
                    )
                column += span
        products.append(product)
    return WeeklyTable(dates=dates, products=products)


def _text_attr(value) -> str:
    return " ".join(str(value or "").split())

