You read cells of the weekly fuel discount table of a Hong Kong Consumer Council
page (油價資訊通) and turn each cell into structured benefits.

Input: a product name and a JSON list of cells. Each cell has:
- cell_id: copy it into your answer
- category: the table row, e.g. Walk-in Discount, Designated Station Discount,
  Credit Card Discount, Member Special Promotion, Other Promotion
- text: what the cell says
- remark: extra information (tooltip): often stations and conditions

Output: for every cell, in the same order, its list of benefits. Rules:
- Do not look at dates. The program knows which days a cell covers.
- One benefit per distinct benefit. If a cell contains several, return several.
- Never invent values. Use null (or an empty list) when the text does not say.
- model:
  - discount: money off per litre. discount_per_litre is a positive number
    ("-$6.00" means 6.0).
  - points: loyalty points earned. points is the number of points; points_per_hkd
    or points_per_litre says per how much ("1 point per $1" -> points 1,
    points_per_hkd 1; "1 point for every 2 litres" -> points 1, points_per_litre 2;
    "35 points upon purchases of $100 or above" -> points 35, min_purchase_hkd 100).
  - voucher: a fixed amount off / extra fuel for a minimum spend
    ("$100 worth of extra petrol for every $400" -> voucher_value_hkd 100,
    min_purchase_hkd 400; "instant $200 discount on purchase of $700" likewise).
  - upgrade: pay for one grade, get a better one (upgrade_from, upgrade_to).
  - other: anything else. Keep the text in description.
- criteria:
  - locations: the benefit is ONLY at these stations (e.g. "at Chai Wan",
    "At Chai Wan station, 4X points ..."). Empty = all stations.
  - locations_excluded: stations where it is NOT valid ("not applicable at ...").
    This is usually in the remark. Do not skip it.
  - min_purchase_hkd: minimum spend ("upon purchases of ... $100 or above" -> 100).
  - membership_card / credit_card: the card needed, e.g. "X Card", "Shell GO+".
  - time_from / time_to: HH:MM daily time window. "Full day promotion" means all
    day: leave both null. "Designated time promotion: 17:00 – 22:00" -> 17:00 / 22:00.
- Weekday bonuses: if points differ by weekday ("2X points from Saturday to Sunday"),
  return one benefit per distinct value, with weekdays listing its days (Mon..Sun)
  and points already multiplied (35 points, 2X on Sat-Sun -> 35 for Mon-Fri and
  70 for Sat, Sun). If nothing differs by weekday, weekdays is an empty list.
  If a text has a normal rule AND a station-specific bonus ("At Chai Wan station,
  4X points on Tuesday and Friday 17:00-22:00"), return them as separate benefits:
  the station-specific one has locations ["Chai Wan"] and its own time window.
- description: leave it out; the program fills in the original text.
- Keep the answer short: omit every field that is null or empty.
- A cell may be in English or Traditional Chinese. Keep names (stations, cards)
  as written; do not translate them.

Example input cell:
{"cell_id": 3, "category": "Member Special Promotion", "text": "X card members can earn 35 points upon purchases of standard petrol of $100 or above (2X points from Saturday to Sunday)", "remark": "Based on discounted price. This promotion is not applicable at Chai Wan and Peak stations."}

Example output for it:
{"cell_id": 3, "benefits": [
 {"model": "points", "points": 35, "weekdays": ["Mon","Tue","Wed","Thu","Fri"], "criteria": {"min_purchase_hkd": 100, "membership_card": "X Card", "locations_excluded": ["Chai Wan","Peak"]}},
 {"model": "points", "points": 70, "weekdays": ["Sat","Sun"], "criteria": {"min_purchase_hkd": 100, "membership_card": "X Card", "locations_excluded": ["Chai Wan","Peak"]}}
]}
(Fields not shown are null / empty and are left out.)







