# استبدل ملف scraper.py بالكامل بالكود التالي:

"""Website scraper."""

from __future__ import annotations

import logging
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from config import config
from core import extractor, llm, safety

log = logging.getLogger(__name__)

PAGE_KEYWORDS = {
    "team": [
        "team",
        "our-team",
        "staff",
        "people",
        "leadership",
        "management",
        "board",
        "directors",
        "faculty",
        "employees",
        "فريق",
        "الفريق",
        "فريقنا",
        "إدارة",
        "الإدارة",
        "مجلس",
        "موظفون",
        "كادر",
        "منسوبي",
        "الهيئة التدريسية",
    ],
    "contact": ["contact", "contact-us", "اتصل", "تواصل", "اتصل-بنا", "تواصل-معنا"],
    "about": ["about", "about-us", "who-we-are", "من-نحن", "عن", "نبذة", "من نحن"],
}


class SiteScraper:
    def __init__(self, region: str | None = None):
        self.region = (region or config.DEFAULT_REGION).upper()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept-Language": "ar,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._robots: dict[str, RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        if not config.RESPECT_ROBOTS:
            return True
        parsed = urlparse(url)
        root = f"{parsed .scheme }://{parsed .netloc }"
        rp = self._robots.get(root)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(urljoin(root, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                rp = None
            self._robots[root] = rp
        if rp is None:
            return True
        try:
            return rp.can_fetch(config.USER_AGENT, url)
        except Exception:
            return True

    def _fetch(self, url: str) -> tuple[str | None, int]:
        if safety.is_unsafe_url(url):
            log.info("Blocked unsafe or irrelevant URL: %s", url)
            return None, 0
        if not self._allowed(url):
            log.info("robots.txt disallows %s", url)
            return None, 0
            
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {
                "Accept": "application/json",
                "X-Return-Format": "html",
            }
            log.info("Fetching via Jina AI: %s", url)
            resp = self.session.get(jina_url, headers=headers, timeout=config.REQUEST_TIMEOUT + 10)
            
            if resp.status_code == 200:
                data = resp.json()
                if data and data.get("data", {}).get("html"):
                    return data["data"]["html"], 200

            log.warning("Jina failed, falling back to direct requests for %s", url)
            resp = self.session.get(
                url, timeout=config.REQUEST_TIMEOUT, allow_redirects=True
            )
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return None, resp.status_code
            resp.encoding = resp.encoding or resp.apparent_encoding
            return resp.text, resp.status_code
            
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", url, exc)
            return None, 0

    def _find_internal_pages(self, base_url: str, html: str) -> dict[str, str]:
        """Return {page_type: url} for the best contact/about/team links."""
        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(base_url).netloc.replace("www.", "")
        found: dict[str, str] = {}
        candidates: list[dict[str, str]] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            skip_keywords = [
                "news",
                "careers",
                "jobs",
                "blog",
                "article",
                "sustainability",
                "login",
                "register",
                "cart",
            ]
            if any(kw in href.lower() for kw in skip_keywords):
                continue

            full = urljoin(base_url, href)
            if urlparse(full).netloc.replace("www.", "") != base_domain:
                continue
            text = a.get_text(" ", strip=True)
            candidates.append({"url": full, "text": text[:120], "href": href[:160]})
            haystack = (href + " " + a.get_text(" ", strip=True)).lower()
            for page_type, keys in PAGE_KEYWORDS.items():
                if page_type in found:
                    continue
                if any(k in haystack for k in keys):
                    found[page_type] = full

        if llm.enabled() and len(found) < len(PAGE_KEYWORDS):
            for item in llm.select_relevant_links(
                base_url,
                candidates,
                budget=len(PAGE_KEYWORDS) - len(found),
            ):
                page_type = item.get("page_type") or "other"
                if page_type in found:
                    continue
                url = item.get("url")
                if url and urlparse(url).netloc.replace("www.", "") == base_domain:
                    found[page_type] = url
        return found

    def scrape(self, start_url: str) -> dict | None:
        """Scrape a website and return a merged entity record (or None)."""
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
        if safety.is_unsafe_url(start_url):
            log.info("Skipping blocked URL before scrape: %s", start_url)
            return None

        html, status = self._fetch(start_url)
        if not html:
            if start_url.startswith("https://"):
                html, status = self._fetch("http://" + start_url[len("https://") :])
            if not html:
                return None

        final_domain = urlparse(start_url).netloc.replace("www.", "")
        pages_visited = [{"url": start_url, "page_type": "home", "status_code": status}]

        record = {
            "name": "",
            "website": start_url,
            "domain": final_domain,
            "description": "",
            "address": "",
            "city": "",
            "country": "",
            "phones": [],
            "emails": [],
            "social": {},
            "people": [],
            "meta": {},
        }

        def _merge(part: dict) -> None:
            if part.get("name") and not record["name"]:
                record["name"] = part["name"]
            if part.get("description") and not record["description"]:
                record["description"] = part["description"]
            addr, city, country = part.get("address", ("", "", ""))
            if addr and not record["address"]:
                record["address"], record["city"], record["country"] = (
                    addr,
                    city,
                    country,
                )
            for email in part.get("emails", []):
                if email not in record["emails"]:
                    record["emails"].append(email)
            for phone in part.get("phones", []):
                if phone not in record["phones"]:
                    record["phones"].append(phone)
            for k, v in part.get("social", {}).items():
                record["social"].setdefault(k, v)
            record["people"].extend(part.get("people", []))
            if part.get("meta"):
                record["meta"].update(part["meta"])

        _merge(extractor.parse_page(html, start_url, self.region))

        internal = self._find_internal_pages(start_url, html)
        budget = max(0, config.MAX_PAGES_PER_SITE - 1)
        for page_type, url in list(internal.items())[:budget]:
            time.sleep(config.REQUEST_DELAY)
            sub_html, sub_status = self._fetch(url)
            pages_visited.append(
                {"url": url, "page_type": page_type, "status_code": sub_status}
            )
            if sub_html:
                _merge(extractor.parse_page(sub_html, url, self.region))

        merged_people: dict[str, dict] = {}
        for p in record["people"]:
            if not p.get("name"):
                continue
            key = p["name"].lower().strip()
            if key not in merged_people:
                merged_people[key] = p
            else:
                for field in ("position", "email", "phone", "profile_url"):
                    if not merged_people[key].get(field) and p.get(field):
                        merged_people[key][field] = p[field]
                        
        # Sorting decision makers to the top of the list
        record["people"] = sorted(
            list(merged_people.values()),
            key=lambda p: any(kw in str(p.get("position", "")).lower() for kw in (
                "ceo", "founder", "director", "manager", "president", "partner", "owner", "chairman", "gm",
                "رئيس", "مدير", "مؤسس", "شريك", "مجلس"
            )),
            reverse=True
        )
        record["pages"] = pages_visited

        if llm.enabled():
            enhancement = llm.enhance_entity_record(record)
            if enhancement:
                _apply_record_enhancement(record, enhancement)
                record.setdefault("meta", {})["llm_record_enhanced"] = True

        if not record["name"]:
            record["name"] = final_domain
        return record


def _apply_record_enhancement(record: dict, enhancement: dict) -> None:
    """Merge an LLM-normalized record without dropping deterministic evidence."""
    for field in ("name", "description", "address", "city", "country"):
        value = enhancement.get(field)
        if isinstance(value, str) and value.strip():
            if field in {"description", "address"}:
                record[field] = value.strip()[: 500 if field == "description" else 300]
            else:
                record[field] = value.strip()

    for field in ("phones", "emails"):
        values = enhancement.get(field)
        if isinstance(values, list):
            merged = []
            for value in list(record.get(field, [])) + values:
                value = str(value).strip()
                if value and value not in merged:
                    merged.append(value)
            record[field] = merged

    social = enhancement.get("social")
    if isinstance(social, dict):
        for key, value in social.items():
            if value:
                record["social"][str(key)] = str(value)

    people = enhancement.get("people")
    if isinstance(people, list):
        merged: dict[str, dict] = {}
        for person in list(record.get("people", [])) + people:
            if not isinstance(person, dict):
                continue
            name = str(person.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            current = merged.setdefault(
                key,
                {
                    "name": name,
                    "position": "",
                    "email": "",
                    "phone": "",
                    "profile_url": "",
                    "source": "llm-enhanced",
                },
            )
            for field in ("position", "email", "phone", "profile_url", "source"):
                if person.get(field):
                    current[field] = str(person[field]).strip()
        record["people"] = list(merged.values())