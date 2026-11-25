"""Rule based interpreter: regular expressions, no AI.

Written against the English and Traditional Chinese wording of the site at the time of writing. Text that
no rule understands becomes a benefit with model "other" (the text is kept), so
nothing is lost silently. Add or fix rules here when the wording changes; the `llm`
interpreter is the fallback that needs no maintenance.
"""
import re

from oil_price_v2.models import WEEKDAYS, Benefit, benefit, criteria_of
from oil_price_v2.weekly_page import Cell, ProductTable

_DAY_NAMES = {d.lower(): d[:3] for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
_DAY = "(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_NUM = r"(\d+(?:\.\d+)?)"


# ---------- small helpers ----------

def _short(day: str) -> str:
    return _DAY_NAMES[day.lower()]


def _split_names(text: str) -> list[str]:
    """'Chai Wan, MacDonnell Road and Peak' / '柴灣、麥當勞道及山頂' -> ['Chai Wan', 'MacDonnell Road', 'Peak']"""
    text = re.sub(r"\(.*?\)|（.*?）", "", text)
    return [p.strip() for p in re.split(r",|、|及|\band\b", text) if p.strip()]


def _excluded_stations(text: str) -> list[str]:
    m = re.search(r"not applicable at (.+?)\s+stations?\b", text, re.I)
    if m:
        return _split_names(m.group(1))
    m = re.search(r"不適用於(.+?)油站", text)  # tc
    return _split_names(m.group(1)) if m else []


def _card_from_remark(remark: str) -> str | None:
    m = re.match(r"^(.*?)\s+discount\b", remark, re.I)  # "X Card discount, this ..."
    if not m:
        m = re.match(r"^(.+?)\s*折扣(?:[，,。]|$)", remark)  # tc: "X Card折扣，此折扣不適用..." / "折扣卡折扣"
    return m.group(1).strip() if m else None


_TC_DAYS = {"一": "Mon", "二": "Tue", "三": "Wed", "四": "Thu", "五": "Fri", "六": "Sat", "日": "Sun"}
_TC_FACTORS = {"兩": 2, "二": 2, "三": 3, "四": 4, "五": 5}


def _tc_days(text: str) -> list[str]:
    """'六至日' -> ['Sat', 'Sun'];  '二及五' -> ['Tue', 'Fri'];  '三' -> ['Wed']"""
    if "至" in text:
        a, _, b = text.partition("至")
        if a in _TC_DAYS and b in _TC_DAYS:
            start, end = WEEKDAYS.index(_TC_DAYS[a]), WEEKDAYS.index(_TC_DAYS[b])
            return WEEKDAYS[start:end + 1]
    return [_TC_DAYS[ch] for ch in text if ch in _TC_DAYS]


def _weekday_multipliers(text: str) -> dict[str, float]:
    """'(2X points from Saturday to Sunday; 3X points on Tuesday and Friday)' -> {'Sat': 2, 'Sun': 2, 'Tue': 3, 'Fri': 3}
    also the tc form '（星期六至日：兩倍積分；星期二及五：三倍積分）'."""
    result: dict[str, float] = {}
    for m in re.finditer(rf"(\d+)X points from {_DAY} to {_DAY}", text, re.I):
        start, end = WEEKDAYS.index(_short(m.group(2))), WEEKDAYS.index(_short(m.group(3)))
        for i in range(start, end + 1):
            result[WEEKDAYS[i]] = float(m.group(1))
    for m in re.finditer(rf"(\d+)X points on {_DAY}(?:\s*(?:,|and)\s*{_DAY})?", text, re.I):
        for d in m.groups()[1:]:
            if d:
                result[_short(d)] = float(m.group(1))
    for m in re.finditer(r"星期([一二三四五六日至及]+)：(兩|二|三|四|五)倍積分", text):  # tc
        for day in _tc_days(m.group(1)):
            result[day] = float(_TC_FACTORS[m.group(2)])
    return result


def _points_benefits(base: float, multipliers: dict[str, float], description: str, **fields) -> list[Benefit]:
    """One benefit per distinct multiplier, with the weekdays it applies to."""
    by_factor: dict[float, list[str]] = {}
    for day in WEEKDAYS:
        by_factor.setdefault(multipliers.get(day, 1.0), []).append(day)
    criteria = fields.pop("criteria")
    return [
        benefit("points", description, criteria=criteria, points=base * factor,
                weekdays=days if len(by_factor) > 1 else [], **fields)
        for factor, days in by_factor.items()
    ]


# ---------- one function per kind of cell; each returns None if it does not recognise the cell ----------

def _walk_in(c: Cell) -> list[Benefit] | None:
    m = re.match(rf"^-\$\s*{_NUM}", c.text)
    if not m:
        return None
    criteria = criteria_of(membership_card=_card_from_remark(c.remark), locations_excluded=_excluded_stations(c.remark))
    return [benefit("discount", f"{c.text} ({c.remark})" if c.remark else c.text, criteria, discount_per_litre=float(m.group(1)))]


def _designated_station(c: Cell) -> list[Benefit] | None:
    t = re.match(r"^(Full day|Designated time) promotion:\s*(\d\d:\d\d)\s*[–-]\s*(\d\d:\d\d)", c.text)
    m = re.match(rf"^Discount of \${_NUM}/L:\s*(.+)$", c.remark)
    if not (t and m):
        return None
    full_day = t.group(1) == "Full day"
    criteria = criteria_of(
        locations=_split_names(m.group(2)),
        time_from=None if full_day else t.group(2),
        time_to=None if full_day else t.group(3),
    )
    return [benefit("discount", f"{c.text} ({c.remark})", criteria, discount_per_litre=float(m.group(1)))]


def _upgrade(c: Cell) -> list[Benefit] | None:
    text = c.text
    m = re.search(r"(?:free upgrade to purchase|can enjoy) (.+?) at (.+?) price at (.+?) stations?", text, re.I)
    if m:
        card = re.match(r"^(.+?) members", text)
        criteria = criteria_of(locations=_split_names(m.group(3)), membership_card=card.group(1) if card else None)
        return [benefit("upgrade", text, criteria, upgrade_from=m.group(2), upgrade_to=m.group(1))]
    if re.search(r"premium petrol at the price of standard petrol", text, re.I):
        return [benefit("upgrade", text, upgrade_from="standard petrol", upgrade_to="premium petrol")]
    return None


def _points(c: Cell) -> list[Benefit] | None:
    m = re.search(rf"^(.+?) members can earn {_NUM} points?", c.text, re.I)
    if not m or re.search(r"\bAt .+? station", c.text):  # station specific bonuses: too irregular for rules
        return None
    card, base = m.group(1), float(m.group(2))
    spend = re.search(rf"upon purchases of .*?\${_NUM}", c.text)
    per_litre = re.search(rf"for every (?:{_NUM} )?litres? of", c.text, re.I)
    per_hkd = re.search(rf"per \${_NUM}", c.text)
    criteria = criteria_of(
        membership_card=card,
        min_purchase_hkd=float(spend.group(1)) if spend else None,
        locations_excluded=_excluded_stations(c.remark),
    )
    return _points_benefits(
        base, _weekday_multipliers(c.text), f"{c.text} ({c.remark})" if c.remark else c.text,
        criteria=criteria,
        points_per_litre=float(per_litre.group(1) or 1) if per_litre else None,
        points_per_hkd=float(per_hkd.group(1)) if per_hkd else None,
    )


def _instant_discount(c: Cell) -> list[Benefit] | None:
    """'... members can enjoy an instant $13.9/L discount when fueling up premium petrol upon spending $300 or above.'"""
    m = re.search(rf"^(.+?) members can enjoy an instant (?:HK)?\${_NUM}/L discount .*?spending (?:HK)?\${_NUM}", c.text)
    if not m:
        return None
    criteria = criteria_of(membership_card=m.group(1), min_purchase_hkd=float(m.group(3)), locations_excluded=_excluded_stations(c.remark))
    return [benefit("discount", f"{c.text} ({c.remark})", criteria, discount_per_litre=float(m.group(2)))]


def _voucher(c: Cell) -> list[Benefit] | None:
    m = re.search(rf"^(.+?) members can enjoy an instant \${_NUM} discount on fuel purchase of \${_NUM}", c.text)
    if m:
        return [benefit("voucher", c.text, criteria_of(membership_card=m.group(1), min_purchase_hkd=float(m.group(3))), voucher_value_hkd=float(m.group(2)))]
    m = re.search(rf"Purchasing every \${_NUM} of petrol .*? with (.+?), customers can redeem \${_NUM} worth", c.text)
    if m:
        return [benefit("voucher", c.text, criteria_of(credit_card=m.group(2), min_purchase_hkd=float(m.group(1))), voucher_value_hkd=float(m.group(3)))]
    return None


def _credit_card(c: Cell) -> list[Benefit] | None:
    text = c.text
    m = re.search(rf"^(.+?) cardholders can enjoy the extra instant petrol discount of \${_NUM}/L", text)
    if m:
        return [benefit("discount", text, criteria_of(credit_card=m.group(1)), discount_per_litre=float(m.group(2)))]
    m = re.search(rf"can enjoy \${_NUM}/L instant discount using (.+?) via", text)
    if m:
        return [benefit("discount", text, criteria_of(credit_card=m.group(2)), discount_per_litre=float(m.group(1)))]
    m = re.search(rf"^(.+?) members who pay with an? (.+?) can enjoy an additional \${_NUM}/L discount", text)
    if m:
        return [benefit("discount", text, criteria_of(membership_card=m.group(1), credit_card=m.group(2)), discount_per_litre=float(m.group(3)))]
    return None


_RULES = [_walk_in, _designated_station, _upgrade, _points, _instant_discount, _voucher, _credit_card]


# ---------- Traditional Chinese (--lang tc) wording ----------

def _designated_station_tc(c: Cell) -> list[Benefit] | None:
    t = re.match(r"^(全日|特定時段)優惠：\s*(\d\d:\d\d)\s*[–-]\s*(\d\d:\d\d)", c.text)
    m = re.match(rf"^每升減\s*\${_NUM}：(.+)$", c.remark)
    if not (t and m):
        return None
    full_day = t.group(1) == "全日"
    criteria = criteria_of(
        locations=_split_names(m.group(2)),
        time_from=None if full_day else t.group(2),
        time_to=None if full_day else t.group(3),
    )
    return [benefit("discount", f"{c.text} ({c.remark})", criteria, discount_per_litre=float(m.group(1)))]


def _upgrade_tc(c: Cell) -> list[Benefit] | None:
    text = c.text
    m = re.search(r"可於(.+?)油站.*?以(.+?)\s*價錢(?:購買|入)(.+)$", text)
    if m:
        card = re.match(r"^(.+?)會員可於", text)
        criteria = criteria_of(locations=_split_names(m.group(1)), membership_card=card.group(1) if card else None)
        return [benefit("upgrade", text, criteria, upgrade_from=m.group(2).strip(), upgrade_to=m.group(3).strip())]
    m = re.search(r"顧客可以(.+?)價格入(.+)$", text)
    if m:
        return [benefit("upgrade", text, upgrade_from=m.group(1), upgrade_to=m.group(2))]
    return None


def _points_tc(c: Cell) -> list[Benefit] | None:
    m = re.search(rf"^(.+?)會員.*?{_NUM}\s*積分", c.text)
    if not m or re.search(r"會員於(?!全線)(.+?)油站", c.text):  # station specific bonuses: too irregular for rules
        return None
    spend = re.search(rf"滿\${_NUM}", c.text)
    per_litre = re.search(rf"每(?:購買|入)?\s*{_NUM}?\s*(?:公升|升)", c.text)
    per_hkd = re.search(rf"每消費\${_NUM}", c.text)
    criteria = criteria_of(
        membership_card=m.group(1).strip(),
        min_purchase_hkd=float(spend.group(1)) if spend else None,
        locations_excluded=_excluded_stations(c.remark),
    )
    return _points_benefits(
        float(m.group(2)), _weekday_multipliers(c.text), f"{c.text} ({c.remark})" if c.remark else c.text,
        criteria=criteria,
        points_per_litre=float(per_litre.group(1) or 1) if per_litre else None,
        points_per_hkd=float(per_hkd.group(1)) if per_hkd else None,
    )


def _instant_discount_tc(c: Cell) -> list[Benefit] | None:
    m = re.search(rf"^(.+?)會員.*?滿\${_NUM}或以上即時享每升\${_NUM}折扣", c.text)
    if not m:
        return None
    criteria = criteria_of(membership_card=m.group(1), min_purchase_hkd=float(m.group(2)), locations_excluded=_excluded_stations(c.remark))
    return [benefit("discount", f"{c.text} ({c.remark})", criteria, discount_per_litre=float(m.group(3)))]


def _voucher_tc(c: Cell) -> list[Benefit] | None:
    m = re.search(rf"^(.+?)會員.*?滿\${_NUM}可享即減\${_NUM}", c.text)
    if m:
        return [benefit("voucher", c.text, criteria_of(membership_card=m.group(1), min_purchase_hkd=float(m.group(2))), voucher_value_hkd=float(m.group(3)))]
    m = re.search(rf"^用(.+?)入汽油每滿\${_NUM}.*?價值\${_NUM}", c.text)
    if m:
        return [benefit("voucher", c.text, criteria_of(credit_card=m.group(1), min_purchase_hkd=float(m.group(2))), voucher_value_hkd=float(m.group(3)))]
    return None


def _credit_card_tc(c: Cell) -> list[Benefit] | None:
    text = c.text
    m = re.search(rf"^以(.+?)於.*?折扣每升\${_NUM}", text)
    if m:
        return [benefit("discount", text, criteria_of(credit_card=m.group(1)), discount_per_litre=float(m.group(2)))]
    m = re.search(rf"^顧客憑(.+?)感應式.*?每升\${_NUM}即時折扣", text)
    if m:
        return [benefit("discount", text, criteria_of(credit_card=m.group(1)), discount_per_litre=float(m.group(2)))]
    m = re.search(rf"^(.+?)會員憑(.+?)付款可享額外每升\${_NUM}", text)
    if m:
        return [benefit("discount", text, criteria_of(membership_card=m.group(1), credit_card=m.group(2)), discount_per_litre=float(m.group(3)))]
    return None


_RULES += [_designated_station_tc, _upgrade_tc, _points_tc, _instant_discount_tc, _voucher_tc, _credit_card_tc]


def interpret_cell(cell: Cell) -> list[Benefit]:
    for rule in _RULES:
        result = rule(cell)
        if result is not None:
            return result
    text = f"{cell.text} ({cell.remark})" if cell.remark else cell.text
    return [benefit("other", text)]


def interpret_with_rules(product: ProductTable) -> dict[int, list[Benefit]]:
    return {cell.id: interpret_cell(cell) for cell in product.cells}


def normalise_benefit(b: Benefit, cell: Cell) -> Benefit:
    """Cheap, deterministic fixes for details a (small) LLM often gets wrong or leaves out.

    Used on the output of the `llm` interpreter. It only fills gaps and never overrides a value.
    """
    c = b.criteria
    if c.time_from == "00:00" and c.time_to in ("23:59", "24:00"):  # "full day" is not a time window
        c.time_from = c.time_to = None
    if not c.locations_excluded:
        c.locations_excluded = _excluded_stations(cell.remark)
    if not c.membership_card and b.model == "discount" and cell.category.lower().startswith(("walk-in", "門市折扣")):
        c.membership_card = _card_from_remark(cell.remark)  # "X Card discount, ..." -> "X Card"
    if c.min_purchase_hkd is None and b.model in ("points", "discount"):
        m = re.search(rf"(?:purchases? of|spending|purchase of) .*?\${_NUM} or (?:above|more)", cell.text) \
            or re.search(rf"滿\${_NUM}", cell.text)
        if m:
            c.min_purchase_hkd = float(m.group(1))
    return b







