import os
import tempfile
from pathlib import Path

from oil_price_v2.errors import OilPriceError


def read_text(path: Path, created_by: str) -> str:
    """Read a text file, with a helpful error naming the command that creates it."""
    path = Path(path)
    if not path.is_file():
        raise OilPriceError(f"Input file not found: {path} (create it with `oil-price-v2 {created_by}`)")
    return path.read_text(encoding="utf-8")


def write_text_atomic(path: Path, content: str) -> Path:
    """Write via a temp file + rename so a failed run never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, 0o644)  # mkstemp creates 0600; published files must be readable by other users (e.g. nginx)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


