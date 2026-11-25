"""High-level operations. One function per command; each reads and writes plain files.

The command line (`_cmd/run.py`) only parses arguments and calls these functions,
so they can also be used from Python or tests.

Most functions take `lang`: "all" (every language in `config.LANGS`) or one of them.
Files are per language, e.g. `weekly.tc.html`, `prices.tc.json`.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from oil_price_v2_xethhung12 import config
from oil_price_v2_xethhung12.decoder import build_report
from oil_price_v2_xethhung12.dockerfile import gen_dockerfile  # noqa: F401  (a command of its own, see dockerfile.py)
from oil_price_v2_xethhung12.errors import OilPriceError
from oil_price_v2_xethhung12.fetcher import fetch_html
from oil_price_v2_xethhung12.files import read_text, write_text_atomic
from oil_price_v2_xethhung12.models import PriceReport
from oil_price_v2_xethhung12.renderer import render

log = logging.getLogger(__name__)


def _langs(lang: str) -> list[str]:
    if lang == "all":
        return list(config.LANGS)
    if lang not in config.LANGS:
        raise OilPriceError(f"Unknown language '{lang}'. Available: all, {', '.join(config.LANGS)}")
    return [lang]


def _weekly_url(site: str, lang: str) -> str:
    return f"{site.rstrip('/')}/{config.WEEKLY_PATH.format(lang=lang)}"


def _today_url(site: str, lang: str) -> str:
    return f"{site.rstrip('/')}/{config.TODAY_PATH.format(lang=lang)}"


def fetch(site: str = config.DEFAULT_SITE, lang: str = config.DEFAULT_LANG, work_dir: Path = config.DEFAULT_WORK_DIR) -> list[Path]:
    """Download the today and weekly pages of each language into HTML files."""
    work_dir = Path(work_dir)
    written: list[Path] = []
    for lg in _langs(lang):
        for url, name in [
            (_today_url(site, lg), config.TODAY_HTML_NAME.format(lang=lg)),
            (_weekly_url(site, lg), config.WEEKLY_HTML_NAME.format(lang=lg)),
        ]:
            if written:
                time.sleep(1)  # be polite to the server
            html = fetch_html(url)
            written.append(write_text_atomic(work_dir / name, html))
            log.info("Fetched %s (%d characters)", url, len(html))
    return written


def decode(
    work_dir: Path = config.DEFAULT_WORK_DIR,
    output: Path | None = None,
    site: str = config.DEFAULT_SITE,
    lang: str = config.DEFAULT_LANG,
    decoder: str = config.DEFAULT_DECODER,
    decoded_dir: Path = config.DEFAULT_DECODED_DIR,
    **decoder_options,
) -> list[Path]:
    """Decode the HTML files into one structured JSON file per language.

    decoder_options (provider, model, base_url, prompt_file) are passed to the LLM decoder.
    `output` can only be used with a single language.
    """
    work_dir = Path(work_dir)
    langs = _langs(lang)
    if output and len(langs) > 1:
        raise OilPriceError("--output can only be used with a single --lang.")

    written: list[Path] = []
    for lg in langs:
        weekly_path = work_dir / config.WEEKLY_HTML_NAME.format(lang=lg)
        weekly_html = read_text(weekly_path, created_by="fetch")
        today_html = read_text(work_dir / config.TODAY_HTML_NAME.format(lang=lg), created_by="fetch")
        report = build_report(
            weekly_html=weekly_html,
            today_html=today_html,
            fetched_at=datetime.fromtimestamp(weekly_path.stat().st_mtime).astimezone(),
            source_url=_weekly_url(site, lg),
            decoder=decoder,
            lang=lg,
            **decoder_options,
        )
        target = Path(output) if output else Path(decoded_dir) / config.PRICES_JSON_NAME.format(lang=lg)
        written.append(write_text_atomic(target, report.model_dump_json(indent=2) + "\n"))
        log.info("[%s] Decoded %d products, %d records", lg, len(report.products), sum(len(p.discounts) for p in report.products))
    return written


def gen_html(
    inputs: list[Path] | None = None,
    out_dir: Path = config.DEFAULT_OUT_DIR,
    decoded_dir: Path = config.DEFAULT_DECODED_DIR,
    output: Path | None = None,
) -> Path:
    """Render the JSON files into one self-contained HTML page that can switch language.

    Without `inputs`, every `prices.<lang>.json` found in the decoded directory is used.
    The page opens in the first language (`config.LANGS[0]`, Chinese) of those found.
    """
    if not inputs:
        inputs = [Path(decoded_dir) / config.PRICES_JSON_NAME.format(lang=lg) for lg in config.LANGS]
        inputs = [p for p in inputs if p.is_file()]
        if not inputs:
            raise OilPriceError(f"No price files in {decoded_dir} (create them with `oil-price-v2 decode`)")
    output = Path(output) if output else Path(out_dir) / config.SITE_HTML_NAME

    reports: list[PriceReport] = []
    for path in inputs:
        try:
            reports.append(PriceReport.model_validate(json.loads(read_text(Path(path), created_by="decode"))))
        except ValueError as e:  # bad JSON or schema mismatch
            raise OilPriceError(f"{path} is not a valid price file: {e}") from e
    reports.sort(key=lambda r: config.LANGS.index(r.lang) if r.lang in config.LANGS else len(config.LANGS))

    write_text_atomic(output, render(reports))
    return output


def refresh(
    site: str = config.DEFAULT_SITE,
    lang: str = config.DEFAULT_LANG,
    work_dir: Path = config.DEFAULT_WORK_DIR,
    out_dir: Path = config.DEFAULT_OUT_DIR,
    decoder: str = config.DEFAULT_DECODER,
    decoded_dir: Path = config.DEFAULT_DECODED_DIR,
    **decoder_options,
) -> Path:
    """fetch + decode + gen-html. Stops at the first failure."""
    fetch(site=site, lang=lang, work_dir=work_dir)
    prices = decode(work_dir=work_dir, site=site, lang=lang, decoder=decoder, decoded_dir=decoded_dir, **decoder_options)
    return gen_html(inputs=prices, out_dir=out_dir)










