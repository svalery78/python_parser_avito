from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on sys.path when running as a script
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.parser import Parser


def main() -> None:
    load_dotenv()

    url = os.getenv("TARGET_URL")
    if not url:
        raise SystemExit("TARGET_URL is not set in .env")

    base_url = os.getenv("BASE_URL")
    use_playwright = os.getenv("USE_PLAYWRIGHT", "0").lower() in {"1", "true", "yes"}

    parser = Parser(base_url=base_url, use_playwright=use_playwright)
    parser.parse_and_output(url)


if __name__ == "__main__":
    main()

