"""Bounded public-query continuation data; these cursors confer no authority."""
import base64
import hashlib
import json
import re

from .product_api import fail

PAGE_SIZE = 20
MAX_RECORDS = 1000


def next_cursor(provider, terms, offset, mark=""):
    value = {"provider": provider, "query_hash": hashlib.sha256(terms.encode()).hexdigest(), "offset": offset, "mark": mark}
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def cursor_position(provider, terms, cursor):
    if cursor is None:
        return 0, "*" if provider == "europepmc" else ""
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}", cursor):
            raise ValueError
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if not isinstance(value, dict) or set(value) != {"provider", "query_hash", "offset", "mark"}:
            raise ValueError
        offset, mark = value["offset"], value["mark"]
        if value["provider"] != provider or value["query_hash"] != hashlib.sha256(terms.encode()).hexdigest():
            raise ValueError
        if type(offset) is not int or not 0 < offset < MAX_RECORDS or offset % PAGE_SIZE:
            raise ValueError
        if not isinstance(mark, str) or (provider == "fedlex" and mark) or (provider == "europepmc" and not re.fullmatch(r"[A-Za-z0-9+/=_-]{1,512}", mark)):
            raise ValueError
        return offset, mark
    except (ValueError, TypeError, UnicodeError):
        fail("This page belongs to a different or invalid search. Start the search again.", 422)
