"""Check that the reports of different languages say the same thing.

The Chinese and English pages describe the same data, so after decoding, everything that is not
text must agree: product count, pump prices and, per product, the multiset of records
(date, benefit model, amounts, time window, number of stations, ...).
Names, categories and descriptions are language specific and are not compared.

Products are matched by their position on the page, because their names differ between languages.
"""
from collections import Counter
from dataclasses import dataclass, field

from oil_price_v2_xethhung12.models import DiscountRecord, PriceReport

SHOWN = 3  # differences listed per side in a message


@dataclass
class Mismatches:
    fatal: list[str] = field(default_factory=list)  # decoding again cannot fix these (counts, pump prices)
    products: dict[int, list[str]] = field(default_factory=dict)  # product index -> messages; decoding again may fix

    def __bool__(self) -> bool:
        return bool(self.fatal or self.products)

    def messages(self) -> list[str]:
        return [*self.fatal, *(m for i in sorted(self.products) for m in self.products[i])]


def _num(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def record_key(d: DiscountRecord) -> tuple:
    c = d.criteria
    return (
        d.date.isoformat(), d.model, _num(d.discount_per_litre), _num(d.voucher_value_hkd), _num(d.points),
        _num(d.points_per_hkd), _num(d.points_per_litre), _num(c.min_purchase_hkd), c.time_from, c.time_to,
        len(c.locations), len(c.locations_excluded), c.membership_card is not None, c.credit_card is not None,
    )


def _fmt(keys) -> str:
    keys = sorted(keys, key=str)
    text = "; ".join(str(k) for k in keys[:SHOWN])
    return text + (f"; ... (+{len(keys) - SHOWN})" if len(keys) > SHOWN else "")


def compare(reference: PriceReport, other: PriceReport) -> Mismatches:
    """Differences between two reports of the same data in different languages."""
    result = Mismatches()
    a, b = reference.lang, other.lang
    if len(reference.products) != len(other.products):
        result.fatal.append(f"[{a} vs {b}] {len(reference.products)} products vs {len(other.products)}")
        return result

    for i, (p, q) in enumerate(zip(reference.products, other.products)):
        label = f"[{a} vs {b}] product #{i + 1} ({p.name} / {q.name})"
        if _num(p.pump_price) != _num(q.pump_price):
            result.fatal.append(f"{label}: pump price {p.pump_price} vs {q.pump_price}")
        only_a = Counter(record_key(d) for d in p.discounts) - Counter(record_key(d) for d in q.discounts)
        only_b = Counter(record_key(d) for d in q.discounts) - Counter(record_key(d) for d in p.discounts)
        if only_a or only_b:
            result.products.setdefault(i, []).append(
                f"{label}: only in {a}: {_fmt(only_a.elements()) or '-'} | only in {b}: {_fmt(only_b.elements()) or '-'}"
            )
    return result


def compare_all(reports: dict[str, PriceReport], order: list[str]) -> Mismatches:
    """Compare every report with the first one (in `order`) that is present."""
    langs = [lg for lg in order if lg in reports]
    result = Mismatches()
    for lg in langs[1:]:
        m = compare(reports[langs[0]], reports[lg])
        result.fatal += m.fatal
        for i, msgs in m.products.items():
            result.products.setdefault(i, []).extend(msgs)
    return result

