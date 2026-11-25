"""LLM interpreter: LangChain chat model with structured output.

One call per product: the model gets the (few) distinct cells of that product
and returns the benefits of each cell. Dates are NOT the model's job: the code
that called us already knows which days a cell covers.
"""
import json
import logging
import os
from pathlib import Path

from oil_price_v2_xethhung12.config import ENV_LLM_BASE_URL, ENV_LLM_MODEL, ENV_LLM_NUM_CTX, ENV_LLM_PROVIDER
from oil_price_v2_xethhung12.errors import OilPriceError
from oil_price_v2_xethhung12.interpreter_rules import normalise_benefit
from oil_price_v2_xethhung12.models import Benefit, CellDecodings, benefit
from oil_price_v2_xethhung12.weekly_page import ProductTable

log = logging.getLogger(__name__)

# Plain text file, edit it to change what the model is told.
DEFAULT_PROMPT_FILE = Path(__file__).parent / "prompts" / "decode_cells.md"
ATTEMPTS = 2
DEFAULT_OLLAMA_NUM_CTX = 16384
MAX_OUTPUT_TOKENS = 6000


def _create_llm(provider: str | None, model: str | None, base_url: str | None):
    model = model or os.getenv(ENV_LLM_MODEL)
    provider = provider or os.getenv(ENV_LLM_PROVIDER)
    base_url = base_url or os.getenv(ENV_LLM_BASE_URL)
    if not model:
        raise OilPriceError(f"No LLM model configured: use --model or set {ENV_LLM_MODEL}.")

    from langchain.chat_models import init_chat_model

    options: dict = {"temperature": 0}
    if base_url:
        options["base_url"] = base_url  # e.g. http://192.168.1.10:11434 for a remote Ollama
    if provider == "ollama":
        # Ollama's default context window is small and silently truncates the input.
        options["num_ctx"] = int(os.getenv(ENV_LLM_NUM_CTX, DEFAULT_OLLAMA_NUM_CTX))
        options["num_predict"] = MAX_OUTPUT_TOKENS  # stop a model that loops instead of waiting forever
        options["reasoning"] = False  # no "thinking": it can use up the output budget and leave an empty answer
    try:
        return init_chat_model(model, model_provider=provider or None, **options)
    except Exception as e:  # missing provider package, bad name, ...
        raise OilPriceError(f"Cannot create LLM '{provider or 'auto'}:{model}': {e}") from e


def interpret_with_llm(
    product: ProductTable,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    prompt_file: Path | None = None,
    **_ignored,
) -> dict[int, list[Benefit]]:
    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = Path(prompt_file or DEFAULT_PROMPT_FILE).read_text(encoding="utf-8")
    cells = [{"cell_id": c.id, "category": c.category, "text": c.text, "remark": c.remark} for c in product.cells]
    if not cells:
        return {}
    messages = [
        SystemMessage(system_prompt),
        HumanMessage(f"Product: {product.name}\n\nCells:\n{json.dumps(cells, ensure_ascii=False, indent=1)}"),
    ]
    chain = _create_llm(provider, model, base_url).with_structured_output(CellDecodings)

    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            result = chain.invoke(messages)
            if isinstance(result, dict):
                result = CellDecodings.model_validate(result)
            decoded = {c.cell_id: c.benefits for c in result.cells}
            break
        except Exception as e:
            last_error = e
            log.warning("LLM attempt %d/%d for '%s' failed: %s", attempt, ATTEMPTS, product.name, e)
    else:
        raise OilPriceError(f"LLM decoding of '{product.name}' failed: {last_error}")

    out: dict[int, list[Benefit]] = {}
    for c in product.cells:
        original = f"{c.text} ({c.remark})" if c.remark else c.text
        if c.id in decoded:
            out[c.id] = decoded[c.id]
            for b in out[c.id]:
                b.description = b.description or original  # the model is told to leave it empty: saves output
                normalise_benefit(b, c)
        else:  # keep the text rather than lose it
            log.warning("LLM returned nothing for cell %d of '%s'; keeping it as 'other'.", c.id, product.name)
            out[c.id] = [benefit("other", original)]
    return out







