"""soupkit - a small, polite web-scraping toolkit built on BeautifulSoup.

    from soupkit import Fetcher, extract_rows, to_csv

    with Fetcher(min_interval=1.0) as fetcher:
        soup = fetcher.soup("https://example.com/listings")

    rows = extract_rows(soup, "div.card", {"name": "h3", "url": "a@href"})
    to_csv(rows, "listings.csv")

Retries with backoff, rate limiting, robots.txt, and extraction helpers that keep
you out of the regex-on-HTML trap.
"""
from .export import to_csv, to_json
from .extract import (
    all_text,
    attr_of,
    clean_text,
    extract_rows,
    links,
    table_to_records,
    text_of,
)
from .fetch import DEFAULT_PARSER, Fetcher, RobotsDisallowed, parse_html
from .polite import RateLimiter, RobotsPolicy
from .session import DEFAULT_USER_AGENT, SessionConfig, build_session

__version__ = "0.2.0"

__all__ = [
    "Fetcher", "parse_html", "RobotsDisallowed", "DEFAULT_PARSER",
    "SessionConfig", "build_session", "DEFAULT_USER_AGENT",
    "RateLimiter", "RobotsPolicy",
    "clean_text", "text_of", "attr_of", "all_text", "links",
    "extract_rows", "table_to_records",
    "to_json", "to_csv",
    "__version__",
]
