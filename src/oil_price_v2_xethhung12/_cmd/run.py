import argparse
import logging
import sys
from pathlib import Path

import oil_price_v2_xethhung12 as project
from oil_price_v2_xethhung12 import config
from oil_price_v2_xethhung12.errors import OilPriceError
from oil_price_v2_xethhung12.interpreters import INTERPRETERS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oil-price-v2", description="Hong Kong oil price and discount information.")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    def common(p, *, site=False, decode=False, out_dir=False):
        p.add_argument("--work-dir", type=Path, default=config.DEFAULT_WORK_DIR, help="directory of intermediate files (default: %(default)s)")
        if site:
            p.add_argument("--site", default=config.DEFAULT_SITE, help="website address (default: %(default)s)")
            p.add_argument("--lang", choices=["all", *config.LANGS], default=config.DEFAULT_LANG, help="site language(s) to fetch and decode (default: %(default)s)")
        if decode:
            p.add_argument("--decoder", choices=list(INTERPRETERS), default=config.DEFAULT_DECODER, help="how to read the cell texts (default: %(default)s)")
            p.add_argument("--provider", help=f"LLM provider, e.g. ollama or openai (default: ${config.ENV_LLM_PROVIDER})")
            p.add_argument("--model", help=f"LLM model name (default: ${config.ENV_LLM_MODEL})")
            p.add_argument("--base-url", help=f"LLM server address, e.g. http://host:11434 (default: ${config.ENV_LLM_BASE_URL}, else the provider default)")
            p.add_argument("--prompt-file", type=Path, help="custom prompt text file for the llm decoder")
            p.add_argument("--no-verify", action="store_true", help="do not compare the languages after decoding")
            p.add_argument("--fix-rounds", type=int, default=config.DEFAULT_FIX_ROUNDS, help="times to decode mismatching products again (default: %(default)s)")
        if decode or out_dir:
            p.add_argument("--decoded-dir", type=Path, default=config.DEFAULT_DECODED_DIR, help="directory of decoded JSON files (default: %(default)s)")
        if out_dir:
            p.add_argument("--out-dir", type=Path, default=config.DEFAULT_OUT_DIR, help="directory of the generated site (default: %(default)s)")

    p = commands.add_parser("refresh", help="fetch + decode + gen-html")
    common(p, site=True, decode=True, out_dir=True)
    p.set_defaults(func=_refresh)

    p = commands.add_parser("fetch", help="download the today and weekly pages of each language into <work-dir>")
    common(p, site=True)
    p.set_defaults(func=_fetch)

    p = commands.add_parser("decode", help="decode the HTML files into one JSON file per language in <work-dir>")
    common(p, site=True, decode=True)
    p.add_argument("--output", type=Path, help="JSON file to write (only with a single --lang; default: <decoded-dir>/prices.<lang>.json)")
    p.set_defaults(func=_decode)

    p = commands.add_parser("gen-html", help="generate the HTML page from the JSON file")
    common(p, out_dir=True)
    p.add_argument("--input", type=Path, nargs="+", help="JSON file(s) to read, one per language (default: every <decoded-dir>/prices.<lang>.json)")
    p.add_argument("--output", type=Path, help=f"HTML file to write (default: <out-dir>/{config.SITE_HTML_NAME})")
    p.set_defaults(func=_gen_html)
    p = commands.add_parser("gen-dockerfile", help="write a Dockerfile (and .dockerignore) that hosts the page with nginx")
    p.add_argument("--output", default="Dockerfile", help="file to write, or - for stdout (default: %(default)s)")
    p.add_argument("--build-site", action="store_true", help="generate the page while building the image (needs network) instead of copying ./site")
    p.add_argument("--python-version", default="3.12", help="Python version of the build stage, with --build-site (default: %(default)s)")
    p.add_argument("--port", type=int, default=8080, help="port nginx listens on (default: %(default)s)")
    p.add_argument("--force", action="store_true", help="replace an existing Dockerfile")
    p.set_defaults(func=_gen_dockerfile)
    return parser


def _decoder_options(a) -> dict:
    return dict(provider=a.provider, model=a.model, base_url=a.base_url, prompt_file=a.prompt_file)


def _fetch(a):
    return ", ".join(str(p) for p in project.fetch(site=a.site, lang=a.lang, work_dir=a.work_dir))


def _decode(a):
    return ", ".join(str(p) for p in project.decode(work_dir=a.work_dir, output=a.output, site=a.site, lang=a.lang, decoder=a.decoder, decoded_dir=a.decoded_dir, verify=not a.no_verify, fix_rounds=a.fix_rounds, **_decoder_options(a)))


def _gen_html(a):
    return project.gen_html(inputs=a.input, output=a.output, out_dir=a.out_dir, decoded_dir=a.decoded_dir)


def _gen_dockerfile(a):
    result = project.gen_dockerfile(output=Path(a.output), build_site=a.build_site, python_version=a.python_version, port=a.port, force=a.force)
    if a.output == "-":
        print(result, end="")
        return None  # the Dockerfile itself was the output
    return result
def _refresh(a):
    return project.refresh(site=a.site, lang=a.lang, work_dir=a.work_dir, out_dir=a.out_dir, decoder=a.decoder, decoded_dir=a.decoded_dir, verify=not a.no_verify, fix_rounds=a.fix_rounds, **_decoder_options(a))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = args.func(args)
    except OilPriceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if result is not None:
        print(f"done: {result}")
    return 0







