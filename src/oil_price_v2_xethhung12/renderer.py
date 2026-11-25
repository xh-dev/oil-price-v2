"""Step 3: render `prices.json` into a static HTML page.

The page has two parts:
1. A ranking table: products sorted by price (lowest first), one column per day.
   Click a column header to sort by that day.
2. One detail table per product (same order): rows are discount categories, columns are days,
   each cell lists the benefits of that day in plain words.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from oil_price_v2_xethhung12.models import DiscountRecord, PriceReport, ProductPrices

# Plain HTML template, edit it to change the look of the page.
DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "index.html.j2"

# Texts of the page, per language ("lang" of the report). Add a language here.
LABELS: dict[str, dict] = {
    "en": {
        "html_lang": "en", "lang_name": "EN", "title": "Hong Kong fuel discounts", "updated": "Updated", "source": "Source",
        "source_name": "Consumer Council", "rank_title": "Price ranking",
        "rank_hint": (
            "Lowest first. Price = pump price minus the biggest per-litre discount of the day that needs no "
            "specific station, minimum spend or credit card (a membership card may be needed). "
            "Click a day to sort by it. Pump price is today's price, assumed unchanged for the week."
        ),
        "product": "Product", "pump": "Pump", "pump_price": "Pump price", "best": "Best price",
        "footer": "Prices and offers are subject to the information provided by each oil company.",
        "models": {"discount": "discount", "points": "points", "voucher": "voucher", "upgrade": "upgrade", "other": "other"},
        "min": "min {}", "only_at": "only at {}", "not_at": "not at {}", "join": ", ",
        "pts": "{} pts", "per_hkd": " per {}", "per_litre": " per litre", "per_litres": " per {} L",
        "voucher": "{} voucher", "upgrade": "upgrade {} → {}",
        "day": lambda d: d.strftime("%a %d %b"),
    },
    "tc": {
        "html_lang": "zh-HK", "lang_name": "中文", "title": "香港油價折扣", "updated": "更新時間", "source": "資料來源",
        "source_name": "消費者委員會", "rank_title": "價格排名",
        "rank_hint": (
            "由低至高。價格 = 零售牌價 − 當日最大的每升折扣（只計不限油站、無最低消費、無須信用卡的折扣，"
            "可能需出示會員卡）。點選日期可按該日排序。零售牌價為今日價格，假設一星期內不變。"
        ),
        "product": "產品", "pump": "牌價", "pump_price": "零售牌價", "best": "最低價",
        "footer": "價格及優惠以各油公司提供的資訊為準。",
        "models": {"discount": "折扣", "points": "積分", "voucher": "禮券", "upgrade": "升級", "other": "其他"},
        "min": "滿{}", "only_at": "僅限{}", "not_at": "不適用於{}", "join": "、",
        "pts": "{}積分", "per_hkd": "／每{}", "per_litre": "／每公升", "per_litres": "／每{}公升",
        "voucher": "{}禮券", "upgrade": "升級 {} → {}",
        "day": lambda d: f"{d.month}月{d.day}日（{'一二三四五六日'[d.weekday()]}）",
    },
}

def _money(value: float) -> str:
    return f"${int(value)}" if value == int(value) else f"${value:.2f}"


def describe(r: DiscountRecord, t: dict) -> str:
    """One line of plain words for a record, e.g. '-$6/L · X Card · not at Chai Wan, Peak'."""
    if r.model == "discount" and r.discount_per_litre is not None:
        what = f"-{_money(r.discount_per_litre)}/L" if t is LABELS["en"] else f"-{_money(r.discount_per_litre)}／公升"
    elif r.model == "points" and r.points is not None:
        per = ""
        if r.points_per_hkd:
            per = t["per_hkd"].format(_money(r.points_per_hkd))
        elif r.points_per_litre:
            per = t["per_litre"] if r.points_per_litre == 1 else t["per_litres"].format(f"{r.points_per_litre:g}")
        what = t["pts"].format(f"{r.points:g}") + per
    elif r.model == "voucher" and r.voucher_value_hkd is not None:
        what = t["voucher"].format(_money(r.voucher_value_hkd))
    elif r.model == "upgrade":
        what = t["upgrade"].format(r.upgrade_from or "?", r.upgrade_to or "?")
    else:
        return r.description
    c = r.criteria
    parts = [what]
    if c.min_purchase_hkd:
        parts.append(t["min"].format(_money(c.min_purchase_hkd)))
    if c.membership_card:
        parts.append(c.membership_card)
    if c.credit_card:
        parts.append(c.credit_card)
    if c.locations:
        parts.append(t["only_at"].format(t["join"].join(c.locations)))
    if c.locations_excluded:
        parts.append(t["not_at"].format(t["join"].join(c.locations_excluded)))
    if c.time_from and c.time_to:
        parts.append(f"{c.time_from}–{c.time_to}")
    return " · ".join(parts)
@dataclass
class DayPrice:
    price: float | None  # HKD per litre after the best general discount; None if the pump price is unknown
    discount: float      # HKD per litre deducted from the pump price (0 if none)
    card: str | None     # card needed for that discount, if any
    requirement: str     # everything needed to get it in words, e.g. "X Card · not at Chai Wan, Peak"; "" if nothing


def day_price(product: ProductPrices, day: date, t: dict) -> DayPrice:
    """Lowest price of the day that needs no special station, minimum spend or credit card.

    = pump price - the biggest plain per-litre discount of that day (walk-in discounts, which
    may need a membership card). Station-specific offers, vouchers and points are not included.
    """
    if product.pump_price is None:
        return DayPrice(None, 0.0, None, "")
    plain = [
        r for r in product.discounts
        if r.date == day and r.model == "discount" and r.discount_per_litre
        and not r.criteria.locations and not r.criteria.min_purchase_hkd and not r.criteria.credit_card
    ]
    if not plain:
        return DayPrice(product.pump_price, 0.0, None, "")
    best = max(plain, key=lambda r: r.discount_per_litre)
    c = best.criteria
    requirement = " · ".join(
        x for x in [c.membership_card, t["not_at"].format(t["join"].join(c.locations_excluded)) if c.locations_excluded else None] if x
    )
    return DayPrice(round(product.pump_price - best.discount_per_litre, 2), best.discount_per_litre, c.membership_card, requirement)


def grid(product: ProductPrices, dates: list[date], t: dict) -> list[tuple[str, list[list[dict]]]]:
    """[(category, [cell of day 1, cell of day 2, ...]), ...]; a cell is a list of {model, text}."""
    categories: list[str] = []
    for r in product.discounts:
        if r.category not in categories:
            categories.append(r.category)
    return [
        (cat, [[{"model": r.model, "text": describe(r, t)} for r in product.discounts if r.category == cat and r.date == d] for d in dates])
        for cat in categories
    ]


def _render_language(report: PriceReport) -> dict:
    """Everything the template needs for one language."""
    t = LABELS.get(report.lang, LABELS["en"])
    dates = sorted({r.date for p in report.products for r in p.discounts})
    rows = [(p, [day_price(p, d, t) for d in dates]) for p in report.products]
    # lowest price first, by the first day; unknown prices last
    rows.sort(key=lambda row: (row[1][0].price is None, row[1][0].price or 0, row[0].name) if dates else (False, 0, row[0].name))
    return {
        "code": report.lang, "t": t, "report": report, "dates": dates, "day_label": t["day"],
        "products": [(p, prices, grid(p, dates, t)) for p, prices in rows],
    }
def render(reports: list[PriceReport], template_dir: Path | None = None) -> str:
    """One page with every report (language) in it; the first report is shown by default."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir or DEFAULT_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env.get_template(TEMPLATE_NAME).render(langs=[_render_language(r) for r in reports])
