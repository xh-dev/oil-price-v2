"""Step 2: weekly + today pages -> PriceReport.

1. weekly_page: deterministic table parsing -> cells with their covered days.
2. interpreter (llm / rules): cell text -> benefits.
3. expand: benefits x covered days -> one DiscountRecord per date.
"""
import logging
from datetime import datetime

from oil_price_v2.interpreters import get_interpreter
from oil_price_v2.models import WEEKDAYS, DiscountRecord, PriceReport, ProductPrices, validate_report
from oil_price_v2.today_page import parse_pump_prices, product_key
from oil_price_v2.weekly_page import parse_weekly

log = logging.getLogger(__name__)


def _split_name(name: str) -> tuple[str, str, str]:
    """'Sinopec - SINO Power (Standard Petrol)' -> ('Sinopec', 'SINO Power', 'Standard Petrol')"""
    company, _, rest = name.partition(" - ")
    product, _, fuel = rest.partition(" (")
    return company.strip(), product.strip() or name, fuel.rstrip(") ").strip()


def build_report(
    weekly_html: str,
    today_html: str,
    fetched_at: datetime,
    source_url: str,
    decoder: str,
    lang: str = "en",
    **decoder_options,
) -> PriceReport:
    table = parse_weekly(weekly_html, fetched_at)
    pump_prices = parse_pump_prices(today_html)
    interpret = get_interpreter(decoder)

    products: list[ProductPrices] = []
    for pt in table.products:
        log.info("Decoding %s (%d cells)", pt.name, len(pt.cells))
        decoded = interpret(pt, **decoder_options)
        records: list[DiscountRecord] = []
        for cell in pt.cells:
            for day in range(cell.first_day, cell.last_day + 1):
                d = table.dates[day]
                weekday = WEEKDAYS[d.weekday()]  # not strftime: that depends on the locale
                for b in decoded.get(cell.id, []):
                    if b.weekdays and weekday not in b.weekdays:
                        continue
                    records.append(DiscountRecord(date=d, day_of_week=weekday, category=cell.category, **b.model_dump()))
        records.sort(key=lambda r: (r.date, r.category))

        company, product, fuel_type = _split_name(pt.name)
        price = pump_prices.get(product_key(pt.name))
        if price is None:
            log.warning("No pump price found for '%s'.", pt.name)
        products.append(ProductPrices(name=pt.name, company=company, product=product, fuel_type=fuel_type, pump_price=price, discounts=records))

    report = PriceReport(source_url=source_url, fetched_at=fetched_at, decoder=decoder, lang=lang, products=products)
    validate_report(report)
    return report

