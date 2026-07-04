"""Data Enrichment via External APIs (Apollo, Hunter, etc.)"""

from collections.abc import Callable

import requests
import logging
from config import config

log = logging.getLogger(__name__)


def enrich_with_hunter(domain: str) -> dict:
    if not config.HUNTER_API_KEY:
        return {}
    try:
        url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={config.HUNTER_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        emails = [email["value"] for email in data.get("emails", [])]
        return {"emails": emails, "phones": [], "people": []}
    except Exception as e:
        log.warning("Hunter.io failed for %s: %s", domain, e)
        return {}


def enrich_with_apollo(domain: str) -> dict:
    if not config.APOLLO_API_KEY:
        return {}
    try:
        url = "https://api.apollo.io/v1/organizations/enrich"
        headers = {"Content-Type": "application/json"}
        data = {"api_key": config.APOLLO_API_KEY, "domain": domain}
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        resp.raise_for_status()
        org = resp.json().get("organization", {})

        phones = []
        if org.get("primary_phone"):
            phones.append(org.get("primary_phone").get("number"))

        return {"emails": [], "phones": phones, "people": []}
    except Exception as e:
        log.warning("Apollo failed for %s: %s", domain, e)
        return {}


def enrich_with_clay(domain: str) -> dict:
    if not config.CLAY_WEBHOOK_URL:
        return {}

    try:
        payload = {"domain": domain}
        resp = requests.post(config.CLAY_WEBHOOK_URL, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()

        return {
            "emails": data.get("emails", []),
            "phones": data.get("phones", []),
            "people": data.get("people", []),
        }
    except Exception as e:
        log.warning("Clay enrichment failed for %s: %s", domain, e)
        return {}


def get_enriched_data(domain: str) -> dict:
    result = {"emails": [], "phones": [], "people": []}
    if not domain:
        return result

    providers: list[tuple[str, Callable[[str], dict]]] = [
        # ("Clay", enrich_with_clay),
        ("Hunter", enrich_with_hunter),
        ("Apollo", enrich_with_apollo),
    ]

    for provider_name, provider_func in providers:
        try:
            log.info(
                "Attempting enrichment with %s for domain: %s", provider_name, domain
            )

            data = provider_func(domain)

            if not isinstance(data, dict):
                log.warning(
                    "%s returned invalid data type for %s", provider_name, domain
                )
                continue

            for email in data.get("emails", []):
                email = str(email).strip().lower()
                if email and email not in result["emails"]:
                    result["emails"].append(email)

            for phone in data.get("phones", []):
                phone = str(phone).strip()
                if phone and phone not in result["phones"]:
                    result["phones"].append(phone)

            for person in data.get("people", []):
                if isinstance(person, dict) and person.get("name"):
                    existing_names = [
                        p.get("name", "").lower() for p in result["people"]
                    ]
                    if person["name"].lower() not in existing_names:
                        result["people"].append(person)

        except Exception as e:
            log.error(
                "Enrichment failed with %s for domain %s: %s", provider_name, domain, e
            )

    return result
