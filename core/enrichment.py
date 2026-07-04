# استبدل ملف enrichment.py بالكامل بالكود التالي:

"""Data Enrichment via External APIs (Apollo, Hunter, Snov.io, Lusha, etc.)"""

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
        
        emails_list = data.get("emails", []) or []
        emails = []
        people = []
        for e in emails_list:
            email_val = e.get("value")
            if email_val:
                emails.append(email_val)
            first = e.get("first_name") or ""
            last = e.get("last_name") or ""
            name = f"{first} {last}".strip()
            pos = e.get("position") or ""
            phone = e.get("phone_number") or ""
            if name and (pos or phone or email_val):
                people.append({
                    "name": name,
                    "position": pos,
                    "email": email_val,
                    "phone": phone,
                    "profile_url": "",
                    "source": "hunter.io"
                })
        return {"emails": emails, "phones": [], "people": people}
    except Exception as e:
        log.warning("Hunter.io failed for %s: %s", domain, e)
        return {}


def enrich_with_apollo(domain: str) -> dict:
    if not config.APOLLO_API_KEY:
        return {}
    try:
        # Utilizing mixed people search for precise decision maker targeting
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }
        data = {
            "api_key": config.APOLLO_API_KEY,
            "q_organization_domains": [domain],
            "person_titles": [
                "CEO", "Founder", "Co-Founder", "Owner", "President", 
                "Managing Director", "Director", "Manager", "Chairman",
                "Chief Executive Officer", "Partner", "General Manager",
                "رئيس تنفيذي", "مدير عام", "مؤسس", "شريك"
            ]
        }
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        resp.raise_for_status()
        contacts = resp.json().get("contacts", [])
        
        people = []
        emails = []
        phones = []
        for c in contacts:
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            if not name:
                continue
            email = c.get("email") or ""
            phone = c.get("phone_number") or c.get("primary_phone", {}).get("number") or ""
            pos = c.get("title") or ""
            linkedin = c.get("linkedin_url") or ""
            
            if email and email not in emails:
                emails.append(email)
            if phone and phone not in phones:
                phones.append(phone)
                
            people.append({
                "name": name,
                "position": pos,
                "email": email,
                "phone": phone,
                "profile_url": linkedin,
                "source": "apollo.io"
            })
        return {"emails": emails, "phones": phones, "people": people}
    except Exception as e:
        log.warning("Apollo mixed people search failed for %s: %s", domain, e)
        # Fallback to general organization enrichment
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
        except Exception as e2:
            log.warning("Apollo fallback failed for %s: %s", domain, e2)
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


def enrich_with_lusha(domain: str) -> dict:
    if not config.LUSHA_API_KEY:
        return {}
    try:
        url = f"https://api.lusha.com/v1/person?domain={domain}"
        headers = {"api_key": config.LUSHA_API_KEY}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        people = []
        emails = []
        phones = []
        
        records = data.get("data")
        if isinstance(records, dict):
            records = [records]
        elif not isinstance(records, list):
            records = []
            
        for r in records:
            name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip()
            if not name:
                continue
            pos = r.get("company", {}).get("title") or r.get("title") or ""
            emails_list = r.get("emailAddresses", []) or []
            phones_list = r.get("phoneNumbers", []) or []
            
            email_val = emails_list[0] if emails_list else ""
            phone_val = phones_list[0] if phones_list else ""
            
            for em in emails_list:
                if em and em not in emails:
                    emails.append(em)
            for ph in phones_list:
                if ph and ph not in phones:
                    phones.append(ph)
                    
            people.append({
                "name": name,
                "position": pos,
                "email": email_val,
                "phone": phone_val,
                "profile_url": r.get("linkedinUrl") or "",
                "source": "lusha"
            })
        return {"emails": emails, "phones": phones, "people": people}
    except Exception as e:
        log.warning("Lusha enrichment failed for %s: %s", domain, e)
        return {}


def get_snovio_token() -> str | None:
    if not config.SNOVIO_CLIENT_ID or not config.SNOVIO_CLIENT_SECRET:
        return None
    try:
        url = "https://api.snov.io/v1/oauth/access_token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": config.SNOVIO_CLIENT_ID,
            "client_secret": config.SNOVIO_CLIENT_SECRET
        }
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        log.warning("Snov.io oauth failed: %s", e)
        return None


def enrich_with_snovio(domain: str) -> dict:
    token = get_snovio_token()
    if not token:
        return {}
    try:
        url = "https://api.snov.io/v2/domain-emails-with-info"
        params = {
            "access_token": token,
            "domain": domain,
            "type": "all",
            "limit": 50,
            "lastId": 0
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        emails = []
        people = []
        
        emails_list = data.get("emails", []) or []
        for em in emails_list:
            email_val = em.get("email")
            if email_val:
                emails.append(email_val)
                
            first = em.get("firstName") or ""
            last = em.get("lastName") or ""
            name = f"{first} {last}".strip()
            pos = em.get("position") or ""
            
            if name and (pos or email_val):
                people.append({
                    "name": name,
                    "position": pos,
                    "email": email_val,
                    "phone": "",
                    "profile_url": "",
                    "source": "snov.io"
                })
        return {"emails": emails, "phones": [], "people": people}
    except Exception as e:
        log.warning("Snovio enrichment failed for %s: %s", domain, e)
        return {}


def get_enriched_data(domain: str) -> dict:
    result = {"emails": [], "phones": [], "people": []}
    if not domain:
        return result

    providers: list[tuple[str, Callable[[str], dict]]] = [
        # ("Clay", enrich_with_clay),
        ("Hunter", enrich_with_hunter),
        ("Apollo", enrich_with_apollo),
        # ("Lusha", enrich_with_lusha),
        # ("Snovio", enrich_with_snovio),
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