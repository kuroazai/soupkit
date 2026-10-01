"""Pulling values out of parsed HTML.

Everything here exists because the alternative keeps getting reached for: running
a regular expression over `str(soup_element)`. The original scrapers did exactly
that - parsed the page with BeautifulSoup, stringified the result, then used
`re.findall` on it. That throws away the parse tree and breaks on any attribute
reordering, added whitespace or nested tag.

If you find yourself importing `re` to read HTML, something in here is the answer.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

_WHITESPACE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Collapse whitespace and strip. HTML is full of incidental newlines."""
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip()


def text_of(node: Tag | None, selector: str | None = None, default: str = "") -> str:
    """Cleaned text of a node, or of the first match for `selector` within it."""
    if node is None:
        return default
    target = node.select_one(selector) if selector else node
    if target is None:
        return default
    return clean_text(target.get_text()) or default


def attr_of(
    node: Tag | None, attribute: str, selector: str | None = None, default: str = ""
) -> str:
    """An attribute value, following `selector` first if given."""
    if node is None:
        return default
    target = node.select_one(selector) if selector else node
    if target is None:
        return default
    value = target.get(attribute, default)
    if isinstance(value, list):  # class="a b" comes back as a list
        return " ".join(value)
    return str(value) if value is not None else default


def all_text(nodes: Iterable[Tag]) -> list[str]:
    """Cleaned text for each node, dropping the ones that are empty."""
    return [t for t in (clean_text(n.get_text()) for n in nodes) if t]


def links(soup: BeautifulSoup | Tag, selector: str = "a[href]") -> list[str]:
    """Every href, de-duplicated and in document order."""
    seen: dict[str, None] = {}
    for node in soup.select(selector):
        href = node.get("href")
        if isinstance(href, str) and href:
            seen.setdefault(href, None)
    return list(seen)


def extract_rows(
    soup: BeautifulSoup | Tag, row_selector: str, fields: dict[str, str]
) -> list[dict[str, str]]:
    """Pull a list of records out of repeated markup.

    `fields` maps output key -> CSS selector, relative to each row. A selector may
    end in `@attr` to read an attribute instead of text:

        extract_rows(soup, "div.card", {
            "name":  "h3",
            "breed": "span.breed",
            "url":   "a@href",
        })

    Missing fields come back as empty strings rather than raising, so one
    malformed card does not cost the rest of the page.
    """
    records = []
    for row in soup.select(row_selector):
        record = {}
        for key, selector in fields.items():
            if "@" in selector:
                css, _, attribute = selector.rpartition("@")
                record[key] = attr_of(row, attribute, css or None)
            else:
                record[key] = text_of(row, selector or None)
        records.append(record)
    return records


def table_to_records(table: Tag) -> list[dict[str, str]]:
    """Convert an HTML table into records keyed by its header cells.

    Rows with the wrong number of cells are padded rather than skipped - a
    missing cell is usually a colspan, and dropping the row loses real data.
    """
    headers = [clean_text(th.get_text()) for th in table.select("thead th")]
    if not headers:
        first = table.select_one("tr")
        headers = [clean_text(c.get_text()) for c in first.select("th, td")] if first else []
    if not headers:
        return []

    records = []
    body_rows = table.select("tbody tr") or table.select("tr")[1:]
    for row in body_rows:
        cells = [clean_text(c.get_text()) for c in row.select("td, th")]
        if not cells:
            continue
        cells += [""] * (len(headers) - len(cells))
        # strict=False is the point: cells were padded above and are then
        # truncated to the header count, so a length mismatch is expected
        # and already handled.
        records.append(dict(zip(headers, cells[: len(headers)], strict=False)))
    return records
