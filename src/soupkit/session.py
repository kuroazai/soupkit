"""An HTTP session that behaves itself.

Scrapers fail in boring, predictable ways: a transient 503, a server that is slow
once, a connection reset. Retrying those with backoff is the difference between a
script you babysit and one you can leave running.

The original used a bare `urllib3.PoolManager()` with `disable_warnings()` at
module scope, which silences TLS verification warnings globally - for the whole
process, including libraries that had nothing to do with the scrape.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

#: Identify yourself. A scraper with a browser's user-agent and no contact route
#: is indistinguishable from an attack, and gets blocked like one.
DEFAULT_USER_AGENT = "soupkit/0.2 (+https://github.com/kuroazai/soupkit)"

#: Codes worth retrying: the server is busy or briefly broken, not refusing.
RETRY_STATUSES = (429, 500, 502, 503, 504)


@dataclass
class SessionConfig:
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 15.0
    retries: int = 3
    backoff_factor: float = 0.5
    headers: dict[str, str] = field(default_factory=dict)


def build_session(config: SessionConfig | None = None) -> requests.Session:
    """A requests Session with retries, backoff and an honest user-agent.

    Retries apply to connection errors and the statuses above, with exponential
    backoff. `Retry` also honours a `Retry-After` header, which is the server
    telling you exactly how long to wait - ignoring it is how you get banned.
    """
    cfg = config or SessionConfig()
    session = requests.Session()
    session.headers.update({"User-Agent": cfg.user_agent, **cfg.headers})

    retry = Retry(
        total=cfg.retries,
        backoff_factor=cfg.backoff_factor,
        status_forcelist=list(RETRY_STATUSES),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
