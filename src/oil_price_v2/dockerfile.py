"""`gen-dockerfile`: write a Dockerfile (and a .dockerignore) that hosts the generated page with nginx."""
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from oil_price_v2 import config
from oil_price_v2.errors import OilPriceError

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "Dockerfile.j2"

_IGNORE_COMMON = """\
.git
.idea
.venv
**/__pycache__
dist
data
x
env.sec
vault.kv
Dockerfile
"""


def render_dockerfile(build_site: bool, python_version: str, port: int) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=True,   # a line with only a {% %} tag leaves no empty line
        lstrip_blocks=True,
    )
    return env.get_template(TEMPLATE_NAME).render(build_site=build_site, python_version=python_version, port=port)


def gen_dockerfile(
    output: Path | None = Path("Dockerfile"),
    build_site: bool = False,
    python_version: str = "3.12",
    port: int = 8080,
    force: bool = False,
) -> str:
    """Write the Dockerfile to `output` ("-" or None = return the text) and return where it went.

    build_site=False: the image is nginx plus the existing `site/` directory.
    build_site=True: the image first runs `oil-price-v2 refresh` in a Python stage, then serves the result.
    A `.dockerignore` is written next to the Dockerfile unless one exists. An existing Dockerfile is
    only replaced with `force`.
    """
    text = render_dockerfile(build_site, python_version, port)
    if output is None or str(output) == "-":
        return text

    output = Path(output)
    if output.exists() and not force:
        raise OilPriceError(f"{output} already exists; use --force to replace it.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")

    ignore = output.parent / ".dockerignore"
    if not ignore.exists():
        # `site` is needed in the image only when it is copied in; otherwise it is built inside.
        ignore.write_text(_IGNORE_COMMON + ("site\n" if build_site else ""), encoding="utf-8")

    if not build_site and not (output.parent / config.DEFAULT_OUT_DIR / config.SITE_HTML_NAME).is_file():
        log.warning("%s/%s does not exist yet: run `oil-price-v2 refresh` before `docker build`.", config.DEFAULT_OUT_DIR, config.SITE_HTML_NAME)
    return str(output)

