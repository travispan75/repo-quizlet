from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    load_dotenv(_ENV_PATH)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set in environment or any discoverable .env"
        )
    with psycopg.connect(url) as conn:
        yield conn
