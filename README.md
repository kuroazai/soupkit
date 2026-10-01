# soupkit

**A small, polite web-scraping toolkit built on BeautifulSoup.**

Retries with backoff, rate limiting, robots.txt, and extraction helpers that keep
you out of the regex-on-HTML trap.

```python
from soupkit import Fetcher, extract_rows, to_csv

with Fetcher(min_interval=1.0) as fetcher:
    soup = fetcher.soup("https://example.com/listings")

rows = extract_rows(soup, "div.card", {
    "name":  "h3",
    "breed": "span.breed",
    "url":   "a@href",
})
to_csv(rows, "listings.csv")
```

---

## Why this exists

Every scraper starts as twenty lines and ends up re-solving the same four
problems badly:

**Transient failures.** A 503, a slow server, a reset connection. `Fetcher`
retries those with exponential backoff and honours `Retry-After` — which is the
server telling you exactly how long to wait, and ignoring it is how you get
blocked.

**Hammering the site.** `RateLimiter` enforces a minimum gap between requests,
and it is thread-safe, because a thread pool is every scraper's next step and a
limiter that only works single-threaded reads as protection while providing none.

**robots.txt.** Checked once per host and cached. A file that can't be fetched
means *allowed* — a site with no robots.txt hasn't forbidden anything, and
treating an unreachable file as a ban would break on any hiccup.

**Parsing.** This is the big one. The reflex is to run a regular expression over
`str(element)` — parse the page properly, stringify the result, then regex it.
That throws away the parse tree and breaks on any attribute reordering, extra
whitespace or nested tag. `extract_rows` and friends exist so you never need to.

> If you're importing `re` to read HTML, something in `soupkit.extract` is the
> answer.

## Extraction

`extract_rows` pulls records out of repeated markup. `fields` maps output key to
a CSS selector relative to each row; append `@attr` to read an attribute:

```python
extract_rows(soup, "div.card", {
    "name":  "h3",          # text
    "url":   "a@href",      # attribute
    "image": "img@src",
})
```

Missing fields come back as empty strings, so one malformed card doesn't cost you
the rest of the page.

```python
from soupkit import clean_text, text_of, attr_of, links, table_to_records

clean_text("Labrador\n    Retriever")   # "Labrador Retriever"
text_of(card, "span.breed", default="unknown")
attr_of(card, "href", "a")
links(soup)                              # deduplicated, document order
table_to_records(soup.select_one("table"))
```

`table_to_records` keys rows by the header cells and **pads short rows rather
than dropping them** — a missing cell is usually a colspan, and discarding the
row loses real data.

## Fetching

```python
from soupkit import Fetcher, SessionConfig

fetcher = Fetcher(
    config=SessionConfig(user_agent="myscraper/1.0 (+contact@example.com)",
                         timeout=20, retries=5),
    min_interval=2.0,
    obey_robots=True,
)
soup = fetcher.soup("https://example.com")
```

Identify yourself in the user agent. A scraper with a browser's UA and no contact
route is indistinguishable from an attack and gets treated as one.

Already have the markup? Skip the network:

```python
from soupkit import parse_html
soup = parse_html(open("saved.html").read())
```

## Export

```python
from soupkit import to_csv, to_json

to_csv(records, "out/data.csv")     # header is the UNION of all keys
to_json(records, "out/data.json")
```

Taking CSV columns from `records[0]` alone silently truncates every later row
that has a field the first one lacked. `to_csv` takes the union, in first-seen
order.

## Install

```bash
pip install -e .              # beautifulsoup4, requests, urllib3
pip install -e ".[lxml]"      # faster parser
pip install -e ".[dev]"       # pytest, ruff, mypy
```

Python 3.10+.

## Development

```bash
pytest          # 35 tests, no network
ruff check src tests
mypy
```

No test touches the network. Fetching is tested through injected fetchers,
parsing through inline fixtures.

## History

This repo was three loose scraping scripts from 2019–2020 — a dog-adoption
listing scraper, a job-board scraper, and a League of Legends champion list —
collected as "examples of BeautifulSoup uses".

They've been replaced by the reusable half. The scripts targeted sites that have
all changed since, used `find_element_by_id` (removed in Selenium 4), called
`urllib3.disable_warnings()` at import to silence TLS warnings *process-wide*, and
parsed HTML with regex after already having a parse tree. Rebuilding three stale
site scrapers would have produced three scrapers that break again; extracting the
engineering produced something that doesn't.

## Licence

MIT. See [LICENSE](LICENSE).
