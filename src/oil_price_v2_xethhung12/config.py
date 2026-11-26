"""Defaults shared by the commands. Change them here, or override on the command line."""
from pathlib import Path

DEFAULT_SITE = "https://oil-price.consumer.org.hk"
LANGS = ["tc", "en"]  # languages of the site; the first one is the default of the generated page
DEFAULT_LANG = "all"  # "all" or one of LANGS
TODAY_PATH = "{lang}/today-discount"    # pump prices
WEEKLY_PATH = "{lang}/weekly-discount"  # discounts of the next 7 days

DEFAULT_WORK_DIR = Path("data")  # intermediate files
DEFAULT_DECODED_DIR = Path("decoded")  # decoded JSON files
DEFAULT_OUT_DIR = Path("site")   # published files

TODAY_HTML_NAME = "today.{lang}.html"   # written by `fetch`, read by `decode`
WEEKLY_HTML_NAME = "weekly.{lang}.html" # written by `fetch`, read by `decode`
PRICES_JSON_NAME = "prices.{lang}.json" # written by `decode`, read by `gen-html`
SITE_HTML_NAME = "index.html"    # written by `gen-html`

DEFAULT_DECODER = "llm"          # see interpreters.py for the available names
DEFAULT_FIX_ROUNDS = 3           # times `decode` decodes mismatching products again before giving up

# Environment variables used by the LLM interpreter.
ENV_LLM_PROVIDER = "OIL_PRICE_LLM_PROVIDER"
ENV_LLM_MODEL = "OIL_PRICE_LLM_MODEL"
ENV_LLM_BASE_URL = "OIL_PRICE_LLM_BASE_URL"  # server address, e.g. http://host:11434
ENV_LLM_NUM_CTX = "OIL_PRICE_LLM_NUM_CTX"    # ollama only: context window size

