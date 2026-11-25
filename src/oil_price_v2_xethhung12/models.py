"""Data model of `prices.json` (modelled on the v1 `price-info.json`).

One `ProductPrices` per fuel product; each has one `DiscountRecord` per day and
benefit. A record is either a money discount, points earning, a voucher or a free
upgrade, with its criteria (minimum purchase, stations, card, time window).

This is the contract between `decode` and `gen-html`. Any decoder (LLM, rules,
or a human editing the JSON by hand) only has to produce this shape.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from oil_price_v2_xethhung12.errors import OilPriceError

Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Criteria(BaseModel):
    """Conditions to get a benefit. Empty / null means "no condition"."""

    min_purchase_hkd: float | None = Field(default=None, description="Minimum spend in HKD (after discount) needed, or null.")
    locations: list[str] = Field(default_factory=list, description="Only valid at these stations, e.g. ['Chai Wan']. Empty = every station.")
    locations_excluded: list[str] = Field(default_factory=list, description="NOT valid at these stations. Empty = no exclusion.")
    membership_card: str | None = Field(default=None, description="Membership / discount card needed, e.g. 'X Card', or null.")
    credit_card: str | None = Field(default=None, description="Credit card needed, e.g. 'Mastercard', or null.")
    time_from: str | None = Field(default=None, description="Start of the daily time window as HH:MM, or null for all day.")
    time_to: str | None = Field(default=None, description="End of the daily time window as HH:MM, or null for all day.")


class Benefit(BaseModel):
    """One benefit, as decoded from one table cell (not yet tied to a date)."""

    model: Literal["discount", "points", "voucher", "upgrade", "other"] = Field(
        description=(
            "discount = money off per litre; points = loyalty points earned; "
            "voucher = extra fuel/money value for a minimum spend; upgrade = pay for a lower grade, "
            "get a higher grade; other = anything that does not fit (keep the text in description)."
        )
    )
    discount_per_litre: float | None = Field(default=None, description="HKD taken off per litre (positive number). For model=discount, else null.")
    voucher_value_hkd: float | None = Field(default=None, description="HKD value of the voucher / extra fuel. For model=voucher, else null.")
    points: float | None = Field(default=None, description="Points earned, already multiplied by any 2X/3X weekday bonus. For model=points, else null.")
    points_per_hkd: float | None = Field(default=None, description="Points are earned for every this many HKD spent (e.g. 100 for '35 points per $100'), or null.")
    points_per_litre: float | None = Field(default=None, description="Points are earned for every this many litres (e.g. 2 for '1 point per 2 litres'), or null.")
    upgrade_from: str | None = Field(default=None, description="Grade the customer pays for, e.g. 'standard petrol', or null.")
    upgrade_to: str | None = Field(default=None, description="Grade the customer receives, e.g. 'premium petrol', or null.")
    criteria: Criteria = Field(default_factory=Criteria, description="Conditions; omit if there are none.")
    weekdays: list[Weekday] = Field(
        default_factory=list,
        description="Weekdays this benefit applies to. Empty = every day the cell covers. "
        "Use it when the text gives different values on different weekdays (one benefit per value)."
    )
    description: str = Field(default="", description="Leave empty; the program fills in the original cell text.")


def benefit(model: str = "other", description: str = "", criteria: Criteria | None = None, **fields) -> Benefit:
    """Build a Benefit with every unspecified field empty (used by non-LLM code)."""
    empty = dict(
        discount_per_litre=None, voucher_value_hkd=None, points=None, points_per_hkd=None,
        points_per_litre=None, upgrade_from=None, upgrade_to=None, weekdays=[],
    )
    return Benefit(model=model, description=description, criteria=criteria or criteria_of(), **{**empty, **fields})


def criteria_of(**fields) -> Criteria:
    """Build Criteria with every unspecified field empty."""
    empty = dict(
        min_purchase_hkd=None, locations=[], locations_excluded=[], membership_card=None,
        credit_card=None, time_from=None, time_to=None,
    )
    return Criteria(**{**empty, **fields})


class CellDecoding(BaseModel):
    cell_id: int = Field(description="The id of the input cell.")
    benefits: list[Benefit] = Field(description="Benefits in that cell. Empty list if the cell holds no benefit.")


class CellDecodings(BaseModel):
    """What an interpreter returns for one product."""

    cells: list[CellDecoding]


class _Day(BaseModel):
    date: date
    day_of_week: Weekday
    category: str = Field(description="Row heading of the table, e.g. Walk-in Discount.")


class DiscountRecord(_Day, Benefit):
    """A benefit on one date."""


class ProductPrices(BaseModel):
    name: str = Field(description="Full product name as on the page, e.g. 'Sinopec - SINO Power (Standard Petrol)'.")
    company: str
    product: str
    fuel_type: str
    pump_price: float | None = Field(description="Retail price in HKD per litre before any discount.")
    discounts: list[DiscountRecord]


class PriceReport(BaseModel):
    """Content of `prices.json`."""

    source_url: str
    fetched_at: datetime
    decoder: str
    lang: str = "en"  # language of the source page: "en" or "tc"; the generated page uses it
    products: list[ProductPrices]


def validate_report(report: PriceReport) -> None:
    """Sanity checks. Raises OilPriceError on bad data."""
    if not report.products:
        raise OilPriceError("No products were decoded.")
    for p in report.products:
        if p.pump_price is not None and not (0 < p.pump_price < 200):
            raise OilPriceError(f"Implausible pump price {p.pump_price} for {p.name}.")
        for d in p.discounts:
            v = d.discount_per_litre
            if v is not None and not (0 < v < 100):
                raise OilPriceError(f"Implausible discount {v} for {p.name} on {d.date}.")


