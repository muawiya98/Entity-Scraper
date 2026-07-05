"""Safety and generic relevance filters shared by search and scraping."""

from __future__ import annotations

import re
from urllib.parse import urlparse

AR_RE = re.compile(r"[\u0600-\u06ff]")
TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)


BLOCKED_DOMAIN_LABELS = {
    "yellowpages",
    "daleel",
    "zoominfo",
    "zawya",
    "mubasher",
    "argaam",
    "dubaicitycompany",
    "propertyfinder",
    "bayut",
    "dubizzle",
    "edarabia",
    "gulftalent",
    "facebook",
    "twitter",
    "x",
    "instagram",
    "linkedin",
    "youtube",
    "youtu",
    "tiktok",
    "pinterest",
    "snapchat",
    "telegram",
    "whatsapp",
    "wa",
    "t",
    "google",
    "bing",
    "yahoo",
    "duckduckgo",
    "baidu",
    "yandex",
    "wikipedia",
    "wikimedia",
    "wikidata",
    "fandom",
    "merriam-webster",
    "yelp",
    "tripadvisor",
    "foursquare",
    "booking",
    "agoda",
    "trivago",
    "amazon",
    "ebay",
    "aliexpress",
    "noon",
    "indeed",
    "glassdoor",
    "bayt",
    "naukrigulf",
    "f6s",
    "crunchbase",
    "bloomberg",
    "reuters",
    "forbes",
    "reddit",
    "medium",
    "quora",
    "blogspot",
    "wordpress",
    "tumblr",
    "github",
    "gitlab",
    "stackoverflow",
    "play",
    "apps",
    "appstore",
    "microsoft",
    "apple",
    "maps",
    "goo",
    "office",
    "outlook",
    "onedrive",
    "live",
    "msn",
    "hotmail",
    "gmail",
    "sharepoint",
    "microsoftonline",
    "skype",
    "bingplaces",
    "lol",
    "leagueoflegends",
    "liquipedia",
    "wegame",
    "xvideos",
    "pornhub",
    "xnxx",
    "xhamster",
    "redtube",
    "youporn",
    "onlyfans",
    "chaturbate",
    "brazzers",
    "spankbang",
    "xhamsterlive",
}

BLOCKED_URL_TERMS = {
    "porn",
    "xxx",
    "sex",
    "adult",
    "escort",
    "casino",
    "betting",
    "gambling",
    "leagueoflegends",
    "liquipedia",
    "/lol",
    "xvideos",
}

NOISE_TERMS = {
    "wiki",
    "wikipedia",
    "news",
    "article",
    "forum",
    "thread",
    "login",
    "sign in",
    "signin",
    "job",
    "jobs",
    "careers",
    "download",
    "definition",
    "dictionary",
    "video",
    "image",
    "images",
    "map",
    "maps",
}

OFFICIAL_HINTS = {
    "official",
    "website",
    "homepage",
    "contact",
    "about",
    "اتصل",
    "تواصل",
    "الموقع",
    "الرسمي",
    "من نحن",
    "عن",
}

ENTITY_HINTS = {
    "company",
    "companies",
    "firm",
    "firms",
    "business",
    "institution",
    "organization",
    "organisation",
    "school",
    "academy",
    "university",
    "college",
    "hospital",
    "clinic",
    "agency",
    "office",
    "center",
    "centre",
    "association",
    "foundation",
    "group",
    "developer",
    "manufacturer",
    "supplier",
    "distributor",
    "contractor",
    "consultant",
    "consulting",
    "شركة",
    "شركات",
    "مؤسسة",
    "مؤسسات",
    "منشأة",
    "منشآت",
    "مدرسة",
    "مدارس",
    "أكاديمية",
    "اكاديمية",
    "جامعة",
    "جامعات",
    "كلية",
    "مستشفى",
    "عيادة",
    "وكالة",
    "مكتب",
    "مركز",
    "جمعية",
    "مجموعة",
    "مصنع",
    "مورد",
    "مقاول",
    "استشارات",
    "استشارية",
}


PEOPLE_HINTS = {
    "team",
    "our team",
    "staff",
    "people",
    "leadership",
    "management",
    "board",
    "directors",
    "director",
    "employees",
    "employee",
    "members",
    "member",
    "founder",
    "founders",
    "officers",
    "executives",
    "executive",
    "personnel",
    "who we are",
    "meet the team",
    "contact",
    "فريق",
    "الفريق",
    "فريقنا",
    "طاقم",
    "الكادر",
    "كادر",
    "موظفون",
    "موظفين",
    "الموظفين",
    "الإدارة",
    "ادارة",
    "إدارة",
    "مجلس الإدارة",
    "مجلس",
    "أعضاء",
    "اعضاء",
    "عضو",
    "القيادة",
    "هيئة",
    "الهيئة",
    "من نحن",
    "تواصل",
    "اتصل",
}

EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "near",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "about",
    "best",
    "top",
    "list",
    "lists",
    "directory",
    "directories",
    "official",
    "website",
    "websites",
    "contact",
}

AR_STOPWORDS = {
    "في",
    "من",
    "عن",
    "على",
    "الى",
    "إلى",
    "و",
    "او",
    "أو",
    "التي",
    "الذي",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "أفضل",
    "افضل",
    "قائمة",
    "دليل",
    "الموقع",
    "الرسمي",
    "تواصل",
    "اتصل",
    "بنا",
}


def registered_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def domain_label(domain: str) -> str:
    labels = domain.lower().split(".")
    return labels[-2] if len(labels) >= 2 else (labels[0] if labels else "")


def is_blocked_domain(domain: str) -> bool:
    if not domain:
        return True
    labels = domain.lower().split(".")
    return any(label in BLOCKED_DOMAIN_LABELS for label in labels)


def is_unsafe_url(url: str) -> bool:
    low = url.lower()
    domain = registered_domain(url)
    return is_blocked_domain(domain) or any(term in low for term in BLOCKED_URL_TERMS)


def has_arabic(text: str) -> bool:
    return bool(AR_RE.search(text or ""))


def _normalize_arabic(token: str) -> str:
    token = (
        token.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ة", "ه")
        .replace("ـ", "")
    )
    if token.startswith("ال") and len(token) > 4:
        token = token[2:]
    for suffix in ("يات", "ات", "ون", "ين", "يه", "ية", "ية", "ه", "ي"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    return token


def normalize_token(token: str) -> str:
    token = token.strip().lower()
    if not token:
        return ""
    if has_arabic(token):
        return _normalize_arabic(token)
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def tokens(text: str, *, keep_entity_terms: bool = True) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in TOKEN_RE.findall(text or ""):
        norm = normalize_token(raw)
        if not norm or len(norm) < 2:
            continue
        if norm in EN_STOPWORDS or raw in AR_STOPWORDS or norm in AR_STOPWORDS:
            continue
        if not keep_entity_terms and norm in {normalize_token(t) for t in ENTITY_HINTS}:
            continue
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def contains_any(text: str, terms: set[str]) -> bool:
    low = (text or "").lower()
    return any(term in low for term in terms)


import logging
import time

log = logging.getLogger(__name__)

_CACHE_EXPANDED: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 6 * 3600  # avoid an unbounded, permanently-stale process-wide cache
_CACHE_MAX_ENTRIES = 500

# Static dictionary is always applied (fast, deterministic) in addition to
# whatever the LLM returns, instead of only being a fallback when the LLM is
# disabled. This means a bilingual query never depends solely on one LLM
# call succeeding.
_STATIC_TRANSLATIONS = {
    "عقارات": "real estate, property, properties",
    "دبي": "dubai",
    "شركة": "company, corporation",
    "شركات": "company, companies, corporation",
    "ابو ظبي": "abu dhabi",
    "أبوظبي": "abu dhabi",
    "السعودية": "saudi arabia, ksa",
    "الرياض": "riyadh",
    "مدرسة": "school",
    "جامعة": "university",
    "برمجة": "software, programming, tech, it",
    "برمجيات": "software, programming, tech, it",
    "تسويق": "marketing, advertising",
    "شحن": "shipping, logistics",
    "تطوير": "development",
    "مقاولات": "contracting, construction",
}


def _apply_static_translation(value: str) -> str:
    if not value:
        return value
    low = value.lower()
    extra = [v for k, v in _STATIC_TRANSLATIONS.items() if k in low]
    return value if not extra else f"{value}, {', '.join(extra)}"


def get_cached_expanded_terms(query: str, location: str, entity_type: str) -> dict:
    key = f"{query}||{location}||{entity_type}"
    now = time.monotonic()

    cached = _CACHE_EXPANDED.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    if len(_CACHE_EXPANDED) >= _CACHE_MAX_ENTRIES:
        _CACHE_EXPANDED.clear()

    # Start from the static dictionary unconditionally...
    expanded = {
        "query": _apply_static_translation(query),
        "location": _apply_static_translation(location),
        "entity_type": _apply_static_translation(entity_type),
    }

    # ...then layer the LLM expansion on top when available, so bilingual
    # coverage doesn't collapse to nothing on any single LLM failure.
    from core import llm

    if llm.enabled():
        try:
            llm_expanded = llm.translate_and_expand_terms(query, location, entity_type)
            for field in ("query", "location", "entity_type"):
                extra = (llm_expanded or {}).get(field) or ""
                # llm.translate_and_expand_terms already echoes the original
                # value back, so only append genuinely new text.
                base_value = {"query": query, "location": location, "entity_type": entity_type}[field]
                new_part = extra.replace(base_value, "", 1).strip(", ").strip()
                if new_part and new_part not in expanded[field]:
                    expanded[field] = f"{expanded[field]}, {new_part}"
        except Exception as exc:
            log.warning("LLM term expansion failed, using static dictionary only: %s", exc)

    _CACHE_EXPANDED[key] = (now, expanded)
    return expanded


def query_profile(query: str, location: str = "", entity_type: str = "") -> dict:
    expanded = get_cached_expanded_terms(query or "", location or "", entity_type or "")
    q_val = expanded.get("query") or ""
    loc_val = expanded.get("location") or ""
    et_val = expanded.get("entity_type") or ""

    combined = " ".join([q_val, loc_val, et_val])
    query_terms = tokens(q_val)
    location_terms = tokens(loc_val)
    type_terms = tokens(et_val)
    if not location_terms:
        location_terms = []
    return {
        "arabic": has_arabic(combined),
        "query_terms": query_terms,
        "location_terms": location_terms,
        "type_terms": type_terms,
        "all_terms": list(dict.fromkeys(query_terms + location_terms + type_terms)),
    }


def query_intent(
    query: str, location: str = "", entity_type: str = ""
) -> dict[str, bool]:
    profile = query_profile(query, location, entity_type)
    entity_norm = {normalize_token(t) for t in ENTITY_HINTS}
    return {
        "arabic": bool(profile["arabic"]),
        "entity": any(t in entity_norm for t in profile["all_terms"])
        or bool(entity_type),
    }


def relevance_score(
    title: str,
    snippet: str,
    domain: str,
    query: str,
    location: str = "",
    entity_type: str = "",
) -> int:
    profile = query_profile(query, location, entity_type)
    text = f"{title } {snippet } {domain }"
    text_low = text.lower()
    text_terms = set(tokens(text_low))
    domain_terms = set(tokens(domain.replace(".", " ").replace("-", " ")))
    score = 0

    query_terms = profile["query_terms"] or profile["all_terms"]
    if query_terms:
        covered = [t for t in query_terms if t in text_terms or t in domain_terms]
        # NOTE: this used to `return -10` immediately when no query token
        # matched literally. That is a hard, binary rejection built on exact
        # token overlap, and it fails structurally for bilingual queries
        # (e.g. an Arabic query matching an English-only company site) and
        # for single, specific-name searches (a company's own site rarely
        # repeats the exact search phrase verbatim). Zero lexical overlap is
        # now a strong negative *signal*, not an automatic veto — the
        # decision to keep or drop a record is made once, downstream in
        # record_is_relevant/pipeline, where LLM verdicts and extracted
        # contact data can outweigh a lexical miss.
        if not covered:
            score -= 10
        else:
            score += len(covered) * 4
            coverage = len(covered) / max(1, len(query_terms))
            if coverage >= 0.75:
                score += 6
            elif coverage >= 0.5:
                score += 3

    for term in profile["location_terms"]:
        if term in text_terms or term in domain_terms:
            score += 5

    for term in profile["type_terms"]:
        if term in text_terms or term in domain_terms:
            score += 4

    if contains_any(text_low, OFFICIAL_HINTS):
        score += 2
    if any(normalize_token(t) in text_terms for t in ENTITY_HINTS):
        score += 2

    if contains_any(text_low, PEOPLE_HINTS):
        score += 3
    if profile["arabic"] and has_arabic(text):
        score += 2

    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if len(tld) == 2 and any(t in text_terms for t in query_terms):
        score += 1

    if contains_any(text_low, NOISE_TERMS):
        score -= 3
    return score


def minimum_score(query: str, location: str = "", entity_type: str = "") -> int:
    return 1


_NAME_SEP_RE = re.compile(r"[\s\-_\.]+")


def _slug(text: str) -> str:
    """Collapse a string to a bare lowercase alnum run, for name-vs-domain matching."""
    return re.sub(r"[^a-z0-9\u0600-\u06ff]", "", (text or "").lower())


def is_direct_name_match(query: str, domain: str, title: str = "", url: str = "") -> bool:
    """True when the query looks like a specific entity name that literally
    appears in the domain, title, or URL — e.g. query "beeorder" /
    "شركة beeorder" against domain "beeorder.com" or title "BeeOrder | Home".

    This is intentionally simple substring matching on a stripped-down slug
    (no stemming, no stopword removal) because the whole point is to catch
    the case where token-level normalization (Arabic stemming, English
    pluralization) would otherwise obscure an exact, unambiguous name hit.
    Used as a hard override that keeps a record even when semantic/lexical
    scoring is uncertain, since an exact name match on a single-entity
    search is the strongest possible relevance signal available.
    """
    query = (query or "").strip()
    if not query:
        return False

    # Strip generic entity-type / stopword tokens (e.g. "شركة", "company")
    # so "شركة beeorder" reduces to "beeorder" before slugging.
    generic = {normalize_token(t) for t in ENTITY_HINTS} | EN_STOPWORDS | AR_STOPWORDS
    words = [w for w in re.split(r"\s+", query) if w]
    core_words = [w for w in words if normalize_token(w) not in generic]
    core = " ".join(core_words) if core_words else query

    query_slug = _slug(core)
    if len(query_slug) < 3:
        return False

    haystacks = [_slug(domain), _slug(domain_label(domain)), _slug(title), _slug(url)]
    return any(query_slug in h for h in haystacks if h)


def record_relevance_score(
    record: dict,
    query: str,
    location: str = "",
    entity_type: str = "",
) -> int:
    meta = record.get("meta") or {}
    title = " ".join(
        str(x or "")
        for x in (
            record.get("name"),
            meta.get("search_title"),
            record.get("domain"),
        )
    )
    snippet = " ".join(
        str(x or "")
        for x in (
            record.get("description"),
            record.get("address"),
            record.get("city"),
            record.get("country"),
            meta.get("search_snippet"),
        )
    )
    score = relevance_score(
        title=title,
        snippet=snippet,
        domain=str(record.get("domain") or ""),
        query=query,
        location=location,
        entity_type=entity_type,
    )

    num_people = len(record.get("people") or [])
    if num_people > 0:
        score += min(num_people * 2, 10)

    # An exact entity-name hit (query "beeorder" against domain
    # "beeorder.com") is decisive evidence that lexical token-overlap
    # scoring can miss entirely (stemming, language mismatch, generic
    # entity-type words diluting the token set). Reward it heavily instead
    # of relying on it as a separate gate the caller might forget to check.
    if is_direct_name_match(
        query, str(record.get("domain") or ""), title=title, url=str(record.get("website") or "")
    ):
        score += 20

    return score


def record_is_relevant(
    record: dict,
    query: str,
    location: str = "",
    entity_type: str = "",
) -> bool:
    """Heuristic relevance gate used only when the LLM is unavailable.

    Kept intentionally permissive: this used to be a strict `score >=
    minimum_score()` gate fed by a scoring function that could return -10
    outright on zero lexical overlap, which meant a single specific-name
    search ("beeorder") or a language-mismatched general search ("شركات
    برمجية" vs an English-only site) could be rejected before any other
    signal was consulted. Direct name matches and any extracted contact
    data (people/emails) are now treated as sufficient on their own.
    """
    if is_direct_name_match(
        query,
        str(record.get("domain") or ""),
        title=str(record.get("name") or ""),
        url=str(record.get("website") or ""),
    ):
        return True
    if has_people_data(record) or record.get("emails"):
        return True
    score = record_relevance_score(record, query, location, entity_type)
    return score >= minimum_score(query, location, entity_type)


def has_people_data(record: dict) -> bool:
    for person in record.get("people") or []:
        if not isinstance(person, dict):
            continue
        if not str(person.get("name") or "").strip():
            continue
        if any(
            str(person.get(field) or "").strip()
            for field in ("position", "email", "phone", "profile_url")
        ):
            return True
    return False