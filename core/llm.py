"""Optional LLM assistance for search, scraping, and extraction.

The deterministic pipeline remains the source of truth.  These helpers only run
when an API key is configured, and each function is written as a safe fallback:
if the model call fails or returns invalid JSON, the caller keeps its core
result.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from config import config

log = logging.getLogger(__name__)

JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.S)


def enabled() -> bool:
    return config.LLM_ENABLED and bool(config.LLM_API_KEY)


def status() -> dict[str, Any]:
    return {
        "enabled": enabled(),
        "provider": config.LLM_PROVIDER,
        "model": config.LLM_MODEL,
    }


def _json_prompt(system: str, user: str, *, max_tokens: int = 1200) -> Any | None:
    if not enabled():
        return None

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            config.LLM_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=config.LLM_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _loads_json(content)
    except Exception as exc:  # noqa: BLE001 - optional best-effort layer
        log.warning("LLM call failed: %s", exc)
        return None


def _loads_json(content: str) -> Any | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = JSON_RE.search(content or "")
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def query_variants(query: str, location: str = "", entity_type: str = "") -> list[str]:
    """Generate backup search queries when the normal search returns too little."""
    data = _json_prompt(
        "You create concise web search queries for finding official entity websites. "
        "Return JSON only: {\"queries\": [\"...\"]}. Prefer official websites over directories.",
        json.dumps(
            {"query": query, "location": location, "entity_type": entity_type},
            ensure_ascii=False,
        ),
        max_tokens=500,
    )
    queries = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(queries, list):
        return []
    cleaned: list[str] = []
    for q in queries[:5]:
        if isinstance(q, str) and q.strip() and q.strip() not in cleaned:
            cleaned.append(q.strip())
    return cleaned


def rank_search_results(
    results: list[dict],
    query: str,
    location: str = "",
    entity_type: str = "",
    max_results: int = 10,
) -> list[str]:
    """Return result URLs in preferred order, filtering likely directories/noise."""
    data = _json_prompt(
        "You rank search results for an entity data scraper. Keep official websites, "
        "schools, companies, institutions, universities, academies, and useful contact pages. "
        "Avoid directories, job boards, social networks, login pages, and generic articles. "
        "Return JSON only: {\"urls\": [\"https://...\"]}.",
        json.dumps(
            {
                "query": query,
                "location": location,
                "entity_type": entity_type,
                "max_results": max_results,
                "results": results[: min(len(results), 30)],
            },
            ensure_ascii=False,
        ),
        max_tokens=900,
    )
    urls = data.get("urls") if isinstance(data, dict) else None
    if not isinstance(urls, list):
        return []
    return [u.strip() for u in urls if isinstance(u, str) and u.strip()]


def select_relevant_links(base_url: str, links: list[dict], budget: int) -> list[dict]:
    """Select contact/about/team links when keyword matching missed or under-filled."""
    if not links or budget <= 0:
        return []
    data = _json_prompt(
        "You select internal pages likely to contain organization contact details, "
        "staff, leadership, team members, addresses, phones, or emails. "
        "Return JSON only: {\"links\": [{\"url\":\"...\", \"page_type\":\"contact|about|team|other\"}]}",
        json.dumps(
            {"base_url": base_url, "budget": budget, "links": links[:80]},
            ensure_ascii=False,
        ),
        max_tokens=1000,
    )
    selected = data.get("links") if isinstance(data, dict) else None
    if not isinstance(selected, list):
        return []
    out: list[dict] = []
    for item in selected[:budget]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        page_type = str(item.get("page_type") or "other").strip().lower()
        if url:
            out.append({"url": url, "page_type": page_type})
    return out


def extract_from_page_text(text: str, url: str, existing: dict | None = None) -> dict:
    """Backup extraction from visible page text."""
    compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    compact = compact[: config.LLM_MAX_PAGE_CHARS]
    if not compact:
        return {}
    data = _json_prompt(
        "Extract organization data from webpage text. Use only facts present in the text. "
        "Return JSON only with keys: name, description, emails, phones, address, city, country, "
        "social, people. people is an array of {name, position, email, phone, profile_url}. "
        "Use empty strings/arrays/objects when unknown.",
        json.dumps(
            {"url": url, "existing": existing or {}, "text": compact},
            ensure_ascii=False,
        ),
        max_tokens=1600,
    )
    return data if isinstance(data, dict) else {}


def enhance_entity_record(record: dict) -> dict:
    """Normalize/complete a merged entity record after deterministic extraction."""
    summary = dict(record)
    summary.pop("pages", None)
    data = _json_prompt(
        "Clean and normalize this scraped organization record without inventing facts. "
        "Prefer official names, remove duplicate contacts, normalize people positions, and keep Arabic text. "
        "Return JSON only using the same keys supplied.",
        json.dumps(summary, ensure_ascii=False),
        max_tokens=1600,
    )
    return data if isinstance(data, dict) else {}


def validate_entity_record(
    record: dict,
    query: str,
    location: str = "",
    entity_type: str = "",
) -> dict:
    """Optional semantic check that a scraped record satisfies the user request."""
    summary = dict(record)
    summary.pop("pages", None)
    data = _json_prompt(
        "You validate whether a scraped organization/entity record matches a user's search request. "
        "Accept companies, establishments, schools, institutions, universities, academies, or other entities "
        "only when they are relevant to the requested category/location/topic. Reject adult, gaming, unrelated, "
        "directory-only, job-board, social-network, or article results. Do not require every contact field to be present. "
        "Return JSON only: {\"relevant\": true|false, \"reason\": \"short explanation\"}.",
        json.dumps(
            {
                "query": query,
                "location": location,
                "entity_type": entity_type,
                "record": summary,
            },
            ensure_ascii=False,
        ),
        max_tokens=500,
    )
    return data if isinstance(data, dict) else {}
