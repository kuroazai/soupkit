# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this is

`soupkit` is a small toolkit for scraping HTML politely: an HTTP session that
retries, a rate limiter, a robots.txt policy, and extraction helpers.

**It is a toolkit, not a scraper.** There are no site-specific scrapers here and
there should not be. Selectors for a particular site rot within months; the repo
that holds them becomes a graveyard. Build site scrapers on top, elsewhere.

## The rule that matters most

> **Never parse HTML with a regular expression.**

The scripts this repo replaced did exactly that: parsed a page with
BeautifulSoup, called `str()` on the result, then ran `re.findall` over it. That
discards the parse tree and breaks on attribute reordering, extra whitespace, or
a nested tag.

`soupkit.extract` exists so there is always a better option. If you reach for
`import re` to read markup, add the helper instead.

(`re` for *whitespace* cleaning in `clean_text` is fine — that operates on
extracted text, not on markup.)

## Layout

```
src/soupkit/
├── session.py   requests Session: retries, backoff, honest user-agent
├── polite.py    RateLimiter (thread-safe), RobotsPolicy (cached per host)
├── fetch.py     Fetcher - ties the above together; parse_html for local markup
├── extract.py   clean_text, text_of, attr_of, links, extract_rows, table_to_records
└── export.py    to_csv, to_json
```

## Rules

### Be identifiable and be slow.

Default user agent names the project and links to it. Default `min_interval` is
1 second. Do not lower either default, and do not add a browser-impersonating UA
— a scraper that looks like a browser and has no contact route gets treated as an
attack.

### Failures degrade, they do not abort.

- robots.txt unreachable → **allowed**. No robots.txt means nothing forbidden.
- A field missing from a row → empty string, not an exception. One malformed card
  must not cost the page.
- A short table row → padded, not dropped. It is usually a colspan.

Each of these has a test. They encode a judgement about which failure is worse,
so read the reasoning before changing one.

### Rate limiting must stay thread-safe.

`RateLimiter` holds a lock. A thread pool is every scraper's next step, and a
limiter that silently stops working under concurrency is worse than no limiter,
because it looks like protection. `test_rate_limiter_is_thread_safe` guards this.

### Never disable TLS warnings.

The originals called `urllib3.disable_warnings()` at module scope, which silences
verification warnings for the whole process, including libraries with nothing to
do with the scrape. If a certificate is a problem, fix the certificate.

### Export writes the union of keys.

`to_csv` collects fieldnames across every record. Taking them from `records[0]`
silently truncates later rows that gained a field.

## Adding an extraction helper

Put it in `extract.py`, give it a `default` rather than letting it raise, and
test it against markup that is *slightly wrong* — missing elements, extra
whitespace, a nested tag. Clean markup proves very little.

## Testing

```bash
pytest          # 35 tests, under a second, no network
```

**No test may touch the network.** `RobotsPolicy` takes a `fetcher` callable
precisely so it can be tested with a string. Parsing is tested against inline
fixture HTML. If a change needs a live request to verify, the design is wrong.

## Things not to do

- Don't add site-specific scrapers.
- Don't parse HTML with regex.
- Don't call `urllib3.disable_warnings()`.
- Don't make `lxml` a hard dependency — it needs a C extension; `html.parser` is
  stdlib and always available.
- Don't commit scraped output or credentials. `.gitignore` covers `*.csv`,
  `*.json`, `data.json` and `.env`.
