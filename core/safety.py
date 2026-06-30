"""Safety and generic relevance filters shared by search and scraping."""

from __future__ import annotations

import re
from urllib.parse import urlparse

AR_RE = re.compile(r"[\u0600-\u06ff]")
TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)

# Second-level labels that should never be treated as target entity websites.
BLOCKED_DOMAIN_LABELS = {
    # Social/search/directory/general platforms.
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
    # Game/esports false positives and adult/inappropriate domains.
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

# --------------------------------------------------------------------------- #
# People-data requirement
# --------------------------------------------------------------------------- #
# Every search exists to extract *people's* data — names paired with their
# positions, phone numbers, e-mail addresses, or other personal details.  This
# requirement is attached to the query at every stage (search variants,
# ranking, relevance scoring, crawling, and the final return gate) so the whole
# system pulls in the same direction.

# Words that mark a page/section as likely to list people and their contacts.
PEOPLE_HINTS = {
    # English
    "team", "our team", "staff", "people", "leadership", "management",
    "board", "directors", "director", "employees", "employee", "members",
    "member", "founder", "founders", "officers", "executives", "executive",
    "personnel", "who we are", "meet the team", "contact",
    # Arabic
    "فريق", "الفريق", "فريقنا", "طاقم", "الكادر", "كادر", "موظفون", "موظفين",
    "الموظفين", "الإدارة", "ادارة", "إدارة", "مجلس الإدارة", "مجلس", "أعضاء",
    "اعضاء", "عضو", "القيادة", "هيئة", "الهيئة", "من نحن", "تواصل", "اتصل",
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


def query_profile(query: str, location: str = "", entity_type: str = "") -> dict:
    combined = " ".join([query or "", location or "", entity_type or ""])
    query_terms = tokens(query)
    location_terms = tokens(location)
    type_terms = tokens(entity_type)
    if not location_terms:
        # Let explicit "in Riyadh" / "في الرياض" location tokens still matter
        # through ordinary query coverage rather than brittle parsing.
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
    text = f"{title} {snippet} {domain}"
    text_low = text.lower()
    text_terms = set(tokens(text_low))
    domain_terms = set(tokens(domain.replace(".", " ").replace("-", " ")))
    score = 0

    query_terms = profile["query_terms"] or profile["all_terms"]
    if query_terms:
        covered = [t for t in query_terms if t in text_terms or t in domain_terms]
        if not covered:
            return -10
        # if len(query_terms) >= 3 and len(covered) < 2:
        #     return -10
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
    # The query is about extracting people's data, so reward team / staff /
    # leadership / contact pages that are likely to carry it.
    if contains_any(text_low, PEOPLE_HINTS):
        score += 3
    if profile["arabic"] and has_arabic(text):
        score += 2

    # A country-code TLD is useful only when the query/location mentions it
    # implicitly through matching text; do not hardcode one country/category.
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if len(tld) == 2 and any(t in text_terms for t in query_terms):
        score += 1

    if contains_any(text_low, NOISE_TERMS):
        score -= 3
    return score


def minimum_score(query: str, location: str = "", entity_type: str = "") -> int:
    # profile = query_profile(query, location, entity_type)
    # term_count = len(profile["query_terms"] or profile["all_terms"])
    # if location or entity_type:
    #     return 5
    # if term_count >= 3:
    #     return 4
    # return 3
    return 1


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

    # Boost score significantly if people data was extracted
    num_people = len(record.get("people") or [])
    if num_people > 0:
        score += min(num_people * 2, 10)  # Up to 10 points bonus

    return score

def record_is_relevant(
    record: dict,
    query: str,
    location: str = "",
    entity_type: str = "",
) -> bool:
    score = record_relevance_score(record, query, location, entity_type)
    return score >= minimum_score(query, location, entity_type)


def has_people_data(record: dict) -> bool:
    """True when the record carries at least one usable person.

    A usable person has a name plus at least one personal detail (position,
    e-mail, phone, or profile link).  Because every search exists to extract
    people's data, records without such a person are dropped before they are
    stored — nothing is returned for an entity that yields no people.
    """
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
