"""Step 2: weekly + today pages -> PriceReport.

1. weekly_page: deterministic table parsing -> cells with their covered days.
2. interpreter (llm / rules): cell text -> benefits.
3. expand: benefits x covered days -> one DiscountRecord per date.
"""
import logging
from datetime import datetime

from oil_price_v2_xethhung12.interpreters import get_interpreter
from oil_price_v2_xethhung12.models import WEEKDAYS, DiscountRecord, PriceReport, ProductPrices, validate_report
from oil_price_v2_xethhung12.today_page import parse_pump_prices, product_key
from oil_price_v2_xethhung12.weekly_page import parse_weekly

log = logging.getLogger(__name__)


def _split_name(name: str) -> tuple[str, str, str]:
    """'Sinopec - SINO Power (Standard Petrol)' -> ('Sinopec', 'SINO Power', 'Standard Petrol')"""
    company, _, rest = name.partition(" - ")
    product, _, fuel = rest.partition(" (")
    return company.strip(), product.strip() or name, fuel.rstrip(") ").strip()


class ReportBuilder:
    """Decodes one language. `build()` decodes every product; `redecode()` decodes one product again."""

    def __init__(
        self,
        weekly_html: str,
        today_html: str,
        fetched_at: datetime,
        source_url: str,
        decoder: str,
        lang: str = "en",
        **decoder_options,
    ):
        self.table = parse_weekly(weekly_html, fetched_at)
        self.pump_prices = parse_pump_prices(today_html)
        self.interpret = get_interpreter(decoder)
        self.fetched_at, self.source_url, self.decoder, self.lang = fetched_at, source_url, decoder, lang
        self.decoder_options = decoder_options

    def decode_product(self, index: int) -> ProductPrices:
        pt = self.table.products[index]
        log.info("[%s] Decoding %s (%d cells)", self.lang, pt.name, len(pt.cells))
        decoded = self.interpret(pt, **self.decoder_options)
        records: list[DiscountRecord] = []
        for cell in pt.cells:
            for day in range(cell.first_day, cell.last_day + 1):
                d = self.table.dates[day]
                weekday = WEEKDAYS[d.weekday()]  # not strftime: that depends on the locale
                for b in decoded.get(cell.id, []):
                    if b.weekdays and weekday not in b.weekdays:
                        continue
                    records.append(DiscountRecord(date=d, day_of_week=weekday, category=cell.category, **b.model_dump()))
        records.sort(key=lambda r: (r.date, r.category))

        company, product, fuel_type = _split_name(pt.name)
        price = self.pump_prices.get(product_key(pt.name))
        if price is None:
            log.warning("No pump price found for '%s'.", pt.name)
        return ProductPrices(name=pt.name, company=company, product=product, fuel_type=fuel_type, pump_price=price, discounts=records)

    def build(self) -> PriceReport:
        products = [self.decode_product(i) for i in range(len(self.table.products))]
        report = PriceReport(source_url=self.source_url, fetched_at=self.fetched_at, decoder=self.decoder, lang=self.lang, products=products)
        validate_report(report)
        return report

    def redecode(self, report: PriceReport, index: int) -> None:
        """Replace one product of `report` with a fresh decoding."""
        report.products[index] = self.decode_product(index)
        validate_report(report)


def build_report(
    weekly_html: str,
    today_html: str,
    fetched_at: datetime,
    source_url: str,
    decoder: str,
    lang: str = "en",
    **decoder_options,
) -> PriceReport:
    return ReportBuilder(weekly_html, today_html, fetched_at, source_url, decoder, lang, **decoder_options).build()