# استبدل محتوى ملف llm.py بهذا المحتوى أو أضف الدالة التالية في نهايته:

"""Optional LLM assistance for search, scraping, and extraction."""

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
    except Exception as exc:
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
        "You create concise web search queries whose goal is to extract the PEOPLE behind "
        "an entity — their names, positions/job titles, phone numbers and e-mail addresses. "
        "Target official team, staff, leadership, board and contact pages. "
        'Return JSON only: {"queries": ["..."]}. Prefer official websites over directories.',
        json.dumps(
            {
                "query": query,
                "location": location,
                "entity_type": entity_type,
                "primary_goal": "Find pages containing people's data (staff, team members, management).",
            },
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
        "You rank search results for a scraper whose goal is to extract people's data "
        "(names, positions, phones, e-mails). Strongly prefer pages that list an entity's "
        "people — team, staff, leadership, board, management — together with their contact "
        "details, plus official websites and contact pages for schools, companies, "
        "institutions, universities and academies. "
        "Avoid directories, job boards, social networks, login pages, and generic articles. "
        'Return JSON only: {"urls": ["https://..."]}.',
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
        "staff directories, leadership, team members, and employee emails/phones. "
        "Your top priority is finding 'team' or 'staff' pages. "
        'Return JSON only: {"links": [{"url":"...", "page_type":"contact|about|team|other"}]}',
        json.dumps(
            {
                "base_url": base_url,
                "primary_goal": "Find pages with people/staff profiles.",
                "budget": budget,
                "links": links[:80],
            },
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
    compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    compact = compact[: config.LLM_MAX_PAGE_CHARS]
    if not compact:
        return {}
    data = _json_prompt(
        "You are an elite B2B data extractor. Your ONLY mission is to find DECISION MAKERS and company data STRICTLY within the provided text.\n"
        "CRITICAL RULES:\n"
        "1. DO NOT HALLUCINATE. DO NOT GUESS. If information is not explicitly written in the text, return empty strings or arrays.\n"
        "2. Extract ONLY people with senior roles (CEO, Founder, Director, Manager, Chairman, Partner, etc.).\n"
        "3. Output MUST be valid JSON with keys: name, description, emails, phones, address, city, country, social, and people.\n"
        "4. 'people' is an array of objects: {\"name\": \"...\", \"position\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"profile_url\": \"...\"}.\n",
        json.dumps(
            {
                "url": url,
                "primary_goal": "Find Decision Makers (C-Level, Founders, Directors).",
                "text": compact,
            },
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
        "You are an expert data cleaner. Clean, deduplicate, and normalize this scraped organization record.\n"
        "CRITICAL RULES:\n"
        "1. DO NOT INVENT or HALLUCINATE any new names, emails, phones, or URLs. Only use the data provided in the input.\n"
        "2. Remove completely duplicated people, emails, or phones.\n"
        "3. Standardize job titles if messy, but KEEP original meanings.\n"
        "4. Preserve all Arabic text perfectly.\n"
        "5. If a field is empty, keep it empty. Return JSON with the exact same structure.",
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
        "You validate whether a scraped entity record matches a user's search request. "
        "You MUST ACCEPT any valid official entity (company, institution, school, etc.) that matches the user's query, EVEN IF no staff or people were found during the scrape. "
        "ONLY reject adult, gaming, completely unrelated topics, directories, job boards, social networks, or news articles. "
        'Return JSON only: {"relevant": true|false, "reason": "short explanation"}.',
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


def translate_and_expand_terms(query: str, location: str = "", entity_type: str = "") -> dict:
    """Translate and expand the search parameters to both English and Arabic for cross-lingual matching."""
    if not enabled():
        return {"query": query, "location": location, "entity_type": entity_type}
    
    prompt = (
        "You are a translation and search term expansion assistant.\n"
        "Translate the given search query, location, and entity_type. "
        "If they are in Arabic, translate them to English. If they are in English, translate them to Arabic.\n"
        "Provide both the original and translated terms as comma-separated values.\n"
        "Return JSON only: {\"query_expanded\": \"...\", \"location_expanded\": \"...\", \"entity_type_expanded\": \"...\"}"
    )
    
    user_data = {
        "query": query,
        "location": location,
        "entity_type": entity_type
    }
    
    res = _json_prompt(prompt, json.dumps(user_data, ensure_ascii=False), max_tokens=500)
    if isinstance(res, dict):
        return {
            "query": f"{query}, {res.get('query_expanded', '')}",
            "location": f"{location}, {res.get('location_expanded', '')}",
            "entity_type": f"{entity_type}, {res.get('entity_type_expanded', '')}"
        }
    return {"query": query, "location": location, "entity_type": entity_type}