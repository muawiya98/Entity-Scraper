"""Web search backends.

Returns a list of candidate websites for a query.  Three backends are
supported:

* ``duckduckgo`` - free, no API key (default, via the ``ddgs`` package)
* ``google``     - Google Programmable Search JSON API (needs key + CSE id)
* ``serpapi``    - SerpAPI Google results (needs key)

The public entry point is :func:`search_websites`, which picks the best
available backend and gracefully falls back to DuckDuckGo on failure.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
import requests

from config import config
from core import llm, safety

log = logging.getLogger(__name__)

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    domain: str

    def to_dict(self) -> dict:
        return asdict(self)


def _registered_domain(url: str) -> str:
    return safety.registered_domain(url)


def _should_skip(domain: str) -> bool:
    return safety.is_blocked_domain(domain)


def _build_query(query: str, location: str, entity_type: str) -> str:
    parts = [p.strip() for p in (entity_type, query, location) if p and p.strip()]
    # Avoid duplicating words already present in the free-text query.
    seen, ordered = set(), []
    for part in parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(part)
    return " ".join(ordered)


def _query_variants(query: str, location: str, entity_type: str) -> list[str]:
    """Deterministic backup queries before optional LLM variants."""
    base = _build_query(query, location, entity_type)
    variants = [
        base,
        f"{base} official website",
        f"{base} contact",
        f"{base} about",
    ]

    if entity_type:
        variants.extend(
            [
                f"{query} {entity_type} official website",
                f"{entity_type} {query} contact",
            ]
        )
    if location:
        variants.extend(
            [
                f"{query} {location} official website",
                f"{query} {location} contact",
            ]
        )

    if safety.has_arabic(base):
        variants.extend(
            [
                f"{base} الموقع الرسمي",
                f"{base} اتصل بنا",
                f"{base} تواصل",
                f"{base} من نحن",
            ]
        )
    else:
        variants.extend(
            [
                f"{base} company website",
                f"{base} organization website",
            ]
        )

    clean: list[str] = []
    seen: set[str] = set()
    for item in variants:
        item = " ".join(item.split())
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            clean.append(item)
    return clean


def _dedupe(
    results: list[SearchResult],
    max_results: int,
    query: str = "",
    location: str = "",
    entity_type: str = "",
) -> list[SearchResult]:
    scored: list[tuple[int, SearchResult]] = []
    min_score = safety.minimum_score(query, location, entity_type) if query else 1
    for r in results:
        if not r.domain or _should_skip(r.domain) or safety.is_unsafe_url(r.url):
            continue
        score = safety.relevance_score(
            r.title,
            r.snippet,
            r.domain,
            query=query,
            location=location,
            entity_type=entity_type,
        )
        if score >= min_score:
            scored.append((score, r))

    out, seen = [], set()
    for _, r in sorted(scored, key=lambda item: item[0], reverse=True):
        if r.domain in seen:
            continue
        seen.add(r.domain)
        out.append(r)
        if len(out) >= max_results:
            break
    return out


def _llm_rank(
    results: list[SearchResult],
    query: str,
    location: str,
    entity_type: str,
    max_results: int,
) -> list[SearchResult]:
    if not llm.enabled() or not results:
        return _dedupe(results, max_results, query, location, entity_type)

    by_url = {r.url: r for r in results}
    ranked_urls = llm.rank_search_results(
        [r.to_dict() for r in results],
        query=query,
        location=location,
        entity_type=entity_type,
        max_results=max_results,
    )
    ranked = [by_url[u] for u in ranked_urls if u in by_url]
    leftovers = [r for r in results if r.url not in ranked_urls]
    return _dedupe(ranked + leftovers, max_results, query, location, entity_type)


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
# Arabic-speaking countries, used to guess the ddgs region language suffix.
_ARABIC_COUNTRIES = {
    "SA", "AE", "EG", "QA", "KW", "BH", "OM", "JO", "MA", "DZ", "TN",
    "LY", "YE", "SD", "IQ", "LB", "PS", "SY",
}


def _region_codes(region: str) -> list[str]:
    """Region codes to try, most specific first, always ending worldwide.

    ddgs 9.x uses ISO ``<country>-<lang>`` codes (e.g. ``sa-ar``) and silently
    returns nothing for unknown combinations, so we always fall back to
    ``wt-wt`` (worldwide).
    """
    cc = region.lower()
    lang = "ar" if region in _ARABIC_COUNTRIES else "en"
    codes = [f"{cc}-{lang}"]
    if "wt-wt" not in codes:
        codes.append("wt-wt")
    return codes


def _ddgs_query(query: str, region_code: str, count: int, retries: int = 2) -> list[SearchResult]:
    import time

    from ddgs import DDGS  # imported lazily so the app starts even if absent

    for attempt in range(retries + 1):
        results: list[SearchResult] = []
        try:
            with DDGS() as ddgs:
                items = ddgs.text(
                    query,
                    region=region_code,
                    backend=config.DDGS_BACKEND,
                    max_results=count * 3,
                )
                for item in items:
                    url = item.get("href") or item.get("url") or ""
                    if not url:
                        continue
                    results.append(
                        SearchResult(
                            url=url,
                            title=item.get("title", ""),
                            snippet=item.get("body", "") or item.get("snippet", ""),
                            domain=_registered_domain(url),
                        )
                    )
            if results:
                return results
        except Exception as exc:  # noqa: BLE001 - transient throttling / network
            log.warning("ddgs attempt %s failed (%s): %s", attempt + 1, region_code, exc)
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))  # gentle back-off before retrying
    return []


def _search_duckduckgo(query: str, region: str, count: int) -> list[SearchResult]:
    last: list[SearchResult] = []
    for region_code in _region_codes(region):
        results = _ddgs_query(query, region_code, count)
        print(f"Found {len(results)} results for search {query} ({region_code})")
        # Keep going only if this region produced no usable (non-skipped) hits.
        if any(not _should_skip(r.domain) for r in results):
            return results
        last = results or last
    return last


def _search_google(query: str, count: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    # Google CSE returns max 10 per call; page through up to 30.
    for start in range(1, min(count * 3, 30), 10):
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": config.GOOGLE_API_KEY,
                "cx": config.GOOGLE_CSE_ID,
                "q": query,
                "start": start,
                "num": 10,
            },
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            break
        for item in items:
            url = item.get("link", "")
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    domain=_registered_domain(url),
                )
            )
    return results


def _search_serpapi(query: str, count: int) -> list[SearchResult]:
    resp = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "q": query,
            "num": min(count * 3, 30),
            "api_key": config.SERPAPI_KEY,
        },
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    organic = resp.json().get("organic_results", [])
    return [
        SearchResult(
            url=item.get("link", ""),
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            domain=_registered_domain(item.get("link", "")),
        )
        for item in organic
        if item.get("link")
    ]


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def search_websites(
    query: str,
    location: str = "",
    entity_type: str = "",
    max_results: int = 10,
    region: str | None = None,
) -> list[SearchResult]:
    """Find candidate websites, picking the best available backend."""
    region = (region or config.DEFAULT_REGION).upper()
    backend = config.SEARCH_BACKEND
    available = config.available_backends()

    # Choose an order: requested backend first (if usable), DuckDuckGo last.
    order = []
    if available.get(backend):
        order.append(backend)
    for fallback in ("serpapi", "google", "duckduckgo"):
        if available.get(fallback) and fallback not in order:
            order.append(fallback)
    for fallback in ("duckduckgo",):
        if fallback not in order:
            order.append(fallback)

    last_error: Exception | None = None
    def _run_one(search_query: str) -> list[SearchResult]:
        nonlocal last_error
        raw: list[SearchResult] = []
        for name in order:
            try:
                #log.info("Searching via %s: %s", name, search_query)
                if name == "google":
                    raw.extend(_search_google(search_query, max_results))
                elif name == "serpapi":
                    raw.extend(_search_serpapi(search_query, max_results))
                else:
                    raw.extend(_search_duckduckgo(search_query, region, max_results))
            except Exception as exc:  # noqa: BLE001 - we deliberately fall back
                last_error = exc
                #log.warning("Backend %s failed: %s", name, exc)
        return _llm_rank(raw, query, location, entity_type, max_results)

    collected: list[SearchResult] = []
    seen_domains: set[str] = set()

    def _add(results: list[SearchResult]) -> None:
        for result in results:
            if result.domain in seen_domains:
                continue
            seen_domains.add(result.domain)
            collected.append(result)

    # deterministic_variants = _query_variants(query, location, entity_type)
    # for variant in deterministic_variants:
    #     _add(_run_one(variant))
    #     if len(collected) >= max_results:
    #         return collected[:max_results]
        
    variants_to_try = _query_variants(query, location, entity_type)
    if llm.enabled():
        known_variants = {q.lower() for q in variants_to_try}
        for variant in llm.query_variants(query, location, entity_type):
            if variant.lower() not in known_variants:
                variants_to_try.append(variant)

    for variant in variants_to_try:
        _add(_run_one(variant))
        if len(collected) >= max_results:
            return collected[:max_results]

    if collected:
        return collected[:max_results]

    if last_error:
        log.error("All search backends failed: %s", last_error)
    return []
        

    # if llm.enabled():
    #     known_variants = {q.lower() for q in deterministic_variants}
    #     for variant in llm.query_variants(query, location, entity_type):
    #         if variant.lower() in known_variants:
    #             continue
    #         _add(_run_one(variant))
    #         if len(collected) >= max_results:
    #             return collected[:max_results]

    # if collected:
    #     return collected[:max_results]

    # if last_error:
    #     log.error("All search backends failed: %s", last_error)
    # return []
