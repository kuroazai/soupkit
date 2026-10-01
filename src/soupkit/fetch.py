"""Fetching pages, politely and with the rules applied."""
from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from .polite import RateLimiter, RobotsPolicy
from .session import SessionConfig, build_session

#: lxml is faster and more forgiving, but needs a C extension. html.parser is in
#: the standard library and always works, so it is the default.
DEFAULT_PARSER = "html.parser"


class RobotsDisallowed(RuntimeError):
    """robots.txt forbids fetching this URL for our user agent."""


@dataclass
class Fetcher:
    """Fetches pages with retries, rate limiting and robots.txt applied.

        with Fetcher(min_interval=1.0) as fetcher:
            soup = fetcher.soup("https://example.com")
    """

    config: SessionConfig | None = None
    min_interval: float = 1.0
    obey_robots: bool = True
    parser: str = DEFAULT_PARSER

    def __post_init__(self) -> None:
        self.config = self.config or SessionConfig()
        self.session = build_session(self.config)
        self.limiter = RateLimiter(self.min_interval)
        self.robots = RobotsPolicy(self.config.user_agent)

    def get(self, url: str) -> requests.Response:
        """Fetch a URL. Raises on a 4xx/5xx that survived the retries."""
        if self.obey_robots and not self.robots.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        self.limiter.wait()
        assert self.config is not None
        response = self.session.get(url, timeout=self.config.timeout)
        response.raise_for_status()
        return response

    def soup(self, url: str) -> BeautifulSoup:
        """Fetch and parse in one step."""
        return BeautifulSoup(self.get(url).text, self.parser)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def parse_html(markup: str, parser: str = DEFAULT_PARSER) -> BeautifulSoup:
    """Parse markup you already have - a saved page, a test fixture."""
    return BeautifulSoup(markup, parser)
