"""Cell interpreters: turn the text of table cells into `Benefit`s.

An interpreter is a function `(product: ProductTable, **options) -> {cell_id: [Benefit]}`.
To add one, write it in its own module and register it in `INTERPRETERS` below.
"""
from typing import Callable

from oil_price_v2.errors import OilPriceError
from oil_price_v2.models import Benefit
from oil_price_v2.weekly_page import ProductTable

Interpreter = Callable[..., dict[int, list[Benefit]]]


def _llm(product: ProductTable, **options) -> dict[int, list[Benefit]]:
    from oil_price_v2.interpreter_llm import interpret_with_llm  # lazy: needs langchain

    return interpret_with_llm(product, **options)


def _rules(product: ProductTable, **options) -> dict[int, list[Benefit]]:
    from oil_price_v2.interpreter_rules import interpret_with_rules

    return interpret_with_rules(product)


INTERPRETERS: dict[str, Interpreter] = {
    "llm": _llm,      # LangChain + chat model; understands any wording and language
    "rules": _rules,  # regular expressions; no AI, English wording only, unknown text -> model "other"
}


def get_interpreter(name: str) -> Interpreter:
    try:
        return INTERPRETERS[name]
    except KeyError:
        raise OilPriceError(f"Unknown decoder '{name}'. Available: {', '.join(INTERPRETERS)}")

