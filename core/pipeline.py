from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import config
from core import database, exporter, llm, safety
from core.scraper import SiteScraper
from core.search import search_websites

log = logging.getLogger(__name__)


def run_pipeline(search_id: int) -> None:
    search = database.get_search(search_id)
    if not search:
        log.error("Search %s not found", search_id)
        return

    query = search["query"]
    location = search.get("location") or ""
    entity_type = search.get("entity_type") or ""
    max_results = search.get("max_results") or 10

    try:
        database.update_search(
            search_id, status="running", progress=2, message="Searching the web…"
        )

        fetch_limit = max(max_results * 3, 30)
        results = search_websites(
            query=query,
            location=location,
            entity_type=entity_type,
            max_results=fetch_limit,
            region=config.DEFAULT_REGION,
        )

        if not results:
            msg = "لم نجد أي موقع إلكتروني للبحث الحالي. يرجى تفعيل SerpAPI أو Google CSE في ملف الإعدادات أو التحقق من الاتصال الشبكي."
            database.update_search(
                search_id,
                status="completed",
                progress=100,
                message=msg,
                results_count=0,
                completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            exporter.export_search(search_id)
            return

        database.update_search(
            search_id,
            progress=10,
            message=f"Found {len(results)} websites. Visiting each…",
        )

        scraper = SiteScraper(region=config.DEFAULT_REGION)
        total = len(results)

        scraped_records = []

        for index, result in enumerate(results, start=1):
            database.update_search(
                search_id,
                progress=10 + int(80 * index / total),
                message=f"Scraping {index}/{total}: {result.domain}",
            )
            try:
                record = scraper.scrape(result.url)
            except Exception as exc:
                log.warning("Scrape failed for %s: %s", result.url, exc)
                record = None

            if record is None:
                # scraper.scrape() can also return None without raising
                # (fetch failure, robots.txt disallow, unsafe URL) — that
                # path previously left no trace here beyond a generic
                # "Scraping i/N" progress message, making it impossible to
                # tell from search-run logs alone why a site the search
                # backend found never became an entity. scraper.py now logs
                # the specific reason (see WARNING/INFO lines tagged
                # "fetch failed" / "robots.txt disallows" / "unsafe URL");
                # this line just makes the pipeline-level drop explicit too.
                log.info("No record produced for %s (scrape returned None)", result.url)
                continue

            if record:
                from core.enrichment import get_enriched_data

                enriched = get_enriched_data(record.get("domain", ""))

                for email in enriched.get("emails", []):
                    if email not in record["emails"]:
                        record["emails"].append(email)

                for phone in enriched.get("phones", []):
                    if phone not in record["phones"]:
                        record["phones"].append(phone)

                record["people"].extend(enriched.get("people", []))

                record.setdefault("meta", {})["enriched_via_apis"] = True

                if not record.get("description"):
                    record["description"] = result.snippet
                record.setdefault("meta", {})["search_title"] = result.title
                record.setdefault("meta", {})["search_snippet"] = result.snippet
                record["meta"]["relevance_score"] = safety.record_relevance_score(
                    record,
                    query=query,
                    location=location,
                    entity_type=entity_type,
                )

                is_heuristic_relevant = safety.record_is_relevant(
                    record,
                    query=query,
                    location=location,
                    entity_type=entity_type,
                )

                # Was: `len(query.split()) <= 3 and result.domain in query.lower()
                # or query.lower() in result.domain.replace(".", " ")`.
                # Operator precedence made this `(A and B) or C`, and both B
                # and C compared strings in directions that almost never
                # match in practice (checking whether a bare domain like
                # "beeorder.com" appears inside the query text, and vice
                # versa with the "." replaced by a space) — so for a query
                # like "شركة beeorder" this was effectively always False,
                # meaning single-entity searches got zero protection from
                # the rejection logic below despite being the exact case it
                # was meant to protect. safety.is_direct_name_match does the
                # actual job: strip generic entity-type words, then check if
                # the remaining core name literally appears in the domain,
                # title, or URL.
                is_specific_search = safety.is_direct_name_match(
                    query,
                    result.domain,
                    title=result.title,
                    url=result.url,
                )

                has_contact_data = bool(
                    record.get("people") or record.get("emails")
                )

                llm_verdict: dict | None = None
                if llm.enabled():
                    llm_verdict = llm.validate_entity_record(
                        record, query, location, entity_type
                    )
                    if llm_verdict:
                        record["meta"]["llm_relevance_reason"] = llm_verdict.get(
                            "reason", ""
                        )

                # Single combined keep/drop decision instead of two separate
                # branches that could each silently `continue`. A record is
                # dropped only when *every* available signal says to drop it:
                # no direct name match, no extracted contact data, and (when
                # the LLM ran) an explicit negative verdict, or (when the LLM
                # didn't run) a negative heuristic score. Any one positive
                # signal is enough to keep the record — this is the fix for
                # "logs show a site was found but no entity ever appears":
                # previously a single False LLM verdict on a contact-less
                # page was enough to drop it outright.
                if is_specific_search or has_contact_data:
                    keep = True
                    reason = "direct name match" if is_specific_search else "has contact data"
                elif llm_verdict is not None:
                    keep = llm_verdict.get("relevant") is not False
                    reason = llm_verdict.get("reason", "llm verdict")
                else:
                    keep = is_heuristic_relevant
                    reason = "heuristic score"

                if not keep:
                    log.info(
                        "Dropping record for %s (query=%r): %s",
                        result.url,
                        query,
                        reason,
                    )
                    continue

                log.info(
                    "Keeping record for %s (query=%r): %s [people=%d emails=%d]",
                    result.url,
                    query,
                    reason,
                    len(record.get("people") or []),
                    len(record.get("emails") or []),
                )
                scraped_records.append(record)

        scraped_records.sort(
            key=lambda r: (
                len(r.get("people", [])),
                r.get("meta", {}).get("relevance_score", 0),
            ),
            reverse=True,
        )

        stored = 0
        for record in scraped_records[:max_results]:
            database.insert_entity(search_id, record)
            stored += 1

        path = exporter.export_search(search_id)
        database.update_search(
            search_id,
            status="completed",
            progress=100,
            message=f"Done. {stored} entities saved. JSON: {path}",
            results_count=stored,
            completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        log.info("Search %s complete: %s entities", search_id, stored)

    except Exception as exc:
        log.exception("Pipeline failed for search %s", search_id)
        database.update_search(
            search_id,
            status="failed",
            message=f"Error: {exc }",
            completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )