import os
if os.getenv("DEV") is not None:
    import sys
    from pathlib import Path

    p=os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, p)

    secrets_file = Path("env.sec")
    if secrets_file.is_file():
        from py_secrets_xethhung12 import load_secrets

        os.environ.update(load_secrets(file_path=secrets_file, create_if_missing=False))

from oil_price_v2_xethhung12._cmd import run
if __name__ == "__main__":
    raise SystemExit(run.main())