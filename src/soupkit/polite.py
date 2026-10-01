"""Rate limiting and robots.txt.

Neither of these is about the law; they are about not being the reason a small
site falls over, and not getting your IP blocked halfway through a run.
"""
from __future__ import annotations

import threading
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


class RateLimiter:
    """Ensures a minimum gap between calls.

    Thread-safe, because the obvious next step for any scraper is a thread pool,
    and a limiter that only works single-threaded is worse than none - it reads
    as protection while providing none.
    """

    def __init__(self, min_interval: float = 1.0) -> None:
        if min_interval < 0:
            raise ValueError("min_interval cannot be negative")
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> float:
        """Block until the interval has elapsed. Returns how long it slept."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            delay = max(0.0, self.min_interval - elapsed) if self._last else 0.0
            if delay:
                time.sleep(delay)
            self._last = time.monotonic()
            return delay


class RobotsPolicy:
    """Checks robots.txt, caching one parser per host.

    Fetch failures default to *allowed*. A site with no robots.txt has not
    forbidden anything, and treating an unreachable file as a blanket ban would
    make the toolkit stop working whenever a server hiccups.
    """

    def __init__(self, user_agent: str = "*", *, fetcher=None) -> None:
        self.user_agent = user_agent
        self._fetcher = fetcher
        self._cache: dict[str, RobotFileParser | None] = {}

    def _parser_for(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host in self._cache:
            return self._cache[host]

        parser = RobotFileParser()
        robots_url = urljoin(host, "/robots.txt")
        try:
            if self._fetcher is not None:
                parser.parse(self._fetcher(robots_url).splitlines())
            else:
                parser.set_url(robots_url)
                parser.read()
        except Exception:
            self._cache[host] = None
            return None
        self._cache[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._parser_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)
