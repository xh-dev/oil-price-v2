"""Check that the reports of different languages say the same thing.

The Chinese and English pages describe the same data, so after decoding, everything that is not
text must agree: product count, pump prices and, per product, the multiset of records
(date, benefit model, amounts, time window, number of stations, ...).
Names, categories and descriptions are language specific and are not compared.

Products are matched by their position on the page, because their names differ between languages.
"""
from collections import Counter
from dataclasses import dataclass, field

from oil_price_v2_xethhung12.models import DiscountRecord, LanguageMismatch, PriceReport

SHOWN = 5  # records listed per side


@dataclass
class Mismatches:
    fatal: list[LanguageMismatch] = field(default_factory=list)  # decoding again cannot fix these (counts, pump prices)
    products: dict[int, list[LanguageMismatch]] = field(default_factory=dict)  # product index -> differences; decoding again may fix

    def __bool__(self) -> bool:
        return bool(self.fatal or self.products)

    def all(self) -> list[LanguageMismatch]:
        return [*self.fatal, *(m for i in sorted(self.products) for m in self.products[i])]

    def messages(self) -> list[str]:
        return [text(m) for m in self.all()]


def _num(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def record_key(d: DiscountRecord) -> tuple:
    c = d.criteria
    return (
        d.date.isoformat(), d.model, _num(d.discount_per_litre), _num(d.voucher_value_hkd), _num(d.points),
        _num(d.points_per_hkd), _num(d.points_per_litre), _num(c.min_purchase_hkd), c.time_from, c.time_to,
        len(c.locations), len(c.locations_excluded), c.membership_card is not None, c.credit_card is not None,
    )


def describe_key(k: tuple) -> str:
    """Readable, language independent text of a record key, e.g. '2026-11-27 discount: -$2.5/L, min $300'."""
    day, model, per_litre, voucher, points, per_hkd, per_l, min_hkd, t_from, t_to, n_in, n_out, member, credit = k
    parts = []
    if per_litre is not None:
        parts.append(f"-${per_litre:g}/L")
    if voucher is not None:
        parts.append(f"voucher ${voucher:g}")
    if points is not None:
        parts.append(f"{points:g} points" + (f" per ${per_hkd:g}" if per_hkd else "") + (f" per {per_l:g} L" if per_l else ""))
    if min_hkd:
        parts.append(f"min ${min_hkd:g}")
    if t_from and t_to:
        parts.append(f"{t_from}-{t_to}")
    if n_in:
        parts.append(f"{n_in} station(s) only")
    if n_out:
        parts.append(f"excludes {n_out} station(s)")
    if member:
        parts.append("membership card")
    if credit:
        parts.append("credit card")
    return f"{day} {model}" + (": " + ", ".join(parts) if parts else "")


def _listed(keys) -> list[str]:
    keys = sorted(keys, key=str)
    out = [describe_key(k) for k in keys[:SHOWN]]
    if len(keys) > SHOWN:
        out.append(f"... (+{len(keys) - SHOWN} more)")
    return out


def text(m: LanguageMismatch) -> str:
    """One-line text of a mismatch, for logs and errors."""
    sides = " | ".join(f"only in {lg}: {'; '.join(items)}" for lg, items in m.only_in.items() if items)
    return " ".join(x for x in [f"{m.kind}:", m.product + ":" if m.product else "", m.note, sides] if x)


def compare(reference: PriceReport, other: PriceReport) -> Mismatches:
    """Differences between two reports of the same data in different languages."""
    result = Mismatches()
    a, b = reference.lang, other.lang
    if len(reference.products) != len(other.products):
        result.fatal.append(LanguageMismatch(
            kind="product_count", note=f"{a}: {len(reference.products)} products, {b}: {len(other.products)} products",
        ))
        return result

    for i, (p, q) in enumerate(zip(reference.products, other.products)):
        label = f"{p.name} / {q.name}"
        if _num(p.pump_price) != _num(q.pump_price):
            result.fatal.append(LanguageMismatch(kind="pump_price", product=label, note=f"{a}: {p.pump_price}, {b}: {q.pump_price}"))
        keys_a = Counter(record_key(d) for d in p.discounts)
        keys_b = Counter(record_key(d) for d in q.discounts)
        only_a, only_b = keys_a - keys_b, keys_b - keys_a
        if only_a or only_b:
            result.products.setdefault(i, []).append(LanguageMismatch(
                kind="records", product=label, only_in={a: _listed(only_a.elements()), b: _listed(only_b.elements())},
            ))
    return result


def compare_all(reports: dict[str, PriceReport], order: list[str]) -> Mismatches:
    """Compare every report with the first one (in `order`) that is present."""
    langs = [lg for lg in order if lg in reports]
    result = Mismatches()
    for lg in langs[1:]:
        m = compare(reports[langs[0]], reports[lg])
        result.fatal += m.fatal
        for i, items in m.products.items():
            result.products.setdefault(i, []).extend(items)
    return result

