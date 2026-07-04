# استبدل ملف pipeline.py بالكامل بالكود التالي:

"""End-to-end pipeline: search -> scrape -> extract -> store -> export."""

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

                # Bypassing strict keyword check when LLM is enabled for robust semantic matching
                is_heuristic_relevant = safety.record_is_relevant(
                    record,
                    query=query,
                    location=location,
                    entity_type=entity_type,
                )

                if llm.enabled():
                    verdict = llm.validate_entity_record(
                        record, query, location, entity_type
                    )
                    if verdict:
                        record["meta"]["llm_relevance_reason"] = verdict.get(
                            "reason", ""
                        )
                        if verdict.get("relevant") is False:
                            log.info(
                                "LLM rejected record %s: %s",
                                result.url,
                                verdict.get("reason"),
                            )
                            continue
                elif not is_heuristic_relevant:
                    log.info("Skipping low-relevance record (heuristic): %s", result.url)
                    continue

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