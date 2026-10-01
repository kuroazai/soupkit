"""soupkit. No test touches the network."""
from __future__ import annotations

import csv
import json
import threading
import time

import pytest

from soupkit import (
    RateLimiter,
    RobotsPolicy,
    SessionConfig,
    all_text,
    attr_of,
    build_session,
    clean_text,
    extract_rows,
    links,
    parse_html,
    table_to_records,
    text_of,
    to_csv,
    to_json,
)

LISTING_HTML = """
<html><body>
  <div class="card">
    <h3>  Rex   </h3>
    <span class="breed">Labrador
    Retriever</span>
    <a href="/dogs/rex">more</a>
  </div>
  <div class="card">
    <h3>Bella</h3><span class="breed">Collie</span><a href="/dogs/bella">more</a>
  </div>
  <div class="card"><h3>Ghost</h3></div>
  <a href="/dogs/rex">duplicate link</a>
</body></html>
"""

TABLE_HTML = """
<table>
  <thead><tr><th>Name</th><th>Age</th><th>Breed</th></tr></thead>
  <tbody>
    <tr><td>Rex</td><td>3</td><td>Labrador</td></tr>
    <tr><td>Bella</td><td>5</td></tr>
  </tbody>
</table>
"""


@pytest.fixture
def listing():
    return parse_html(LISTING_HTML)


# -- text cleaning ---------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Rex   ", "Rex"),
        ("Labrador\n    Retriever", "Labrador Retriever"),
        ("a\t\tb", "a b"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_text(raw, expected):
    """HTML is full of incidental newlines and indentation."""
    assert clean_text(raw) == expected


def test_text_of_follows_a_selector(listing):
    card = listing.select_one("div.card")
    assert text_of(card, "h3") == "Rex"


def test_text_of_returns_default_when_absent(listing):
    card = listing.select("div.card")[2]
    assert text_of(card, "span.breed", default="unknown") == "unknown"


def test_text_of_handles_none():
    assert text_of(None, "h3", default="x") == "x"


def test_attr_of_reads_attributes(listing):
    card = listing.select_one("div.card")
    assert attr_of(card, "href", "a") == "/dogs/rex"


def test_attr_of_joins_multi_valued_attributes():
    soup = parse_html('<div class="a b c">x</div>')
    assert attr_of(soup.select_one("div"), "class") == "a b c"


def test_all_text_drops_empties():
    soup = parse_html("<p>one</p><p>  </p><p>two</p>")
    assert all_text(soup.select("p")) == ["one", "two"]


# -- extraction ------------------------------------------------------------
def test_extract_rows_reads_text_and_attributes(listing):
    rows = extract_rows(listing, "div.card",
                        {"name": "h3", "breed": "span.breed", "url": "a@href"})
    assert rows[0] == {"name": "Rex", "breed": "Labrador Retriever", "url": "/dogs/rex"}


def test_extract_rows_returns_one_record_per_match(listing):
    rows = extract_rows(listing, "div.card", {"name": "h3"})
    assert [r["name"] for r in rows] == ["Rex", "Bella", "Ghost"]


def test_a_malformed_row_does_not_cost_the_page(listing):
    """One card missing a field should not abort the extraction."""
    rows = extract_rows(listing, "div.card",
                        {"name": "h3", "breed": "span.breed", "url": "a@href"})
    assert rows[2] == {"name": "Ghost", "breed": "", "url": ""}


def test_extract_rows_on_no_matches_returns_empty(listing):
    assert extract_rows(listing, "div.nonexistent", {"name": "h3"}) == []


def test_links_are_deduplicated_in_document_order(listing):
    assert links(listing) == ["/dogs/rex", "/dogs/bella"]


def test_table_to_records_uses_header_cells():
    records = table_to_records(parse_html(TABLE_HTML).select_one("table"))
    assert records[0] == {"Name": "Rex", "Age": "3", "Breed": "Labrador"}


def test_short_table_rows_are_padded_not_dropped():
    """A missing cell is usually a colspan. Dropping the row loses real data."""
    records = table_to_records(parse_html(TABLE_HTML).select_one("table"))
    assert len(records) == 2
    assert records[1] == {"Name": "Bella", "Age": "5", "Breed": ""}


def test_table_without_thead_uses_the_first_row():
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    records = table_to_records(parse_html(html).select_one("table"))
    assert records == [{"A": "1", "B": "2"}]


def test_table_with_no_headers_returns_empty():
    html = "<table></table>"
    assert table_to_records(parse_html(html).select_one("table")) == []


# -- export ----------------------------------------------------------------
def test_to_json_roundtrips(tmp_path):
    records = [{"name": "Rex"}, {"name": "Bella"}]
    path = to_json(records, tmp_path / "out" / "dogs.json")
    assert json.loads(path.read_text(encoding="utf-8")) == records


def test_to_csv_header_is_the_union_of_all_keys(tmp_path):
    """Taking columns from records[0] alone silently truncates every later row
    that has a field the first one lacked."""
    records = [{"name": "Rex"}, {"name": "Bella", "breed": "Collie"}]
    path = to_csv(records, tmp_path / "dogs.csv")

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert set(rows[0]) == {"name", "breed"}
    assert rows[1]["breed"] == "Collie"


def test_to_csv_creates_parent_directories(tmp_path):
    path = to_csv([{"a": "1"}], tmp_path / "deep" / "nested" / "out.csv")
    assert path.exists()


def test_exports_handle_empty_input(tmp_path):
    assert json.loads(to_json([], tmp_path / "e.json").read_text(encoding="utf-8")) == []
    assert to_csv([], tmp_path / "e.csv").exists()


# -- politeness ------------------------------------------------------------
def test_rate_limiter_enforces_a_gap():
    limiter = RateLimiter(min_interval=0.05)
    limiter.wait()  # first call is free
    start = time.monotonic()
    limiter.wait()
    assert time.monotonic() - start >= 0.04


def test_first_call_is_not_delayed():
    assert RateLimiter(min_interval=5.0).wait() == 0.0


def test_rate_limiter_is_thread_safe():
    """A limiter that only works single-threaded reads as protection while
    providing none - and a thread pool is every scraper's next step."""
    limiter = RateLimiter(min_interval=0.02)
    timestamps: list[float] = []
    lock = threading.Lock()

    def worker():
        limiter.wait()
        with lock:
            timestamps.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    timestamps.sort()
    # Pairwise over consecutive items: the two sequences differ in length by
    # one by construction.
    gaps = [b - a for a, b in zip(timestamps, timestamps[1:], strict=False)]
    assert all(g >= 0.015 for g in gaps), f"calls overlapped: {gaps}"


def test_negative_interval_is_rejected():
    with pytest.raises(ValueError):
        RateLimiter(min_interval=-1)


def test_robots_blocks_a_disallowed_path():
    policy = RobotsPolicy("soupkit", fetcher=lambda _: "User-agent: *\nDisallow: /private")
    assert policy.allowed("https://example.com/public") is True
    assert policy.allowed("https://example.com/private/page") is False


def test_robots_allows_when_the_file_cannot_be_fetched():
    """A site with no robots.txt has not forbidden anything. Treating an
    unreachable file as a ban would break on any server hiccup."""
    def boom(_url):
        raise OSError("unreachable")

    assert RobotsPolicy("soupkit", fetcher=boom).allowed("https://example.com/x") is True


def test_robots_is_cached_per_host():
    calls: list[str] = []

    def counting_fetcher(url):
        calls.append(url)
        return "User-agent: *\nDisallow:"

    policy = RobotsPolicy("soupkit", fetcher=counting_fetcher)
    policy.allowed("https://example.com/a")
    policy.allowed("https://example.com/b")
    policy.allowed("https://other.com/a")
    assert len(calls) == 2, "one fetch per host, not per URL"


# -- session ---------------------------------------------------------------
def test_session_sends_an_identifying_user_agent():
    session = build_session()
    assert "soupkit" in session.headers["User-Agent"]


def test_session_retries_are_mounted():
    session = build_session(SessionConfig(retries=5))
    adapter = session.get_adapter("https://example.com")
    assert adapter.max_retries.total == 5
    assert 503 in adapter.max_retries.status_forcelist


def test_session_respects_retry_after():
    """Retry-After is the server saying exactly how long to wait. Ignoring it is
    how a scraper gets banned."""
    adapter = build_session().get_adapter("https://example.com")
    assert adapter.max_retries.respect_retry_after_header is True


def test_custom_headers_are_merged():
    session = build_session(SessionConfig(headers={"Accept-Language": "en-GB"}))
    assert session.headers["Accept-Language"] == "en-GB"
    assert "soupkit" in session.headers["User-Agent"]
