from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from config import SETTINGS


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(SETTINGS.database_url, row_factory=dict_row) as conn:
        yield conn
